"""ContentManager-based operations for content access and manipulation.

This module provides a unified interface for working with render-engine
ContentManager instances. All content operations go through ContentManager.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from .collections_config import CollectionsManager


class ContentManagerWrapper:
    """Wrapper for managing ContentManager-based content operations.

    All content is accessed and modified exclusively through render-engine
    ContentManager instances. No direct database access is performed.
    """

    def __init__(
        self,
        collection: str = "blog",
        config_path: Optional[str] = None,
        use_render_engine: bool = True,
        project_root: Optional[Path] = None,
    ):
        """Initialize the ContentManager wrapper.

        Args:
            collection: Collection to manage (default: "blog")
            config_path: Path to collections.yaml config file
            use_render_engine: If True, load collections from render-engine if available (default: True)
            project_root: Path to render-engine project root (defaults to current directory)

        Raises:
            ValueError: If collection is invalid
            RuntimeError: If ContentManager setup fails
        """
        # Load collections from render-engine, YAML, or defaults
        self.collections_manager = CollectionsManager(
            config_path=config_path,
            use_render_engine=use_render_engine,
            project_root=project_root,
        )

        if not self.collections_manager.validate_collection(collection):
            available = self.collections_manager.get_available_collection_names()
            raise ValueError(f"Invalid collection '{collection}'. Available: {available}")

        self.current_collection = collection
        self.content_manager = None  # Will be set if using render-engine ContentManager
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
                self.content_manager = ContentManagerAdapter(cm_class, config)
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
        date: Optional[datetime] = None,
    ) -> int:
        """Create a new post in current collection.

        Args:
            slug: Post slug (URL identifier)
            title: Post title
            content: Post content
            description: Post description
            external_link: External URL (optional)
            image_url: Image URL (optional)
            date: Publication date (defaults to now)

        Returns:
            The ID of the created post

        Raises:
            RuntimeError: If creation fails
        """
        if not self.content_manager:
            raise RuntimeError(f"No ContentManager available for collection '{self.current_collection}'")

        if date is None:
            date = datetime.now()

        try:
            config = self._get_current_config()
            # Build data dict based on collection schema
            data = {
                "slug": slug,
                "content": content,
                "external_link": external_link,
                "image_url": image_url,
                "date": date,
            }

            # Only include title/description if collection supports them
            if config.has_field("title"):
                data["title"] = title
            if config.has_field("description"):
                data["description"] = description

            post_id = self.content_manager.create(**data)
            if post_id:
                return post_id
            raise RuntimeError("ContentManager.create() returned no ID")
        except Exception as e:
            raise RuntimeError(f"Failed to create post: {e}")


    def update_post(
        self,
        post_id: int,
        slug: Optional[str] = None,
        title: Optional[str] = None,
        content: Optional[str] = None,
        description: Optional[str] = None,
        external_link: Optional[str] = None,
        image_url: Optional[str] = None,
        date: Optional[datetime] = None,
    ) -> bool:
        """Update an existing post in current collection.

        Args:
            post_id: The post ID
            slug: Post slug (optional)
            title: Post title (optional, ignored if collection doesn't support it)
            content: Post content (optional)
            description: Post description (optional, ignored if collection doesn't support it)
            external_link: External URL (optional)
            image_url: Image URL (optional)
            date: Publication date (optional)

        Returns:
            True if update successful

        Raises:
            RuntimeError: If update fails
        """
        if not self.content_manager:
            raise RuntimeError(f"No ContentManager available for collection '{self.current_collection}'")

        try:
            config = self._get_current_config()
            # Build update data based on collection schema
            data = {}

            if slug is not None:
                data["slug"] = slug
            if content is not None:
                data["content"] = content
            if external_link is not None:
                data["external_link"] = external_link
            if image_url is not None:
                data["image_url"] = image_url
            if date is not None:
                data["date"] = date

            # Only include title/description if collection supports them
            if config.has_field("title") and title is not None:
                data["title"] = title
            if config.has_field("description") and description is not None:
                data["description"] = description

            if data:
                self.content_manager.update(post_id, **data)

            return True
        except Exception as e:
            raise RuntimeError(f"Failed to update post: {e}")


    def delete_post(self, post_id: int) -> bool:
        """Delete a post from current collection.

        Args:
            post_id: The post ID

        Returns:
            True if delete successful

        Raises:
            RuntimeError: If delete fails
        """
        if not self.content_manager:
            raise RuntimeError(f"No ContentManager available for collection '{self.current_collection}'")

        try:
            return self.content_manager.delete(post_id)
        except Exception as e:
            raise RuntimeError(f"Failed to delete post: {e}")


# Alias for backward compatibility
DatabaseManager = ContentManagerWrapper
