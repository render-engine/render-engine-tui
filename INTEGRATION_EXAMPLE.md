# Integration Example: Dynamic Collections in Content Editor TUI

This document shows concrete examples of how to integrate dynamic collection loading into the existing Content Editor TUI.

## Current State vs. New Approach

### Current Approach (Hardcoded)

```python
# content_editor/db.py
class DatabaseManager:
    AVAILABLE_COLLECTIONS = {
        "blog": "Blog Posts",
        "notes": "Notes",
        "microblog": "Microblog Posts",
    }

    JUNCTION_TABLES = {
        "blog": "blog_tags",
        "notes": "notes_tags",
        "microblog": "microblog_tags",
    }

    ID_COLUMN_NAMES = {
        "blog": "blog_id",
        "notes": "notes_id",
        "microblog": "microblog_id",
    }
```

**Problems:**
- Hardcoded collection names
- Duplicates information from routes.py
- Requires manual updates when collections change

### New Approach (Dynamic)

```python
# content_editor/db.py
from content_editor.config import RenderEngineConfig

class DatabaseManager:
    def __init__(self, connection_string: Optional[str] = None, collection: str = "blog"):
        # Load collections from render-engine site
        config = RenderEngineConfig()
        metadata = config.get_collection_metadata()

        # Generate AVAILABLE_COLLECTIONS dynamically
        self.AVAILABLE_COLLECTIONS = {
            slug: meta['title']
            for slug, meta in metadata.items()
        }

        # Generate JUNCTION_TABLES dynamically
        self.JUNCTION_TABLES = {
            slug: f"{slug}_tags"
            for slug in metadata.keys()
        }

        # Generate ID_COLUMN_NAMES dynamically
        self.ID_COLUMN_NAMES = {
            slug: f"{slug}_id"
            for slug in metadata.keys()
        }

        # Rest of initialization...
```

**Benefits:**
- Automatically discovers collections from routes.py
- Single source of truth
- No manual updates needed

## Updated db.py (Full Example)

```python
"""Database connection and operations with dynamic collection loading."""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any

import psycopg
from psycopg import sql

from .config import RenderEngineConfig


class DatabaseManager:
    """Manages PostgreSQL connections and operations with dynamic collection discovery."""

    def __init__(
        self,
        connection_string: Optional[str] = None,
        collection: str = "blog",
        project_root: Optional[str] = None
    ):
        """Initialize database manager with dynamic collection loading.

        Args:
            connection_string: PostgreSQL connection string (defaults to CONNECTION_STRING env var)
            collection: Collection to manage (will be validated against discovered collections)
            project_root: Path to render-engine project root (defaults to current directory)

        Raises:
            ValueError: If CONNECTION_STRING not set or collection is invalid
            FileNotFoundError: If pyproject.toml not found
            KeyError: If [tool.render-engine] configuration is missing
        """
        # Load collections from render-engine configuration
        config = RenderEngineConfig(project_root)
        self.config = config
        self.collections_metadata = config.get_collection_metadata()

        # Generate mappings dynamically
        self.AVAILABLE_COLLECTIONS = {
            slug: meta['title']
            for slug, meta in self.collections_metadata.items()
        }

        self.JUNCTION_TABLES = {
            slug: f"{slug}_tags"
            for slug in self.collections_metadata.keys()
        }

        self.ID_COLUMN_NAMES = {
            slug: f"{slug}_id"
            for slug in self.collections_metadata.keys()
        }

        # Validate connection string
        conn_str = connection_string or os.environ.get("CONNECTION_STRING")
        if not conn_str:
            raise ValueError("CONNECTION_STRING environment variable not set")

        # Validate collection
        if collection not in self.AVAILABLE_COLLECTIONS:
            raise ValueError(
                f"Invalid collection '{collection}'. Available: {list(self.AVAILABLE_COLLECTIONS.keys())}"
            )

        self.connection_string = conn_str
        self.current_collection = collection
        self.conn = None
        self.connect()

    def set_collection(self, collection: str) -> None:
        """Switch to a different collection at runtime.

        Args:
            collection: Collection name (must exist in discovered collections)

        Raises:
            ValueError: If collection name is invalid
        """
        if collection not in self.AVAILABLE_COLLECTIONS:
            raise ValueError(
                f"Invalid collection '{collection}'. Available: {list(self.AVAILABLE_COLLECTIONS.keys())}"
            )
        self.current_collection = collection

    def get_collection_metadata(self, collection: Optional[str] = None) -> Dict[str, Any]:
        """Get metadata for a collection.

        Args:
            collection: Collection name (defaults to current collection)

        Returns:
            Dictionary with collection metadata (title, parser, routes, etc.)
        """
        collection = collection or self.current_collection
        return self.collections_metadata.get(collection, {})

    # Rest of the DatabaseManager methods remain the same...
    # (connect, disconnect, get_posts, get_post, etc.)
```

