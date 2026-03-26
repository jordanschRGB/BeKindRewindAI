"""Local tool base classes and registry.

Replaces the nanobot.agent.tools dependency which was a robotics framework
on PyPI with no agent submodule. These are minimal replacements that match
the interface expected by harness/tools.py and harness/runner.py.
"""

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """Base class for MemoryVault tools.

    Each tool has a name, description, parameters schema, and execute method.
    The agent calls tools by name; the harness dispatches to execute().
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name the model uses to call this tool."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Plain-language description the model reads to decide when to use this tool."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema object describing this tool's parameters."""
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """Execute the tool. Always returns a string (JSON or plain text)."""
        ...

    def to_schema(self) -> dict[str, Any]:
        """Return the tool as an OpenAI function-calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Registry that maps tool names to Tool instances.

    Usage:
        registry = ToolRegistry()
        registry.register(MyTool())
        tool = registry.get("my_tool")
        result = await tool.execute(param="value")
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool instance. Raises ValueError if name already registered."""
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Return a tool by name, or None if not found."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def schemas(self) -> list[dict[str, Any]]:
        """Return all tool schemas for passing to the model."""
        return [t.to_schema() for t in self._tools.values()]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)
