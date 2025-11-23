# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python TUI (Terminal User Interface) application for editing blog content stored in PostgreSQL. Built with [Textual](https://textual.textualize.io/), it allows users to browse, search, create, edit, and delete posts across multiple collections.

**Key Features:**
- Automatic collection loading from **render-engine Site configuration**
- Support for **multiple ContentManager types** (PostgreSQL, custom)
- **Configurable collections** via YAML or render-engine
- Dynamic UI that adapts to collection schema
- Async loading prevents UI blocking

## Commands

### Development Setup
```bash
# Install dependencies with uv
uv sync

# Create environment file from template
cp .env.example .env
# Edit .env with your PostgreSQL CONNECTION_STRING
```

### Running the Application
```bash
# Using uv
uv run render-engine-tui

# Or with Python directly (if virtual environment is activated)
.venv/bin/render-engine-tui
```

### Environment Configuration
The application requires the `CONNECTION_STRING` environment variable:
```bash
# Option 1: Use .env file
echo 'CONNECTION_STRING=postgresql://user:password@localhost:5432/database' > .env

# Option 2: Set environment variable
export CONNECTION_STRING="postgresql://user:password@localhost:5432/database"
uv run render-engine-tui

# Option 3: Inline (one command)
CONNECTION_STRING="postgresql://..." uv run render-engine-tui
```

## Architecture

### Core Components

**Configuration Layer** (`render-engine-tui/collections_config.py`)
- `CollectionsManager` - Loads collections from render-engine, YAML, or defaults (in order)
- `CollectionConfig` - Represents a collection schema with fields, table names, etc.
- `Field` - Represents a single field in a collection

**render-engine Integration** (`render-engine-tui/render_engine_integration.py`)
- `RenderEngineCollectionsLoader` - Loads collections from render-engine Site configuration
- Automatically extracts schema from Collection objects and their Parsers
- `ContentManagerAdapter` - Wraps render-engine ContentManager instances for unified API

**Database Layer** (`render-engine-tui/db.py`)
- `DatabaseManager` class coordinates content operations
- **ContentManager-First Architecture**: Tries render-engine ContentManager first, falls back to direct DB
- Loads collections dynamically from config (render-engine, YAML, or defaults)
- Automatic field mapping between ContentManager output and TUI format
- Schema-aware: respects collection field availability (title, description, content, etc.)
- Tags always managed via database (separate from ContentManager)
- Key methods: `get_posts()`, `get_post()`, `create_post()`, `update_post()`, `delete_post()`

**UI Layer** (`render-engine-tui/main.py`)
- `ContentEditorApp` - main Textual application managing the TUI
- Organizes layout into three sections: preview (markdown), table (posts), sidebar (tags)
- Implements pagination (50 posts per page) for large collections
- Uses async workers (`@work` decorator) to fetch full post content without blocking UI
- Dynamic table columns based on collection schema (title for blog, content for microblog, etc.)

**UI Screens** (`render-engine-tui/ui.py`)
- Modal screens for search, create/edit posts, delete confirmation
- Collection selection screen dynamically populated from config
- Dynamic field visibility based on collection schema

### Multi-Collection Architecture

Collections are **fully configurable** and can be loaded from three sources:

1. **render-engine Site** - Collections defined in a render-engine project's `pyproject.toml`
2. **YAML Configuration** - Collections defined in `collections.yaml`
3. **Hard-coded Defaults** - Blog, notes, microblog (fallback)

Each collection has:
- Its own database table
- Its own junction table for tags (e.g., `blog_tags`, `portfolio_tags`)
- Field schema with metadata (searchable, editable, type, etc.)
- Display name and configuration

**Collection Schema Detection:**
- For render-engine collections: Automatically inferred from Parser type and ContentManager
- For YAML collections: Explicitly defined in `collections.yaml`
- For defaults: Standard schema with title, description, content, date

**Key Collection-Agnostic Logic:**
- Database layer uses dynamically loaded table names and ID columns
- UI table columns adjust based on collection schema (shows title if available, content preview otherwise)
- Create/Edit screens show/hide fields based on collection configuration
- Field validation is schema-aware (required fields differ per collection)
- ContentManager integration allows custom data access patterns

### Async Architecture

- Full post content loads asynchronously using Textual's `@work` decorator
- UI shows post preview while fetching full content in background worker thread
- Exclusive workers prevent race conditions during concurrent operations
- Post refreshes maintain scroll position and selection

## Project Dependencies

- **textual>=1.0.0** - TUI framework
- **psycopg[binary]>=3.0.0** - PostgreSQL adapter
- **pyyaml>=6.0** - YAML parsing (for potential config)
- **python-dotenv>=1.0.0** - Environment variable management
- **Python 3.10+** - Required

## Code Organization

```
content_editor/
├── __init__.py          # Package initialization
├── main.py              # ContentEditorApp (main TUI logic, styling, keybindings)
├── db.py                # DatabaseManager (all database operations)
└── ui.py                # Screen classes (modals, forms, dialogs)

Project Root/
├── pyproject.toml                          # Project metadata and dependencies
├── README.md                               # User-facing documentation
├── QUICKSTART.md                           # Quick setup guide
├── RENDER_ENGINE_INTEGRATION.md            # render-engine integration guide
├── collections.yaml                        # Collection configuration (optional)
└── tui-collection.md                       # Collection switcher implementation details
```