## Updated main.py (TUI Application)

### Current CollectionSelectScreen

The current implementation might have:

```python
# content_editor/ui.py
class CollectionSelectScreen(ModalScreen):
    def compose(self):
        # Hardcoded options
        options = [
            ("Blog Posts", "blog"),
            ("Notes", "notes"),
            ("Microblog", "microblog"),
        ]
        # ...
```

### Updated CollectionSelectScreen

```python
# content_editor/ui.py
class CollectionSelectScreen(ModalScreen):
    def __init__(self, on_select, available_collections):
        """Initialize collection selector.

        Args:
            on_select: Callback when collection is selected
            available_collections: Dict mapping slugs to display names
        """
        self.available_collections = available_collections
        self.on_select = on_select
        super().__init__()

    def compose(self):
        # Generate options dynamically
        options = [
            (display_name, slug)
            for slug, display_name in self.available_collections.items()
        ]
        # ... rest of UI code
```

### Updated ContentEditorApp

```python
# content_editor/main.py
from content_editor.config import RenderEngineConfig

class ContentEditorApp(App):
    def __init__(self, project_root: Optional[str] = None):
        """Initialize the app.

        Args:
            project_root: Path to render-engine project (defaults to current directory)
        """
        super().__init__()

        # Load configuration from render-engine site
        try:
            self.config = RenderEngineConfig(project_root)
            self.available_collections = self.config.get_collection_metadata()
        except Exception as e:
            print(f"Error loading render-engine configuration: {e}")
            print("Make sure you're running from a render-engine project directory.")
            raise

        # Initialize with first available collection
        if not self.available_collections:
            raise ValueError("No collections found in render-engine site")

        first_collection = next(iter(self.available_collections.keys()))
        self.db = DatabaseManager(collection=first_collection, project_root=project_root)

        self.current_collection = first_collection
        self.current_post = None
        self.posts = []
        self.tags = []
        # ...

    def _update_subtitle(self) -> None:
        """Update the subtitle to show current collection."""
        collection_meta = self.available_collections.get(self.current_collection, {})
        collection_display = collection_meta.get('title', self.current_collection)
        self.sub_title = f"Editing {collection_display}"

    def action_change_collection(self):
        """Open collection selector modal with dynamic collections."""
        from .ui import CollectionSelectScreen

        def on_collection_selected(collection: str):
            """Handle collection selection."""
            if collection != self.current_collection:
                self.current_collection = collection
                self.db.set_collection(collection)
                self._update_subtitle()
                self.selected_tag_id = None
                self.current_page = 0
                self.current_search = None
                self.load_posts()
                self.load_tags_sidebar()

                collection_meta = self.available_collections.get(collection, {})
                self.notify(
                    f"Switched to {collection_meta.get('title', collection)}",
                    severity="information"
                )

        # Pass available collections to the modal
        available_colls = {
            slug: meta['title']
            for slug, meta in self.available_collections.items()
        }
        self.push_screen(CollectionSelectScreen(on_collection_selected, available_colls))
```

## CLI Entry Point Update

### Current Entry Point

```python
# content_editor/main.py
def run():
    """Run the content editor TUI."""
    app = ContentEditorApp()
    app.run()
```

### Updated Entry Point with Project Detection

```python
# content_editor/main.py
import sys
from pathlib import Path

def run():
    """Run the content editor TUI.

    Automatically detects render-engine project by looking for pyproject.toml
    in current directory or parent directories.
    """
    # Try to find pyproject.toml in current directory or parents
    current = Path.cwd()
    project_root = None

    for parent in [current] + list(current.parents):
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            project_root = parent
            break

    if not project_root:
        print("Error: No pyproject.toml found.")
        print("Run this command from a render-engine project directory.")
        sys.exit(1)

    try:
        app = ContentEditorApp(project_root=str(project_root))
        app.run()
    except Exception as e:
        print(f"Error initializing Content Editor: {e}")
        sys.exit(1)
```

## Example: Running the TUI

### Directory Structure

```
kjaymiller.com/
├── pyproject.toml         # Contains [tool.render-engine.cli]
├── routes.py              # Contains Site and Collections
├── content/
├── templates/
└── ...
```

### Running from Project Root

```bash
cd /Users/jay.miller/kjaymiller.com
content-editor
```

The TUI will:
1. Find `pyproject.toml` in current directory
2. Read `[tool.render-engine.cli]` to get `module = "routes"` and `site = "app"`
3. Import `routes.py` and access `app` (the Site instance)
4. Query `app.route_list` to discover collections
5. Filter for PostgreSQL-backed collections
6. Display them in the collection selector

### Collections Discovered

Based on `/Users/jay.miller/kjaymiller.com/routes.py`, the TUI would discover:

