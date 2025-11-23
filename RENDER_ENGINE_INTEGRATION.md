# Render-Engine Integration

The Content Editor TUI can automatically load collections from a render-engine Site configuration, instead of requiring separate YAML configuration.

## How It Works

When the TUI starts, it tries to load collections in this order:

1. **render-engine Site** (if `[tool.render-engine.cli]` is configured in `pyproject.toml`)
2. **collections.yaml** file (if no render-engine configuration found)
3. **Hard-coded defaults** (blog, notes, microblog)

## Using render-engine Collections

### Setup

Your render-engine project must have a `[tool.render-engine.cli]` section in `pyproject.toml`:

```toml
[tool.render-engine.cli]
module = "routes"  # Your module name
site = "app"       # Your Site object name
```

Your routes module should export a Site with registered collections:

```python
# routes.py
from render_engine import Site, Collection
from render_engine_pg import PostgresContentManager, PGMarkdownCollectionParser

app = Site()

blog = Collection(
    slug="blog",
    _title="Blog Posts",
    Parser=PGMarkdownCollectionParser,
    ContentManager=PostgresContentManager,
)

app.add_collection(blog)
```

### How Collections Are Extracted

The TUI automatically extracts collection information from render-engine Collection objects:

- **Collection name/slug** → Used as collection identifier in TUI
- **Collection._title** → Display name shown in collection selector
- **ContentManager.table_name** → Database table name (or derived from slug)
- **Parser type** → Used to infer field schema (e.g., MarkdownCollectionParser → has title, description, content)

### What Fields Are Detected

The TUI intelligently detects available fields based on the Parser:

#### Markdown Parsers
Collections using `PGMarkdownCollectionParser` or similar are detected to have:
- `id` - Primary key
- `slug` - URL-friendly identifier
- `title` - Post title
- `description` - Short description
- `content` - Full markdown content
- `date` - Publication date
- `external_link` - External URL (optional)
- `image_url` - Image URL (optional)

#### Text Parsers
Collections using text parsers are detected to have:
- `id`, `slug`, `content`, `date`
- No title or description

#### Custom Parsers
For custom parsers, the TUI uses sensible defaults based on common render-engine patterns.

## Using ContentManager for Database Operations

The TUI can optionally use the ContentManager from render-engine instead of direct database access.

### PostgresContentManager

If your collection uses `PostgresContentManager` from `render_engine_pg`:

```python
from render_engine_pg import PostgresContentManager

blog = Collection(
    slug="blog",
    _title="Blog Posts",
    ContentManager=PostgresContentManager,  # TUI will detect this
    Parser=...,
)
```

The TUI will:
1. Detect the PostgresContentManager
2. Wrap it in a `ContentManagerAdapter`
3. Use it for all database operations

This allows your TUI to stay in sync with your render-engine application's database operations.

### Custom ContentManager

The TUI also supports custom ContentManager implementations. Your ContentManager should implement these methods:

```python
class MyContentManager:
    def get_all(self, **kwargs) -> List[Dict]:
        """Get all items"""
        pass

    def get(self, item_id: int, **kwargs) -> Optional[Dict]:
        """Get a single item"""
        pass

    def create(self, **kwargs) -> int:
        """Create a new item, return ID"""
        pass

    def update(self, item_id: int, **kwargs) -> bool:
        """Update an item"""
        pass

    def delete(self, item_id: int, **kwargs) -> bool:
        """Delete an item"""
        pass
```

## Database Schema Detection

The TUI automatically detects:

- **Table name** - From ContentManager configuration
- **ID column name** - Derived from collection slug (e.g., `blog_id`)
- **Junction table** - For tags (e.g., `blog_tags`)
- **Searchable fields** - Detected from Parser type

If your schema uses different naming conventions, you can customize the collection configuration:

## Example: render-engine Site with Multiple Collections

```python
# routes.py
from render_engine import Site, Collection
from render_engine_pg import PostgresContentManager, PGMarkdownCollectionParser

app = Site()

# Blog collection
blog = Collection(
    slug="blog",
    _title="Blog Posts",
    Parser=PGMarkdownCollectionParser,
    ContentManager=PostgresContentManager,
)

# Notes collection
notes = Collection(
    slug="notes",
    _title="Notes",
    Parser=PGMarkdownCollectionParser,
    ContentManager=PostgresContentManager,
)

# Microblog (content-only)
microblog = Collection(
    slug="microblog",
    _title="Microblog",
    Parser=PGMarkdownCollectionParser,
    ContentManager=PostgresContentManager,
)

app.add_collection(blog)
app.add_collection(notes)
app.add_collection(microblog)
```

The TUI will automatically detect and load all three collections.

## Running the TUI with render-engine

Simply run the TUI from your render-engine project root:

```bash
cd /path/to/render-engine-project
uv run content-editor
```

The TUI will:
1. Load collections from your Site configuration
2. Detect the ContentManager for each collection
3. Display all collections in the collection selector
4. Use the appropriate database schema for each collection

## Fallback to YAML Configuration

If render-engine integration fails (no `pyproject.toml`, missing `[tool.render-engine.cli]` section, etc.), the TUI will fall back to:

1. Loading `collections.yaml` from the project root
2. Using hard-coded default collections (blog, notes, microblog)

This ensures the TUI is always usable, even if render-engine isn't configured.

## Disabling render-engine Integration

To force the TUI to skip render-engine integration and use YAML/defaults instead:

```python
from render_engine_tui.db import DatabaseManager

# Create manager without render-engine
db = DatabaseManager(
    use_render_engine=False
)
```

Or in the main application:

```python
self.db = DatabaseManager(
    use_render_engine=False
)
```

## Debugging

To see what's happening during collection loading:

1. Run the TUI - it will print messages about collection sources
2. Check the subtitle in the TUI which shows the current collection and its display name
3. Verify your `pyproject.toml` has the correct `[tool.render-engine.cli]` section

## Advanced: ContentManager Integration Details

When using ContentManager:

- The TUI creates a `ContentManagerAdapter` wrapper around the ContentManager
- This adapter translates TUI operations into ContentManager method calls
- Falls back to direct database access if ContentManager methods aren't available
- Logs warnings if ContentManager setup fails, continues with direct database access

This design ensures:
- **Compatibility** with both ContentManager and direct database access
- **Extensibility** for custom ContentManagers
- **Reliability** by falling back gracefully
- **Integration** with render-engine's architecture
