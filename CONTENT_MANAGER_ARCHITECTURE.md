# ContentManager-First Architecture

The TUI now prioritizes **render-engine's ContentManager** for all content operations, with direct database access as a fallback. This ensures the TUI stays synchronized with your render-engine application's data layer.

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│              TUI (UI Layer)                         │
│  CreatePostScreen, EditPostScreen, main.py          │
└────────────────────┬────────────────────────────────┘
                     │ calls
                     ↓
┌─────────────────────────────────────────────────────┐
│           DatabaseManager (Coordinator)             │
│  get_posts(), get_post(), create_post(), etc.       │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ↓ tries first            ↓ fallback
┌──────────────────────┐    ┌──────────────────┐
│  ContentManager      │    │  Direct Database │
│  (render-engine)     │    │  Access (psycopg)│
│                      │    │                  │
│  get()               │    │  SELECT/INSERT/  │
│  get_all()           │    │  UPDATE/DELETE   │
│  search()            │    │                  │
│  create()            │    │  Fallback for:   │
│  update()            │    │  - Tags          │
│  delete()            │    │  - Unsupported CM│
└──────────────────────┘    │    operations    │
                            └──────────────────┘
```

## How It Works

### Content Operations (Primary)

When you perform any content operation (get, search, create, update, delete), the DatabaseManager:

1. **Tries ContentManager first** - If a ContentManager is configured for the collection
2. **Falls back to direct database** - If ContentManager is unavailable or throws an error
3. **Handles field mapping** - Normalizes ContentManager output to TUI's expected format

### Example: Getting Posts

```python
# TUI calls
db.get_posts(search="python", limit=50, offset=0)

# DatabaseManager does:
# 1. Check if ContentManager is available for current collection
if self.content_manager:
    # Try ContentManager first
    items = self.content_manager.search("python", limit=50, offset=0)
    return self._normalize_posts(items)  # Convert to TUI format

# 2. Fallback to direct database
else:
    return self._get_posts_from_db(search="python", limit=50, offset=0)
```

## Operations and Fallback Behavior

| Operation | ContentManager | Database Fallback | Notes |
|-----------|---|---|---|
| `get_posts()` | `get_all()` or `search()` | Direct SQL SELECT | Search filters applied |
| `get_post(id)` | `get(id)` | Direct SQL SELECT | Tags always from DB |
| `create_post()` | `create()` | Direct SQL INSERT | Tags managed via DB |
| `update_post()` | `update()` | Direct SQL UPDATE | Tags managed via DB |
| `delete_post()` | `delete()` | Direct SQL DELETE | Cascade deletes tags |
| Tags | Always from database | Always from database | Separate from post data |

## Field Normalization

The TUI expects posts in this format:

```python
{
    "id": 1,
    "slug": "post-slug",
    "title": "Post Title",
    "description": "Short description",
    "content": "Full content",
    "date": datetime,
    "tags": [{"id": 1, "name": "tag"}],
    "external_link": None,
    "image_url": None,
}
```

ContentManagers may return different formats. The `_normalize_posts()` method converts them:

```python
# ContentManager might return:
{"id": 1, "slug": "post-slug", "title": "Title", "body": "content"}

# Normalized to:
{
    "id": 1,
    "slug": "post-slug",
    "title": "Title",
    "description": "",
    "content": "content",  # from "body"
    "date": None,
    # ... other fields
}
```

## Collection Schema Awareness

When creating or updating posts, the DatabaseManager respects collection schemas:

### Full-Featured Collection (Blog, Notes)

```python
# Has title, description, content fields
create_post(
    slug="my-post",
    title="My Post",
    description="A description",
    content="Full content"
)

# DatabaseManager includes all in ContentManager call
if config.has_field("title"):
    data["title"] = title  # ✅ included
if config.has_field("description"):
    data["description"] = description  # ✅ included
```

### Content-Only Collection (Microblog)

```python
# Only has content field
create_post(
    slug="note",
    title="",  # ignored
    description="",  # ignored
    content="Just the content"
)

