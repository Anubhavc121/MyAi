from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(BaseModel):
    role: Role
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tool_name: str | None = None


class Conversation(BaseModel):
    id: str
    user_id: str
    messages: list[Message] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ToolCall(BaseModel):
    name: str
    arguments: dict
    result: str | None = None


class PermissionRequest(BaseModel):
    tool_name: str
    action: str
    resource: str
    tier: int = 1


class AgentResponse(BaseModel):
    content: str
    tool_calls: list[ToolCall] = []
    permission_requests: list[PermissionRequest] = []
