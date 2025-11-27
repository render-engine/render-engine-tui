"""Integration with render-engine to load collections from Site configuration.

This module bridges the TUI with render-engine, allowing it to:
1. Load collections from render-engine Site configuration
2. Extract schema information from Collection objects
3. Use ContentManager instances for database operations
"""

from pathlib import Path
from typing import Dict, Optional, List, Any
import inspect
import logging

from .config import RenderEngineConfig
from .collections_config import CollectionConfig, Field

logger = logging.getLogger(__name__)


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

    def get_content_manager_extras(self, slug: str) -> Dict[str, Any]:
        """Get ContentManager initialization extras for a collection.

        Args:
            slug: The collection slug

        Returns:
            Dictionary of extras to pass to ContentManager.__init__()
        """
        try:
            collections = self.config.get_collections()
            if slug in collections:
                collection = collections[slug]
                # Get the collection name from the slug (used for database queries)
                extras = getattr(collection, "content_manager_extras", {}).copy()
                # Always ensure the collection instance is available
                if "collection" not in extras:
                    extras["collection"] = collection
                return extras
        except Exception:
            pass
        return {}


class ContentManagerAdapter:
    """Adapter to use render-engine ContentManager's standard pages property.

    Uses the standard render-engine ContentManager API (pages property) for
    reading content. All writes require a database connection, as the standard
    ContentManager API is read-only.

    Translates between Page objects and TUI's expected dictionary format.
    """

    def __init__(self, content_manager_class, collection_config, content_manager_extras: Optional[Dict[str, Any]] = None):
        """Initialize the adapter.

        Args:
            content_manager_class: The ContentManager class from render-engine
            collection_config: CollectionConfig instance for the collection
            content_manager_extras: Additional arguments to pass to ContentManager.__init__()
        """
        self.content_manager_class = content_manager_class
        self.collection_config = collection_config
        self.content_manager_extras = content_manager_extras or {}
        self._instance: Optional[Any] = None

    def _get_instance(self):
        """Get or create a ContentManager instance."""
        if self._instance is None:
            try:
                self._instance = self.content_manager_class(**self.content_manager_extras)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to instantiate {self.content_manager_class.__name__}: {e}"
                )
        return self._instance

    def _debug_page_object(self, page: Any) -> None:
        """Log all available attributes and methods on a Page object for debugging.

        Args:
            page: A Page object from ContentManager
        """
        logger.debug(f"\n{'='*80}")
        logger.debug(f"Page object type: {type(page)}")
        logger.debug(f"Page object class: {page.__class__.__name__}")
        logger.debug(f"Page module: {page.__class__.__module__}")

        # Log all attributes
        if hasattr(page, '__dict__'):
            logger.debug(f"\nPage __dict__ attributes ({len(page.__dict__)} total):")
            for key, value in page.__dict__.items():
                if isinstance(value, str):
                    val_preview = value[:100] + "..." if len(value) > 100 else value
                    logger.debug(f"  {key}: [{type(value).__name__}] {repr(val_preview)}")
                elif isinstance(value, (int, float, bool, type(None))):
                    logger.debug(f"  {key}: [{type(value).__name__}] {repr(value)}")
                else:
                    logger.debug(f"  {key}: [{type(value).__name__}]")

        # Check specific attributes we're looking for
        logger.debug(f"\nSpecific attribute checks:")
        for attr in ['id', 'slug', 'title', 'description', 'content', 'body', 'date', 'raw', 'markdown']:
            if hasattr(page, attr):
                val = getattr(page, attr)
                if isinstance(val, str):
                    preview = val[:50] + "..." if len(val) > 50 else val
                    logger.debug(f"  {attr}: EXISTS - {repr(preview)}")
                else:
                    logger.debug(f"  {attr}: EXISTS - type={type(val).__name__}, value={repr(val)}")
            else:
                logger.debug(f"  {attr}: NOT FOUND")

        logger.debug(f"{'='*80}\n")

    def _page_to_dict(self, page: Any) -> Dict[str, Any]:
        """Convert a render-engine Page object to a dictionary.

        Args:
            page: A Page object from ContentManager

        Returns:
            Dictionary with normalized fields (id, slug, title, description, content, date)
        """
        # Handle both dict-like and object-like pages
        if isinstance(page, dict):
            page_dict = page
        else:
            # Debug first page object to understand structure
            if not hasattr(self, '_debug_logged'):
                self._debug_page_object(page)
                self._debug_logged = True

            # Try to convert Page object to dict
            page_dict = {}
            # Get basic attributes
            for attr in ['id', 'slug', 'title', 'description', 'content', 'date',
                        'external_link', 'image_url', 'tags']:
                if hasattr(page, attr):
                    page_dict[attr] = getattr(page, attr)

            # Try alternative attribute names for content
            # render-engine typically uses 'body' for markdown content
            if 'content' not in page_dict or not page_dict['content']:
                for alt_attr in ['body', 'raw', 'markdown', 'text', '_content', 'full_content']:
                    if hasattr(page, alt_attr):
                        content = getattr(page, alt_attr)
                        if content:
                            page_dict['content'] = content
                            logger.debug(f"Found content in '{alt_attr}' attribute")
                            break

            # Check metadata if available
            if hasattr(page, 'meta') and isinstance(page.meta, dict):
                page_dict.update(page.meta)
            elif hasattr(page, 'metadata') and isinstance(page.metadata, dict):
                page_dict.update(page.metadata)

            # Last resort: try __dict__ to see all attributes
            if 'content' not in page_dict or not page_dict['content']:
                if hasattr(page, '__dict__'):
                    for key, value in page.__dict__.items():
                        if key not in page_dict and value and isinstance(value, str):
                            # Check if this looks like content (longer strings)
                            if len(str(value)) > 50:
                                page_dict[key] = value

        # Normalize result with required fields
        result = {
            "id": page_dict.get("id"),
            "slug": page_dict.get("slug", ""),
            "title": page_dict.get("title", ""),
            "description": page_dict.get("description", ""),
            "content": page_dict.get("content", ""),
            "external_link": page_dict.get("external_link"),
            "image_url": page_dict.get("image_url"),
            "date": page_dict.get("date"),
        }
        return result

    def get_all(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all items with pagination using the standard pages property.

        Args:
            limit: Maximum number of items to return
            offset: Number of items to skip

        Returns:
            List of item dictionaries
        """
        manager = self._get_instance()

        # Use standard ContentManager API: pages property
        if not hasattr(manager, "pages"):
            raise RuntimeError(
                f"{self.content_manager_class.__name__} does not have a pages property"
            )

        try:
            # Get all pages and convert to dicts
            all_pages = list(manager.pages)
            pages_as_dicts = [self._page_to_dict(page) for page in all_pages]

            # Apply pagination
            return pages_as_dicts[offset : offset + limit]
        except Exception as e:
            raise RuntimeError(f"Failed to fetch pages: {e}")

    def search(
        self, search_term: str, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Search items using the standard pages property.

        Performs in-memory search on all pages using searchable fields.

        Args:
            search_term: Search term to filter by
            limit: Maximum number of items to return
            offset: Number of items to skip

        Returns:
            List of matching item dictionaries
        """
        manager = self._get_instance()

        if not hasattr(manager, "pages"):
            raise RuntimeError(
                f"{self.content_manager_class.__name__} does not have a pages property"
            )

        try:
            all_pages = list(manager.pages)
            pages_as_dicts = [self._page_to_dict(page) for page in all_pages]

            # Filter by searchable fields
            filtered = []
            search_lower = search_term.lower()

            for item in pages_as_dicts:
                for field in self.collection_config.fields:
                    if field.searchable and field.name in item:
                        value = str(item[field.name]).lower()
                        if search_lower in value:
                            filtered.append(item)
                            break

            # Apply pagination
            return filtered[offset : offset + limit]
        except Exception as e:
            raise RuntimeError(f"Failed to search pages: {e}")

    def get(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get a single item by ID using the standard pages property.

        Args:
            item_id: The item ID

        Returns:
            Item dictionary or None if not found
        """
        manager = self._get_instance()

        if not hasattr(manager, "pages"):
            raise RuntimeError(
                f"{self.content_manager_class.__name__} does not have a pages property"
            )

        try:
            # Search through pages for matching ID
            for page in manager.pages:
                page_dict = self._page_to_dict(page)
                if page_dict.get("id") == item_id:
                    return page_dict
            return None
        except Exception as e:
            raise RuntimeError(f"Failed to fetch page {item_id}: {e}")

    def create_entry(self, content: str, **kwargs) -> str:
        """Create a new entry using ContentManager's create_entry() method.

        Uses the ContentManager's standard create_entry() interface, which all
        backends implement (PostgreSQL, FileSystem, etc.).

        Args:
            content: Markdown content with YAML frontmatter
            **kwargs: Additional arguments passed to ContentManager.create_entry()
                     (connection, table, collection_name, etc.)

        Returns:
            Result from ContentManager.create_entry() (typically SQL query or file path)

        Raises:
            RuntimeError: If create_entry fails
        """
        manager = self._get_instance()

        if not hasattr(manager, "create_entry") or not callable(getattr(manager, "create_entry")):
            raise NotImplementedError(
                f"{self.content_manager_class.__name__} does not implement create_entry(). "
                f"Use a ContentManager that supports write operations."
            )

        try:
            return manager.create_entry(content=content, **kwargs)
        except Exception as e:
            raise RuntimeError(f"Failed to create entry via ContentManager: {e}")
