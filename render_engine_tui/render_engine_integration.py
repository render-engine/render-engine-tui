"""Integration with render-engine to load collections from Site configuration.

This module bridges the TUI with render-engine, allowing it to:
1. Load collections from render-engine Site configuration
2. Extract schema information from Collection objects
3. Use ContentManager instances for database operations
"""

from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple
import importlib
import inspect
import sys
import tomllib
import logging

from .collections_config import CollectionConfig, Field
from render_engine import Site, Collection

logger = logging.getLogger(__name__)


class RenderEngineCollectionsLoader:
    """Loads collection configurations from a render-engine Site.

    Handles all aspects of loading and parsing render-engine configuration:
    - Reading pyproject.toml
    - Dynamically importing the Site
    - Extracting collection schemas
    """

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the loader.

        Args:
            project_root: Path to the render-engine project root.
                         Defaults to current working directory.
        """
        self.project_root = project_root or Path.cwd()
        self.pyproject_path = self.project_root / "pyproject.toml"
        self._config: Optional[Dict[str, Any]] = None
        self._site: Optional[Site] = None
        self._module: Optional[Any] = None
        self.collections: Dict[str, CollectionConfig] = {}
        self._load_collections()

    @property
    def config(self) -> Dict[str, Any]:
        """Load and cache the [tool.render-engine] configuration."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def _load_config(self) -> Dict[str, Any]:
        """Read pyproject.toml and extract [tool.render-engine] section.

        Returns:
            Dictionary containing render-engine configuration

        Raises:
            FileNotFoundError: If pyproject.toml doesn't exist
            KeyError: If [tool.render-engine] section is missing
        """
        if not self.pyproject_path.exists():
            raise FileNotFoundError(
                f"pyproject.toml not found at {self.pyproject_path}. "
                "Make sure you're running from a render-engine project directory."
            )

        with open(self.pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)

        if "tool" not in pyproject or "render-engine" not in pyproject["tool"]:
            raise KeyError(
                "[tool.render-engine] section not found in pyproject.toml. "
                "Add configuration like:\n"
                "[tool.render-engine.cli]\n"
                'module = "routes"\n'
                'site = "app"'
            )

        return pyproject["tool"]["render-engine"]

    def _get_site_reference(self) -> Tuple[str, str]:
        """Get the module and site object names from configuration.

        Returns:
            Tuple of (module_name, site_name)
        """
        cli_config = self.config.get("cli", {})
        module = cli_config.get("module")
        site = cli_config.get("site")

        if not module or not site:
            raise ValueError(
                "[tool.render-engine.cli] must specify both 'module' and 'site'.\n"
                "Example:\n"
                "[tool.render-engine.cli]\n"
                'module = "routes"\n'
                'site = "app"'
            )

        return module, site

    def _load_site(self) -> Site:
        """Dynamically import and return the render-engine Site object.

        Returns:
            The instantiated Site object from the configured module

        Raises:
            ImportError: If module cannot be imported
            AttributeError: If site object doesn't exist in module
        """
        if self._site is not None:
            return self._site

        module_name, site_name = self._get_site_reference()

        # Add project root to sys.path so we can import the module
        project_root_str = str(self.project_root)
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)

        try:
            # Import the module
            self._module = importlib.import_module(module_name)

            # Get the site object
            if not hasattr(self._module, site_name):
                raise AttributeError(
                    f"Module '{module_name}' does not have a '{site_name}' attribute. "
                    f"Check your [tool.render-engine.cli] configuration."
                )

            self._site = getattr(self._module, site_name)

            if not isinstance(self._site, Site):
                raise TypeError(
                    f"{module_name}.{site_name} is not a render_engine.Site instance. "
                    f"Got {type(self._site)} instead."
                )

            return self._site

        except ImportError as e:
            raise ImportError(
                f"Failed to import module '{module_name}'. "
                f"Make sure the module exists and is importable from {self.project_root}. "
                f"Original error: {e}"
            ) from e

    def _get_render_engine_collections(self) -> Dict[str, Collection]:
        """Get all collections registered with the site.

        Returns:
            Dictionary mapping collection slugs to Collection instances
        """
        site = self._load_site()

        # Filter route_list to only include Collection instances
        # (route_list also includes Page instances)
        return {
            slug: entry
            for slug, entry in site.route_list.items()
            if isinstance(entry, Collection)
        }

    def _load_collections(self) -> None:
        """Load collections from render-engine Site."""
        try:
            collections = self._get_render_engine_collections()

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
        # Try ContentManager first
        cm = getattr(collection, "ContentManager", None)
        if cm:
            if table := getattr(cm, "table_name", None):
                return table
            if table := getattr(cm, "_table", None):
                return table

        # Fallback to collection attributes
        if table := getattr(collection, "table_name", None):
            return table
        if table := getattr(collection, "_table", None):
            return table

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

    def get_render_engine_collections(self) -> Dict[str, Collection]:
        """Get the original render-engine Collection objects.

        Useful for accessing ContentManager instances.

        Returns:
            Dictionary mapping collection slugs to Collection instances
        """
        return self._get_render_engine_collections()

    def get_content_manager_for_collection(self, slug: str) -> Optional[Any]:
        """Get the ContentManager class for a collection.

        Args:
            slug: The collection slug

        Returns:
            The ContentManager class if available, None otherwise
        """
        try:
            collections = self.get_render_engine_collections()
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
            collections = self.get_render_engine_collections()
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


