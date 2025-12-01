# Render Engine TUI

A terminal user interface for browsing and creating blog content via render-engine ContentManager backends. Built with [Textual](https://textual.textualize.io/).

Integrates directly with [render-engine](https://github.com/kjaymiller/render-engine) projects and works with any ContentManager backend (PostgreSQL, FileSystem, custom).

## Features

- **Browse Posts**: View all posts from your render-engine collections
- **Create**: Add new posts via render-engine's ContentManager
- **Multi-Collection Support**: Browse and create across different content collections
- **Backend-Agnostic**: Works with PostgreSQL, FileSystem, or custom ContentManager backends
- **Live Preview**: Async content preview with no UI blocking
- **Collection Switching**: Switch between collections at runtime

## Installation

1. Install the package:
```bash
uv pip install git+https://github.com/yourusername/render-engine-tui
```

Or clone and install locally:
```bash
git clone https://github.com/yourusername/render-engine-tui
cd render-engine-tui
uv sync
```

## Usage

Run from within a render-engine project directory:

```bash
uv run render-engine-tui
```

The application will automatically load collections from your render-engine `pyproject.toml`.

## Setup

### 1. Create a render-engine project

If you don't have one yet:
```bash
pip install render-engine
render-engine create my-site
cd my-site
```

### 2. Configure collections in pyproject.toml

Add your collections to `[tool.render-engine.collections]`:

```toml
[tool.render-engine.collections.blog]
parser = "render_engine.parsers.YAMLParser"
content_manager = "render_engine.content_managers.PostgreSQLManager"
# or FileSystemManager, or your custom ContentManager

[tool.render-engine.collections.pages]
parser = "render_engine.parsers.YAMLParser"
content_manager = "render_engine.content_managers.FileSystemManager"
```

### 3. Run the TUI

```bash
uv run render-engine-tui
```

## Navigation

### Post List Screen (Main)
- **c**: Change collection
- **n**: Create a new post
- **m**: Show post metadata
- **?**: Show about screen
- **Arrow keys**: Navigate through posts
- **Enter** or **click**: Select post and view content
- **q**: Quit application

### Create Post Screen
- **Ctrl+S**: Save the post
- **Escape**: Cancel without saving

### Collection Selector
- **Arrow keys**: Navigate collections
- **Enter**: Select collection
- **Escape**: Cancel

## Project Structure

```
render_engine_tui/
├── __init__.py                         # Package initialization
├── main.py                             # Main TUI app and layout
├── db.py                               # ContentManagerWrapper
├── ui.py                               # Modal screens and forms
├── collections_config.py               # Collection configuration
└── render_engine_integration.py        # ContentManager integration

pyproject.toml                          # Project metadata
README.md                               # This file
CLAUDE.md                               # Developer documentation
```

## Architecture

The TUI uses a **render-engine-only** architecture:

- **No database dependencies**: All data access goes through render-engine's ContentManager
- **Backend-agnostic**: Works with PostgreSQL, FileSystem, or any custom ContentManager
- **Schema-aware**: Adapts UI to collection schema automatically
- **Async operations**: Content fetching doesn't block the UI

For detailed architecture information, see [CLAUDE.md](./CLAUDE.md).

## Development

### Requirements
- Python 3.11+
- render-engine (at runtime)
- Textual
- python-frontmatter

Install development dependencies:
```bash
uv sync
```

### Running tests
Currently manual testing only. To test:

1. Create a render-engine project with test data
2. Run the TUI: `uv run render-engine-tui`
3. Test collection switching and post creation

## Troubleshooting

### "No render-engine project found"
Ensure you're running the TUI from within a render-engine project directory that has a `pyproject.toml` with `[tool.render-engine]` configured.

### "No ContentManager available for collection"
Check that your collection in `pyproject.toml` has a valid `content_manager` configured. Example:
```toml
[tool.render-engine.collections.blog]
content_manager = "render_engine.content_managers.PostgreSQLManager"
```

### Posts not loading
- Verify your ContentManager backend is running (PostgreSQL, etc.)
- Check that your render-engine collection configuration is correct
- Try creating a test post with `render-engine create` to verify the backend works

## Contributing

Contributions welcome! Please:
1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Test with multiple collections and backends
5. Submit a PR

## License

See LICENSE file for details.
