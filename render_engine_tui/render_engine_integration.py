"""Integration with render-engine to load collections from Site configuration.

This module bridges the TUI with render-engine, allowing it to:
1. Load collections from render-engine Site configuration
2. Use Collection objects and their ContentManager instances for data operations
"""

from pathlib import Path
from typing import Dict, Optional, List, Any
import logging

from .site_loader import SiteLoader
from render_engine import Collection, Page

logger = logging.getLogger(__name__)


class RenderEngineCollectionsLoader(SiteLoader):
    """Loads collections from a render-engine Site.

    Extends SiteLoader and provides direct access to render-engine Collection objects.
    Inherits all Site loading logic from parent class.
    """

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the loader.

        Args:
            project_root: Path to the render-engine project root.
                         Defaults to current working directory.
        """
        super().__init__(project_root)
        self._collections: Optional[Dict[str, Collection]] = None

    def get_collections(self) -> Dict[str, Collection]:
        """Get all collections from render-engine Site.

        Returns:
            Dictionary mapping collection slugs to Collection instances
        """
        if self._collections is None:
            self._collections = super().get_collections()
        return self._collections

    def get_collection(self, name: str) -> Optional[Collection]:
        """Get a collection by name.

        Args:
            name: The collection slug

        Returns:
            Collection instance or None if not found
        """
        return self.get_collections().get(name)

    def get_all_collections(self) -> Dict[str, Collection]:
        """Get all available collections.

        Returns:
            Dictionary mapping slugs to Collection objects
        """
        return self.get_collections()

    def get_available_collection_names(self) -> List[str]:
        """Get list of available collection names."""
        return list(self.get_collections().keys())

    def validate_collection(self, name: str) -> bool:
        """Check if a collection exists."""
        return name in self.get_collections()

    def get_collection_display_name(self, slug: str) -> str:
        """Get the display name for a collection.

        Args:
            slug: The collection slug

        Returns:
            Display name (uses _title if available, otherwise title case of slug)
        """
        collection = self.get_collection(slug)
        if collection:
            return getattr(collection, "_title", slug.title())
        return slug.title()

    def get_content_manager_for_collection(self, slug: str) -> Optional[Any]:
        """Get the ContentManager class for a collection.

        Args:
            slug: The collection slug

        Returns:
            The ContentManager class if available, None otherwise
        """
        try:
            collection = self.get_collection(slug)
            if collection and hasattr(collection, "ContentManager"):
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
            collection = self.get_collection(slug)
            if collection:
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
        """Get available collections with their display names."""
        return {name: self.loader.get_collection_display_name(name)
                for name in self.loader.get_available_collection_names()}

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

    def get_current_collection(self) -> Optional[Collection]:
        """Get the current Collection object.

        Returns:
            The Collection instance for the current collection
        """
        return self.loader.get_collection(self.current_collection)

    def _get_current_config(self):
        """Get the current Collection object.

        Kept for backward compatibility, use get_current_collection() instead.
        """
        return self.get_current_collection()

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

    def _collection_has_field(self, collection: Collection, field_name: str) -> bool:
        """Check if a collection has a specific field.

        Args:
            collection: The Collection object
            field_name: The field name to check

        Returns:
            True if the field is available, False otherwise
        """
        # Try to detect from Parser type
        if hasattr(collection, "Parser"):
            parser = collection.Parser
            parser_name = parser.__name__

            # Markdown/YAML parsers have title, description, content
            if "Markdown" in parser_name or "YAML" in parser_name:
                if field_name in {"title", "description", "content", "slug", "date"}:
                    return True
            # Text parsers have content
            elif "Text" in parser_name:
                if field_name in {"content", "slug", "date"}:
                    return True

        # Default fields are always available
        if field_name in {"slug", "date", "id"}:
            return True

        # Assume common metadata fields are available
        if field_name in {"external_link", "image_url", "tags"}:
            return True

        return False

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
            collection = self.get_current_collection()

            if date is None:
                date = datetime.now().isoformat()

            # Build YAML frontmatter dictionary
            frontmatter_data = {
                "slug": slug,
                "date": date,
            }

            if self._collection_has_field(collection, "title") and title:
                frontmatter_data["title"] = title
            if self._collection_has_field(collection, "description") and description:
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

            # Get table name from ContentManager if available
            table_name = getattr(manager, "table_name", None) or self.current_collection

            manager.create_entry(
                content=markdown_with_frontmatter,
                table=table_name,
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

