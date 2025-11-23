"""Configuration loader for render-engine sites.

This module provides utilities to dynamically load render-engine sites
from [tool.render-engine] configuration in pyproject.toml, similar to
how render-engine-cli operates.
"""

import importlib
import sys
import tomllib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from render_engine import Site, Collection


class RenderEngineConfig:
    """Loads and manages render-engine site configuration."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize configuration loader.

        Args:
            project_root: Path to the project root containing pyproject.toml.
                         Defaults to current working directory.
        """
        self.project_root = project_root or Path.cwd()
        self.pyproject_path = self.project_root / "pyproject.toml"
        self._config: Optional[Dict[str, Any]] = None
        self._site: Optional[Site] = None
        self._module: Optional[Any] = None

    @property
    def config(self) -> Dict[str, Any]:
        """Load and cache the [tool.render-engine] configuration."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def _load_config(self) -> Dict[str, Any]:
        """Read pyproject.toml and extract [tool.render-engine] section.

        Returns:
            Dictionary containing render-engine configuration

        Raises:
            FileNotFoundError: If pyproject.toml doesn't exist
            KeyError: If [tool.render-engine] section is missing
        """
        if not self.pyproject_path.exists():
            raise FileNotFoundError(
                f"pyproject.toml not found at {self.pyproject_path}. "
                "Make sure you're running from a render-engine project directory."
            )

        with open(self.pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)

        if "tool" not in pyproject or "render-engine" not in pyproject["tool"]:
            raise KeyError(
                "[tool.render-engine] section not found in pyproject.toml. "
                "Add configuration like:\n"
                "[tool.render-engine.cli]\n"
                'module = "routes"\n'
                'site = "app"'
            )

        return pyproject["tool"]["render-engine"]

    def get_site_reference(self) -> Tuple[str, str]:
        """Get the module and site object names from configuration.

        Returns:
            Tuple of (module_name, site_name)

        Example:
            >>> config = RenderEngineConfig()
            >>> module, site = config.get_site_reference()
            >>> # Returns ("routes", "app") for typical configuration
        """
        cli_config = self.config.get("cli", {})
        module = cli_config.get("module")
        site = cli_config.get("site")

        if not module or not site:
            raise ValueError(
                "[tool.render-engine.cli] must specify both 'module' and 'site'.\n"
                "Example:\n"
                "[tool.render-engine.cli]\n"
                'module = "routes"\n'
                'site = "app"'
            )

        return module, site

    def load_site(self) -> Site:
        """Dynamically import and return the render-engine Site object.

        This follows the pattern used by render-engine-cli to load sites.

        Returns:
            The instantiated Site object from the configured module

        Raises:
            ImportError: If module cannot be imported
            AttributeError: If site object doesn't exist in module
        """
        if self._site is not None:
            return self._site

        module_name, site_name = self.get_site_reference()

        # Add project root to sys.path so we can import the module
        project_root_str = str(self.project_root)
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)

        try:
            # Import the module
            self._module = importlib.import_module(module_name)

            # Get the site object
            if not hasattr(self._module, site_name):
                raise AttributeError(
                    f"Module '{module_name}' does not have a '{site_name}' attribute. "
                    f"Check your [tool.render-engine.cli] configuration."
                )

            self._site = getattr(self._module, site_name)

            if not isinstance(self._site, Site):
                raise TypeError(
                    f"{module_name}.{site_name} is not a render_engine.Site instance. "
                    f"Got {type(self._site)} instead."
                )

            return self._site

        except ImportError as e:
            raise ImportError(
                f"Failed to import module '{module_name}'. "
                f"Make sure the module exists and is importable from {self.project_root}. "
                f"Original error: {e}"
            ) from e

    def get_collections(self) -> Dict[str, Collection]:
        """Get all collections registered with the site.

        Returns:
            Dictionary mapping collection slugs to Collection instances

        Example:
            >>> config = RenderEngineConfig()
            >>> collections = config.get_collections()
            >>> for slug, collection in collections.items():
            ...     print(f"{slug}: {collection._title}")
            blog: Blog Posts
            notes: Notes to Self
            microblog: MicroBlog
        """
        site = self.load_site()

        # Filter route_list to only include Collection instances
        # (route_list also includes Page instances)
        return {
            slug: entry
            for slug, entry in site.route_list.items()
            if isinstance(entry, Collection)
        }

    def get_collection_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Extract metadata about each collection for UI display.

        Returns:
            Dictionary mapping collection slugs to metadata dictionaries
            containing title, parser type, content manager, etc.

        Example:
            >>> config = RenderEngineConfig()
            >>> metadata = config.get_collection_metadata()
            >>> metadata['blog']
            {
                'slug': 'blog',
                'title': 'Blog Posts',
                'parser': 'PGMarkdownCollectionParser',
                'content_manager': 'PostgresContentManager',
                'has_archive': True,
                'routes': ['blog']
            }
        """
        collections = self.get_collections()
        metadata = {}

        for slug, collection in collections.items():
            metadata[slug] = {
                "slug": slug,
                "title": getattr(collection, "_title", slug),
                "parser": collection.Parser.__name__ if hasattr(collection, "Parser") else None,
                "content_manager": (
                    collection.ContentManager.__name__
                    if hasattr(collection, "ContentManager")
                    else None
                ),
                "has_archive": getattr(collection, "has_archive", False),
                "routes": getattr(collection, "routes", []),
                "items_per_page": getattr(collection, "items_per_page", None),
            }

        return metadata

    def get_postgres_collections(self) -> Dict[str, Collection]:
        """Get only collections that use PostgresContentManager.

        This is useful for the TUI since it specifically works with
        PostgreSQL-backed collections.

        Returns:
            Dictionary of PostgreSQL-backed collections
        """
        from render_engine_pg import PostgresContentManager

        collections = self.get_collections()
        return {
            slug: collection
            for slug, collection in collections.items()
            if hasattr(collection, "ContentManager")
            and collection.ContentManager == PostgresContentManager
        }
