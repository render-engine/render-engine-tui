"""Configuration management for render-engine collections only.

Collections MUST be defined in [tool.render-engine] or [tool.render-engine.tui]
in the project's pyproject.toml. Falls back to [tool.render-engine.tui] if
[tool.render-engine] collections are not found.
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
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


class CollectionsManager:
    """Manages collection configurations from render-engine only."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the collections manager.

        Collections MUST be defined in [tool.render-engine] or [tool.render-engine.tui]
        in the project's pyproject.toml.

        Args:
            project_root: Path to project root for render-engine (defaults to current directory)

        Raises:
            RuntimeError: If collections cannot be loaded from render-engine
        """
        self.collections: Dict[str, CollectionConfig] = {}
        self._render_engine_loader: Optional[Any] = None
        self._load_from_render_engine(project_root or Path.cwd())


    def _load_from_render_engine(self, project_root: Path) -> None:
        """Load collections from render-engine Site configuration.

        Args:
            project_root: Path to project root containing pyproject.toml

        Raises:
            RuntimeError: If render-engine configuration is not found or invalid
        """
        try:
            from .render_engine_integration import RenderEngineCollectionsLoader

            loader = RenderEngineCollectionsLoader(project_root)
            self.collections = loader.get_all_collections()
            self._render_engine_loader = loader  # Store for later use

            if not self.collections:
                raise RuntimeError(
                    "No collections found in render-engine configuration. "
                    "Define collections in [tool.render-engine] or [tool.render-engine.tui] "
                    "in your project's pyproject.toml."
                )

            print(
                f"Loaded {len(self.collections)} collection(s) from render-engine Site"
            )
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Failed to load collections from render-engine: {e}. "
                f"Ensure render-engine is installed and [tool.render-engine] or "
                f"[tool.render-engine.tui] is configured in pyproject.toml."
            )


    def get_collection(self, name: str) -> Optional[CollectionConfig]:
        """Get a collection by name."""
        return self.collections.get(name)

    def get_all_collections(self) -> Dict[str, CollectionConfig]:
        """Get all available collections."""
        return self.collections

    def get_available_collection_names(self) -> List[str]:
        """Get list of available collection names."""
        return list(self.collections.keys())

    def validate_collection(self, name: str) -> bool:
        """Check if a collection exists."""
        return name in self.collections

    def get_render_engine_loader(self) -> Optional[Any]:
        """Get the render-engine loader instance if available.

        Returns:
            RenderEngineCollectionsLoader instance or None if not using render-engine
        """
        return self._render_engine_loader

    def has_render_engine_integration(self) -> bool:
        """Check if render-engine integration is active.

        Returns:
            True if collections were loaded from render-engine
        """
        return self._render_engine_loader is not None

    def get_content_manager_class(self, collection_name: str) -> Optional[Any]:
        """Get the ContentManager class for a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            The ContentManager class or None if not available
        """
        if self._render_engine_loader:
            return self._render_engine_loader.get_content_manager_for_collection(
                collection_name
            )
        return None
