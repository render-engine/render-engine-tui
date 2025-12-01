# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python TUI (Terminal User Interface) application for browsing and creating blog content via render-engine ContentManager backends. Built with [Textual](https://textual.textualize.io/), it integrates directly with render-engine projects and supports any ContentManager backend (PostgreSQL, FileSystem, custom).

**Key Features:**
- **Automatic collection loading** from render-engine Site configuration
- **Backend-agnostic** - Works with any ContentManager (PostgreSQL, FileSystem, custom)
- **Async content loading** - Preview updates without blocking UI
- **Multi-collection support** - Browse and create across different content collections

## Commands

### Development Setup
```bash
# Install dependencies with uv
uv sync
```

### Running the Application
```bash
# From a render-engine project directory:
uv run render-engine-tui

# Or with Python directly (if virtual environment is activated)
.venv/bin/render-engine-tui
```

The application must be run from within a render-engine project directory that has collections configured in `pyproject.toml`.

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

**Content Management Layer** (`render-engine-tui/db.py`)
- `ContentManagerWrapper` class - Unified interface to render-engine's ContentManager
- **Backend-agnostic** - Works with any ContentManager (PostgreSQL, FileSystem, custom)
- Loads collections dynamically from render-engine configuration
- Automatic field mapping between ContentManager output and TUI format
- Schema-aware: respects collection field availability (title, description, content, etc.)
- Key methods: `get_posts()`, `get_post()`, `create_post()`, `set_collection()`

**UI Layer** (`render-engine-tui/main.py`)
- `ContentEditorApp` - main Textual application managing the TUI
- Two-pane layout: preview (markdown) above, posts table below
- Uses async workers (`@work` decorator) to fetch full post content without blocking UI
- Dynamic table columns based on collection schema (title for blog, content for microblog, etc.)

**UI Screens** (`render-engine-tui/ui.py`)
- Modal screens for creating posts
- Collection selection screen dynamically populated from config
- Dynamic field visibility based on collection schema

### Multi-Collection Architecture

Collections are loaded directly from render-engine's Site configuration in `pyproject.toml`:

```toml
[tool.render-engine.collections.blog]
parser = "render_engine.parsers.YAMLParser"
content_manager = "render_engine.content_managers.PostgreSQLManager"

[tool.render-engine.collections.pages]
parser = "render_engine.parsers.YAMLParser"
content_manager = "render_engine.content_managers.FileSystemManager"
```

Each collection provides:
- Field schema with metadata (searchable, editable, type, etc.)
- Display name and configuration
- ContentManager implementation for data access

**Collection Schema Detection:**
- Automatically inferred from render-engine's Collection configuration
- ContentManager determines backend (PostgreSQL, FileSystem, custom)
- Parser type determines field schema (title, description, content, date, etc.)

**Key Collection-Agnostic Logic:**
- ContentManager layer handles all backend differences
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
- **python-frontmatter>=1.0.0** - YAML frontmatter parsing for content
- **render-engine** - Required at runtime (collections configuration source)
- **Python 3.11+** - Required

## Code Organization

```
render_engine_tui/
├── __init__.py                             # Package initialization
├── main.py                                 # ContentEditorApp (TUI logic, layout, keybindings)
├── db.py                                   # ContentManagerWrapper (render-engine integration)
├── ui.py                                   # Screen classes (create post, collection select)
├── collections_config.py                   # Collection configuration loader
└── render_engine_integration.py            # ContentManager adapter

Project Root/
├── pyproject.toml                          # Project metadata and dependencies
├── README.md                               # User-facing documentation
└── CLAUDE.md                               # This file
```

## render-engine Integration

The TUI automatically integrates with render-engine projects:

1. **Automatic Collection Detection** - Reads collections from render-engine Site configuration
2. **Schema Inference** - Detects field schemas from Parser types
3. **ContentManager-First** - Uses render-engine's ContentManager for all content operations

### ContentManager-Based Architecture

The TUI uses **render-engine's ContentManager** for all data operations:

