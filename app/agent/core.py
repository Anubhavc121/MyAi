from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import ToolRegistry
from app.config import permissions_config
from app.services.ollama import OllamaClient
from app.storage.database import Database
from app.storage.models import Message, Role

logger = logging.getLogger(__name__)


class IntentRouter:
    """Detects user intent and routes to tools directly.

    Instead of hoping the LLM outputs a magic format,
    we pattern-match common requests and call tools ourselves.
    """

    @classmethod
    def detect(cls, text: str) -> dict | None:
        low = text.lower().strip()

        allowed = permissions_config.allowed_dirs

        # ── List directory ──
        if cls._wants_list(low):
            path = cls._extract_path(low, allowed)
            if path:
                return {"tool": "list_directory", "args": {"path": path}}

        # ── Read file ──
        if cls._wants_read(low):
            path = cls._extract_file_path(low, allowed)
            if path:
                return {"tool": "read_file", "args": {"path": path}}

        # ── Search files ──
        if cls._wants_search_files(low):
            result = cls._extract_search(low, allowed)
            if result:
                return {"tool": "search_files", "args": result}

        # ── Write file ──
        if cls._wants_write(low):
            result = cls._extract_write(text, allowed)
            if result:
                return {"tool": "write_file", "args": result, "generate_content": True, "original": text}

        # ── Web search ──
        if cls._wants_web_search(low):
            query = cls._extract_query(low)
            if query:
                return {"tool": "web_search", "args": {"query": query}}

        return None

    # ── Intent detection helpers ──

    @classmethod
    def _wants_list(cls, t: str) -> bool:
        triggers = [
            "what files", "what's in", "whats in", "list files", "show files",
            "list directory", "list folder", "what is in my", "what are in my",
            "show me the files", "show me what", "contents of",
            "files in my", "files in the", "what do i have in",
        ]
        return any(tr in t for tr in triggers)

    @classmethod
    def _wants_read(cls, t: str) -> bool:
        triggers = [
            "read ", "read my", "show me ", "open ", "cat ", "view ",
            "look at ", "display ", "print ", "what does ",
            "summarize ", "summarise ", "what's in the file",
        ]
        has_file_ref = bool(re.search(r'\.\w{1,5}\b', t)) or "readme" in t
        return any(tr in t for tr in triggers) and has_file_ref

    @classmethod
    def _wants_search_files(cls, t: str) -> bool:
        triggers = [
            "find all", "search for", "find files", "look for files",
            "find python", "find .py", "search files", "locate",
            "find all python", "find all .py", "find every",
        ]
        return any(tr in t for tr in triggers)

    @classmethod
    def _wants_write(cls, t: str) -> bool:
        triggers = [
            "write a file", "create a file", "make a file",
            "save a file", "write file", "create file",
        ]
        return any(tr in t for tr in triggers)

    @classmethod
    def _wants_web_search(cls, t: str) -> bool:
        triggers = [
            "search for", "search the web", "look up", "google",
            "what's the latest", "find online", "search online",
        ]
        return any(tr in t for tr in triggers) and not cls._wants_search_files(t)

    # ── Extraction helpers ──

    @classmethod
    def _extract_path(cls, text: str, allowed: list[str]) -> str | None:
        """Extract a directory path from user text."""
        path_match = re.search(r'(/[\w/.\-~]+)', text)
        if path_match:
            p = str(Path(path_match.group(1)).expanduser().resolve())
            if permissions_config.is_path_allowed(p):
                return p

        folder_words = ["downloads", "documents", "desktop", "projects", "project",
                        "miai", "home", "code", "src", "repo"]
        for word in folder_words:
            if word in text:
                for d in allowed:
                    if word in d.lower():
                        return d

        if ("my " in text or "the " in text) and allowed:
            return allowed[0]

        return allowed[0] if allowed else None

    @classmethod
    def _extract_file_path(cls, text: str, allowed: list[str]) -> str | None:
        """Extract a file path from user text."""
        path_match = re.search(r'(/[\w/.\-~]+\.\w+)', text)
        if path_match:
            p = str(Path(path_match.group(1)).expanduser().resolve())
            if permissions_config.is_path_allowed(p):
                return p

        file_match = re.search(r'([\w/.\-]+\.\w{1,5})\b', text)
        if file_match and allowed:
            filename = file_match.group(1)
            for d in allowed:
                candidate = os.path.join(d, filename)
                if os.path.exists(candidate):
                    return candidate

        if "readme" in text and allowed:
            for d in allowed:
                for ext in [".md", ".txt", ".rst", ""]:
                    candidate = os.path.join(d, f"README{ext}")
                    if os.path.exists(candidate):
                        return candidate

        return None

    @classmethod
    def _extract_search(cls, text: str, allowed: list[str]) -> dict | None:
        """Extract search pattern and directory."""
        ext_match = re.search(r'(?:find|search)\s+(?:all\s+)?(?:(\.\w+)|(\w+))\s+files?', text)
        if ext_match:
            ext = ext_match.group(1) or ext_match.group(2)
            if not ext.startswith(".") and not ext.startswith("*"):
                ext = f"*.{ext}"
            elif ext.startswith("."):
                ext = f"*{ext}"

            path = None
            path_match = re.search(r'(?:in|under|inside)\s+(/[\w/.\-~]+)', text)
            if path_match:
                path = str(Path(path_match.group(1)).expanduser().resolve())
            elif allowed:
                path = allowed[0]

            if path and permissions_config.is_path_allowed(path):
                return {"directory": path, "pattern": ext}

        return None

    @classmethod
    def _extract_write(cls, text: str, allowed: list[str]) -> dict | None:
        """Extract file path for writing."""
        name_match = re.search(r'(?:called|named)\s+([\w.\-]+)', text, re.IGNORECASE)
        if not name_match:
            name_match = re.search(r'file\s+([\w.\-]+)', text, re.IGNORECASE)
        if not name_match:
            return None

        filename = name_match.group(1)

        dir_match = re.search(r'(?:in|to|at|under)\s+(/[\w/.\-~]+)', text)
        if dir_match:
            directory = str(Path(dir_match.group(1)).expanduser().resolve())
        elif allowed:
            directory = allowed[0]
        else:
            return None

        if permissions_config.is_path_allowed(directory):
            return {"path": f"{directory.rstrip('/')}/{filename}", "content": ""}

        return None

    @classmethod
    def _extract_query(cls, text: str) -> str | None:
        """Extract a web search query."""
        for phrase in ["search for", "search the web for", "look up", "google",
                       "find online", "search online for", "search online"]:
            if phrase in text:
                query = text.split(phrase, 1)[1].strip().rstrip("?. ")
                if query:
                    return query
        return None


