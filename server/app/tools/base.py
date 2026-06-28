"""Base tool interface for the Agent framework.

Each tool:
  - name: unique identifier used in function calling
  - description: tells the LLM when and how to use this tool
  - parameters: JSON Schema dict describing the tool's input
  - execute(**kwargs): async method that runs the tool and returns a ToolResult
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    content: str
    tool_name: str = ""
    error: str | None = None
    metadata: dict = field(default_factory=dict)


class BaseTool(ABC):
    """Abstract base for all tools."""

    name: str
    description: str
    parameters: dict  # JSON Schema

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with the given arguments.

        Args are validated against self.parameters by the Agent loop before calling.
        """
        ...

    def to_openai_function(self) -> dict:
        """Export as an OpenAI-compatible function definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
