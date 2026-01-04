"""Version management for content-editor-tui."""

try:
    from ._version import version as __version__
except ImportError:
    # Fallback for development environments without git tags
    __version__ = "0.0.0.dev0"


def get_version() -> str:
    """Get the current version."""
    return __version__


def get_release_url() -> str:
    """Get the GitHub release URL for the current version."""
    version = __version__.split("+")[0]  # Remove local version suffix if present
    return f"https://github.com/kjaymiller/render-engine-tui/releases/tag/{version}"
