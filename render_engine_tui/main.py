"""Main TUI application."""

from typing import Optional, Any, Dict
from textual.app import ComposeResult, App
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import (
    Header,
    Footer,
    Static,
    DataTable,
    MarkdownViewer,
)
from textual.binding import Binding
from textual import work

from .db import DatabaseManager
from .ui import AboutScreen


class ContentEditorApp(App):
    """Main application."""

    BINDINGS = [
        Binding("n", "new_post", "New", show=True),
        Binding("/", "search", "Search", show=True),
        Binding("c", "change_collection", "Collection", show=True),
        Binding("r", "reset", "Reset", show=True),
        Binding("pagedown", "next_page", "Next", show=True),
        Binding("pageup", "prev_page", "Prev", show=True),
        Binding("?", "about", "About", show=True),
        Binding("q", "app.quit", "Quit", show=True),
    ]

    CSS = """
    #preview-content {
        height: 80%;
        overflow: auto;
    }

    #posts-table {
        width: 100%;
    }
    """

    def __init__(self):
        """Initialize the app."""
        super().__init__()
        self.db = DatabaseManager()
        self.current_post = None
        self.posts = []
        self.current_collection = "blog"  # Default collection
        self.current_post_full = None  # Cache full post data to avoid duplicate fetches
        self.preview_loading = False  # Track if preview fetch is in progress

        # Pagination state
        self.page_size = 50  # Number of posts per page
        self.current_page = 0  # 0-indexed page number
        self.current_search = None  # Store search term for pagination

    def compose(self) -> ComposeResult:
        """Compose the app."""
        yield Header()
        yield MarkdownViewer(
            "Select a post to preview",
            id="preview-content",
            show_table_of_contents=False,
        )
        yield DataTable(id="posts-table")
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
        collection_display = self.db.AVAILABLE_COLLECTIONS.get(
            self.current_collection, self.current_collection
        )
        self.sub_title = f"Editing {collection_display}"

    def load_posts(self, search: Optional[str] = None, page: int = 0):
        """Load posts from database with pagination support.

        Args:
            search: Optional search term to filter posts
            page: Page number (0-indexed) to load
        """
        try:
            self.current_page = page
            self.current_search = search
            offset = page * self.page_size
            self.posts = self.db.get_posts(search=search, limit=self.page_size, offset=offset)
            self.populate_table()
        except Exception as e:
            self.notify(f"Error loading posts: {e}", severity="error")

    def refresh_current_post(self, post_id: int) -> None:
        """Refresh a single post in the table without reloading all posts.

        Much more efficient than load_posts() when only one post changed.
        Keeps scroll position and selection.

        Args:
            post_id: The ID of the post to refresh
        """
        try:
            # Find the post in our current list
            for i, post in enumerate(self.posts):
                if post["id"] == post_id:
                    # Fetch updated post data
                    updated_post = self.db.get_post(post_id)
                    if updated_post:
                        # Update the post dict in our list
                        self.posts[i] = {
                            "id": updated_post["id"],
                            "slug": updated_post["slug"],
                            "title": updated_post.get("title", ""),
                            "description": updated_post.get("description", ""),
                            "date": updated_post["date"],
                        }
                        # Re-render just this row in the table
                        table = self.query_one("#posts-table", DataTable)
                        date_str = self.posts[i]["date"].strftime("%Y-%m-%d") if self.posts[i]["date"] else "N/A"

                        # Update row data
                        if self.current_collection == "microblog":
                            table.update_cell(str(post_id), "Content", self.posts[i]["description"][:50])
                        else:
                            table.update_cell(str(post_id), "Title", self.posts[i]["title"])
                        table.update_cell(str(post_id), "Date", date_str)

                        # Update the preview if it's the currently selected post
                        if self.current_post and self.current_post["id"] == post_id:
                            self.current_post_full = updated_post
                            self._update_preview_content(updated_post)
                    break
        except Exception as e:
            self.notify(f"Error refreshing post: {e}", severity="error")

    def _get_display_field_for_collection(self) -> str:
        """Get the main field to display in table for current collection.

        Returns the field name that should be shown in the table
        (e.g., 'title' for blog, 'content' for microblog).
        """
        config = self.db._get_current_config()
        if config.has_field("title"):
            return "title"
        elif config.has_field("content"):
            return "content"
        else:
            return "slug"

    def populate_table(self):
        """Populate the data table with posts.

        Collection-specific column handling based on collection config.
        """
        table = self.query_one("#posts-table", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"

        # Determine which field to display based on collection config
        display_field = self._get_display_field_for_collection()
        column_name = display_field.title()

        # Add columns
        table.add_columns(
            "ID",
            column_name,
            "Date",
        )

        # Add rows
        for post in self.posts:
            date_str = post["date"].strftime("%Y-%m-%d") if post["date"] else "N/A"

            # Get the value for the display field
            if display_field == "content":
                # Show content preview
                content_preview = post.get("description", "(empty)")[:50] if post.get("description") else "(empty)"
                display_value = content_preview
            elif display_field == "title":
                display_value = post.get("title", "")
            else:
                display_value = post.get(display_field, "")

            table.add_row(
                str(post["id"]),
                display_value,
                date_str,
                key=str(post["id"]),
            )

        # Update preview to show the first post
        self.update_preview()


    def update_preview(self):
        """Update the preview panel with the currently selected post.

        Triggers an async fetch of full post content to avoid blocking the UI.
        Shows summary while loading, then updates with full content when ready.
        """
        table = self.query_one("#posts-table", DataTable)
        preview = self.query_one("#preview-content", MarkdownViewer)

        if (
            self.posts
            and table.cursor_row is not None
            and table.cursor_row < len(self.posts)
        ):
            post = self.posts[table.cursor_row]
            self.current_post = post

            # Show a quick preview while we fetch the full content asynchronously
            preview.document.update(f"# {post['title']}\n\n*Loading full content...*")

            # Fetch full post content asynchronously
            self.fetch_full_post(post["id"])
        else:
            preview.document.update("Select a post to preview")

    @work(exclusive=True, thread=True)
    def fetch_full_post(self, post_id: int) -> Optional[Dict[str, Any]]:
        """Fetch full post content asynchronously.

        This runs in a background worker so it doesn't block the UI.
        Uses exclusive=True to ensure only one fetch runs at a time.

        Args:
            post_id: The ID of the post to fetch

        Returns:
            Full post dict or None if not found
        """
        try:
            full_post = self.db.get_post(post_id)
            if full_post:
                self.current_post_full = full_post
                # Schedule UI update back on the main event loop thread
                self.call_from_thread(self._update_preview_content, full_post)
            return full_post
        except Exception as e:
            # Schedule error notification back on the main event loop thread
            self.call_from_thread(
                lambda: self.notify(f"Error loading full post content: {e}", severity="error")
            )
            return None

    def _update_preview_content(self, full_post: Dict[str, Any]) -> None:
        """Update the preview panel with full post content.

        Called when async post fetch completes.

        Args:
            full_post: The full post dict with all content
        """
        preview = self.query_one("#preview-content", MarkdownViewer)
        title = full_post.get("title", self.current_post.get("title", ""))
        content = full_post.get("content", "No content available")
        preview.document.update(f"# {title}\n\n{content}")

    @property
    def cursor_row(self):
        """Get current cursor row."""
        table = self.query_one("#posts-table", DataTable)
        return table.cursor_row

    def on_data_table_row_highlighted(self, event):
        """Update preview when row is highlighted."""
        self.update_preview()


    def action_reset(self):
        """Reset the view to default state: show all posts, go to top."""
        # Reset pagination and load all posts
        self.current_page = 0
        self.current_search = None
        self.load_posts(search=None, page=0)

        # Move cursor to the top of the table
        table = self.query_one("#posts-table", DataTable)
        table.focus()

        # Move cursor to the first row (row 0, column 0)
        if table.row_count > 0:
            table.move_cursor(row=0)

        # Notify user
        self.notify("View reset to default", severity="information")

    def action_new_post(self):
        """Create a new blog post."""
        from .ui import CreatePostScreen

        def on_created(post_id):
            self.load_posts()
            self.notify("Post created successfully", severity="information")

        self.push_screen(CreatePostScreen(self.db, on_created))

    def action_search(self):
        """Open search modal."""
        from .ui import SearchModal

        def on_search(search_term):
            self.load_posts(search=search_term)
            if search_term:
                self.notify(f"Searching for: {search_term}", severity="information")
            else:
                self.notify("Search cleared", severity="information")

        self.push_screen(SearchModal(on_search))

    def action_change_collection(self):
        """Open collection selector modal."""
        from .ui import CollectionSelectScreen

        def on_collection_selected(collection: str):
            """Handle collection selection."""
            if collection != self.current_collection:
                self.current_collection = collection
                self.db.set_collection(collection)
                self._update_subtitle()
                self.current_page = 0  # Reset pagination
                self.current_search = None
                self.load_posts()
                self.notify(
                    f"Switched to {self.db.AVAILABLE_COLLECTIONS[collection]}",
                    severity="information"
                )

        self.push_screen(CollectionSelectScreen(on_collection_selected, self.db.collections_manager))

    def action_next_page(self):
        """Load the next page of posts."""
        if len(self.posts) < self.page_size:
            # Less posts than page size means we're on the last page
            self.notify("Already on last page", severity="information")
            return

        self.load_posts(search=self.current_search, page=self.current_page + 1)
        self.notify(f"Page {self.current_page + 1}", severity="information")

    def action_prev_page(self):
        """Load the previous page of posts."""
        if self.current_page == 0:
            self.notify("Already on first page", severity="information")
            return

        self.load_posts(search=self.current_search, page=self.current_page - 1)
        self.notify(f"Page {self.current_page + 1}", severity="information")

    def action_about(self):
        """Open the about screen."""
        self.push_screen(AboutScreen())


def run():
    """Run the content editor TUI."""
    app = ContentEditorApp()
    app.run()


def main():
    """Entry point."""
    run()


if __name__ == "__main__":
    main()
