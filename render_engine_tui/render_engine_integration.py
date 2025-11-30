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
from render_engine import Site, Collection, Page

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
    """Thin adapter for render-engine ContentManager.

    Handles collection switching and provides access to the underlying
    render-engine ContentManager. All content operations are delegated
    to separate services (PostService, SearchService).
    """

    def __init__(
        self,
        collection: str = "blog",
        project_root: Optional[Path] = None,
    ):
        """Initialize the content manager.

        Args:
            collection: Collection to manage (default: "blog")
            project_root: Path to render-engine project root (defaults to current directory)

        Raises:
            ValueError: If collection is invalid
            RuntimeError: If render-engine config not found or ContentManager setup fails
        """
        self.loader = RenderEngineCollectionsLoader(project_root=project_root)

        if not self.loader.validate_collection(collection):
            available = self.loader.get_available_collection_names()
            raise ValueError(f"Invalid collection '{collection}'. Available: {available}")

        self.current_collection = collection
        self._content_manager_instance: Optional[Any] = None
        self._setup_content_manager()

    @property
    def collections_manager(self):
        """Get the collections loader for accessing collection information."""
        return self.loader

    @property
    def AVAILABLE_COLLECTIONS(self) -> Dict[str, str]:
        """Get available collections from config."""
        return {name: config.display_name
                for name, config in self.loader.get_all_collections().items()}

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

    def get_instance(self):
        """Get the current render-engine ContentManager instance.

        Returns:
            The underlying render-engine ContentManager

        Raises:
            RuntimeError: If ContentManager not initialized
        """
        if self._content_manager_instance is None:
            raise RuntimeError("ContentManager not initialized")
        return self._content_manager_instance

    def _get_current_config(self):
        """Get the config for the current collection."""
        return self.loader.get_collection(self.current_collection)

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


class SearchService:
    """Handles search operations on Page objects.

    Performs in-memory filtering on a list of pages.
    """

    SEARCHABLE_FIELDS = ['title', 'slug', 'content', 'description']

    @staticmethod
    def search(pages: List[Page], search_term: str) -> List[Page]:
        """Search pages by common fields.

        Args:
            pages: List of Page objects to search
            search_term: Term to search for

        Returns:
            List of matching Page objects
        """
        if not search_term:
            return pages

        search_lower = search_term.lower()
        filtered = []

        for page in pages:
            for attr in SearchService.SEARCHABLE_FIELDS:
                if hasattr(page, attr):
                    value = str(getattr(page, attr, "")).lower()
                    if search_lower in value:
                        filtered.append(page)
                        break

        return filtered


class PostService:
    """Handles post operations using a ContentManager.

    Provides simple delegation to render-engine's ContentManager.
    Pagination is the caller's responsibility.
    """

    def __init__(self, content_manager: ContentManager):
        """Initialize the post service.

        Args:
            content_manager: ContentManager instance to use
        """
        self.content_manager = content_manager

    def get_all_posts(self) -> List[Page]:
        """Get all posts from current collection.

        Returns:
            List of all Page objects

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            manager = self.content_manager.get_instance()
            if not hasattr(manager, "pages"):
                raise RuntimeError(
                    f"{manager.__class__.__name__} does not have a pages property"
                )
            return list(manager.pages)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch pages: {e}")

    def get_post(self, post_id: int) -> Optional[Page]:
        """Get a single post by ID.

        Args:
            post_id: The post ID

        Returns:
            Page object or None if not found

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            posts = self.get_all_posts()
            for page in posts:
                if getattr(page, 'id', None) == post_id:
                    return page
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
        """Create a new post in current collection.

        Args:
            slug: Post slug (URL identifier)
            title: Post title
            content: Post content (markdown)
            description: Post description
            external_link: External URL (optional)
            image_url: Image URL (optional)
            date: Publication date as ISO string (optional)

        Returns:
            The ID of the created post

        Raises:
            RuntimeError: If creation fails
        """
        try:
            import frontmatter
            from datetime import datetime

            manager = self.content_manager.get_instance()
            config = self.content_manager._get_current_config()

            if date is None:
                date = datetime.now().isoformat()

            # Build YAML frontmatter dictionary
            frontmatter_data = {
                "slug": slug,
                "date": date,
            }

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

            # Delegate to ContentManager
            if not hasattr(manager, "create_entry") or not callable(getattr(manager, "create_entry")):
                raise NotImplementedError(
                    f"{manager.__class__.__name__} does not implement create_entry(). "
                    f"Use a ContentManager that supports write operations."
                )

            manager.create_entry(
                content=markdown_with_frontmatter,
                table=config.table_name,
                collection_name=self.content_manager.current_collection,
            )

            # Get the ID of the created post
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
            posts = self.get_all_posts()
            matching = SearchService.search(posts, slug)
            if matching:
                return matching[0].id
            raise RuntimeError(f"Post with slug '{slug}' not found after creation")
        except Exception as e:
            raise RuntimeError(f"Failed to get post ID after creation: {e}")

