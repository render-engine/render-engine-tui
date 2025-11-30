"""Configuration data classes for collections."""

from dataclasses import dataclass, field
from typing import Set


@dataclass
class CollectionConfig:
    """Minimal collection configuration.

    Stores only the essential metadata needed by the TUI:
    - Basic identification and display
    - Available fields (which subset of common fields this collection has)
    """

    name: str
    display_name: str
    table_name: str = ""
    id_column: str = ""
    junction_table: str = ""
    available_fields: Set[str] = field(default_factory=lambda: {"title", "description", "content", "slug", "date"})

    def has_field(self, name: str) -> bool:
        """Check if collection has a field."""
        return name in self.available_fields
