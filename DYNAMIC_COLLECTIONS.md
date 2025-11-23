# Dynamic Collection Loading for Content Editor TUI

This document explains how the Content Editor TUI dynamically loads collections from `[tool.render-engine]` configuration in `pyproject.toml`, following the same pattern as `render-engine-cli`.

## Overview

Instead of hardcoding collection names or creating custom `[tool.content-editor.collections]` configuration, the TUI reuses the existing `[tool.render-engine]` configuration that already defines your site structure.

## How render-engine Sites Work

### Site Structure

A render-engine `Site` object has a `route_list` dictionary that contains all registered pages and collections:

```python
from render_engine import Site, Collection

app = Site()

@app.collection
class Blog(Collection):
    title = "Blog Posts"
    # ... collection configuration

# The @app.collection decorator adds Blog to app.route_list
# app.route_list = {"blog": <Blog instance>}
```

### Collection Attributes

Each `Collection` instance has rich metadata you can query:

- `_title`: Human-readable title (e.g., "Blog Posts")
- `_slug`: URL-safe slug (e.g., "blog")
- `Parser`: The parser class used (e.g., `PGMarkdownCollectionParser`)
- `ContentManager`: The content manager class (e.g., `PostgresContentManager`)
- `content_manager`: Instantiated content manager with database connection
- `routes`: List of URL routes (e.g., `["blog"]`)
- `has_archive`: Whether the collection has archive pages
- `items_per_page`: Number of items per archive page

## Configuration Pattern

### pyproject.toml Structure

Your `pyproject.toml` should have a `[tool.render-engine.cli]` section:

```toml
[tool.render-engine.cli]
module = "routes"  # The Python module containing your site
site = "app"       # The Site instance variable name
```

This tells the system:
1. Import the `routes` module
2. Access the `app` variable from that module
3. `app` is a `render_engine.Site` instance

### Example: kjaymiller.com Configuration

From `/Users/jay.miller/kjaymiller.com/pyproject.toml`:

```toml
[tool.render-engine.cli]
module = "routes"
site = "app"
```

From `/Users/jay.miller/kjaymiller.com/routes.py`:

```python
from render_engine import Site, Collection
from render_engine_pg import PostgresContentManager, PGMarkdownCollectionParser

app = Site()  # This is the "app" referenced in pyproject.toml

@app.collection
class Blog(Collection):
    routes = ["blog"]
    title = "Blog Posts"
    Parser = PGMarkdownCollectionParser
    ContentManager = PostgresContentManager
    content_manager_extras = {"connection": conn}
    # ...

@app.collection
class Notes(Collection):
    routes = ["notes"]
    title = "Notes to Self"
    Parser = PGMarkdownCollectionParser
    ContentManager = PostgresContentManager
    # ...

@app.collection
class MicroBlog(Collection):
    routes = ["microblog"]
    # ...
```

## Implementation Guide

### 1. Reading Configuration

Use Python's built-in `tomllib` to read `pyproject.toml`:

```python
import tomllib
from pathlib import Path

def load_config(project_root: Path) -> dict:
    pyproject_path = project_root / "pyproject.toml"

    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    # Extract [tool.render-engine] section
    return pyproject["tool"]["render-engine"]
```

### 2. Dynamic Module Import

Use `importlib` to dynamically import the module specified in configuration:

```python
import importlib
import sys

def load_site(project_root: Path, module_name: str, site_name: str):
    # Add project root to Python path
    sys.path.insert(0, str(project_root))

    # Import the module
    module = importlib.import_module(module_name)

    # Get the site object
    site = getattr(module, site_name)

    return site
```

### 3. Querying Collections

Once you have the Site object, access its collections:

```python
from render_engine import Collection

def get_collections(site) -> dict:
    """Get all collections from the site."""
    return {
        slug: entry
        for slug, entry in site.route_list.items()
        if isinstance(entry, Collection)
    }

def get_collection_names(site) -> dict:
    """Get collection slugs mapped to display names."""
    collections = get_collections(site)
    return {
        slug: collection._title
        for slug, collection in collections.items()
    }
```

### 4. Filtering PostgreSQL Collections

For the TUI, you specifically want PostgreSQL-backed collections:

```python
from render_engine_pg import PostgresContentManager

def get_postgres_collections(site) -> dict:
    """Get only PostgreSQL-backed collections."""
    collections = get_collections(site)
    return {
        slug: collection
        for slug, collection in collections.items()
        if hasattr(collection, 'ContentManager')
        and collection.ContentManager == PostgresContentManager
    }
```

## Using the RenderEngineConfig Class

The provided `content_editor/config.py` module implements all of this:

### Basic Usage

```python
from content_editor.config import RenderEngineConfig

# Initialize with project root (defaults to current directory)
config = RenderEngineConfig()

# Load the site
site = config.load_site()

# Get all collections
collections = config.get_collections()

# Get collection metadata
metadata = config.get_collection_metadata()
for slug, meta in metadata.items():
    print(f"{slug}: {meta['title']}")
    # Output:
    # blog: Blog Posts
    # notes: Notes to Self
    # microblog: MicroBlog

# Get only PostgreSQL collections
pg_collections = config.get_postgres_collections()
```

### Integration with DatabaseManager

Replace the hardcoded `AVAILABLE_COLLECTIONS` in `db.py`:

