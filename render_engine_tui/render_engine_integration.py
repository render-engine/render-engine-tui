"""Integration with render-engine to load collections from Site configuration.

This module bridges the TUI with render-engine, allowing it to:
1. Load collections from render-engine Site configuration
2. Extract schema information from Collection objects
3. Use ContentManager instances for database operations
"""

from pathlib import Path
from typing import Dict, Optional, List, Any
import logging

from .site_loader import SiteLoader
from .collections_config import CollectionConfig
from render_engine import Collection, Page

logger = logging.getLogger(__name__)


class RenderEngineCollectionsLoader(SiteLoader):
    """Loads collection configurations from a render-engine Site.

    Extends SiteLoader with schema extraction for CollectionConfig objects.
    Inherits all Site loading logic from parent class.
    """

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the loader.

        Args:
            project_root: Path to the render-engine project root.
                         Defaults to current working directory.
        """
        super().__init__(project_root)
        self.collections: Dict[str, CollectionConfig] = {}
        self._load_collections()

    def _load_collections(self) -> None:
        """Load collections from render-engine Site."""
        try:
            # Use parent's get_collections() method
            collections = self.get_collections()

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

            # Extract available fields
            available_fields = self._extract_available_fields(collection)

            return CollectionConfig(
                name=slug,
                display_name=display_name,
                table_name=table_name,
                id_column=f"{table_name}_id",
                junction_table=f"{table_name}_tags",
                available_fields=available_fields,
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

    def _extract_available_fields(self, collection) -> set:
        """Extract which fields are available in this collection.

        For render-engine Collections, we detect fields based on:
        1. Parser type (Markdown parsers have title, description, content)
        2. Common render-engine fields (id, slug, date)

        Args:
            collection: The render-engine Collection instance

        Returns:
            Set of field names available in this collection
        """
        # Always available
        available = {"id", "slug", "date"}

        # Detect based on parser type
        if hasattr(collection, "Parser"):
            parser = collection.Parser
            parser_name = parser.__name__

            # Markdown parsers typically have title, description, content
            if "Markdown" in parser_name or "YAML" in parser_name:
                available.update({"title", "description", "content"})
            # Text parsers might just have content
            elif "Text" in parser_name:
                available.add("content")

        # Add metadata fields that might be present
        available.update({"external_link", "image_url", "tags"})

        # Fallback to common fields if detection failed
        return available if available else {"title", "description", "content", "slug", "date"}

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
        # Use parent's get_collections() method
        return self.get_collections()

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
    """Unified content management interface combining render-engine ContentManager,
    post operations, and search functionality.

    Handles:
    - Collection switching
    - Post retrieval and creation
    - Search operations
    - Pagination support
    """

    # Fields that can be searched
    SEARCHABLE_FIELDS = ['title', 'slug', 'content', 'description']

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
        self._posts_cache: Dict[str, List[Page]] = {}  # Cache posts by collection
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
        self._posts_cache.clear()  # Clear cache when switching collections
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

    # ====== Post Operations (merged from PostService) ======

    def get_all_posts(self, use_cache: bool = True) -> List[Page]:
        """Get all posts from current collection.

        Uses caching to avoid repeated backend calls. Cache is automatically
        invalidated when switching collections.

        Args:
            use_cache: Whether to use cached posts if available (default: True)

        Returns:
            List of all Page objects

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            # Check cache first
            if use_cache and self.current_collection in self._posts_cache:
                return self._posts_cache[self.current_collection]

            # Fetch from backend
            manager = self.get_instance()
            if not hasattr(manager, "pages"):
                raise RuntimeError(
                    f"{manager.__class__.__name__} does not have a pages property"
                )
            posts = list(manager.pages)

            # Cache for future use
            self._posts_cache[self.current_collection] = posts
            return posts
        except Exception as e:
            raise RuntimeError(f"Failed to fetch pages: {e}")

    def invalidate_posts_cache(self) -> None:
        """Invalidate the posts cache for the current collection.

        Call this after creating or modifying posts to ensure fresh data on next fetch.
        """
        self._posts_cache.pop(self.current_collection, None)

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

            manager = self.get_instance()
            config = self._get_current_config()

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
                collection_name=self.current_collection,
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
            # Invalidate cache to fetch fresh posts
            self.invalidate_posts_cache()
            posts = self.get_all_posts(use_cache=False)
            matching = self.search_posts(posts, slug)
            if matching:
                return matching[0].id
            raise RuntimeError(f"Post with slug '{slug}' not found after creation")
        except Exception as e:
            raise RuntimeError(f"Failed to get post ID after creation: {e}")

    # ====== Search Operations (merged from SearchService) ======

    def search_posts(self, pages: List[Page], search_term: str) -> List[Page]:
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
            for attr in self.SEARCHABLE_FIELDS:
                if hasattr(page, attr):
                    value = str(getattr(page, attr, "")).lower()
                    if search_lower in value:
                        filtered.append(page)
                        break

        return filtered

