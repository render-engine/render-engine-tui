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

from .render_engine_integration import ContentManager
from .ui import (
    AboutScreen,
    CreatePostScreen,
    SearchModal,
    CollectionSelectScreen,
    MetadataModal,
)


class ContentEditorApp(App):
    """Main application."""

    # Configuration constants
    DEFAULT_COLLECTION = "blog"
    PAGE_SIZE = 50
    POSTS_TABLE_WIDTH = "30%"
    PREVIEW_PANEL_WIDTH = "70%"

    BINDINGS = [
        Binding("n", "new_post", "New", show=True),
        Binding("/", "search", "Search", show=True),
        Binding("c", "change_collection", "Collection", show=True),
        Binding("m", "show_metadata", "Metadata", show=True),
        Binding("r", "reset", "Reset", show=True),
        Binding("pagedown", "next_page", "Next", show=True),
        Binding("pageup", "prev_page", "Prev", show=True),
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
        self.content_manager = ContentManager()
        self.current_post: Optional[Page] = None
        self.posts: List[Page] = []
        self.current_collection = self.DEFAULT_COLLECTION

        # Pagination state
        self.page_size = self.PAGE_SIZE
        self.current_page = 0  # 0-indexed page number
        self.current_search = None  # Store search term for pagination

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
        collection_display = self.content_manager.AVAILABLE_COLLECTIONS.get(
            self.current_collection, self.current_collection
        )
        self.sub_title = f"Browsing {collection_display}"

    def load_posts(self, search: Optional[str] = None, page: int = 0):
        """Load posts from render-engine with pagination support.

        Args:
            search: Optional search term to filter posts
            page: Page number (0-indexed) to load
        """
        try:
            self.current_page = page
            self.current_search = search

            # Get all posts, apply search filtering, then paginate
            all_posts = self.content_manager.get_all_posts()
            filtered_posts = (
                self.content_manager.search_posts(all_posts, search)
                if search
                else all_posts
            )

            # Apply pagination
            offset = page * self.page_size
            self.posts = filtered_posts[offset : offset + self.page_size]
            self.populate_table()
        except Exception as e:
            self.notify(f"Error loading posts: {e}", severity="error")

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
                        updated_post = self.content_manager.get_post(post_id)

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
            self.current_post = post

        preview.text = self.current_post.content

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

        def on_created(post_id):
            self.load_posts()
            self.notify("Post created successfully", severity="information")

        self.push_screen(CreatePostScreen(self.content_manager, on_created))

    def action_search(self):
        """Open search modal."""

        def on_search(search_term):
            self.load_posts(search=search_term)
            if search_term:
                self.notify(f"Searching for: {search_term}", severity="information")
            else:
                self.notify("Search cleared", severity="information")

        self.push_screen(SearchModal(on_search))

    def action_change_collection(self):
        """Open collection selector modal."""

        def on_collection_selected(collection: str):
            """Handle collection selection."""
            if collection != self.current_collection:
                self.current_collection = collection
                self.content_manager.set_collection(collection)
                self._update_subtitle()
                self.current_page = 0  # Reset pagination
                self.current_search = None
                self.load_posts()
                self.notify(
                    f"Switched to {self.content_manager.AVAILABLE_COLLECTIONS[collection]}",
                    severity="information",
                )

        self.push_screen(
            CollectionSelectScreen(on_collection_selected, self.content_manager.loader)
        )

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

    def action_show_metadata(self):
        """Show metadata in a modal popup."""
        if not self.current_post:
            self.notify("No post selected", severity="warning")
            return

        try:
            post_id = getattr(self.current_post, "id", None)
            full_post = self.content_manager.get_post(post_id)
            if full_post:
                self.push_screen(MetadataModal(full_post, self.content_manager))
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
