"""Configuration data classes for collections."""

from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Field:
    """Represents a field in a collection."""

    name: str
    type: str
    searchable: bool = False
    editable: bool = True
    display: bool = True


@dataclass
class CollectionConfig:
    """Configuration for a single collection."""

    name: str
    display_name: str
    table_name: str
    id_column: str
    junction_table: str
    fields: List[Field]

    def get_field(self, name: str) -> Optional[Field]:
        """Get a field by name."""
        for field in self.fields:
            if field.name == name:
                return field
        return None

    def get_editable_fields(self) -> List[Field]:
        """Get all editable fields."""
        return [f for f in self.fields if f.editable]

    def has_field(self, name: str) -> bool:
        """Check if collection has a field."""
        return any(f.name == name for f in self.fields)
