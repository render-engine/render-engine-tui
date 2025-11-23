# Implementation Summary: Dynamic Collection Loading

## Overview

The Content Editor TUI now supports dynamic collection loading by reading `[tool.render-engine]` configuration from `pyproject.toml` and querying the render-engine Site object for available collections.

## Key Components

### 1. Configuration Loader (`content_editor/config.py`)

**Location:** `/Users/jay.miller/render-engine-tui/content_editor/config.py`

**Purpose:** Loads render-engine sites dynamically from pyproject.toml configuration

**Key Classes:**
- `RenderEngineConfig`: Main class for loading and querying render-engine sites

**Key Methods:**
```python
config = RenderEngineConfig(project_root)
site = config.load_site()                      # Import site from module
collections = config.get_collections()          # Get all Collection instances
metadata = config.get_collection_metadata()     # Get collection metadata
pg_colls = config.get_postgres_collections()   # Get PostgreSQL collections only
```

### 2. How It Works

#### Step 1: Read Configuration

```toml
# pyproject.toml
[tool.render-engine.cli]
module = "routes"  # Python module containing the site
site = "app"       # Site instance variable name
```

#### Step 2: Dynamic Import

```python
import importlib
module = importlib.import_module("routes")
site = getattr(module, "app")  # Get the Site instance
```

#### Step 3: Query Collections

```python
# Site has a route_list dictionary with all registered collections
collections = {
    slug: entry
    for slug, entry in site.route_list.items()
    if isinstance(entry, Collection)
}
```

#### Step 4: Extract Metadata

```python
metadata = {
    slug: {
        'title': collection._title,
        'parser': collection.Parser.__name__,
        'content_manager': collection.ContentManager.__name__,
        'routes': collection.routes,
        'has_archive': collection.has_archive,
    }
    for slug, collection in collections.items()
}
```

## Integration Points

### Database Manager (db.py)

**Before (Hardcoded):**
```python
AVAILABLE_COLLECTIONS = {
    "blog": "Blog Posts",
    "notes": "Notes",
    "microblog": "Microblog Posts",
}
```

**After (Dynamic):**
```python
from content_editor.config import RenderEngineConfig

config = RenderEngineConfig()
metadata = config.get_collection_metadata()
AVAILABLE_COLLECTIONS = {
    slug: meta['title']
    for slug, meta in metadata.items()
}
```

### TUI Application (main.py)

**Before:**
```python
class ContentEditorApp(App):
    def __init__(self):
        self.db = DatabaseManager()
        self.current_collection = "blog"  # Hardcoded
```

**After:**
```python
class ContentEditorApp(App):
    def __init__(self):
        self.config = RenderEngineConfig()
        self.available_collections = self.config.get_collection_metadata()
        first_collection = next(iter(self.available_collections.keys()))
        self.db = DatabaseManager(collection=first_collection)
```

## How render-engine-cli Uses This Pattern

While render-engine doesn't have a separate CLI package (it's integrated into the main package), the pattern of reading `[tool.render-engine]` configuration is standard across the ecosystem.

### Configuration Standard

```toml
[tool.render-engine.cli]
module = "routes"  # Module containing your site definition
site = "app"       # Variable name of Site instance
```

### Import Pattern

```python
# Equivalent to: from routes import app
module = importlib.import_module(config['module'])
site = getattr(module, config['site'])
```

This pattern ensures:
1. **Consistency**: All tools use the same configuration
2. **Single Source of Truth**: Site definition lives in one place
3. **No Duplication**: Don't repeat collection definitions

## render-engine Site Architecture

### Site.route_list Structure

```python
site.route_list = {
    "blog": <Blog Collection instance>,
    "notes": <Notes Collection instance>,
    "microblog": <MicroBlog Collection instance>,
    "index": <Index Page instance>,
    "about": <About Page instance>,
}
```

### Collection Attributes

```python
collection = site.route_list["blog"]

# Core attributes
collection._title          # "Blog Posts"
collection._slug           # "blog"
collection.routes          # ["blog"]
collection.template        # "blog.html"

# Content handling
collection.Parser          # PGMarkdownCollectionParser class
collection.ContentManager  # PostgresContentManager class
collection.content_manager # Instantiated content manager with DB connection

# Archive settings
collection.has_archive     # True
collection.items_per_page  # 20
collection.archive_template # "blog_list.html"

# PostgreSQL-specific (if using render-engine-pg)
collection._metadata_attrs()  # Returns {'table': 'blog', 'connection': conn}
collection.content_manager_extras  # {'connection': conn}
```

## Essential render-engine Imports

```python
# Core classes
from render_engine import Site, Collection, Page

# PostgreSQL support (if using)
from render_engine_pg import (
    PostgresContentManager,
    PGMarkdownCollectionParser,
    get_db_connection,
)

# Standard library for config loading
import tomllib
import importlib
from pathlib import Path
```

## Example: kjaymiller.com

### Configuration
**File:** `/Users/jay.miller/kjaymiller.com/pyproject.toml`
```toml
[tool.render-engine.cli]
module = "routes"
site = "app"
```