```python
# OLD APPROACH (hardcoded):
class DatabaseManager:
    AVAILABLE_COLLECTIONS = {
        "blog": "Blog Posts",
        "notes": "Notes",
        "microblog": "Microblog Posts",
    }

# NEW APPROACH (dynamic):
from content_editor.config import RenderEngineConfig

class DatabaseManager:
    def __init__(self, connection_string: Optional[str] = None, collection: str = "blog"):
        # Load collections dynamically from render-engine site
        config = RenderEngineConfig()
        collections = config.get_collection_metadata()

        self.AVAILABLE_COLLECTIONS = {
            slug: meta['title']
            for slug, meta in collections.items()
        }

        # Rest of initialization...
```

### Integration with TUI Main App

Update `main.py` to load collections dynamically:

```python
from content_editor.config import RenderEngineConfig

class ContentEditorApp(App):
    def __init__(self):
        super().__init__()

        # Load collections from render-engine site
        self.config = RenderEngineConfig()
        self.available_collections = self.config.get_collection_metadata()

        # Initialize with first available collection
        first_collection = next(iter(self.available_collections.keys()))
        self.db = DatabaseManager(collection=first_collection)
```

## Advanced: Accessing Collection Data

### Getting Database Tables

Each PostgreSQL collection in render-engine typically has a `_metadata_attrs()` method that specifies the database table:

```python
def get_collection_table(collection) -> str:
    """Extract the database table name from a collection."""
    if hasattr(collection, '_metadata_attrs'):
        metadata = collection._metadata_attrs()
        return metadata.get('table', collection._slug)
    return collection._slug
```

### Getting Content Manager Connection

Collections store their database connection in `content_manager_extras`:

```python
def get_collection_connection(collection):
    """Get the database connection from a collection."""
    if hasattr(collection, 'content_manager_extras'):
        return collection.content_manager_extras.get('connection')
    return None
```

### Example: Discovering All Tables

```python
from content_editor.config import RenderEngineConfig

config = RenderEngineConfig()
collections = config.get_postgres_collections()

for slug, collection in collections.items():
    # Get table name
    if hasattr(collection, '_metadata_attrs'):
        table = collection._metadata_attrs().get('table', slug)
    else:
        table = slug

    print(f"Collection '{slug}' uses table '{table}'")
```

## render-engine Utilities to Import

Key imports from the render-engine ecosystem:

```python
# Core classes
from render_engine import Site, Collection, Page

# PostgreSQL support
from render_engine_pg import (
    PostgresContentManager,
    PGMarkdownCollectionParser,
    get_db_connection,
)

# Type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from render_engine import Collection
```

## Error Handling

### Missing Configuration

```python
try:
    config = RenderEngineConfig()
    site = config.load_site()
except FileNotFoundError as e:
    print("No pyproject.toml found. Make sure you're in a render-engine project.")
except KeyError as e:
    print("Missing [tool.render-engine] configuration in pyproject.toml")
except ImportError as e:
    print(f"Could not import site module: {e}")
```

### Validating Collections

```python
def validate_collection_for_tui(collection) -> bool:
    """Check if a collection is compatible with the TUI."""
    # Must use PostgreSQL
    from render_engine_pg import PostgresContentManager
    if not hasattr(collection, 'ContentManager'):
        return False
    if collection.ContentManager != PostgresContentManager:
        return False

    # Must have content manager extras with connection
    if not hasattr(collection, 'content_manager_extras'):
        return False
    if 'connection' not in collection.content_manager_extras:
        return False

    return True
```

## Migration Path

### Phase 1: Add Dynamic Loading (Backward Compatible)

Keep existing hardcoded collections but also load from config:

```python
class DatabaseManager:
    # Fallback hardcoded collections
    DEFAULT_COLLECTIONS = {
        "blog": "Blog Posts",
        "notes": "Notes",
        "microblog": "Microblog Posts",
    }

    def __init__(self, ...):
        # Try to load dynamically
        try:
            config = RenderEngineConfig()
            metadata = config.get_collection_metadata()
            self.AVAILABLE_COLLECTIONS = {
                slug: meta['title']
                for slug, meta in metadata.items()
            }
        except Exception as e:
            # Fallback to defaults
            self.AVAILABLE_COLLECTIONS = self.DEFAULT_COLLECTIONS
```

### Phase 2: Remove Hardcoded Collections

Once stable, remove the fallback and require `[tool.render-engine]` configuration.

## Benefits of This Approach

1. **Single Source of Truth**: Collection configuration lives in one place (routes.py)
2. **Automatic Discovery**: New collections appear in TUI without code changes
3. **Consistency**: TUI uses exact same collection definitions as the site
4. **Type Safety**: Leverages render-engine's Collection class instead of dictionaries
5. **Rich Metadata**: Access to parser type, content manager, routes, etc.
6. **Standard Pattern**: Follows render-engine-cli conventions

## References

- render-engine Site class: `/Users/jay.miller/.pyenv/versions/3.14.0/lib/python3.14/site-packages/render_engine/site.py`
- render-engine Collection class: `/Users/jay.miller/.pyenv/versions/3.14.0/lib/python3.14/site-packages/render_engine/collection.py`
- kjaymiller.com configuration: `/Users/jay.miller/kjaymiller.com/pyproject.toml`
- kjaymiller.com routes: `/Users/jay.miller/kjaymiller.com/routes.py`
