"""Minimal render-engine Site loader for the TUI.

This module provides a simplified interface to load render-engine Sites
directly from pyproject.toml configuration, without any custom schema
inference or normalization.
"""

from pathlib import Path
from typing import Dict, Optional, Any
import importlib
import sys
import tomllib

from render_engine import Site, Collection


class SiteLoader:
    """Loads render-engine Site and provides access to Collections.

    This simplified loader trusts render-engine's native Collection interface
    and avoids custom schema inference. Works directly with Collection objects
    and their ContentManager instances.
    """

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the loader.

        Args:
            project_root: Path to the render-engine project root.
                         Defaults to current working directory.
        """
        self.project_root = project_root or Path.cwd()
        self.pyproject_path = self.project_root / "pyproject.toml"
        self._site: Optional[Site] = None
        self._module: Optional[Any] = None

    def load_site(self) -> Site:
        """Load the render-engine Site from pyproject.toml configuration.

        Returns:
            The instantiated Site object

        Raises:
            FileNotFoundError: If pyproject.toml doesn't exist
            KeyError: If [tool.render-engine.cli] configuration is missing
            ImportError: If module cannot be imported
            AttributeError: If site object doesn't exist
            TypeError: If loaded object is not a Site instance
        """
        if self._site is not None:
            return self._site

        # Read pyproject.toml
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

        # Get module and site names from CLI config
        cli_config = pyproject["tool"]["render-engine"].get("cli", {})
        module_name = cli_config.get("module")
        site_name = cli_config.get("site")

        if not module_name or not site_name:
            raise KeyError(
                "[tool.render-engine.cli] must specify both 'module' and 'site'.\n"
                "Example:\n"
                "[tool.render-engine.cli]\n"
                'module = "routes"\n'
                'site = "app"'
            )

        # Add project root to sys.path for imports
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

            site = getattr(self._module, site_name)

            if not isinstance(site, Site):
                raise TypeError(
                    f"{module_name}.{site_name} is not a render_engine.Site instance. "
                    f"Got {type(site)} instead."
                )

            self._site = site
            return self._site

        except ImportError as e:
            raise ImportError(
                f"Failed to import module '{module_name}'. "
                f"Make sure the module exists and is importable from {self.project_root}. "
                f"Original error: {e}"
            ) from e

    def get_collections(self) -> Dict[str, Collection]:
        """Get all Collections from the Site.

        Returns:
            Dictionary mapping collection slugs to Collection instances
        """
        site = self.load_site()
        return {
            slug: obj for slug, obj in site.route_list.items()
            if isinstance(obj, Collection)
        }

    def get_collection(self, slug: str) -> Optional[Collection]:
        """Get a specific Collection by slug.

        Args:
            slug: The collection slug

        Returns:
            The Collection instance or None if not found
        """
        return self.get_collections().get(slug)

    def get_collection_names(self) -> list[str]:
        """Get list of available collection slugs.

        Returns:
            List of collection slug names
        """
        return list(self.get_collections().keys())