class AgentCore:
    """Agent with intent routing + LLM conversation."""

    def __init__(self, ollama: OllamaClient, tools: ToolRegistry, database: Database):
        self.ollama = ollama
        self.tools = tools
        self.db = database

    def _build_system_prompt(self) -> str:
        prompt = SYSTEM_PROMPT
        if permissions_config.allowed_dirs:
            dirs = "\n".join(f"  - {d}" for d in permissions_config.allowed_dirs)
            prompt += f"\n\n## Currently Allowed Directories\n{dirs}\n"
        return prompt

    async def process_message(self, user_id: str, user_text: str) -> str:
        conv = await self.db.get_or_create_conversation(user_id)

        user_msg = Message(role=Role.USER, content=user_text)
        await self.db.add_message(conv.id, user_msg)
        conv.messages.append(user_msg)

        # Try intent-based routing first
        intent = IntentRouter.detect(user_text)

        if intent:
            response = await self._execute_tool(intent, user_text)
        else:
            response = await self._chat(conv)

        assistant_msg = Message(role=Role.ASSISTANT, content=response)
        await self.db.add_message(conv.id, assistant_msg)
        return response

    async def _execute_tool(self, intent: dict, original_text: str) -> str:
        """Execute a tool call and present the results."""
        tool_name = intent["tool"]
        tool_args = intent["args"]

        # For write_file, generate content with LLM first
        if intent.get("generate_content") and tool_args.get("content") == "":
            logger.info(f"Generating file content for: {tool_args['path']}")
            content = await self._generate_content(original_text)
            tool_args["content"] = content

        logger.info(f"🔧 Tool call: {tool_name}({tool_args})")
        result = await self.tools.execute(tool_name, tool_args)

        # Have LLM present the result nicely
        messages = [
            {"role": "system", "content": "You are MyAi. Present the tool result to the user clearly and concisely. Don't add unnecessary commentary."},
            {"role": "user", "content": f"User asked: \"{original_text}\"\n\nTool `{tool_name}` returned:\n{result}\n\nPresent this helpfully."},
        ]

        try:
            llm_result = await self.ollama.chat(messages=messages)
            return llm_result.get("message", {}).get("content", result)
        except Exception:
            return f"**{tool_name}** result:\n\n{result}"

    async def _web_search_context(self, query: str) -> str:
        """Search the web and return context string, or empty if disabled."""
        if not self.tools.search_service.enabled:
            return ""
        try:
            logger.info(f"🌐 Auto web search: {query}")
            result = await self.tools.search_service.search(query, max_results=3)
            if result and "No results" not in result:
                return f"\n\n## Web Search Results\n{result}\n"
        except Exception as e:
            logger.warning(f"Web search failed: {e}")
        return ""

    def _should_web_search(self, text: str) -> str | None:
        """Detect if a question would benefit from a web search. Returns a search query or None."""
        low = text.lower()

        # Skip for generic conversation
        skip_patterns = ["hello", "hi ", "hey", "how are you", "thanks", "thank you",
                         "write me a", "write a ", "code", "implement", "create a function",
                         "help me with", "can you"]
        if any(low.startswith(p) for p in skip_patterns):
            return None

        # Trigger for questions about specific things, current events, facts
        search_triggers = [
            r"what (?:is|are|was|were) (?:the )?(.+?)[\?\.]?$",
            r"(?:tell me|explain) (?:about|what) (.+?)[\?\.]?$",
            r"who (?:is|are|was) (.+?)[\?\.]?$",
            r"(?:latest|newest|recent|current) (.+)",
            r"how (?:does|do|did) (.+?) work",
        ]

        for pattern in search_triggers:
            match = re.search(pattern, low)
            if match:
                topic = match.group(1).strip()
                if len(topic.split()) >= 2 or any(c.isupper() for c in text if c.isalpha()):
                    return topic

        return None

    async def _generate_content(self, request: str) -> str:
        """Ask LLM to generate file content, using web search for context."""
        context = ""

        # Try web search if enabled
        topic_match = re.search(r"(?:summary|description|overview|about|what)\s+(?:of\s+)?(?:what\s+)?(.+?)(?:\s+is)?$", request.lower())
        search_query = topic_match.group(1).strip() if topic_match else request[:100]
        web_context = await self._web_search_context(search_query)
        if web_context:
            context += web_context

        system = "You are a professional writer. Write clean, well-structured content."
        if context:
            system += f"\n\nUse this context for accuracy:{context}"

        system += "\n\nRULES:\n- Output ONLY the file content\n- No greetings, no 'Hello', no 'Summary:' headers\n- No mentions of tools, /allow, /search, or system commands\n- No meta-commentary about what you're doing\n- Just write the actual content directly"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": request},
        ]
        try:
            result = await self.ollama.chat(messages=messages)
            return result.get("message", {}).get("content", "").strip()
        except Exception:
            return f"Generated content for: {request}"

    async def _chat(self, conv) -> str:
        """Regular LLM conversation, enriched with web search when helpful."""
        system = self._build_system_prompt()

        # Check if the latest message would benefit from a web search
        latest_msg = conv.messages[-1].content if conv.messages else ""
        search_query = self._should_web_search(latest_msg)
        if search_query:
            web_context = await self._web_search_context(search_query)
            if web_context:
                system += f"\n\nUse these web search results to give an accurate, up-to-date answer:{web_context}"

        msgs = [{"role": "system", "content": system}]
        for msg in conv.messages[-20:]:
            msgs.append({"role": msg.role.value, "content": msg.content})

        try:
            result = await self.ollama.chat(messages=msgs)
            return result.get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"Ollama failed: {e}", exc_info=True)
            return f"⚠️ Couldn't reach Ollama. Make sure it's running and `{self.ollama.model}` is pulled."