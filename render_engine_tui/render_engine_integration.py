"""Integration with render-engine to load collections from Site configuration.

This module bridges the TUI with render-engine, allowing it to:
1. Load collections from render-engine Site configuration
2. Extract schema information from Collection objects
3. Use ContentManager instances for database operations
"""

from pathlib import Path
from typing import Dict, Optional, List, Any
import inspect

from .config import RenderEngineConfig
from .collections_config import CollectionConfig, Field


class RenderEngineCollectionsLoader:
    """Loads collection configurations from a render-engine Site."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the loader.

        Args:
            project_root: Path to the render-engine project root.
                         Defaults to current working directory.
        """
        self.project_root = project_root or Path.cwd()
        self.config = RenderEngineConfig(self.project_root)
        self.collections: Dict[str, CollectionConfig] = {}
        self._load_collections()

    def _load_collections(self) -> None:
        """Load collections from render-engine Site."""
        try:
            collections = self.config.get_collections()

            for slug, collection in collections.items():
                # Try to extract collection config from render-engine collection
                config = self._extract_collection_config(slug, collection)
                if config:
                    self.collections[slug] = config
        except Exception as e:
            print(f"Warning: Failed to load render-engine collections: {e}")
            # Fallback to empty collections if render-engine loading fails
            pass

    def _extract_collection_config(
        self, slug: str, collection
    ) -> Optional[CollectionConfig]:
        """Extract CollectionConfig from a render-engine Collection.

        Args:
            slug: The collection slug
            collection: The render-engine Collection instance

        Returns:
            CollectionConfig if successful, None otherwise
        """
        try:
            # Get display name
            display_name = getattr(collection, "_title", slug.title())

            # Try to get table name from ContentManager
            table_name = self._extract_table_name(collection)
            if not table_name:
                table_name = slug

            # Generate junction table name
            junction_table = f"{table_name}_tags"

            # Generate ID column name
            id_column = f"{table_name}_id"

            # Extract fields
            fields = self._extract_fields(collection)

            return CollectionConfig(
                name=slug,
                display_name=display_name,
                table_name=table_name,
                id_column=id_column,
                junction_table=junction_table,
                fields=fields,
            )
        except Exception as e:
            print(f"Warning: Failed to extract config for collection '{slug}': {e}")
            return None

    def _extract_table_name(self, collection) -> Optional[str]:
        """Extract the table name from a Collection's ContentManager.

        Args:
            collection: The render-engine Collection instance

        Returns:
            Table name if found, None otherwise
        """
        try:
            # Try to get from ContentManager
            if hasattr(collection, "ContentManager"):
                cm = collection.ContentManager

                # For PostgresContentManager
                if hasattr(cm, "table_name"):
                    return cm.table_name

                # Check if ContentManager has a table attribute
                if hasattr(cm, "_table"):
                    return cm._table

                # Try to instantiate and get table name
                if hasattr(cm, "__init__"):
                    # Try to get from class attributes
                    for name, value in inspect.getmembers(cm):
                        if "table" in name.lower() and isinstance(value, str):
                            return value

            # Try to get from collection itself
            if hasattr(collection, "table_name"):
                return collection.table_name

            if hasattr(collection, "_table"):
                return collection._table

        except Exception:
            pass

        return None

    def _extract_fields(self, collection) -> List[Field]:
        """Extract field information from a Collection.

        For render-engine Collections, we extract fields based on:
        1. Collection's defined attributes
        2. Inspection of the Collection class
        3. Known render-engine fields (id, slug, title, description, content, date, etc.)

        Args:
            collection: The render-engine Collection instance

        Returns:
            List of Field objects
        """
        fields = []

        # Always include common fields
        common_fields = {
            "id": Field(name="id", type="int", display=False),
            "slug": Field(name="slug", type="str", searchable=True),
            "date": Field(name="date", type="datetime"),
        }

        # Check which common fields are likely present
        fields_to_include = {"id", "slug", "date"}

        # Try to determine which fields the collection uses
        if hasattr(collection, "Parser"):
            parser = collection.Parser
            # Check parser class for field hints
            parser_name = parser.__name__

            # Markdown parsers typically have title, description, content
            if "Markdown" in parser_name:
                fields_to_include.update({"title", "description", "content"})
            # Text parsers might just have content
            elif "Text" in parser_name:
                fields_to_include.add("content")

        # Add detected fields
        for field_name in sorted(fields_to_include):
            if field_name in common_fields:
                fields.append(common_fields[field_name])

        # Add optional metadata fields if they're commonly used
        for field_name in ["external_link", "image_url", "tags"]:
            if field_name not in [f.name for f in fields]:
                fields.append(
                    Field(name=field_name, type="str", searchable=False, editable=True)
                )

        return fields if fields else self._get_default_fields()

    def _get_default_fields(self) -> List[Field]:
        """Get default field set for collections without explicit schema.

        Returns:
            List of default Field objects
        """
        return [
            Field(name="id", type="int", display=False),
            Field(name="slug", type="str", searchable=True),
            Field(name="title", type="str", searchable=True, editable=True),
            Field(name="description", type="str", searchable=True, editable=True),
            Field(name="content", type="str", searchable=True, editable=True),
            Field(name="external_link", type="str", editable=True),
            Field(name="image_url", type="str", editable=True),
            Field(name="date", type="datetime"),
        ]

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

    def get_render_engine_collections(self) -> Dict[str, Any]:
        """Get the original render-engine Collection objects.

        Useful for accessing ContentManager instances.

        Returns:
            Dictionary mapping collection slugs to Collection instances
        """
        return self.config.get_collections()

    def get_content_manager_for_collection(self, slug: str) -> Optional[Any]:
        """Get the ContentManager class for a collection.

        Args:
            slug: The collection slug

        Returns:
            The ContentManager class if available, None otherwise
        """
        try:
            collections = self.config.get_collections()
            if slug in collections:
                collection = collections[slug]
                if hasattr(collection, "ContentManager"):
                    return collection.ContentManager
        except Exception:
            pass
        return None


