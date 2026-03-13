"""Load comprehensive project context into the database for a user.

Usage:
    python scripts/load_project_context.py [--user-id USER_ID]

If --user-id is not provided, loads for all existing user profiles.
"""

import asyncio
import argparse
import sys
sys.path.insert(0, ".")

from app.storage.database import Database
from app.config import settings


CONTEXTS = {
    "MyAi-Project-Overview": """MyAi (codenamed OpenClaw) is a secure, locally-running AI agent that integrates into Microsoft Teams as a personal assistant. All LLM inference happens locally via Ollama — no data leaves the user's machine unless they explicitly enable web search.

Key capabilities:
- Chat with a local LLM (llama3.1:8b default, switchable at runtime)
- Read/write/search files on the user's machine (sandboxed, permission-gated)
- Web search via DuckDuckGo or Tavily
- RAG: index directories and do semantic search over documents using ChromaDB
- Join Teams meetings, listen to live transcripts, and suggest real-time responses
- Proactive messaging: sends meeting suggestions directly to the user's Teams chat
- User profiles and meeting history for personalized suggestions""",

    "MyAi-Tech-Stack": """Tech stack:
- Python 3.11+ with async throughout (aiohttp, aiosqlite, httpx)
- Ollama for local LLM inference (chat + embeddings)
- ChromaDB for vector storage (RAG)
- Microsoft Bot Framework SDK (botbuilder-core) for Teams integration
- Microsoft Graph API for meeting calls, transcripts, proactive messaging
- SQLite (aiosqlite) for conversations, user profiles, meeting history
- pydantic-settings for configuration management
- Docker + docker-compose for deployment
- ngrok for local development tunneling
- pytest + pytest-asyncio for testing""",

    "MyAi-Architecture": """Architecture overview:
- app/main.py: aiohttp web server with webhook endpoints (/api/messages, /api/calling, /api/transcript-webhook)
- app/bot.py: Teams ActivityHandler, routes slash commands and messages to the agent
- app/agent/core.py: AgentCore with IntentRouter — pattern-matches common requests (file ops, search) before falling back to LLM
- app/agent/tools.py: ToolRegistry with 6 tools (read_file, list_directory, search_files, write_file, web_search, rag_query)
- app/services/ollama.py: OllamaClient for chat, generate, embeddings
- app/services/graph.py: GraphClient for OAuth2 tokens, meeting join, transcript subscription, proactive messaging
- app/services/meeting_transcript.py: MeetingTranscriptService — session management, transcript ingestion, debounced suggestion generation
- app/services/rag.py: RAGService — directory indexing, chunking, ChromaDB semantic search
- app/services/file_access.py: Sandboxed file operations with permission checks
- app/storage/database.py: SQLite tables for conversations, messages, user_profiles, meeting_history, user_contexts
- app/security/permissions.py: Per-user auth and permission grants""",

    "MyAi-Meeting-System": """Meeting transcript & suggestion system:
1. User sends /join <meeting-url> or bot is added to a meeting
2. Bot calls Graph API to join the call (joinMeetingIdMeetingInfo on v1.0)
3. Graph sends calling webhook notifications (incoming → established → terminated)
4. On "established": bot starts a MeetingSession, subscribes to transcript webhook, starts polling fallback
5. Transcript arrives via webhook or polling → parsed (VTT format) → appended to session
6. After debounce period (15s default), Ollama generates a suggestion using:
   - User's profile (name, role, bio)
   - User's stored contexts (project knowledge, domain info)
   - Recent meeting history (last 3 meetings with summaries)
   - The rolling transcript (last 12000 chars)
7. Suggestion is delivered via proactive message (Bot Framework REST API with tenant-specific token)
8. On meeting end: transcript is summarized by Ollama and saved to meeting_history table

Key technical details:
- Bot Framework token must use tenant-specific endpoint (not botframework.com) for regional service URLs
- Meeting URLs in /meet/<id>?p=<passcode> format use joinMeetingIdMeetingInfo (v1.0 compatible)
- Content-hash dedup prevents duplicate suggestions
- Debounce timer resets when new transcript arrives""",

    "MyAi-My-Role": """Anubhav Choudhury's role in the MyAi project:
- Primary developer building the MyAi Teams bot
- Responsible for the full stack: backend (Python/aiohttp), Teams integration, Graph API, meeting transcript system
- Built the real-time meeting suggestion pipeline (transcript → Ollama → proactive message)
- Set up Azure Bot registration, Teams app manifest, and deployment
- Handles frontend webhook integration, database schema design, and end-to-end testing
- Uses Windows 11, VS Code, Python 3.12, with local Ollama for inference
- Current focus: making the meeting suggestion system production-ready""",

    "MyAi-Commands": """Bot slash commands:
- /help — List all commands
- /status — Show bot health, model, features
- /model <name> — Switch Ollama model (e.g., /model mistral:7b)
- /profile name:<> role:<> bio:<> — Set user profile for personalized suggestions
- /context add <name> <content> — Store project/topic knowledge for meeting context
- /context list — View stored contexts
- /context remove <name> — Delete a context
- /allow <path> — Grant file access to a directory
- /revoke — Revoke all file permissions
- /search on|off — Toggle web search
- /index <path> — Index directory for RAG semantic search
- /join [url] — Join a Teams meeting
- /clear — Clear conversation history""",

    "MyAi-Deployment": """Deployment and setup:
- Requires: Python 3.11+, Ollama running locally, ngrok for tunneling
- Azure: App Registration (single tenant) + Bot resource (F0 free tier) + Teams channel enabled
- Teams: Custom app uploaded via sideloading (manifest.json + icons zipped)
- 3 terminals needed: Ollama (ollama serve), MyAi (python -m app.main), ngrok (ngrok http 8000)
- After each ngrok restart: update Azure Bot messaging endpoint + CALLBACK_HOST in .env
- Docker deployment available (docker-compose.yml) with host.docker.internal for Ollama
- Data persisted in data/ directory (SQLite + ChromaDB)
- Configuration via .env file and config/permissions.yaml""",
}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=str, default="", help="Teams user ID to load context for")
    args = parser.parse_args()

    db = Database(settings.database_path)
    await db.init()

    if args.user_id:
        user_ids = [args.user_id]
    else:
        # Load for all existing user profiles
        import aiosqlite
        async with aiosqlite.connect(settings.database_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT user_id FROM user_profiles")
            rows = await cursor.fetchall()
            user_ids = [r["user_id"] for r in rows]

        if not user_ids:
            # Try to find any user from conversations
            async with aiosqlite.connect(settings.database_path) as conn:
                cursor = await conn.execute("SELECT DISTINCT user_id FROM conversations LIMIT 5")
                rows = await cursor.fetchall()
                user_ids = [r[0] for r in rows]

    if not user_ids:
        print("No users found in database. Please provide --user-id or set your profile first with /profile in Teams.")
        return

    for uid in user_ids:
        print(f"\nLoading contexts for user: {uid[:20]}...")
        for name, content in CONTEXTS.items():
            await db.add_context(uid, name, content)
            print(f"  + {name} ({len(content)} chars)")

    print(f"\nDone! Loaded {len(CONTEXTS)} contexts for {len(user_ids)} user(s).")
    print("These will be used in meeting suggestions automatically.")


if __name__ == "__main__":
    asyncio.run(main())
