"""Main TUI application."""

from typing import Optional, List
from textual.app import ComposeResult, App
from textual.containers import Horizontal
from textual.widgets import (
    Header,
    Footer,
    DataTable,
    TextArea,
)
from textual.binding import Binding

from render_engine import Page

from .site_loader import SiteLoader
from .ui import (
    AboutScreen,
    CreatePostScreen,
    CollectionSelectScreen,
    MetadataModal,
)


class ContentEditorApp(App):
    """Main application."""

    # Configuration constants
    DEFAULT_COLLECTION = "blog"
    POSTS_TABLE_WIDTH = "30%"
    PREVIEW_PANEL_WIDTH = "70%"

    BINDINGS = [
        Binding("n", "new_post", "New", show=True),
        Binding("c", "change_collection", "Collection", show=True),
        Binding("m", "show_metadata", "Metadata", show=True),
        Binding("?", "about", "About", show=True),
        Binding("q", "app.quit", "Quit", show=True),
    ]

    CSS = f"""
    Screen {{
        layout: vertical;
    }}

    #main-container {{
        width: 100%;
        height: 1fr;
        layout: horizontal;
    }}

    #posts-table {{
        width: {POSTS_TABLE_WIDTH};
        height: 100%;
        border: solid $accent;
    }}

    #preview-content {{
        width: {PREVIEW_PANEL_WIDTH};
        height: 100%;
        border: solid $accent;
    }}
    """

    def __init__(self):
        """Initialize the app."""
        super().__init__()
        self.loader = SiteLoader()
        self.current_post: Optional[Page] = None
        self.posts: List[Page] = []
        self.current_collection = self.DEFAULT_COLLECTION

    def compose(self) -> ComposeResult:
        """Compose the app."""
        yield Header()
        with Horizontal(id="main-container"):
            yield DataTable(id="posts-table")
            yield TextArea(
                text="Select a post to preview",
                id="preview-content",
                read_only=True,
            )
        yield Footer()

    def on_mount(self) -> None:
        """App mounted."""
        try:
            self.title = "Content Editor"
            self._update_subtitle()
            self.load_posts()
            table = self.query_one("#posts-table", DataTable)
            table.focus()
        except Exception as e:
            self.title = "Content Editor"
            error_message = f"Error: {e}"
            self.sub_title = error_message
            self.notify(error_message, severity="error")

    def _update_subtitle(self) -> None:
        """Update the subtitle to show current collection."""
        collection = self.loader.get_collection(self.current_collection)
        collection_display = (
            getattr(collection, "_title", self.current_collection.title())
            if collection
            else self.current_collection
        )
        self.sub_title = f"Browsing {collection_display}"

    def load_posts(self):
        """Load all posts from render-engine."""
        try:
            # Iterate directly through the render-engine collection
            collection = self.loader.get_collection(self.current_collection)
            if not collection:
                raise RuntimeError(f"Collection '{self.current_collection}' not found")

            self.posts = list(collection.sorted_pages)
            self.populate_table()
        except Exception as e:
            self.notify(f"Error loading posts: {e}", severity="error")

    def _get_post(self, post_id: int) -> Optional[Page]:
        """Get a single post by ID from current collection.

        Args:
            post_id: The post ID

        Returns:
            Page object or None if not found
        """
        collection = self.loader.get_collection(self.current_collection)
        if not collection:
            return None

        for page in collection.sorted_pages:
            if getattr(page, "id", None) == post_id:
                return page
        return None

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

            collection = self.loader.get_collection(self.current_collection)
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
            if not hasattr(manager, "create_entry") or not callable(
                getattr(manager, "create_entry")
            ):
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
            collection = self.loader.get_collection(self.current_collection)
            if not collection:
                raise RuntimeError(f"Collection '{self.current_collection}' not found")

            # Search for post by slug in collection
            for page in collection.sorted_pages:
                if getattr(page, "slug", None) == slug:
                    return getattr(page, "id", None)
            raise RuntimeError(f"Post with slug '{slug}' not found after creation")
        except Exception as e:
            raise RuntimeError(f"Failed to get post ID after creation: {e}")

    def refresh_current_post(self, post_id: int) -> None:
        """Refresh a single post in the table efficiently.

        Updates the post from local cache. Only fetches from backend if necessary.
        Keeps scroll position and selection.

        Args:
            post_id: The ID of the post to refresh
        """
        try:
            table = self.query_one("#posts-table", DataTable)

            # Find the post in our current list
            for i, post in enumerate(self.posts):
                if getattr(post, "id", None) == post_id:
                    # Use the post from our local cache - it's already fresh
                    # Only fetch from backend if this specific post doesn't have content
                    updated_post = post
                    if getattr(post, "content", None) is None:
                        updated_post = self._get_post(post_id)

                    if updated_post:
                        # Update post in list if fetched
                        if updated_post != post:
                            self.posts[i] = updated_post

                        # Format and update the table row
                        date_obj = getattr(updated_post, "date", None)
                        date_str = date_obj.strftime("%Y-%m-%d") if date_obj else "N/A"

                        title = getattr(updated_post, "title", None) or getattr(
                            updated_post, "slug", "(untitled)"
                        )
                        table.update_cell(str(post_id), "Title", title)
                        table.update_cell(str(post_id), "Date", date_str)

                        # Update the preview if it's the currently selected post
                        if (
                            self.current_post
                            and getattr(self.current_post, "id", None) == post_id
                        ):
                            self.current_post = updated_post
                            self.update_preview()
                    break
        except Exception as e:
            self.notify(f"Error refreshing post: {e}", severity="error")

    def populate_table(self):
        """Populate the data table with posts.

        Shows title (with slug fallback) for all collections.
        Content preview is shown in the preview panel when selected.
        Posts are sorted by date (newest first).
        """
        table = self.query_one("#posts-table", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"

        # Add columns: ID, Title, Date
        table.add_columns(
            "ID",
            "Title",
            "Date",
        )

        # Sort posts by date (newest first), handling None dates
        sorted_posts = sorted(
            self.posts, key=lambda p: getattr(p, "date", None) or None, reverse=True
        )

        # Add rows with title (fallback to slug if no title)
        for post in sorted_posts:
            post_id = getattr(post, "id", None)
            post_date = getattr(post, "date", None)
            post_title = getattr(post, "title", None)
            post_slug = getattr(post, "slug", "(untitled)")

            date_str = post_date.strftime("%Y-%m-%d") if post_date else "N/A"

            # Show title, or fallback to slug if no title available
            title_display = post_title or post_slug

            table.add_row(
                str(post_id),
                title_display,
                date_str,
                key=str(post_id),
            )

        # Update preview to show the first post
        self.update_preview()

    def update_preview(self):
        """Update the preview panel with the currently selected post."""
        table = self.query_one("#posts-table", DataTable)
        preview = self.query_one("#preview-content", TextArea)

        if (
            self.posts
            and table.cursor_row is not None
            and table.cursor_row < len(self.posts)
        ):
            post = self.posts[table.cursor_row]
            # Update current_post for metadata display
            self.current_post = post
            # Use the raw content from the Page object
            preview.text = getattr(post, "content", "No content available")
        else:
            # No post selected - show placeholder
            preview.text = "Select a post to preview"

    @property
    def cursor_row(self):
        """Get current cursor row."""
        table = self.query_one("#posts-table", DataTable)
        return table.cursor_row

    def on_data_table_row_highlighted(self, event):
        """Update preview when row is highlighted."""
        self.update_preview()

    def action_new_post(self):
        """Create a new blog post."""

        def on_created(post_id):
            self.load_posts()
            self.notify("Post created successfully", severity="information")

        self.push_screen(CreatePostScreen(self, on_created))

    def action_change_collection(self):
        """Open collection selector modal."""

        def on_collection_selected(collection: str):
            """Handle collection selection."""
            if collection != self.current_collection:
                self.current_collection = collection
                self._update_subtitle()
                self.load_posts()
                coll = self.loader.get_collection(collection)
                collection_display = (
                    getattr(coll, "_title", collection.title()) if coll else collection
                )
                self.notify(
                    f"Switched to {collection_display}",
                    severity="information",
                )

        self.push_screen(CollectionSelectScreen(on_collection_selected, self.loader))

    def action_about(self):
        """Open the about screen."""
        self.push_screen(AboutScreen())

    def action_show_metadata(self):
        """Show metadata in a modal popup."""
        if not self.current_post:
            self.notify("No post selected", severity="warning")
            return

        try:
            post_id = getattr(self.current_post, "id", None)
            full_post = self._get_post(post_id)
            if full_post:
                self.push_screen(MetadataModal(full_post))
            else:
                self.notify("Could not load post metadata", severity="error")
        except Exception as e:
            self.notify(f"Error loading metadata: {e}", severity="error")


def run():
    """Run the content editor TUI."""
    app = ContentEditorApp()
    app.run()


def main():
    """Entry point."""
    run()


if __name__ == "__main__":
    main()
