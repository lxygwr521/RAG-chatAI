"""Tool registry — registration and lookup for Agent tools."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.tools.base import BaseTool


class ToolRegistry:
    """Thread-safe registry of available tools."""

    def __init__(self):
        self._tools: dict[str, "BaseTool"] = {}

    def register(self, tool: "BaseTool") -> None:
        """Register a tool. Overwrites if name already exists."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Remove a tool by name."""
        self._tools.pop(name, None)

    def get(self, name: str) -> "BaseTool | None":
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> list["BaseTool"]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get_names(self) -> list[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())

    def to_openai_functions(self) -> list[dict]:
        """Export all tools as OpenAI function definitions."""
        return [tool.to_openai_function() for tool in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# Global singleton
tool_registry = ToolRegistry()