class ContentManager:
    """Unified content management for the TUI.

    Consolidates render-engine ContentManager interaction with collection management
    and TUI data normalization. Provides a single interface for all content operations:
    - Collection switching and validation
    - Content fetching (all, search, single)
    - Content creation
    - Data normalization to TUI format
    """

    def __init__(
        self,
        collection: str = "blog",
        project_root: Optional[Path] = None,
    ):
        """Initialize the content manager.

        Collections MUST be defined in [tool.render-engine] in the project's pyproject.toml.

        Args:
            collection: Collection to manage (default: "blog")
            project_root: Path to render-engine project root (defaults to current directory)

        Raises:
            ValueError: If collection is invalid
            RuntimeError: If render-engine config not found or ContentManager setup fails
        """
        # Load collections from render-engine
        self.loader = RenderEngineCollectionsLoader(project_root=project_root)

        if not self.loader.validate_collection(collection):
            available = self.loader.get_available_collection_names()
            raise ValueError(f"Invalid collection '{collection}'. Available: {available}")

        self.current_collection = collection
        self._content_manager_instance: Optional[Any] = None
        self._setup_content_manager()

    @property
    def AVAILABLE_COLLECTIONS(self) -> Dict[str, str]:
        """Get available collections from config."""
        return {name: config.display_name
                for name, config in self.loader.get_all_collections().items()}

    def _get_current_config(self):
        """Get the config for the current collection."""
        return self.loader.get_collection(self.current_collection)

    def has_content_manager(self) -> bool:
        """Check if the current collection has a ContentManager.

        Returns:
            True if a ContentManager is available
        """
        return self._content_manager_instance is not None

    def _setup_content_manager(self) -> None:
        """Set up ContentManager for the current collection.

        Raises:
            RuntimeError: If ContentManager cannot be set up
        """
        cm_class = self.loader.get_content_manager_for_collection(
            self.current_collection
        )
        if cm_class:
            try:
                config = self._get_current_config()
                # Get extras from render-engine configuration
                extras = self.loader.get_content_manager_extras(self.current_collection)
                self._content_manager_instance = cm_class(**extras)
            except Exception as e:
                raise RuntimeError(f"Failed to set up ContentManager for {self.current_collection}: {e}")
        else:
            raise RuntimeError(
                f"No ContentManager available for collection '{self.current_collection}'. "
                f"Ensure the collection is properly configured in your render-engine project."
            )

    def set_collection(self, collection: str) -> None:
        """Switch to a different collection at runtime.

        Args:
            collection: Collection name

        Raises:
            ValueError: If collection name is invalid
            RuntimeError: If ContentManager setup fails
        """
        if not self.loader.validate_collection(collection):
            available = self.loader.get_available_collection_names()
            raise ValueError(f"Invalid collection '{collection}'. Available: {available}")
        self.current_collection = collection
        self._setup_content_manager()

    def get_posts(self, search: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get posts from current collection with search and pagination.

        Args:
            search: Optional search term to filter posts
            limit: Maximum number of posts to return (default: 50)
            offset: Number of posts to skip for pagination (default: 0)

        Returns:
            List of post dictionaries with id, slug, title, description, date

        Raises:
            RuntimeError: If ContentManager operation fails
        """
        if not self._content_manager_instance:
            raise RuntimeError(f"No ContentManager available for collection '{self.current_collection}'")

        try:
            if search:
                items = self._search(search, limit=limit, offset=offset)
            else:
                items = self._get_all(limit=limit, offset=offset)

            if items:
                # Normalize ContentManager output to TUI format
                return self._normalize_posts(items)
            return []
        except Exception as e:
            raise RuntimeError(f"Failed to fetch posts: {e}")

    def _normalize_post(self, item: Dict[str, Any], full: bool = False) -> Dict[str, Any]:
        """Normalize a ContentManager item to TUI format.

        Args:
            item: Item from ContentManager
            full: If True, include all fields (content, external_link, image_url).
                  If False, include only basic fields and content preview.

        Returns:
            Post dictionary with normalized fields
        """
        post = {
            "id": item.get("id"),
            "slug": item.get("slug", ""),
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "date": item.get("date"),
        }

        if full:
            # For full posts: include all available fields
            post.update({
                "content": item.get("content", ""),
                "external_link": item.get("external_link"),
                "image_url": item.get("image_url"),
            })
        else:
            # For list views: use content preview if title is missing
            if not post["title"] and "content" in item:
                post["description"] = str(item.get("content", ""))[:100]

        return post

    def _normalize_posts(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize list of ContentManager items to TUI format.

        Args:
            items: List of items from ContentManager

        Returns:
            List of normalized posts with basic fields
        """
        return [self._normalize_post(item, full=False) for item in items]

    def get_post(self, post_id: int) -> Optional[Dict[str, Any]]:
        """Get a single post with all details from current collection.

        Args:
            post_id: The post ID

        Returns:
            Post dictionary with all fields, or None if not found

        Raises:
            RuntimeError: If ContentManager operation fails
        """
        if not self._content_manager_instance:
            raise RuntimeError(f"No ContentManager available for collection '{self.current_collection}'")

        try:
            post = self._get(post_id)
            if post:
                # Normalize output with full fields
                return self._normalize_post(post, full=True)
            return None
        except Exception as e:
            raise RuntimeError(f"Failed to fetch post {post_id}: {e}")

    def create_post(
        self,
        slug: str,
        title: str,
        content: str,
        description: str = "",
        external_link: Optional[str] = None,
        image_url: Optional[str] = None,
        date: Optional[str] = None,
    ) -> int:
        """Create a new post in current collection using ContentManager.create_entry().

        Builds markdown with YAML frontmatter and delegates to ContentManager,
        which handles storage transparently (PostgreSQL, FileSystem, etc.).

        Args:
            slug: Post slug (URL identifier)
            title: Post title
            content: Post content (markdown)
            description: Post description
            external_link: External URL (optional)
            image_url: Image URL (optional)
            date: Publication date as ISO string (optional, uses current time if not provided)

        Returns:
            The ID of the created post

        Raises:
            RuntimeError: If creation fails
        """
        if not self._content_manager_instance:
            raise RuntimeError("No ContentManager available for collection")

        try:
            import frontmatter
            from datetime import datetime

            config = self._get_current_config()

            # Use provided date or current time
            if date is None:
                date = datetime.now().isoformat()

            # Build YAML frontmatter dictionary
            frontmatter_data = {
                "slug": slug,
                "date": date,
            }

            # Add optional fields based on collection schema
            if config.has_field("title") and title:
                frontmatter_data["title"] = title
            if config.has_field("description") and description:
                frontmatter_data["description"] = description
            if external_link:
                frontmatter_data["external_link"] = external_link
            if image_url:
                frontmatter_data["image_url"] = image_url

            # Create markdown post object with frontmatter
            post = frontmatter.Post(content, **frontmatter_data)
            markdown_with_frontmatter = frontmatter.dumps(post)

            # Delegate to ContentManager - works with any backend
            result = self._create_entry(
                content=markdown_with_frontmatter,
                table=config.table_name,
                collection_name=self.current_collection,
            )

            # Extract post ID from result
            post_id = self._get_post_id_after_create(slug)
            return post_id

        except Exception as e:
            raise RuntimeError(f"Failed to create post: {e}")

    def _get_post_id_after_create(self, slug: str) -> int:
        """Get the ID of a post that was just created by slug.

        Args:
            slug: The post slug

        Returns:
            The post ID

        Raises:
            RuntimeError: If post not found
        """
        try:
            posts = self.get_posts(search=slug, limit=1)
            if posts:
                return posts[0].get("id")
            raise RuntimeError(f"Post with slug '{slug}' not found after creation")
        except Exception as e:
            raise RuntimeError(f"Failed to get post ID after creation: {e}")

    def _get_instance(self):
        """Get the current ContentManager instance."""
        if self._content_manager_instance is None:
            raise RuntimeError("ContentManager not initialized")
        return self._content_manager_instance

    def _validate_has_pages(self, manager: Any) -> None:
        """Validate that manager has a pages property.

        Raises:
            RuntimeError: If manager doesn't have pages property
        """
        if not hasattr(manager, "pages"):
            raise RuntimeError(
                f"{manager.__class__.__name__} does not have a pages property"
            )

    def _get_all(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all items with pagination using the standard pages property.

        Args:
            limit: Maximum number of items to return
            offset: Number of items to skip

        Returns:
            List of item dictionaries
        """
        manager = self._get_instance()
        self._validate_has_pages(manager)

        try:
            # Get all pages and convert to dicts
            all_pages = list(manager.pages)
            pages_as_dicts = [self._page_to_dict(page) for page in all_pages]
            return pages_as_dicts[offset : offset + limit]
        except Exception as e:
            raise RuntimeError(f"Failed to fetch pages: {e}")

    def _search(
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
        config = self._get_current_config()
        self._validate_has_pages(manager)

        try:
            all_pages = list(manager.pages)
            pages_as_dicts = [self._page_to_dict(page) for page in all_pages]

            # Filter by searchable fields
            filtered = []
            search_lower = search_term.lower()

            for item in pages_as_dicts:
                for field in config.fields:
                    if field.searchable and field.name in item:
                        value = str(item[field.name]).lower()
                        if search_lower in value:
                            filtered.append(item)
                            break

            return filtered[offset : offset + limit]
        except Exception as e:
            raise RuntimeError(f"Failed to search pages: {e}")

    def _get(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get a single item by ID using the standard pages property.

        Args:
            item_id: The item ID

        Returns:
            Item dictionary or None if not found
        """
        manager = self._get_instance()
        self._validate_has_pages(manager)

        try:
            # Search through pages for matching ID
            for page in manager.pages:
                page_dict = self._page_to_dict(page)
                if page_dict.get("id") == item_id:
                    return page_dict
            return None
        except Exception as e:
            raise RuntimeError(f"Failed to fetch page {item_id}: {e}")

    def _create_entry(self, content: str, **kwargs) -> str:
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
                f"{manager.__class__.__name__} does not implement create_entry(). "
                f"Use a ContentManager that supports write operations."
            )

        try:
            return manager.create_entry(content=content, **kwargs)
        except Exception as e:
            raise RuntimeError(f"Failed to create entry via ContentManager: {e}")

    def _page_to_dict(self, page: Any) -> Dict[str, Any]:
        """Convert a render-engine Page object to a dictionary.

        Args:
            page: A Page object from ContentManager

        Returns:
            Dictionary with normalized fields (id, slug, title, description, content, date)
        """
        # Handle dict-like pages
        if isinstance(page, dict):
            page_dict = page
        else:
            # Convert Page object to dict by extracting attributes
            page_dict = {}
            for attr in ['id', 'slug', 'title', 'description', 'date', 'external_link', 'image_url', 'tags']:
                if hasattr(page, attr):
                    page_dict[attr] = getattr(page, attr)

            # Extract RAW content (not parsed) for editing in TUI
            # Use page.content (raw source), NOT page._content (parsed/rendered)
            if hasattr(page, 'content'):
                page_dict['content'] = page.content
            elif hasattr(page, '_content'):
                page_dict['content'] = page._content  # fallback for edge cases

            # Merge metadata if available
            if hasattr(page, 'meta') and isinstance(page.meta, dict):
                page_dict.update(page.meta)
            elif hasattr(page, 'metadata') and isinstance(page.metadata, dict):
                page_dict.update(page.metadata)

        # Normalize result with required fields
        return {
            "id": page_dict.get("id"),
            "slug": page_dict.get("slug", ""),
            "title": page_dict.get("title", ""),
            "description": page_dict.get("description", ""),
            "content": page_dict.get("content", ""),
            "external_link": page_dict.get("external_link"),
            "image_url": page_dict.get("image_url"),
            "date": page_dict.get("date"),
        }
