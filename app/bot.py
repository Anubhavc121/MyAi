from __future__ import annotations

import logging
from pathlib import Path

from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import Activity, ActivityTypes

from app.agent.core import AgentCore
from app.config import permissions_config
from app.security.permissions import auth_service, permission_manager
from app.services.web_search import WebSearchService

logger = logging.getLogger(__name__)


class OpenClawBot(ActivityHandler):
    """Microsoft Teams bot that routes messages to the OpenClaw agent."""

    def __init__(
        self,
        agent: AgentCore,
        search_service: WebSearchService,
    ):
        self.agent = agent
        self.search_service = search_service

    async def on_message_activity(self, turn_context: TurnContext):
        user_id = turn_context.activity.from_property.id
        user_name = turn_context.activity.from_property.name or "User"
        text = (turn_context.activity.text or "").strip()

        if not text:
            return

        # Auth check
        if not auth_service.is_user_allowed(user_id):
            await turn_context.send_activity("⛔ You are not authorized to use OpenClaw.")
            return

        # Check for slash commands
        if text.startswith("/"):
            response = await self._handle_command(text, user_id, user_name)
            if response:
                await turn_context.send_activity(response)
                return

        # Send typing indicator
        await turn_context.send_activities([
            Activity(type=ActivityTypes.typing)
        ])

        # Process through agent
        try:
            response = await self.agent.process_message(user_id, text)
        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
            response = f"⚠️ Something went wrong: {str(e)[:200]}"

        # Teams has a 4096 char limit per message — split if needed
        if len(response) > 4000:
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await turn_context.send_activity(chunk)
        else:
            await turn_context.send_activity(response)

    async def _handle_command(self, text: str, user_id: str, user_name: str) -> str | None:
        parts = text.split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if command == "/help":
            return (
                "🐾 **OpenClaw Commands**\n\n"
                "• `/model <name>` — Switch Ollama model\n"
                "• `/status` — Show current config and health\n"
                "• `/allow <path>` — Grant file access to a directory\n"
                "• `/revoke` — Revoke all file permissions\n"
                "• `/search on|off` — Toggle web search\n"
                "• `/index <path>` — Index a directory for RAG\n"
                "• `/clear` — Clear conversation history\n"
                "• `/help` — Show this message"
            )

        elif command == "/status":
            ollama_ok = await self.agent.ollama.health_check()
            models = []
            if ollama_ok:
                try:
                    model_list = await self.agent.ollama.list_models()
                    models = [m.get("name", "?") for m in model_list[:10]]
                except Exception:
                    pass

            search_status = "🟢 On" if permission_manager.is_search_enabled(user_id) else "🔴 Off"
            dirs = permissions_config.allowed_dirs or ["None"]

            return (
                f"🐾 **OpenClaw Status**\n\n"
                f"**Ollama:** {'🟢 Connected' if ollama_ok else '🔴 Not reachable'}\n"
                f"**Model:** `{self.agent.ollama.model}`\n"
                f"**Available models:** {', '.join(models) or 'N/A'}\n"
                f"**Web search:** {search_status}\n"
                f"**Allowed dirs:** {chr(10).join(dirs)}\n"
                f"**User:** {user_name} (`{user_id[:16]}...`)"
            )

        elif command == "/model":
            if not arg:
                return "Usage: `/model <model_name>` (e.g., `/model mistral:7b`)"
            self.agent.ollama.set_model(arg)
            return f"✅ Switched to model: `{arg}`"

        elif command == "/allow":
            if not arg:
                return "Usage: `/allow <directory_path>` (e.g., `/allow /home/user/projects`)"
            resolved = str(Path(arg).resolve())
            if not Path(resolved).exists():
                return f"⚠️ Directory not found: `{arg}`"
            if not Path(resolved).is_dir():
                return f"⚠️ Not a directory: `{arg}`"
            permissions_config.grant_directory(resolved)
            permission_manager.grant(user_id, f"dir:{resolved}")
            return f"✅ Granted access to: `{resolved}`"

        elif command == "/revoke":
            permissions_config.revoke_all()
            permission_manager.revoke_all(user_id)
            return "✅ All file permissions revoked."

        elif command == "/search":
            if arg.lower() in ("on", "true", "enable", "1"):
                self.search_service.toggle(True)
                permission_manager.set_search_enabled(user_id, True)
                return "🔍 Web search **enabled**. The agent can now search the web when needed."
            elif arg.lower() in ("off", "false", "disable", "0"):
                self.search_service.toggle(False)
                permission_manager.set_search_enabled(user_id, False)
                return "🔍 Web search **disabled**."
            else:
                return "Usage: `/search on` or `/search off`"

        elif command == "/index":
            if not arg:
                return "Usage: `/index <directory_path>`"
            resolved = str(Path(arg).resolve())
            if not permissions_config.is_path_allowed(resolved):
                return f"⚠️ Directory not in allowlist. Run `/allow {arg}` first."
            try:
                result = await self.agent.tools.rag_service.index_directory(resolved)
                return f"⏳ Indexing complete!\n\n✅ {result}"
            except Exception as e:
                return f"❌ Indexing failed: {e}"

        elif command == "/clear":
            await self.agent.db.clear_conversation(user_id)
            return "✅ Conversation history cleared."

        return None  # Not a recognized command — pass to agent

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    "🐾 **Welcome to OpenClaw!**\n\n"
                    "I'm your local AI assistant, powered by Ollama. "
                    "I run entirely on your machine — your data stays private.\n\n"
                    "Type `/help` to see what I can do, or just start chatting!"
                )
