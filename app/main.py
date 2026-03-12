"""MyAi — Local AI Agent for Microsoft Teams.

Run with: python -m app.main
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
import httpx

import uvicorn
from aiohttp import web
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
)
from botbuilder.schema import Activity

from app.config import settings
from app.agent.core import AgentCore
from app.agent.tools import ToolRegistry
from app.bot import MyAiBot
from app.services.ollama import OllamaClient
from app.services.file_access import FileAccessService
from app.services.web_search import WebSearchService
from app.services.rag import RAGService
from app.services.graph import GraphClient
from app.storage.database import Database

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("miai")

# ── Initialize services ──
ollama_client = OllamaClient()
file_service = FileAccessService()
search_service = WebSearchService()
rag_service = RAGService(ollama_client)
graph_client = GraphClient()
database = Database(settings.database_path)

# ── Initialize agent ──
tool_registry = ToolRegistry(file_service, search_service, rag_service)
agent = AgentCore(ollama_client, tool_registry, database)

# ── Initialize bot ──
adapter_settings = BotFrameworkAdapterSettings(
    app_id=settings.microsoft_app_id,
    app_password=settings.microsoft_app_password,
    channel_auth_tenant=settings.microsoft_app_tenant_id or None,
)
adapter = BotFrameworkAdapter(adapter_settings)
bot = MyAiBot(agent, search_service)


# ── Error handler ──
async def on_error(context, error):
    logger.error(f"Bot error: {error}", exc_info=True)
    await context.send_activity("⚠️ An internal error occurred. Please try again.")


adapter.on_turn_error = on_error


# ── aiohttp web app (required by botbuilder) ──
async def messages(req: web.Request) -> web.Response:
    """Main webhook endpoint for Teams Bot Framework."""
    if "application/json" not in req.headers.get("Content-Type", ""):
        return web.Response(status=415)

    body = await req.json()
    activity = Activity().deserialize(body)

    auth_header = req.headers.get("Authorization", "")

    response = await adapter.process_activity(activity, auth_header, bot.on_turn)

    if response:
        return web.json_response(data=response.body, status=response.status)
    return web.Response(status=201)


async def health(req: web.Request) -> web.Response:
    """Health check endpoint."""
    ollama_ok = await ollama_client.health_check()
    return web.json_response({
        "status": "ok" if ollama_ok else "degraded",
        "ollama": "connected" if ollama_ok else "unreachable",
        "model": ollama_client.model,
    })


async def calling(req: web.Request) -> web.Response:
    """Webhook endpoint for Teams Calling events."""
    if "application/json" not in req.headers.get("Content-Type", ""):
        return web.Response(status=415)
        
    try:
        body = await req.json()
        logger.info(f"Incoming call event: {body}")
        
        # When Microsoft Teams sends an Invite to join a Bot, it sends a payload containing the 'value'
        # with 'commsOperation' or 'incomingCall'.
        # We extract the incoming context / meeting URL to explicitly 'Answer' the call 
        # using our GraphClient.
        
        # For transcripts, we would find the onlineMeeting ID and subscribe:
        # await graph_client.subscribe_to_transcript(meeting_id, f"https://{req.host}/api/transcript-webhook")

        return web.json_response({"status": "acknowledged"})
    except Exception as e:
        logger.error(f"Calling webhook error: {e}")
        return web.Response(status=500)


async def transcript_webhook(req: web.Request) -> web.Response:
    """Webhook endpoint for Microsoft Graph meeting transcript subscriptions."""
    validation_token = req.query.get("validationToken")
    if validation_token:
        logger.info("Validating Microsoft Graph transcript webhook...")
        return web.Response(text=validation_token, content_type="text/plain")

    if "application/json" not in req.headers.get("Content-Type", ""):
        return web.Response(status=415)
        
    try:
        body = await req.json()
        
        # Graph API sends an array of 'value' notifications
        for notification in body.get("value", []):
            resource_url = notification.get("resource")
            if resource_url:
                logger.info(f"New transcript block available at: {resource_url}")
                # We fetch the actual transcript text:
                token = await graph_client.get_access_token()
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"https://graph.microsoft.com/v1.0/{resource_url}?$format=text/vtt", 
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    
                    if resp.status_code == 200:
                        transcript_text = resp.text
                        logger.info(f"🎤 [LIVE TRANSCRIPT]: {transcript_text}")
                        # Next step: Pass `transcript_text` to Ollama/Gemini to suggest responses!
        
        return web.Response(status=202)
    except Exception as e:
        logger.error(f"Transcript webhook error: {e}")
        return web.Response(status=500)


async def on_startup(app: web.Application):
    """Initialize database on startup."""
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
    await database.init()
    logger.info("=" * 60)
    logger.info("🐾  MyAi Agent Started")
    logger.info(f"   Model:    {ollama_client.model}")
    logger.info(f"   Server:   http://{settings.host}:{settings.port}")
    logger.info(f"   Webhook:  http://{settings.host}:{settings.port}/api/messages")
    logger.info(f"   Health:   http://{settings.host}:{settings.port}/health")
    logger.info("=" * 60)
    logger.info("Waiting for Teams messages...")


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/api/messages", messages)
    app.router.add_get("/health", health)
    app.router.add_post("/api/calling", calling)
    app.router.add_post("/api/transcript-webhook", transcript_webhook)
    app.on_startup.append(on_startup)
    return app


def main():
    app = create_app()
    web.run_app(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