class ContentManagerAdapter:
    """Adapter to use render-engine ContentManager for content operations.

    This allows the TUI to use the ContentManager from render-engine
    as the primary data source instead of direct database access.

    Translates between TUI's expected data format and ContentManager's format.
    """

    def __init__(self, content_manager_class, collection_config):
        """Initialize the adapter.

        Args:
            content_manager_class: The ContentManager class from render-engine
            collection_config: CollectionConfig instance for the collection
        """
        self.content_manager_class = content_manager_class
        self.collection_config = collection_config
        self._instance: Optional[Any] = None

    def _get_instance(self):
        """Get or create a ContentManager instance."""
        if self._instance is None:
            try:
                self._instance = self.content_manager_class()
            except Exception as e:
                raise RuntimeError(
                    f"Failed to instantiate {self.content_manager_class.__name__}: {e}"
                )
        return self._instance

    def supports_operation(self, operation: str) -> bool:
        """Check if ContentManager supports an operation.

        Args:
            operation: Operation name (get_all, get, create, update, delete, search)

        Returns:
            True if the operation is available
        """
        manager = self._get_instance()
        method_map = {
            "get_all": "get_all",
            "get": "get",
            "create": "create",
            "update": "update",
            "delete": "delete",
            "search": "search",
        }
        method_name = method_map.get(operation)
        return method_name and hasattr(manager, method_name)

    def get_all(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all items with pagination.

        Args:
            limit: Maximum number of items to return
            offset: Number of items to skip

        Returns:
            List of item dictionaries
        """
        manager = self._get_instance()

        # Try to use get_all if available
        if hasattr(manager, "get_all"):
            items = manager.get_all()
            # Apply pagination manually if get_all returns list
            if isinstance(items, list):
                return items[offset : offset + limit]
            return items

        raise NotImplementedError(
            f"{self.content_manager_class.__name__} does not support get_all()"
        )

    def search(
        self, search_term: str, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Search items with optional pagination.

        Args:
            search_term: Search term to filter by
            limit: Maximum number of items to return
            offset: Number of items to skip

        Returns:
            List of matching item dictionaries
        """
        manager = self._get_instance()

        # Try to use search if available
        if hasattr(manager, "search"):
            items = manager.search(search_term)
            if isinstance(items, list):
                return items[offset : offset + limit]
            return items

        # Fallback: get all and filter manually
        if hasattr(manager, "get_all"):
            items = manager.get_all()
            if not isinstance(items, list):
                return []

            # Filter by searchable fields
            filtered = []
            search_lower = search_term.lower()

            for item in items:
                for field in self.collection_config.fields:
                    if field.searchable and field.name in item:
                        value = str(item[field.name]).lower()
                        if search_lower in value:
                            filtered.append(item)
                            break

            return filtered[offset : offset + limit]

        raise NotImplementedError(
            f"{self.content_manager_class.__name__} does not support search or get_all()"
        )

    def get(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get a single item by ID.

        Args:
            item_id: The item ID

        Returns:
            Item dictionary or None if not found
        """
        manager = self._get_instance()

        if hasattr(manager, "get"):
            return manager.get(item_id)

        # Fallback: get all and search
        if hasattr(manager, "get_all"):
            items = manager.get_all()
            if isinstance(items, list):
                for item in items:
                    if item.get("id") == item_id:
                        return item

        return None

    def create(self, **kwargs) -> int:
        """Create a new item.

        Args:
            **kwargs: Item fields and values

        Returns:
            The ID of the created item
        """
        manager = self._get_instance()

        if hasattr(manager, "create"):
            result = manager.create(**kwargs)
            # Handle different return types
            if isinstance(result, dict) and "id" in result:
                return result["id"]
            return int(result) if result else None

        raise NotImplementedError(
            f"{self.content_manager_class.__name__} does not support create()"
        )

    def update(self, item_id: int, **kwargs) -> bool:
        """Update an existing item.

        Args:
            item_id: The item ID
            **kwargs: Fields and values to update

        Returns:
            True if successful
        """
        manager = self._get_instance()

        if hasattr(manager, "update"):
            result = manager.update(item_id, **kwargs)
            return bool(result) if result is not None else True

        raise NotImplementedError(
            f"{self.content_manager_class.__name__} does not support update()"
        )

    def delete(self, item_id: int) -> bool:
        """Delete an item.

        Args:
            item_id: The item ID

        Returns:
            True if successful
        """
        manager = self._get_instance()

        if hasattr(manager, "delete"):
            result = manager.delete(item_id)
            return bool(result) if result is not None else True

        raise NotImplementedError(
            f"{self.content_manager_class.__name__} does not support delete()"
        )
