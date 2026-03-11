from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

import aiosqlite

from app.storage.models import Conversation, Message, Role


class Database:
    def __init__(self, db_path: str = "data/openclaw.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_name TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conv
                ON messages(conversation_id)
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    directory TEXT NOT NULL,
                    granted_at TEXT NOT NULL
                )
            """)
            await db.commit()

    async def get_or_create_conversation(self, user_id: str) -> Conversation:
        """Get the latest active conversation for a user, or create one."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
                (user_id,),
            )
            row = await cursor.fetchone()

            if row:
                conv = Conversation(
                    id=row["id"],
                    user_id=row["user_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                # Load messages
                cursor = await db.execute(
                    "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp",
                    (conv.id,),
                )
                rows = await cursor.fetchall()
                conv.messages = [
                    Message(
                        role=Role(r["role"]),
                        content=r["content"],
                        tool_name=r["tool_name"],
                        timestamp=datetime.fromisoformat(r["timestamp"]),
                    )
                    for r in rows
                ]
                return conv

            # Create new
            conv_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            await db.execute(
                "INSERT INTO conversations (id, user_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conv_id, user_id, now, now),
            )
            await db.commit()
            return Conversation(id=conv_id, user_id=user_id)

    async def add_message(self, conversation_id: str, message: Message):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO messages (conversation_id, role, content, tool_name, timestamp) VALUES (?, ?, ?, ?, ?)",
                (
                    conversation_id,
                    message.role.value,
                    message.content,
                    message.tool_name,
                    message.timestamp.isoformat(),
                ),
            )
            await db.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), conversation_id),
            )
            await db.commit()

    async def clear_conversation(self, user_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id FROM conversations WHERE user_id = ?", (user_id,)
            )
            rows = await cursor.fetchall()
            for row in rows:
                await db.execute(
                    "DELETE FROM messages WHERE conversation_id = ?", (row[0],)
                )
            await db.execute(
                "DELETE FROM conversations WHERE user_id = ?", (user_id,)
            )
            await db.commit()

    async def save_permission(self, user_id: str, directory: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO permissions (user_id, directory, granted_at) VALUES (?, ?, ?)",
                (user_id, directory, datetime.utcnow().isoformat()),
            )
            await db.commit()
