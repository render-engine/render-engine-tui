"""Render-engine ContentManager wrapper for TUI operations.

This module provides a unified interface for working with render-engine collections:
- READ operations: Use ContentManager's standard `pages` property
- CREATE operations: Use ContentManager's create_entry() method
- All data access is backend-agnostic (PostgreSQL, FileSystem, custom, etc.)
"""

from pathlib import Path
from typing import Optional, List, Dict, Any

from .collections_config import CollectionsManager


class ContentManagerWrapper:
    """Wrapper for render-engine ContentManager operations.

    All operations go through render-engine's ContentManager,
    which handles backend storage (PostgreSQL, FileSystem, custom, etc.) transparently.
    """

    def __init__(
        self,
        collection: str = "blog",
        project_root: Optional[Path] = None,
    ):
        """Initialize the ContentManager wrapper.

        Collections MUST be defined in [tool.render-engine] in the project's pyproject.toml.

        Args:
            collection: Collection to manage (default: "blog")
            project_root: Path to render-engine project root (defaults to current directory)

        Raises:
            ValueError: If collection is invalid
            RuntimeError: If render-engine config not found or ContentManager setup fails
        """
        # Load collections from render-engine
        self.collections_manager = CollectionsManager(
            project_root=project_root,
        )

        if not self.collections_manager.validate_collection(collection):
            available = self.collections_manager.get_available_collection_names()
            raise ValueError(f"Invalid collection '{collection}'. Available: {available}")

        self.current_collection = collection
        self.content_manager = None
        self._setup_content_manager()

    @property
    def AVAILABLE_COLLECTIONS(self) -> Dict[str, str]:
        """Get available collections from config."""
        return {name: config.display_name
                for name, config in self.collections_manager.get_all_collections().items()}

    def _get_current_config(self):
        """Get the config for the current collection."""
        return self.collections_manager.get_collection(self.current_collection)

    def is_using_render_engine(self) -> bool:
        """Check if collections are loaded from render-engine.

        Returns:
            True if render-engine integration is active
        """
        return self.collections_manager.has_render_engine_integration()

    def has_content_manager(self) -> bool:
        """Check if the current collection has a ContentManager.

        Returns:
            True if a ContentManager is available
        """
        return self.content_manager is not None

    def _setup_content_manager(self) -> None:
        """Set up ContentManager for the current collection.

        Raises:
            RuntimeError: If ContentManager cannot be set up
        """
        cm_class = self.collections_manager.get_content_manager_class(
            self.current_collection
        )
        if cm_class:
            try:
                from .render_engine_integration import ContentManagerAdapter

                config = self._get_current_config()
                # Get extras from render-engine configuration
                loader = self.collections_manager.get_render_engine_loader()
                extras = loader.get_content_manager_extras(self.current_collection) if loader else {}
                self.content_manager = ContentManagerAdapter(cm_class, config, extras)
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
        if not self.collections_manager.validate_collection(collection):
            available = self.collections_manager.get_available_collection_names()
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
        if not self.content_manager:
            raise RuntimeError(f"No ContentManager available for collection '{self.current_collection}'")

        try:
            if search:
                items = self.content_manager.search(search, limit=limit, offset=offset)
            else:
                items = self.content_manager.get_all(limit=limit, offset=offset)

            if items:
                # Normalize ContentManager output to TUI format
                return self._normalize_posts(items)
            return []
        except Exception as e:
            raise RuntimeError(f"Failed to fetch posts: {e}")

    def _normalize_posts(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize ContentManager output to TUI format.

        Args:
            items: List of items from ContentManager

        Returns:
            List of posts with normalized fields (id, slug, title, description, date)
        """
        config = self._get_current_config()
        normalized = []

        for item in items:
            post = {
                "id": item.get("id"),
                "slug": item.get("slug", ""),
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "date": item.get("date"),
            }

            # If title not available, use content preview
            if not post["title"] and "content" in item:
                post["title"] = ""  # Keep title empty for content-only collections
                post["description"] = str(item.get("content", ""))[:100]

            normalized.append(post)

        return normalized

    def get_post(self, post_id: int) -> Optional[Dict[str, Any]]:
        """Get a single post with all details from current collection.

        Args:
            post_id: The post ID

        Returns:
            Post dictionary with all fields, or None if not found

        Raises:
            RuntimeError: If ContentManager operation fails
        """
        if not self.content_manager:
            raise RuntimeError(f"No ContentManager available for collection '{self.current_collection}'")

        try:
            post = self.content_manager.get(post_id)
            if post:
                # Normalize output
                post = self._normalize_single_post(post)
                return post
            return None
        except Exception as e:
            raise RuntimeError(f"Failed to fetch post {post_id}: {e}")

    def _normalize_single_post(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single ContentManager item to TUI format.

        Args:
            item: Item from ContentManager

        Returns:
            Post dictionary with normalized fields
        """
        config = self._get_current_config()
        post = {
            "id": item.get("id"),
            "slug": item.get("slug", ""),
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "content": item.get("content", ""),
            "external_link": item.get("external_link"),
            "image_url": item.get("image_url"),
            "date": item.get("date"),
        }
        return post

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
        if not self.content_manager:
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
            result = self.content_manager.create_entry(
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


# Alias for backward compatibility
DatabaseManager = ContentManagerWrapper
