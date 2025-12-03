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


class CreatePostScreen(Screen):
    """Screen for creating a new blog post with blank canvas and metadata popup."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=True),
        Binding("ctrl+d", "save_draft", "Draft", show=True),
        Binding("ctrl+m", "show_metadata", "Metadata", show=True),
        Binding("escape", "quit_screen", "Cancel", show=True),
    ]

    CSS = """
    #content-input {
        height: 100%;
    }
    """

    def __init__(self, app, on_created):
        """Initialize the create post screen."""
        super().__init__()
        self.app_instance = app
        self.on_created = on_created
        self.metadata = {
            "title": "",
            "slug": "",
            "description": "",
            "external_link": "",
            "image_url": "",
        }

    def compose(self) -> ComposeResult:
        """Compose the screen with blank canvas and metadata popup."""
        yield Vertical(
            TextArea(id="content-input", language="markdown"),
        )

    def on_mount(self):
        """Mount the screen."""
        self.title = "Create New Post"
        # Focus on content input
        self.query_one("#content-input", TextArea).focus()

    def action_show_metadata(self):
        """Show metadata entry modal."""
        self.push_screen(CreatePostMetadataModal(self.metadata, self._update_metadata))

    def _update_metadata(self, metadata):
        """Update metadata from the modal."""
        self.metadata = metadata

    def action_save(self):
        """Save the new post."""
        try:
            if not self.metadata["slug"]:
                self.app.notify("Slug is required", severity="warning")
                return

            content = self.query_one("#content-input", TextArea).text

            self.app_instance.create_post(
                slug=self.metadata["slug"],
                title=self.metadata["title"],
                content=content,
                description=self.metadata["description"],
                external_link=self.metadata.get("external_link") or None,
                image_url=self.metadata.get("image_url") or None,
            )

            self.on_created(None)
            self.app.pop_screen()
            self.app.notify("Post created successfully", severity="information")
        except Exception as e:
            self.app.notify(f"Error creating post: {e}", severity="error")

    def action_save_draft(self):
        """Save post as draft to /tmp/render-engine-tui/drafts/"""
        try:
            from pathlib import Path
            import json
            from datetime import datetime

            # Create drafts directory
            drafts_dir = Path("/tmp/render-engine-tui/drafts")
            drafts_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename from slug or timestamp
            filename = self.metadata["slug"] or datetime.now().isoformat().replace(":", "-")
            draft_file = drafts_dir / f"{filename}.json"

            # Prepare draft data
            draft_data = {
                "metadata": self.metadata,
                "content": self.query_one("#content-input", TextArea).text,
                "saved_at": datetime.now().isoformat(),
            }

            # Write draft file
            with open(draft_file, "w") as f:
                json.dump(draft_data, f, indent=2)

            self.app.notify(f"Draft saved to {draft_file}", severity="information")
        except Exception as e:
            self.app.notify(f"Error saving draft: {e}", severity="error")

    def action_quit_screen(self):
        """Quit the screen without saving."""
        self.app.pop_screen()


class CreatePostMetadataModal(ModalScreen):
    """Modal screen for entering post metadata."""

    BINDINGS = [
        Binding("ctrl+s", "submit", "Submit", show=True),
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    CSS = """
    CreatePostMetadataModal {
        align: center middle;
    }

    CreatePostMetadataModal > ScrollableContainer {
        width: 60;
        height: auto;
        border: solid $accent;
        background: $panel;
    }

    #metadata-form {
        padding: 1 2;
    }

    .form-group {
        margin-bottom: 1;
    }

    .form-label {
        text-style: bold;
        margin-bottom: 0;
    }

    .form-input {
        margin-bottom: 1;
    }

    .button-group {
        margin-top: 2;
        text-align: center;
    }
    """

    def __init__(self, metadata, on_submit):
        """Initialize the metadata modal.

        Args:
            metadata: Dictionary of metadata fields
            on_submit: Callback function when metadata is submitted
        """
        super().__init__()
        self.metadata = metadata.copy()
        self.on_submit = on_submit

    def compose(self) -> ComposeResult:
        """Compose the metadata modal."""
        yield ScrollableContainer(
            Vertical(
                Static("Post Metadata", classes="form-label"),
                Vertical(
                    Static("Title:", classes="form-label"),
                    Input(
                        id="title-input",
                        placeholder="Post title",
                        value=self.metadata.get("title", ""),
                        classes="form-input",
                    ),
                    Static("Slug (required):", classes="form-label"),
                    Input(
                        id="slug-input",
                        placeholder="url-slug",
                        value=self.metadata.get("slug", ""),
                        classes="form-input",
                    ),
                    Static("Description:", classes="form-label"),
                    Input(
                        id="description-input",
                        placeholder="Short description",
                        value=self.metadata.get("description", ""),
                        classes="form-input",
                    ),
                    Static("External Link (optional):", classes="form-label"),
                    Input(
                        id="external-link-input",
                        placeholder="https://example.com",
                        value=self.metadata.get("external_link", ""),
                        classes="form-input",
                    ),
                    Static("Image URL (optional):", classes="form-label"),
                    Input(
                        id="image-url-input",
                        placeholder="https://example.com/image.jpg",
                        value=self.metadata.get("image_url", ""),
                        classes="form-input",
                    ),
                    Horizontal(
                        Button("Submit", id="submit-btn", variant="primary"),
                        Button("Cancel", id="cancel-btn"),
                        classes="button-group",
                    ),
                    id="metadata-form",
                    classes="form-group",
                ),
            )
        )

    def on_mount(self):
        """Mount the modal."""
        self.title = "Post Metadata"
        self.query_one("#title-input", Input).focus()

    def action_submit(self):
        """Submit the metadata."""
        self.metadata["title"] = self.query_one("#title-input", Input).value
        self.metadata["slug"] = self.query_one("#slug-input", Input).value
        self.metadata["description"] = self.query_one("#description-input", Input).value
        self.metadata["external_link"] = self.query_one(
            "#external-link-input", Input
        ).value
        self.metadata["image_url"] = self.query_one("#image-url-input", Input).value

        if not self.metadata["slug"]:
            self.app.notify("Slug is required", severity="warning")
            return

        self.on_submit(self.metadata)
        self.app.pop_screen()

    def action_cancel(self):
        """Cancel without saving."""
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "submit-btn":
            self.action_submit()
        elif event.button.id == "cancel-btn":
            self.action_cancel()


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
        priority_attrs = ["slug", "title", "date", "description"]
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