## render-engine Integration

The TUI automatically integrates with render-engine projects:

1. **Automatic Collection Detection** - Reads collections from render-engine Site configuration
2. **Schema Inference** - Detects field schemas from Parser types
3. **ContentManager-First** - Uses render-engine's ContentManager for all content operations

### ContentManager-First Architecture

The TUI prioritizes **render-engine's ContentManager** for content operations:

```
TUI → DatabaseManager → [ContentManager] → Content
                    → [Database fallback if CM unavailable]
```

**Benefits:**
- ✅ Synchronized with render-engine's data layer
- ✅ Works with any custom ContentManager
- ✅ Falls back gracefully to direct database
- ✅ Schema-aware (respects available fields)
- ✅ Tags managed separately via database

See [`RENDER_ENGINE_INTEGRATION.md`](./RENDER_ENGINE_INTEGRATION.md) and [`CONTENT_MANAGER_ARCHITECTURE.md`](./CONTENT_MANAGER_ARCHITECTURE.md) for detailed setup and usage.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit application |
| `e` | Edit selected post |
| `n` | Create new post |
| `d` | Delete selected post |
| `/` | Search posts |
| `c` | Change collection |
| `r` | Reset view |
| `PageDown` | Next page |
| `PageUp` | Previous page |
| `Ctrl+S` | Save changes (in edit/create screens) |
| `Escape` | Cancel/Go back |

## Key Implementation Details

### Database Queries
- All queries use parameterized statements with `psycopg.sql` module for safety
- Junction tables use dynamic SQL identifiers based on current collection
- Tag operations use aggregate queries to avoid N+1 problems (see `get_all_tags_with_counts()`)

### UI Rendering
- `DataTable` shows posts with collection-aware columns
- `ListView` shows tags with post count in sidebar
- `MarkdownViewer` renders post content in preview panel
- Async fetch prevents UI blocking during database queries

### Error Handling
- Database connection errors display in subtitle
- Operation failures show toast notifications
- All database operations wrapped in try/finally to clean up cursor resources

### Pagination
- Default page size: 50 posts per page
- Search term preserved across page navigation
- Current page tracked in app state

## Common Development Tasks

### Adding a New Feature
1. Identify if it involves database changes (modify `db.py`) or UI changes (modify `main.py`/`ui.py`)
2. For database: Add method to `DatabaseManager` and test with all collections
3. For UI: Update keybindings in `BINDINGS` list and implement action method
4. Test with at least two collections to ensure collection-agnostic code

### Debugging Database Issues
- Check `CONNECTION_STRING` is set and PostgreSQL is running
- Use `psql` to verify table structure and data
- Review `tui-collection.md` for schema documentation
- Check cursor cleanup in finally blocks (all queries should close cursors)

### Testing Collection Switching
- Manually switch between collections (`c` key)
- Verify posts load for each collection
- Verify tag sidebar updates appropriately
- Create/edit/delete in each collection to ensure proper table/junction table usage

### Performance Optimization
- Current async architecture prevents UI blocking
- Tag sidebar query uses aggregate (`COUNT`) to avoid N+1
- Full post content fetched only when selected (lazy loading)
- Pagination loads 50 posts at a time, not all posts

### Using with render-engine
1. Ensure your render-engine project has `[tool.render-engine.cli]` in `pyproject.toml`
2. Run TUI from the project root: `uv run render-engine-tui`
3. Collections will be automatically loaded from your Site configuration
4. See `RENDER_ENGINE_INTEGRATION.md` for advanced setup

### Adding a New Collection
**From render-engine:**
1. Add Collection to your render-engine Site
2. Restart TUI - collection auto-detected from Site configuration

**From YAML:**
1. Add entry to `collections.yaml` with table name, ID column, junction table
2. Ensure database tables and junction tables exist
3. Restart TUI

### Supporting Custom ContentManager
1. Implement `get_all()`, `get()`, `create()`, `update()`, `delete()` methods
2. Add to render-engine Collection as `ContentManager` class
3. TUI will wrap it with `ContentManagerAdapter` automatically

## Important Notes

- **MCP Postgres Server**: Disabled in settings (`content_editor/.claude/settings.local.json`) - Claude Code skips the postgres MCP server integration
- **No Tests**: This project currently has no automated test suite; testing is manual
- **ContentManager-First**: All CRUD operations try ContentManager first, fall back to direct database - ensures sync with render-engine
- **Schema-Agnostic Code**: All new code must handle arbitrary collection schemas, not hard-code field names (use `config.has_field()` to check)
- **Collection-Agnostic UI**: Table columns, form fields, and validation must adapt to collection schema dynamically
- **SQL Injection Prevention**: Always use `psycopg.sql.SQL()` with identifiers for table/column names, parameterized queries for values
- **render-engine Priority**: When running from a render-engine project, collections are loaded from Site first, then fallback to YAML/defaults
- **Field Normalization**: ContentManager output is normalized to TUI format (`_normalize_posts()` method) - handles schema differences
- **Tag Management**: Tags are always managed via database, not ContentManager, because they're shared across collections
