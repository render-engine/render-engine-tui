# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python TUI (Terminal User Interface) application for editing blog content stored in PostgreSQL. Built with [Textual](https://textual.textualize.io/), it allows users to browse, search, create, edit, and delete posts across multiple collections (blog, notes, microblog).

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
uv run content-editor

# Or with Python directly (if virtual environment is activated)
.venv/bin/content-editor
```

### Environment Configuration
The application requires the `CONNECTION_STRING` environment variable:
```bash
# Option 1: Use .env file
echo 'CONNECTION_STRING=postgresql://user:password@localhost:5432/database' > .env

# Option 2: Set environment variable
export CONNECTION_STRING="postgresql://user:password@localhost:5432/database"
uv run content-editor

# Option 3: Inline (one command)
CONNECTION_STRING="postgresql://..." uv run content-editor
```

## Architecture

### Core Components

**Database Layer** (`content_editor/db.py`)
- `DatabaseManager` class handles all PostgreSQL operations
- Supports three collections: `blog`, `notes`, `microblog` (switchable at runtime)
- Uses dynamic SQL with proper parameterization to prevent SQL injection
- Junction tables: `blog_tags`, `notes_tags`, `microblog_tags` (unified `tags` table)
- Key methods: `get_posts()`, `get_post()`, `create_post()`, `update_post()`, `delete_post()`

**UI Layer** (`content_editor/main.py`)
- `ContentEditorApp` - main Textual application managing the TUI
- Organizes layout into three sections: preview (markdown), table (posts), sidebar (tags)
- Implements pagination (50 posts per page) for large collections
- Uses async workers (`@work` decorator) to fetch full post content without blocking UI
- Tag sidebar shows post counts per tag

**UI Screens** (`content_editor/ui.py`)
- Modal screens for search, create/edit posts, delete confirmation
- Collection selection screen for switching between blog/notes/microblog
- Dynamic field visibility based on collection (microblog has no title/description)

### Multi-Collection Architecture

The application dynamically switches between three collections stored in the same PostgreSQL database:
- **Blog**: Full-featured posts with title, description, content
- **Notes**: Same schema as blog, separate data
- **Microblog**: Content-only posts (no title/description fields)

Each collection has:
- Its own table (`blog`, `notes`, `microblog`)
- Its own junction table for tags (`blog_tags`, `notes_tags`, `microblog_tags`)
- Shared unified `tags` table across all collections

**Key Collection-Specific Logic:**
- Database layer handles schema differences (microblog queries don't select title/description)
- UI table columns adjust dynamically (Blog/Notes show title; Microblog shows content preview)
- Create/Edit screens hide title/description fields for microblog
- Field validation accounts for collection-specific requirements

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
├── pyproject.toml       # Project metadata and dependencies
├── README.md            # User-facing documentation
├── QUICKSTART.md        # Quick setup guide
└── tui-collection.md    # Collection switcher implementation details
```

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

## Important Notes

- **MCP Postgres Server**: Disabled in settings (`content_editor/.claude/settings.local.json`) - Claude Code skips the postgres MCP server integration
- **No Tests**: This project currently has no automated test suite; testing is manual
- **Microblog Edge Case**: Microblog collection has different schema (no title/description) - ensure all new code handles this
- **SQL Injection Prevention**: Always use `psycopg.sql.SQL()` with identifiers for table/column names, parameterized queries for values
