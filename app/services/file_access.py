from __future__ import annotations

import logging
import os
from pathlib import Path

from app.config import permissions_config

logger = logging.getLogger(__name__)


class FileAccessError(Exception):
    pass


class PermissionDeniedError(FileAccessError):
    pass


class FileAccessService:
    """Sandboxed file operations — every access checked against the allowlist."""

    SUPPORTED_TEXT_EXTENSIONS = {
        ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
        ".toml", ".cfg", ".ini", ".csv", ".html", ".css", ".xml",
        ".sh", ".bash", ".sql", ".rs", ".go", ".java", ".c", ".cpp",
        ".h", ".rb", ".php", ".swift", ".kt", ".r", ".log", ".env",
        ".gitignore", ".dockerfile",
    }

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    def _check_permission(self, path: str) -> str:
        resolved = str(Path(path).resolve())
        if not permissions_config.is_path_allowed(resolved):
            raise PermissionDeniedError(
                f"Access denied: '{path}' is not in the allowed directories.\n"
                f"Use `/allow <directory>` to grant access first."
            )
        return resolved

    async def read_file(self, path: str) -> str:
        resolved = self._check_permission(path)
        p = Path(resolved)

        if not p.exists():
            raise FileAccessError(f"File not found: {path}")
        if not p.is_file():
            raise FileAccessError(f"Not a file: {path}")
        if p.stat().st_size > self.MAX_FILE_SIZE:
            raise FileAccessError(f"File too large (>{self.MAX_FILE_SIZE // 1024 // 1024}MB): {path}")

        suffix = p.suffix.lower()
        if suffix in self.SUPPORTED_TEXT_EXTENSIONS or suffix == "":
            return p.read_text(encoding="utf-8", errors="replace")

        # For binary files, return metadata
        return (
            f"[Binary file: {p.name}]\n"
            f"Size: {p.stat().st_size:,} bytes\n"
            f"Type: {suffix or 'unknown'}\n"
            f"Modified: {p.stat().st_mtime}"
        )

    async def list_directory(self, path: str, max_items: int = 50) -> str:
        resolved = self._check_permission(path)
        p = Path(resolved)

        if not p.exists():
            raise FileAccessError(f"Directory not found: {path}")
        if not p.is_dir():
            raise FileAccessError(f"Not a directory: {path}")

        items = []
        for i, item in enumerate(sorted(p.iterdir())):
            if i >= max_items:
                items.append(f"  ... and {len(list(p.iterdir())) - max_items} more")
                break
            prefix = "📁" if item.is_dir() else "📄"
            size = ""
            if item.is_file():
                size = f" ({item.stat().st_size:,} bytes)"
            items.append(f"  {prefix} {item.name}{size}")

        return f"Contents of {path}:\n" + "\n".join(items)

    async def search_files(
        self, directory: str, pattern: str, max_results: int = 20
    ) -> str:
        resolved = self._check_permission(directory)
        p = Path(resolved)

        if not p.exists() or not p.is_dir():
            raise FileAccessError(f"Invalid directory: {directory}")

        results = []
        for match in p.rglob(pattern):
            if len(results) >= max_results:
                break
            rel = match.relative_to(p)
            results.append(str(rel))

        if not results:
            return f"No files matching '{pattern}' in {directory}"

        return f"Found {len(results)} files matching '{pattern}':\n" + "\n".join(
            f"  {r}" for r in results
        )

    async def read_file_metadata(self, path: str) -> str:
        resolved = self._check_permission(path)
        p = Path(resolved)

        if not p.exists():
            raise FileAccessError(f"Not found: {path}")

        stat = p.stat()
        return (
            f"Name: {p.name}\n"
            f"Path: {resolved}\n"
            f"Type: {'directory' if p.is_dir() else 'file'}\n"
            f"Size: {stat.st_size:,} bytes\n"
            f"Modified: {stat.st_mtime}\n"
            f"Extension: {p.suffix or 'none'}"
        )

    async def write_file(self, path: str, content: str) -> str:
        resolved = self._check_permission(path)
        p = Path(resolved)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"File written: {path} ({len(content)} characters)"
