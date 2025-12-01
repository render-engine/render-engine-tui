"""Integration with render-engine to provide a unified content management interface.

This module provides ContentManager which wraps render-engine's Collection
and ContentManager to offer post operations and search functionality.
"""

from pathlib import Path
from typing import Dict, Optional, List
import logging

from .site_loader import SiteLoader
from render_engine import Collection, Page

logger = logging.getLogger(__name__)


class ContentManager:
    """Unified content management interface for TUI.

    Works directly with render-engine's Collection and its built-in
    ContentManager for post operations and search.
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
            RuntimeError: If render-engine config not found
        """
        self.loader = SiteLoader(project_root=project_root)
        self.current_collection = collection
        self._posts_cache: Dict[str, List[Page]] = {}  # Cache posts by collection

        # Validate collection exists
        if not self.get_current_collection():
            available = list(self.loader.get_collections().keys())
            raise ValueError(f"Invalid collection '{collection}'. Available: {available}")

    @property
    def AVAILABLE_COLLECTIONS(self) -> Dict[str, str]:
        """Get available collections with their display names."""
        return {
            name: getattr(collection, "_title", name.title())
            for name, collection in self.loader.get_collections().items()
        }

    def set_collection(self, collection: str) -> None:
        """Switch to a different collection at runtime.

        Args:
            collection: Collection name

        Raises:
            ValueError: If collection name is invalid
        """
        if not self.loader.get_collection(collection):
            available = list(self.loader.get_collections().keys())
            raise ValueError(f"Invalid collection '{collection}'. Available: {available}")
        self.current_collection = collection
        self._posts_cache.clear()  # Clear cache when switching collections

    def get_current_collection(self) -> Optional[Collection]:
        """Get the current Collection object.

        Returns:
            The Collection instance for the current collection
        """
        return self.loader.get_collection(self.current_collection)

    # ====== Post Operations ======

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

            # Fetch from render-engine Collection
            collection = self.get_current_collection()
            if not collection:
                raise RuntimeError(f"Collection '{self.current_collection}' not found")

            # Use Collection's sorted_pages (already sorted by render-engine)
            posts = list(collection.sorted_pages)

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

            collection = self.get_current_collection()
            if not collection:
                raise RuntimeError(f"Collection '{self.current_collection}' not found")

            manager = collection.content_manager

            if date is None:
                date = datetime.now().isoformat()

            # Build YAML frontmatter dictionary
            frontmatter_data = {
                "slug": slug,
                "date": date,
            }

            if title:
                frontmatter_data["title"] = title
            if description:
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

