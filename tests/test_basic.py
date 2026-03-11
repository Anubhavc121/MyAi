"""Basic smoke tests for OpenClaw."""
import pytest


def test_imports():
    """Verify all modules import without error."""
    from app.config import settings, permissions_config
    from app.storage.models import Message, Conversation, Role
    from app.services.ollama import OllamaClient
    from app.services.file_access import FileAccessService
    from app.services.web_search import WebSearchService
    from app.agent.tools import ToolRegistry
    from app.agent.core import AgentCore

    assert settings is not None
    assert permissions_config is not None


def test_permissions_config():
    from app.config import PermissionsConfig

    config = PermissionsConfig(path="nonexistent.yaml")
    assert config.allowed_dirs == []
    assert not config.is_path_allowed("/etc/passwd")

    config.grant_directory("/tmp/test")
    assert config.is_path_allowed("/tmp/test/file.txt")
    assert not config.is_path_allowed("/home/secret")

    config.revoke_all()
    assert config.allowed_dirs == []


def test_tool_call_parsing():
    from app.agent.tools import ToolRegistry

    # Test ```tool block parsing
    text = 'Let me read that file.\n```tool\n{"name": "read_file", "arguments": {"path": "/tmp/test.txt"}}\n```'
    result = ToolRegistry.parse_tool_call(text)
    assert result is not None
    assert result["name"] == "read_file"
    assert result["arguments"]["path"] == "/tmp/test.txt"

    # Test no tool call
    assert ToolRegistry.parse_tool_call("Just a normal response.") is None