### Site Definition
**File:** `/Users/jay.miller/kjaymiller.com/routes.py`
```python
from render_engine import Site, Collection
from render_engine_pg import PostgresContentManager

app = Site()  # This is the "app" from config

@app.collection
class Blog(Collection):
    title = "Blog Posts"
    Parser = PGMarkdownCollectionParser
    ContentManager = PostgresContentManager
    # ...

@app.collection
class Notes(Collection):
    title = "Notes to Self"
    # ...
```

### How TUI Discovers Collections

```python
from content_editor.config import RenderEngineConfig

# 1. Read pyproject.toml
config = RenderEngineConfig(Path("/Users/jay.miller/kjaymiller.com"))

# 2. Gets: module="routes", site="app"
module_name, site_name = config.get_site_reference()

# 3. Imports: from routes import app
site = config.load_site()

# 4. Queries: site.route_list
collections = config.get_collections()
# Result: {"blog": <Blog>, "notes": <Notes>, "microblog": <MicroBlog>}

# 5. Extracts metadata
metadata = config.get_collection_metadata()
# Result: {"blog": {"title": "Blog Posts", ...}, ...}
```

## Testing

### Test Script
**File:** `/Users/jay.miller/render-engine-tui/test_dynamic_loading.py`

**Usage:**
```bash
# Test with kjaymiller.com
python test_dynamic_loading.py /Users/jay.miller/kjaymiller.com

# Test with current directory
python test_dynamic_loading.py
```

**Expected Output:**
```
Loading configuration from: /Users/jay.miller/kjaymiller.com

Site reference:
  Module: routes
  Site variable: app

Successfully imported: routes.app

Discovered 3 collections from render-engine site:
  - blog: Blog Posts
  - notes: Notes to Self
  - microblog: MicroBlog

PostgreSQL Collections (3):
  - blog: Blog Posts
  - notes: Notes to Self
  - microblog: MicroBlog
```

## File Structure

```
render-engine-tui/
├── content_editor/
│   ├── __init__.py
│   ├── config.py              # NEW: Dynamic config loader
│   ├── db.py                  # UPDATE: Use config.py
│   ├── main.py                # UPDATE: Use config.py
│   └── ui.py                  # UPDATE: Dynamic collection list
├── pyproject.toml             # UPDATE: Add [tool.render-engine.cli]
├── test_dynamic_loading.py    # NEW: Test script
├── DYNAMIC_COLLECTIONS.md     # NEW: Technical documentation
├── INTEGRATION_EXAMPLE.md     # NEW: Integration guide
└── IMPLEMENTATION_SUMMARY.md  # NEW: This file
```

## Benefits

1. **No Hardcoding**: Collections discovered automatically from routes.py
2. **Single Source of Truth**: Collection definitions in one place
3. **Consistency**: TUI uses exact same collections as the site
4. **Flexibility**: New collections appear automatically
5. **Standard Pattern**: Follows render-engine ecosystem conventions
6. **Rich Metadata**: Access to parser, content manager, routes, etc.

## Migration Steps

1. **Add config.py**: Already created at `/Users/jay.miller/render-engine-tui/content_editor/config.py`

2. **Update pyproject.toml**: Add render-engine configuration
   ```toml
   [tool.render-engine.cli]
   module = "routes"  # Or your module name
   site = "app"       # Or your site variable name
   ```

3. **Update db.py**: Use RenderEngineConfig instead of hardcoded collections

4. **Update main.py**: Load collections dynamically at startup

5. **Update ui.py**: Pass dynamic collection list to UI components

6. **Test**: Run test_dynamic_loading.py to verify

## Next Actions

1. Decide whether to integrate this immediately or keep as backward-compatible option
2. Add `[tool.render-engine.cli]` to `/Users/jay.miller/render-engine-tui/pyproject.toml`
3. Update db.py to use RenderEngineConfig
4. Test with kjaymiller.com to ensure it works
5. Update documentation with usage instructions

## References

- **render-engine Site class**: Shows how collections are registered and stored
  - `/Users/jay.miller/.pyenv/versions/3.14.0/lib/python3.14/site-packages/render_engine/site.py`

- **render-engine Collection class**: Shows Collection attributes and methods
  - `/Users/jay.miller/.pyenv/versions/3.14.0/lib/python3.14/site-packages/render_engine/collection.py`

- **kjaymiller.com example**: Reference implementation with PostgreSQL collections
  - Config: `/Users/jay.miller/kjaymiller.com/pyproject.toml`
  - Site: `/Users/jay.miller/kjaymiller.com/routes.py`

- **Documentation created**:
  - `/Users/jay.miller/render-engine-tui/DYNAMIC_COLLECTIONS.md` - Technical details
  - `/Users/jay.miller/render-engine-tui/INTEGRATION_EXAMPLE.md` - Integration guide
  - `/Users/jay.miller/render-engine-tui/IMPLEMENTATION_SUMMARY.md` - This document