```
CREATE:  TUI → ContentManager.create_entry() → [Any backend: PostgreSQL, FileSystem, custom]
READ:    TUI → ContentManager.get_all/search → [Any backend: PostgreSQL, FileSystem, custom]
UPDATE:  Not yet supported by render-engine ContentManager API
DELETE:  Not yet supported by render-engine ContentManager API
```

**Benefits:**
- ✅ Works with any ContentManager backend
- ✅ Synchronized with render-engine's data layer
- ✅ Schema-aware (respects available fields)
- ✅ No database-specific code in TUI
- ✅ Supports FileSystem and custom backends out of the box

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit application |
| `n` | Create new post |
| `c` | Change collection |
| `m` | Show metadata |
| `?` | Show about screen |
| `Ctrl+S` | Save changes (in create screen) |
| `Escape` | Cancel/Go back |

## Key Implementation Details

### ContentManager Integration
- `ContentManagerWrapper` in `db.py` provides unified interface to any ContentManager
- All data operations (read, create) go through ContentManager
- No database-specific code in the TUI layer
- Backend differences handled transparently by ContentManager

### UI Rendering
- `DataTable` shows posts with collection-aware columns
- `MarkdownViewer` renders post content in preview panel
- Async fetch prevents UI blocking during content retrieval
- Two-pane layout: preview (40% height) and posts table (60% height)

### Error Handling
- ContentManager errors caught and displayed as toast notifications
- Operation failures show user-friendly error messages
- All async operations wrapped in try/except to handle failures gracefully

## Common Development Tasks

### Adding a New Feature
1. Identify if it involves ContentManager integration (modify `db.py`) or UI changes (modify `main.py`/`ui.py`)
2. For ContentManager: Add method to `ContentManagerWrapper` and test with all collections
3. For UI: Update keybindings in `BINDINGS` list and implement action method
4. Test with at least two collections to ensure collection-agnostic code

### Debugging ContentManager Issues
- Verify render-engine collections are configured in `pyproject.toml`
- Check that ContentManager is properly initialized for the collection
- Test with a known-working render-engine project first
- Enable verbose output from ContentManager if available

### Testing Collection Switching
- Manually switch between collections (`c` key)
- Verify posts load for each collection
- Create posts in each collection to ensure proper ContentManager integration
- Test with different backend types (PostgreSQL, FileSystem, custom)

### Performance Optimization
- Current async architecture prevents UI blocking
- Full post content fetched only when selected (lazy loading)
- ContentManager caching can improve repeated queries

### Using with render-engine
1. Create or navigate to a render-engine project directory
2. Configure collections in `pyproject.toml` with ContentManager backends
3. Run TUI from the project root: `uv run render-engine-tui`
4. Collections will be automatically loaded from your Site configuration

### Adding a New Collection
1. Add Collection to your render-engine Site in `pyproject.toml`
2. Configure a ContentManager backend (PostgreSQL, FileSystem, or custom)
3. Restart TUI - collection auto-detected from Site configuration
4. Create/browse posts using the TUI

### Supporting Custom ContentManager
1. Implement `pages` property (for reads) and `create_entry()` method (for creates)
2. Add to render-engine Collection as `ContentManager` class
3. TUI will wrap it with `ContentManagerAdapter` automatically
4. Note: Update/delete operations are not yet supported by render-engine ContentManager API

## Important Notes

- **No Tests**: This project currently has no automated test suite; testing is manual
- **ContentManager-Based**: All data operations (read, create) use render-engine's ContentManager - ensures sync with render-engine and works with any backend
- **Schema-Agnostic Code**: All new code must handle arbitrary collection schemas, not hard-code field names (use `config.has_field()` to check)
- **Collection-Agnostic UI**: Table columns, form fields, and validation must adapt to collection schema dynamically
- **No Database Dependencies**: The TUI has no direct database code; all backends are handled by render-engine's ContentManager
- **render-engine Required**: The app must be run from within a render-engine project with collections configured in `pyproject.toml`
- **Field Normalization**: ContentManager output is normalized to TUI format (`_normalize_posts()` method) - handles schema differences across backends
- **Async Operations**: All ContentManager calls that might block are wrapped in async workers to maintain UI responsiveness
