"""UI screens for modals and secondary screens."""

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import (
    Static,
    Input,
    TextArea,
    Button,
    Label,
    ListView,
    ListItem,
    DataTable,
    Markdown,
)
from textual.binding import Binding
from textual.screen import Screen, ModalScreen

from .site_loader import SiteLoader


class SearchModal(ModalScreen):
    """Modal screen for searching posts."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    CSS = """
    SearchModal {
        align: center middle;
    }

    SearchModal > Vertical {
        width: 60;
        height: 7;
        border: solid $accent;
        background: $panel;
    }
    """

    def __init__(self, on_search):
        """Initialize the search modal."""
        super().__init__()
        self.on_search = on_search

    def compose(self) -> ComposeResult:
        """Compose the search modal."""
        yield Vertical(
            Static("Search Posts"),
            Input(
                id="search-modal-input",
                placeholder="Enter search term (press Enter to search)",
            ),
        )

    def on_mount(self):
        """Mount the modal."""
        self.title = "Search"
        input_widget = self.query_one("#search-modal-input", Input)
        input_widget.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle search submission."""
        if event.input.id == "search-modal-input":
            search_term = event.input.value.strip()
            self.on_search(search_term if search_term else None)
            self.app.pop_screen()

    def action_cancel(self):
        """Cancel the search."""
        self.app.pop_screen()


class CreatePostScreen(Screen):
    """Screen for creating a new blog post."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=True),
        Binding("escape", "quit_screen", "Cancel", show=True),
    ]

    def __init__(self, app, on_created):
        """Initialize the create post screen."""
        super().__init__()
        self.app_instance = app
        self.on_created = on_created

    def compose(self) -> ComposeResult:
        """Compose the screen."""
        yield Horizontal(
            ScrollableContainer(
                Vertical(
                    Static("Title:"),
                    Input(id="title-input", placeholder="Post title"),
                    Static("Slug:"),
                    Input(id="slug-input", placeholder="url-slug"),
                    Static("Description:"),
                    Input(id="description-input", placeholder="Short description"),
                    Static("External Link (optional):"),
                    Input(id="external-link-input", placeholder="https://example.com"),
                    Static("Image URL (optional):"),
                    Input(
                        id="image-url-input",
                        placeholder="https://example.com/image.jpg",
                    ),
                    Horizontal(
                        Button("Save", id="save-btn", variant="primary"),
                        Button("Cancel", id="cancel-btn"),
                    ),
                    id="form-sidebar",
                ),
                id="sidebar-container",
            ),
            Vertical(
                Static("Content:"),
                TextArea(id="content-input", language="markdown"),
                id="content-container",
            ),
        )

    def on_mount(self):
        """Mount the screen."""
        self.title = "Create New Post"

    def action_save(self):
        """Save the new post."""
        try:
            title = self.query_one("#title-input", Input).value
            slug = self.query_one("#slug-input", Input).value
            description = self.query_one("#description-input", Input).value
            content = self.query_one("#content-input", TextArea).text
            external_link = self.query_one("#external-link-input", Input).value or None
            image_url = self.query_one("#image-url-input", Input).value or None

            post_id = self.app_instance.create_post(
                slug=slug,
                title=title,
                content=content,
                description=description,
                external_link=external_link,
                image_url=image_url,
            )

            self.on_created(post_id)
            self.app.pop_screen()
        except Exception as e:
            self.app.notify(f"Error creating post: {e}", severity="error")

    def action_quit_screen(self):
        """Quit the screen without saving."""
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save-btn":
            self.action_save()
        elif event.button.id == "cancel-btn":
            self.action_quit_screen()


class CollectionSelectScreen(ModalScreen):
    """Modal screen for selecting a collection."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    CSS = """
    CollectionSelectScreen {
        align: center middle;
    }

    CollectionSelectScreen > Vertical {
        width: 50;
        height: 15;
        border: solid $accent;
        background: $panel;
    }

    #collection-list {
        height: 8;
    }
    """

    def __init__(self, on_collection_selected, loader=None):
        """Initialize the collection selection modal.

        Args:
            on_collection_selected: Callback function that receives the selected collection name
            loader: SiteLoader instance (optional, creates new one if not provided)
        """
        super().__init__()
        self.on_collection_selected = on_collection_selected
        self.loader = loader
        if self.loader is None:
            # Create a new instance if not provided
            self.loader = SiteLoader()

    def compose(self) -> ComposeResult:
        """Compose the collection selection modal."""
        yield Vertical(
            Static("Select Collection", classes="title"),
            ListView(id="collection-list"),
        )

    def on_mount(self):
        """Mount the modal and populate collections."""
        self.title = "Change Collection"
        list_view = self.query_one("#collection-list", ListView)

        # Add available collections from loader
        collections = self.loader.get_collections()
        for collection_name, collection in collections.items():
            display_name = getattr(collection, "_title", collection_name.title())
            label = Label(display_name, id=f"collection-{collection_name}")
            list_item = ListItem(label, id=collection_name)
            list_view.append(list_item)

        # Focus the list
        list_view.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle collection selection."""
        selected_item = event.item
        if selected_item and selected_item.id:
            self.on_collection_selected(selected_item.id)
            self.app.pop_screen()

    def action_cancel(self):
        """Cancel the selection."""
        self.app.pop_screen()


