"""Main TUI application."""

from typing import Optional, Any, Dict
from textual.app import ComposeResult, App
from textual.containers import Vertical
from textual.widgets import (
    Header,
    Footer,
    DataTable,
    MarkdownViewer,
)
from textual.binding import Binding

from .db import ContentManagerWrapper
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
    Screen {
        layout: vertical;
    }

    #main-container {
        width: 100%;
        height: 1fr;
        layout: vertical;
    }

    #preview-content {
        width: 100%;
        height: 40%;
        border: solid $accent;
    }

    #posts-table {
        width: 100%;
        height: 60%;
        border: solid $accent;
    }
    """

    def __init__(self):
        """Initialize the app."""
        super().__init__()
        self.content_manager = ContentManagerWrapper()
        self.current_post = None
        self.posts = []
        self.current_collection = "blog"  # Default collection

        # Pagination state
        self.page_size = 50  # Number of posts per page
        self.current_page = 0  # 0-indexed page number
        self.current_search = None  # Store search term for pagination

    def compose(self) -> ComposeResult:
        """Compose the app."""
        yield Header()
        with Vertical(id="main-container"):
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
            offset = page * self.page_size
            self.posts = self.content_manager.get_posts(search=search, limit=self.page_size, offset=offset)
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
                    updated_post = self.content_manager.get_post(post_id)
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

                        # Update row data (title with fallback to slug)
                        title_display = self.posts[i]["title"] or self.posts[i].get("slug", "(untitled)")
                        table.update_cell(str(post_id), "Title", title_display)
                        table.update_cell(str(post_id), "Date", date_str)

                        # Update the preview if it's the currently selected post
                        if self.current_post and self.current_post["id"] == post_id:
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
            self.posts,
            key=lambda p: p["date"] if p["date"] else None,
            reverse=True
        )

        # Add rows with title (fallback to slug if no title)
        for post in sorted_posts:
            date_str = post["date"].strftime("%Y-%m-%d") if post["date"] else "N/A"

            # Show title, or fallback to slug if no title available
            title_display = post.get("title") or post.get("slug", "(untitled)")

            table.add_row(
                str(post["id"]),
                title_display,
                date_str,
                key=str(post["id"]),
            )

        # Update preview to show the first post
        self.update_preview()


    def update_preview(self):
        """Update the preview panel with the currently selected post."""
        table = self.query_one("#posts-table", DataTable)
        preview = self.query_one("#preview-content", MarkdownViewer)

        if (
            self.posts
            and table.cursor_row is not None
            and table.cursor_row < len(self.posts)
        ):
            post = self.posts[table.cursor_row]
            self.current_post = post

            try:
                # Get full post content
                full_post = self.content_manager.get_post(post["id"])
                if not full_post:
                    preview.document.update("Post not found")
                    return

                # Build preview with all post variables
                preview_lines = []

                # Title
                title = full_post.get("title", "")
                if title:
                    preview_lines.append(f"# {title}")
                    preview_lines.append("")

                # Post metadata
                preview_lines.append("## Metadata")
                if full_post.get("id"):
                    preview_lines.append(f"**ID:** {full_post.get('id')}")
                if full_post.get("slug"):
                    preview_lines.append(f"**Slug:** {full_post.get('slug')}")
                if full_post.get("date"):
                    preview_lines.append(f"**Date:** {full_post.get('date')}")
                if full_post.get("description"):
                    preview_lines.append(f"**Description:** {full_post.get('description')}")
                if full_post.get("external_link"):
                    preview_lines.append(f"**External Link:** {full_post.get('external_link')}")
                if full_post.get("image_url"):
                    preview_lines.append(f"**Image URL:** {full_post.get('image_url')}")

                preview_lines.append("")

                # Content
                content = full_post.get("content", "")
                if content:
                    preview_lines.append("## Content")
                    preview_lines.append(content)
                else:
                    preview_lines.append("*(No content available)*")

                preview_content = "\n".join(preview_lines)
                preview.document.update(preview_content)
            except Exception as e:
                self.notify(f"Error loading post content: {e}", severity="error")
        else:
            preview.document.update("Select a post to preview")

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

        self.push_screen(CreatePostScreen(self.content_manager, on_created))

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
                self.content_manager.set_collection(collection)
                self._update_subtitle()
                self.current_page = 0  # Reset pagination
                self.current_search = None
                self.load_posts()
                self.notify(
                    f"Switched to {self.content_manager.AVAILABLE_COLLECTIONS[collection]}",
                    severity="information"
                )

        self.push_screen(CollectionSelectScreen(on_collection_selected, self.content_manager.collections_manager))

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
