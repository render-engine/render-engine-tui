"""Configuration management for configurable collections.

Supports loading collections from three sources (in order of priority):
1. render-engine Site configuration (if in a render-engine project)
2. collections.yaml file
3. Hard-coded defaults
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import yaml


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
    """Manages collection configurations from render-engine, YAML, or defaults."""

    def __init__(self, config_path: Optional[str] = None, use_render_engine: bool = True, project_root: Optional[Path] = None):
        """Initialize the collections manager.

        Args:
            config_path: Path to collections.yaml file (optional).
                        If not provided, looks in standard locations.
            use_render_engine: If True, try to load from render-engine first (default: True)
            project_root: Path to project root for render-engine (defaults to current directory)
        """
        self.collections: Dict[str, CollectionConfig] = {}
        self._render_engine_loader: Optional[Any] = None
        self._load_config(config_path, use_render_engine, project_root)

    def _load_config(self, config_path: Optional[str] = None, use_render_engine: bool = True, project_root: Optional[Path] = None) -> None:
        """Load collections from render-engine, YAML, or defaults (in order).

        Args:
            config_path: Path to config file. If None, uses default location.
            use_render_engine: If True, try render-engine first.
            project_root: Path to project root for render-engine.
        """
        # Try to load from render-engine first
        if use_render_engine:
            if self._load_from_render_engine(project_root):
                return

        # Try to load from YAML config
        if config_path is None:
            # Look for collections.yaml in current directory and parent directory
            for path in [
                "collections.yaml",
                ".collections.yaml",
                os.path.join(os.path.dirname(__file__), "..", "collections.yaml"),
            ]:
                if os.path.exists(path):
                    config_path = path
                    break
            else:
                # Use default collections if no config file found
                self._load_default_collections()
                return

        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)

            if not data or "collections" not in data:
                self._load_default_collections()
                return

            for collection_name, collection_data in data["collections"].items():
                self.collections[collection_name] = self._parse_collection(
                    collection_name, collection_data
                )
        except Exception as e:
            print(f"Error loading collections.yaml: {e}. Using defaults.")
            self._load_default_collections()

    def _load_from_render_engine(self, project_root: Optional[Path] = None) -> bool:
        """Try to load collections from render-engine Site configuration.

        Args:
            project_root: Path to project root containing pyproject.toml

        Returns:
            True if successful, False otherwise
        """
        try:
            from .render_engine_integration import RenderEngineCollectionsLoader

            loader = RenderEngineCollectionsLoader(project_root or Path.cwd())
            self.collections = loader.get_all_collections()
            self._render_engine_loader = loader  # Store for later use

            if self.collections:
                print(
                    f"Loaded {len(self.collections)} collection(s) from render-engine Site"
                )
                return True
        except Exception as e:
            # Silently fail - render-engine might not be configured
            print(f"Note: Could not load from render-engine: {e}")
            return False

        return False

    def _parse_collection(
        self, name: str, data: Dict[str, Any]
    ) -> CollectionConfig:
        """Parse a collection configuration from dict."""
        fields_data = data.get("fields", [])
        fields = []

        for field_data in fields_data:
            if isinstance(field_data, str):
                # Simple field name
                fields.append(Field(name=field_data, type="str"))
            elif isinstance(field_data, dict):
                fields.append(
                    Field(
                        name=field_data["name"],
                        type=field_data.get("type", "str"),
                        searchable=field_data.get("searchable", False),
                        editable=field_data.get("editable", True),
                        display=field_data.get("display", True),
                    )
                )

        return CollectionConfig(
            name=name,
            display_name=data.get("display_name", name.title()),
            table_name=data.get("table_name", name),
            id_column=data.get("id_column", f"{name}_id"),
            junction_table=data.get("junction_table", f"{name}_tags"),
            fields=fields,
        )

    def _load_default_collections(self) -> None:
        """Load default hard-coded collections."""
        self.collections = {
            "blog": CollectionConfig(
                name="blog",
                display_name="Blog Posts",
                table_name="blog",
                id_column="blog_id",
                junction_table="blog_tags",
                fields=[
                    Field(name="id", type="int", display=False),
                    Field(name="slug", type="str", searchable=True),
                    Field(name="title", type="str", searchable=True, editable=True),
                    Field(
                        name="description",
                        type="str",
                        searchable=True,
                        editable=True,
                    ),
                    Field(name="content", type="str", searchable=True, editable=True),
                    Field(name="external_link", type="str", editable=True),
                    Field(name="image_url", type="str", editable=True),
                    Field(name="date", type="datetime"),
                ],
            ),
            "notes": CollectionConfig(
                name="notes",
                display_name="Notes",
                table_name="notes",
                id_column="notes_id",
                junction_table="notes_tags",
                fields=[
                    Field(name="id", type="int", display=False),
                    Field(name="slug", type="str", searchable=True),
                    Field(name="title", type="str", searchable=True, editable=True),
                    Field(
                        name="description",
                        type="str",
                        searchable=True,
                        editable=True,
                    ),
                    Field(name="content", type="str", searchable=True, editable=True),
                    Field(name="external_link", type="str", editable=True),
                    Field(name="image_url", type="str", editable=True),
                    Field(name="date", type="datetime"),
                ],
            ),
            "microblog": CollectionConfig(
                name="microblog",
                display_name="Microblog Posts",
                table_name="microblog",
                id_column="microblog_id",
                junction_table="microblog_tags",
                fields=[
                    Field(name="id", type="int", display=False),
                    Field(name="slug", type="str", searchable=True),
                    Field(name="content", type="str", searchable=True, editable=True),
                    Field(name="external_link", type="str", editable=True),
                    Field(name="image_url", type="str", editable=True),
                    Field(name="date", type="datetime"),
                ],
            ),
        }

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