# DatabaseManager filters out unsupported fields
if config.has_field("title"):
    data["title"] = title  # ❌ skipped
if config.has_field("description"):
    data["description"] = description  # ❌ skipped
```

## Error Handling

If ContentManager fails, the TUI logs a warning and falls back:

```python
if self.content_manager:
    try:
        return self.content_manager.get(post_id)
    except Exception as e:
        print(f"Warning: ContentManager get failed: {e}. Falling back to database.")
        return self._get_post_from_db(post_id)  # Fallback
```

This ensures **the application always works**, even if:
- ContentManager is unavailable
- ContentManager throws an error
- Operation is unsupported by ContentManager

## Tag Management

**Tags are always managed via database**, not ContentManager, because:

1. Tags are shared across all collections
2. TUI has specific tag management features (rename, delete, count)
3. ContentManagers may not support tag operations

Tags are:
- Fetched from database: `_get_post_tags(post_id)`
- Created/updated: `_add_post_tags(post_id, tags)`
- Deleted: Cascade delete via foreign key

## Integration with render-engine

When using render-engine ContentManager:

```python
# Your render-engine routes.py
from render_engine_pg import PostgresContentManager

blog = Collection(
    slug="blog",
    ContentManager=PostgresContentManager,
)
```

The TUI:
1. Detects PostgresContentManager for the collection
2. Wraps it in ContentManagerAdapter
3. Calls ContentManager methods for all post operations
4. Falls back to direct psycopg only if necessary

## Benefits

✅ **Synchronization** - Uses same data layer as render-engine app
✅ **Extensibility** - Custom ContentManagers automatically supported
✅ **Robustness** - Falls back gracefully if ContentManager unavailable
✅ **Schema-Agnostic** - Works with any collection schema
✅ **Performance** - Can leverage ContentManager optimizations
✅ **Flexibility** - Can switch between ContentManager and direct DB per operation

## Custom ContentManager Implementation

To make your ContentManager work with the TUI, implement these methods:

```python
class MyContentManager:
    """Custom ContentManager for render-engine."""

    def get_all(self) -> List[Dict]:
        """Get all items. Return list of dicts with id, slug, title, content, date, etc."""
        return [
            {
                "id": 1,
                "slug": "post-1",
                "title": "First Post",
                "content": "...",
                "date": datetime.now(),
            }
        ]

    def get(self, item_id: int) -> Optional[Dict]:
        """Get a single item by ID."""
        return {"id": item_id, "slug": "post-1", ...}

    def search(self, term: str) -> List[Dict]:
        """Search items (optional, get_all + filter is fallback)."""
        return [...]  # filtered items

    def create(self, **kwargs) -> int:
        """Create new item. Return the item ID."""
        # kwargs contains: slug, title, content, description, date, etc.
        return new_item_id

    def update(self, item_id: int, **kwargs) -> bool:
        """Update item. Return True if successful."""
        # kwargs contains: slug, title, content, description, date, etc.
        return True

    def delete(self, item_id: int) -> bool:
        """Delete item. Return True if successful."""
        return True
```

Then register with your render-engine Collection:

```python
blog = Collection(
    slug="blog",
    ContentManager=MyContentManager,
)
```

The TUI will automatically use your ContentManager!

## Debugging

To see what's happening:

1. **Check the terminal** - Warnings are printed when ContentManager fails
2. **Monitor the subtitle** - Shows current collection and status
3. **Test operations** - Try create/edit/delete to see where ContentManager vs. DB is used

Example output:
```
Note: Could not load from render-engine: ...
Loaded 3 collection(s) from render-engine Site
Warning: ContentManager get_post failed: ... Falling back to database.
```

## Migration Path

If you have an existing TUI setup using only direct database access:

1. ✅ **No changes needed** - Existing setup continues to work
2. 📋 **Optional upgrade** - Add ContentManager to collections
3. 🔄 **Automatic integration** - TUI detects and uses ContentManager
4. 🚀 **Synchronized** - TUI now uses your render-engine's data layer
