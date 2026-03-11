from __future__ import annotations

import json
import logging
from typing import Any, Callable, Awaitable

from app.services.file_access import FileAccessService, FileAccessError, PermissionDeniedError
from app.services.web_search import WebSearchService
from app.services.rag import RAGService

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry of available tools for the agent."""

    def __init__(
        self,
        file_service: FileAccessService,
        search_service: WebSearchService,
        rag_service: RAGService,
    ):
        self.file_service = file_service
        self.search_service = search_service
        self.rag_service = rag_service

        self._tools: dict[str, Callable[..., Awaitable[str]]] = {
            "read_file": self._read_file,
            "list_directory": self._list_directory,
            "search_files": self._search_files,
            "write_file": self._write_file,
            "web_search": self._web_search,
            "rag_query": self._rag_query,
        }

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool by name with given arguments."""
        if tool_name not in self._tools:
            return f"Unknown tool: {tool_name}. Available: {', '.join(self._tools.keys())}"

        try:
            result = await self._tools[tool_name](**arguments)
            return result
        except PermissionDeniedError as e:
            return f"⛔ Permission denied: {e}"
        except FileAccessError as e:
            return f"❌ File error: {e}"
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
            return f"❌ Tool error: {e}"

    # ── Tool implementations ──

    async def _read_file(self, path: str) -> str:
        content = await self.file_service.read_file(path)
        # Truncate very long files for the LLM context
        if len(content) > 8000:
            return content[:8000] + f"\n\n... [truncated, {len(content)} chars total]"
        return content

    async def _list_directory(self, path: str) -> str:
        return await self.file_service.list_directory(path)

    async def _search_files(self, directory: str, pattern: str) -> str:
        return await self.file_service.search_files(directory, pattern)

    async def _write_file(self, path: str, content: str) -> str:
        return await self.file_service.write_file(path, content)

    async def _web_search(self, query: str) -> str:
        return await self.search_service.search(query)

    async def _rag_query(self, question: str) -> str:
        return await self.rag_service.query(question)

    @staticmethod
    def parse_tool_call(text: str) -> dict | None:
        """Extract a tool call JSON from the model's response."""
        # Look for ```tool ... ``` blocks
        import re

        pattern = r"```tool\s*\n?\s*(\{.*?\})\s*\n?\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return None

        # Also try bare JSON with "name" and "arguments" keys
        pattern2 = r'\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{.*?\}\s*\}'
        match2 = re.search(pattern2, text, re.DOTALL)
        if match2:
            try:
                return json.loads(match2.group(0))
            except json.JSONDecodeError:
                return None

        return None