- **blog**: "Blog Posts" (PostgreSQL)
- **notes**: "Notes to Self" (PostgreSQL)
- **microblog**: "MicroBlog" (PostgreSQL)

It would NOT show:
- **pages**: Uses FileContentManager (not PostgreSQL)
- Individual Page instances (not Collections)

## Fallback for Missing Configuration

For robustness, add a fallback mode:

```python
class DatabaseManager:
    # Fallback collections if render-engine config not found
    DEFAULT_COLLECTIONS = {
        "blog": "Blog Posts",
        "notes": "Notes",
        "microblog": "Microblog Posts",
    }

    def __init__(self, connection_string=None, collection="blog", project_root=None):
        try:
            # Try dynamic loading
            config = RenderEngineConfig(project_root)
            self.collections_metadata = config.get_collection_metadata()
            self.AVAILABLE_COLLECTIONS = {
                slug: meta['title']
                for slug, meta in self.collections_metadata.items()
            }
        except (FileNotFoundError, KeyError) as e:
            # Fallback to defaults
            print(f"Warning: Could not load render-engine config: {e}")
            print("Using default collections.")
            self.collections_metadata = {}
            self.AVAILABLE_COLLECTIONS = self.DEFAULT_COLLECTIONS

        # Continue with initialization...
```

## Testing the Integration

### Unit Test Example

```python
# tests/test_config.py
import pytest
from pathlib import Path
from content_editor.config import RenderEngineConfig

def test_load_kjaymiller_site():
    """Test loading the kjaymiller.com site configuration."""
    project_root = Path("/Users/jay.miller/kjaymiller.com")

    config = RenderEngineConfig(project_root)
    site = config.load_site()

    # Verify site loaded
    assert site is not None

    # Verify collections discovered
    collections = config.get_collections()
    assert "blog" in collections
    assert "notes" in collections
    assert "microblog" in collections

    # Verify metadata
    metadata = config.get_collection_metadata()
    assert metadata["blog"]["title"] == "Blog Posts"
    assert metadata["blog"]["parser"] == "PGMarkdownCollectionParser"
    assert metadata["blog"]["content_manager"] == "PostgresContentManager"

def test_postgres_collections_only():
    """Test filtering for PostgreSQL collections."""
    project_root = Path("/Users/jay.miller/kjaymiller.com")

    config = RenderEngineConfig(project_root)
    pg_collections = config.get_postgres_collections()

    # Should include PostgreSQL collections
    assert "blog" in pg_collections
    assert "notes" in pg_collections
    assert "microblog" in pg_collections

    # Should exclude file-based collections
    assert "pages" not in pg_collections
```

### Manual Testing

```python
# test_dynamic_loading.py
from content_editor.config import RenderEngineConfig
from pathlib import Path

# Test with kjaymiller.com
project_root = Path("/Users/jay.miller/kjaymiller.com")
config = RenderEngineConfig(project_root)

print("Site reference:", config.get_site_reference())
# Output: ('routes', 'app')

site = config.load_site()
print(f"Site loaded: {site}")

collections = config.get_collections()
print(f"\nDiscovered {len(collections)} collections:")
for slug, collection in collections.items():
    print(f"  - {slug}: {collection._title}")

metadata = config.get_collection_metadata()
print("\nCollection Metadata:")
for slug, meta in metadata.items():
    print(f"\n{slug}:")
    print(f"  Title: {meta['title']}")
    print(f"  Parser: {meta['parser']}")
    print(f"  Content Manager: {meta['content_manager']}")
    print(f"  Routes: {meta['routes']}")
    print(f"  Has Archive: {meta['has_archive']}")

pg_collections = config.get_postgres_collections()
print(f"\nPostgreSQL Collections ({len(pg_collections)}):")
for slug in pg_collections.keys():
    print(f"  - {slug}")
```

## Next Steps

1. **Update db.py**: Integrate `RenderEngineConfig` for dynamic collection discovery
2. **Update main.py**: Pass dynamic collections to UI components
3. **Update ui.py**: Make collection selector use dynamic list
4. **Add Error Handling**: Graceful fallbacks if configuration is missing
5. **Update pyproject.toml**: Ensure `[tool.render-engine.cli]` is configured
6. **Test**: Run with kjaymiller.com to verify everything works
7. **Document**: Update README with usage instructions

## Files Modified

- `/Users/jay.miller/render-engine-tui/content_editor/config.py` (NEW)
- `/Users/jay.miller/render-engine-tui/content_editor/db.py` (MODIFIED)
- `/Users/jay.miller/render-engine-tui/content_editor/main.py` (MODIFIED)
- `/Users/jay.miller/render-engine-tui/content_editor/ui.py` (MODIFIED)
- `/Users/jay.miller/render-engine-tui/pyproject.toml` (ADD [tool.render-engine.cli])
