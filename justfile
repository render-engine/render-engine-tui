# Release management commands for content-editor-tui

# Display all available commands
help:
    just --list

# Create a release (requires version argument)
release version:
    gh release create "{{version}}" --generate-notes

# Create a prerelease (requires version argument)
prerelease version:
    gh release create "{{version}}" --prerelease --generate-notes

# Show current version
version:
    python3 -c "import setuptools_scm; print(setuptools_scm.get_version())"

# Clean build artifacts
clean:
    rm -rf build/ dist/ *.egg-info .eggs/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete

# Install development dependencies
dev:
    uv sync

# Run the application
run:
    uv run content-editor
