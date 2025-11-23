# Quick Start: Dynamic Collection Loading

## What This Solves

Before: Collections were hardcoded in `db.py`
```python
AVAILABLE_COLLECTIONS = {
    "blog": "Blog Posts",
    "notes": "Notes",
    "microblog": "Microblog Posts",
}
```

After: Collections are discovered from your render-engine site
```python
from content_editor.config import RenderEngineConfig

config = RenderEngineConfig()
collections = config.get_collection_metadata()
# Automatically discovers all collections from routes.py
```

## 5-Minute Integration

### 1. Add Configuration to pyproject.toml

```toml
[tool.render-engine.cli]
module = "routes"  # Your module with the Site instance
site = "app"       # Your Site variable name
```

### 2. Use RenderEngineConfig in db.py

```python
from content_editor.config import RenderEngineConfig

class DatabaseManager:
    def __init__(self, connection_string=None, collection="blog"):
        # Load collections dynamically
        config = RenderEngineConfig()
        metadata = config.get_collection_metadata()

        self.AVAILABLE_COLLECTIONS = {
            slug: meta['title']
            for slug, meta in metadata.items()
        }

        # Rest of initialization...
```

### 3. Test It

```bash
python test_dynamic_loading.py
```

## Key Functions

```python
from content_editor.config import RenderEngineConfig

config = RenderEngineConfig()

# Get the module and site reference
module, site = config.get_site_reference()
# Returns: ("routes", "app")

# Load the Site instance
site = config.load_site()

# Get all collections
collections = config.get_collections()
# Returns: {"blog": <Blog>, "notes": <Notes>, ...}

# Get collection metadata
metadata = config.get_collection_metadata()
# Returns: {"blog": {"title": "Blog Posts", "parser": "...", ...}, ...}

# Get only PostgreSQL collections
pg_collections = config.get_postgres_collections()
```

## How render-engine-cli Does It

1. **Reads `[tool.render-engine.cli]`** from pyproject.toml
2. **Dynamically imports** the module: `importlib.import_module("routes")`
3. **Accesses the Site** instance: `getattr(module, "app")`
4. **Queries collections** from `site.route_list`

The TUI now follows the exact same pattern.

## What You Get

### Site Object

```python
site = config.load_site()

site.route_list
# All registered pages and collections

site.site_vars
# Site-wide variables (SITE_TITLE, SITE_URL, etc.)

site.output_path
# Output directory
```

### Collection Object

```python
collection = config.get_collections()["blog"]

collection._title          # "Blog Posts"
collection._slug          # "blog"
collection.Parser         # PGMarkdownCollectionParser
collection.ContentManager # PostgresContentManager
collection.routes         # ["blog"]
collection.has_archive    # True
```

## Example Output

```bash
$ python test_dynamic_loading.py /Users/jay.miller/kjaymiller.com

Loading configuration from: /Users/jay.miller/kjaymiller.com

Site reference:
  Module: routes
  Site variable: app
  Full import: from routes import app

Successfully imported: routes.app

Filtered Collections (3):
  - blog: Blog Posts
  - notes: Notes to Self
  - microblog: MicroBlog

BLOG:
  Title: Blog Posts
  Parser: PGMarkdownCollectionParser
  Content Manager: PostgresContentManager
  Routes: ['blog']
  Has Archive: True
  Items per page: 20
```

## Files Created

1. **`content_editor/config.py`** - Configuration loader class
2. **`test_dynamic_loading.py`** - Test script
3. **`DYNAMIC_COLLECTIONS.md`** - Detailed technical documentation
4. **`INTEGRATION_EXAMPLE.md`** - Step-by-step integration guide
5. **`IMPLEMENTATION_SUMMARY.md`** - Architecture overview
6. **`DYNAMIC_LOADING_QUICKSTART.md`** - This file

## render-engine Utilities to Import

```python
# Core classes
from render_engine import Site, Collection, Page

# PostgreSQL support
from render_engine_pg import (
    PostgresContentManager,
    PGMarkdownCollectionParser,
    get_db_connection,
)

# Configuration loading (built-in Python)
import tomllib
import importlib
from pathlib import Path
```

## Common Patterns

### Get Collection Display Names

```python
config = RenderEngineConfig()
metadata = config.get_collection_metadata()

display_names = {
    slug: meta['title']
    for slug, meta in metadata.items()
}
# {"blog": "Blog Posts", "notes": "Notes to Self", ...}
```

### Get Database Table Names

```python
collections = config.get_collections()

for slug, collection in collections.items():
    if hasattr(collection, '_metadata_attrs'):
        table = collection._metadata_attrs().get('table', slug)
        print(f"{slug} -> {table}")
```

### Filter by Content Manager

```python
from render_engine_pg import PostgresContentManager

pg_collections = {
    slug: collection
    for slug, collection in config.get_collections().items()
    if hasattr(collection, 'ContentManager')
    and collection.ContentManager == PostgresContentManager
}
```

## Error Handling

```python
from content_editor.config import RenderEngineConfig

try:
    config = RenderEngineConfig()
    site = config.load_site()
except FileNotFoundError:
    print("No pyproject.toml found")
except KeyError:
    print("Missing [tool.render-engine] configuration")
except ImportError as e:
    print(f"Could not import module: {e}")
```

## Next Steps

1. Read `INTEGRATION_EXAMPLE.md` for detailed integration steps
2. Read `DYNAMIC_COLLECTIONS.md` for technical deep dive
3. Run `test_dynamic_loading.py` to see it in action
4. Update your `db.py` and `main.py` to use RenderEngineConfig