class AboutScreen(ModalScreen):
    """Modal screen displaying application information."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
    ]

    CSS = """
    AboutScreen {
        align: center middle;
    }

    AboutScreen > Vertical {
        width: 70;
        height: auto;
        border: solid $accent;
        background: $panel;
    }

    #about-content {
        width: 100%;
        height: auto;
    }

    .about-button {
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the about screen."""
        from .version import get_version, get_release_url

        version = get_version()
        release_url = get_release_url()

        yield Vertical(
            Static("Content Editor TUI", classes="title"),
            Static(f"Version: {version}"),
            Static(f"GitHub: https://github.com/kjaymiller/render-engine-tui"),
            Static(f"Release: {release_url}"),
            Static(
                "A terminal user interface for editing content via render-engine ContentManager.",
                classes="about-description",
            ),
            id="about-content",
        )

    def on_mount(self):
        """Mount the modal."""
        self.title = "About"

    def action_close(self):
        """Close the about screen."""
        self.app.pop_screen()


class MetadataModal(ModalScreen):
    """Modal screen displaying post metadata."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
    ]

    CSS = """
    MetadataModal {
        align: center middle;
    }

    MetadataModal > ScrollableContainer {
        width: 80;
        height: auto;
        max-height: 20;
        border: solid $accent;
        background: $panel;
    }

    #metadata-content {
        width: 100%;
        height: auto;
        padding: 1 2;
    }

    .metadata-title {
        width: 100%;
        text-style: bold;
        margin-bottom: 1;
    }

    .metadata-field {
        width: 100%;
        margin-bottom: 1;
    }

    .metadata-label {
        text-style: bold;
        color: $accent;
    }
    """

    def __init__(self, post):
        """Initialize the metadata modal.

        Args:
            post: Page object containing post data
        """
        super().__init__()
        self.post = post

    def compose(self) -> ComposeResult:
        """Compose the metadata modal."""
        yield ScrollableContainer(
            Vertical(
                Static("Post Metadata", classes="metadata-title"),
                id="metadata-content",
            )
        )

    def on_mount(self):
        """Mount the modal and populate metadata from post attributes."""
        self.title = "Post Metadata"
        content = self.query_one("#metadata-content", Vertical)

        # Display all non-callable attributes from the post as metadata
        # Common attributes to prioritize
        priority_attrs = ["id", "slug", "title", "date", "description"]
        shown_attrs = set()

        # First, show priority attributes
        for attr_name in priority_attrs:
            if self._display_field(content, attr_name, shown_attrs):
                pass

        # Then, show any other attributes (except private/special ones)
        for attr_name in dir(self.post):
            if (
                not attr_name.startswith("_")  # Skip private attributes
                and attr_name not in shown_attrs  # Skip already shown
                and not callable(getattr(self.post, attr_name, None))  # Skip methods
            ):
                self._display_field(content, attr_name, shown_attrs)

    def _display_field(self, container: Vertical, attr_name: str, shown_attrs: set) -> bool:
        """Display a field in the metadata modal if it has a value.

        Args:
            container: The Vertical container to append to
            attr_name: The attribute name
            shown_attrs: Set of already-shown attributes (modified in place)

        Returns:
            True if field was displayed, False otherwise
        """
        value = getattr(self.post, attr_name, None)
        if value is not None and value != "":
            # Format date if it exists
            if attr_name == "date" and hasattr(value, "strftime"):
                value = value.strftime("%Y-%m-%d %H:%M:%S")

            # Convert attribute name to title case for display
            display_label = attr_name.replace("_", " ").title()
            field_text = f"{display_label}: {value}"
            container.append(Static(field_text, classes="metadata-field"))
            shown_attrs.add(attr_name)
            return True
        return False

    def action_close(self):
        """Close the metadata modal."""
        self.app.pop_screen()
