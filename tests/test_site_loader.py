"""Comprehensive pytest tests for SiteLoader class.

Tests cover:
- Happy path: successful site and collection loading
- Error handling: missing files, invalid config, import failures
- Collection filtering: only Collection instances returned
- Caching behavior: site caching on subsequent calls
- Edge cases: empty route lists, non-Collection objects in routes
"""

import sys
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock

import pytest

from render_engine import Site, Collection
from render_engine_tui.site_loader import SiteLoader


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_site():
    """Create a mock Site instance with route_list."""
    site = Mock(spec=Site)
    site.route_list = {}
    return site


@pytest.fixture
def mock_collection():
    """Create a mock Collection instance."""
    collection = Mock(spec=Collection)
    collection.slug = "test_collection"
    return collection


@pytest.fixture
def valid_pyproject_content():
    """Return valid pyproject.toml TOML content."""
    return """[tool.render-engine]
name = "Test Site"

[tool.render-engine.cli]
module = "routes"
site = "app"
"""


@pytest.fixture
def valid_pyproject_path(temp_project_dir, valid_pyproject_content):
    """Create a valid pyproject.toml file in temp directory."""
    pyproject_path = temp_project_dir / "pyproject.toml"
    pyproject_path.write_text(valid_pyproject_content)
    return temp_project_dir


@pytest.fixture
def mock_module_with_site(mock_site):
    """Create a mock module with a valid Site object."""
    module = MagicMock()
    module.app = mock_site
    return module


@pytest.fixture
def mock_module_with_bad_site():
    """Create a mock module with a non-Site object."""
    module = MagicMock()
    module.app = "not a site"  # String instead of Site
    return module


# ============================================================================
# Happy Path Tests
# ============================================================================


class TestSiteLoaderHappyPath:
    """Test successful site loading and collection access."""

    def test_site_loader_initialization_default_cwd(self, temp_project_dir):
        """Test SiteLoader initializes with default current working directory."""
        # Save current cwd
        original_cwd = Path.cwd()

        try:
            # Change to temp directory
            import os
            os.chdir(temp_project_dir)

            loader = SiteLoader()
            # Resolve both paths to handle symlinks (macOS /var vs /private/var)
            assert loader.project_root.resolve() == temp_project_dir.resolve()
            assert loader.pyproject_path == loader.project_root / "pyproject.toml"
            assert loader._site is None
            assert loader._module is None
        finally:
            # Restore original cwd
            os.chdir(original_cwd)

    def test_site_loader_initialization_explicit_path(self, temp_project_dir):
        """Test SiteLoader initializes with explicit project root."""
        loader = SiteLoader(project_root=temp_project_dir)
        assert loader.project_root == temp_project_dir
        assert loader.pyproject_path == temp_project_dir / "pyproject.toml"

    def test_load_site_success(self, valid_pyproject_path, mock_module_with_site):
        """Test successful site loading from pyproject.toml."""
        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            site = loader.load_site()
            assert site is mock_module_with_site.app
            assert loader._site is not None

    def test_load_site_returns_cached_site(self, valid_pyproject_path, mock_module_with_site):
        """Test that load_site returns cached site on subsequent calls."""
        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            site1 = loader.load_site()
            site2 = loader.load_site()

            # Should return the same cached instance
            assert site1 is site2
            # import_module should only be called once
            assert loader._site is site1

    def test_get_collections_returns_dict(self, valid_pyproject_path, mock_site, mock_module_with_site):
        """Test get_collections returns dict of Collection instances."""
        # Add some collections to the mock site's route_list
        collection1 = Mock(spec=Collection)
        collection1.slug = "blog"
        collection2 = Mock(spec=Collection)
        collection2.slug = "pages"

        mock_site.route_list = {
            "blog": collection1,
            "pages": collection2,
        }

        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            collections = loader.get_collections()

            assert isinstance(collections, dict)
            assert len(collections) == 2
            assert "blog" in collections
            assert "pages" in collections
            assert collections["blog"] is collection1
            assert collections["pages"] is collection2

    def test_get_collection_by_slug_found(self, valid_pyproject_path, mock_site, mock_module_with_site):
        """Test get_collection returns Collection by slug."""
        collection = Mock(spec=Collection)
        collection.slug = "blog"
        mock_site.route_list = {"blog": collection}

        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            result = loader.get_collection("blog")
            assert result is collection

    def test_get_collection_by_slug_not_found(self, valid_pyproject_path, mock_site, mock_module_with_site):
        """Test get_collection returns None when slug not found."""
        mock_site.route_list = {}
        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            result = loader.get_collection("nonexistent")
            assert result is None

    def test_get_collection_names_returns_list(self, valid_pyproject_path, mock_site, mock_module_with_site):
        """Test get_collection_names returns list of slugs."""
        collection1 = Mock(spec=Collection)
        collection2 = Mock(spec=Collection)
        collection3 = Mock(spec=Collection)

        mock_site.route_list = {
            "blog": collection1,
            "pages": collection2,
            "microblog": collection3,
        }

        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            names = loader.get_collection_names()

            assert isinstance(names, list)
            assert len(names) == 3
            assert set(names) == {"blog", "pages", "microblog"}


# ============================================================================
# Collection Filtering Tests
# ============================================================================


class TestCollectionFiltering:
    """Test that only Collection instances are returned."""

    def test_get_collections_filters_non_collection_objects(
        self, valid_pyproject_path, mock_site, mock_module_with_site
    ):
        """Test that non-Collection objects in route_list are filtered out."""
        collection = Mock(spec=Collection)
        mock_site.route_list = {
            "blog": collection,
            "static_files": "not a collection",
            "archive": 12345,
            "other": None,
            "middleware": lambda x: x,
        }

        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            collections = loader.get_collections()

            # Only the actual Collection should be returned
            assert len(collections) == 1
            assert "blog" in collections
            assert collections["blog"] is collection

    def test_get_collections_empty_route_list(self, valid_pyproject_path, mock_site, mock_module_with_site):
        """Test get_collections with empty route_list."""
        mock_site.route_list = {}
        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            collections = loader.get_collections()
            assert collections == {}
            assert len(collections) == 0

    def test_get_collections_no_valid_collections(
        self, valid_pyproject_path, mock_site, mock_module_with_site
    ):
        """Test get_collections when route_list has no Collection objects."""
        mock_site.route_list = {
            "static": "files",
            "archive": Mock(),  # Not a Collection
            "middleware": Mock(),  # Not a Collection
        }

        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            collections = loader.get_collections()
            assert collections == {}

    def test_get_collection_names_empty(self, valid_pyproject_path, mock_site, mock_module_with_site):
        """Test get_collection_names when no collections exist."""
        mock_site.route_list = {}
        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            names = loader.get_collection_names()
            assert names == []


# ============================================================================
# Caching Tests
# ============================================================================


class TestSiteLoaderCaching:
    """Test caching behavior of loaded site and module."""

    def test_site_cached_after_load(self, valid_pyproject_path, mock_module_with_site):
        """Test that site is cached in _site after load."""
        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            assert loader._site is None
            site = loader.load_site()
            assert loader._site is not None
            assert loader._site is site

    def test_module_cached_after_load(self, valid_pyproject_path, mock_module_with_site):
        """Test that module is cached in _module after load."""
        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            assert loader._module is None
            loader.load_site()
            assert loader._module is not None
            assert loader._module is mock_module_with_site

    def test_cache_prevents_reimport(self, valid_pyproject_path, mock_module_with_site):
        """Test that cached site prevents re-importing module."""
        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site) as mock_import:
            site1 = loader.load_site()
            site2 = loader.load_site()
            site3 = loader.load_site()

            # import_module should only be called once due to caching
            assert mock_import.call_count == 1


# ============================================================================
# Error Handling Tests - File and Configuration
# ============================================================================


class TestFileAndConfigurationErrors:
    """Test error handling for missing files and configuration."""

    def test_pyproject_toml_not_found(self, temp_project_dir):
        """Test FileNotFoundError when pyproject.toml doesn't exist."""
        loader = SiteLoader(project_root=temp_project_dir)

        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load_site()

        assert "pyproject.toml not found" in str(exc_info.value)
        assert str(temp_project_dir) in str(exc_info.value)

    def test_missing_tool_render_engine_section(self, temp_project_dir):
        """Test KeyError when [tool.render-engine] section is missing."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("[build-system]\nrequires = []\n")

        loader = SiteLoader(project_root=temp_project_dir)

        with pytest.raises(KeyError) as exc_info:
            loader.load_site()

        assert "[tool.render-engine] section not found" in str(exc_info.value)

    def test_missing_tool_section(self, temp_project_dir):
        """Test KeyError when [tool] section is missing entirely."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("[build-system]\nrequires = []\n")

        loader = SiteLoader(project_root=temp_project_dir)

        with pytest.raises(KeyError) as exc_info:
            loader.load_site()

        assert "[tool.render-engine] section not found" in str(exc_info.value)

    def test_missing_cli_config_section(self, temp_project_dir):
        """Test KeyError when [tool.render-engine.cli] section is missing."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("[tool.render-engine]\nname = 'Test'\n")

        loader = SiteLoader(project_root=temp_project_dir)

        with pytest.raises(KeyError) as exc_info:
            loader.load_site()

        error_msg = str(exc_info.value)
        assert "[tool.render-engine.cli]" in error_msg

    def test_missing_module_key(self, temp_project_dir):
        """Test KeyError when 'module' key is missing from cli config."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text(
            "[tool.render-engine.cli]\nsite = 'app'\n"
        )

        loader = SiteLoader(project_root=temp_project_dir)

        with pytest.raises(KeyError) as exc_info:
            loader.load_site()

        error_msg = exc_info.value.args[0]
        assert "both" in error_msg and "module" in error_msg and "site" in error_msg

    def test_missing_site_key(self, temp_project_dir):
        """Test KeyError when 'site' key is missing from cli config."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text(
            "[tool.render-engine.cli]\nmodule = 'routes'\n"
        )

        loader = SiteLoader(project_root=temp_project_dir)

        with pytest.raises(KeyError) as exc_info:
            loader.load_site()

        error_msg = exc_info.value.args[0]
        assert "both" in error_msg and "module" in error_msg and "site" in error_msg

    def test_empty_module_value(self, temp_project_dir):
        """Test KeyError when 'module' is empty string."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text(
            '[tool.render-engine.cli]\nmodule = ""\nsite = "app"\n'
        )

        loader = SiteLoader(project_root=temp_project_dir)

        with pytest.raises(KeyError) as exc_info:
            loader.load_site()

        error_msg = exc_info.value.args[0]
        assert "both" in error_msg and "module" in error_msg and "site" in error_msg

    def test_empty_site_value(self, temp_project_dir):
        """Test KeyError when 'site' is empty string."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text(
            '[tool.render-engine.cli]\nmodule = "routes"\nsite = ""\n'
        )

        loader = SiteLoader(project_root=temp_project_dir)

        with pytest.raises(KeyError) as exc_info:
            loader.load_site()

        error_msg = exc_info.value.args[0]
        assert "both" in error_msg and "module" in error_msg and "site" in error_msg


# ============================================================================
# Error Handling Tests - Module and Attribute
# ============================================================================


class TestImportAndAttributeErrors:
    """Test error handling for import failures and missing attributes."""

    def test_module_import_error_nonexistent_module(self, valid_pyproject_path):
        """Test ImportError when module cannot be imported."""
        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", side_effect=ImportError("No module")):
            with pytest.raises(ImportError) as exc_info:
                loader.load_site()

            assert "Failed to import module" in str(exc_info.value)
            assert "routes" in str(exc_info.value)

    def test_module_import_error_with_original_error(self, valid_pyproject_path):
        """Test ImportError preserves original error message."""
        loader = SiteLoader(project_root=valid_pyproject_path)
        original_error = ImportError("Module not found: bad_module")

        with patch("importlib.import_module", side_effect=original_error):
            with pytest.raises(ImportError) as exc_info:
                loader.load_site()

            error_msg = str(exc_info.value)
            assert "Failed to import module" in error_msg
            assert "bad_module" in error_msg or "Module not found" in error_msg

    def test_attribute_error_missing_site_attribute(self, valid_pyproject_path):
        """Test AttributeError when site object doesn't exist in module."""
        module = MagicMock()
        # Don't set 'app' attribute
        del module.app

        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=module):
            with pytest.raises(AttributeError) as exc_info:
                loader.load_site()

            error_msg = str(exc_info.value)
            assert "does not have a" in error_msg
            assert "app" in error_msg
            assert "routes" in error_msg

    def test_attribute_error_custom_site_name(self, temp_project_dir, mock_site):
        """Test AttributeError with custom site variable name."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text(
            '[tool.render-engine.cli]\nmodule = "app_module"\nsite = "my_site"\n'
        )

        module = MagicMock()
        del module.my_site

        loader = SiteLoader(project_root=temp_project_dir)

        with patch("importlib.import_module", return_value=module):
            with pytest.raises(AttributeError) as exc_info:
                loader.load_site()

            error_msg = str(exc_info.value)
            assert "my_site" in error_msg
            assert "app_module" in error_msg


# ============================================================================
# Error Handling Tests - Type Validation
# ============================================================================


class TestTypeValidationErrors:
    """Test error handling for type validation."""

    def test_non_site_object_string(self, valid_pyproject_path):
        """Test TypeError when loaded object is a string."""
        module = MagicMock()
        module.app = "not a site"

        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=module):
            with pytest.raises(TypeError) as exc_info:
                loader.load_site()

            error_msg = str(exc_info.value)
            assert "is not a render_engine.Site instance" in error_msg
            assert "routes.app" in error_msg

    def test_non_site_object_dict(self, valid_pyproject_path):
        """Test TypeError when loaded object is a dict."""
        module = MagicMock()
        module.app = {"key": "value"}

        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=module):
            with pytest.raises(TypeError) as exc_info:
                loader.load_site()

            error_msg = str(exc_info.value)
            assert "is not a render_engine.Site instance" in error_msg
            assert "dict" in error_msg

    def test_non_site_object_none(self, valid_pyproject_path):
        """Test TypeError when loaded object is None."""
        module = MagicMock()
        module.app = None

        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=module):
            with pytest.raises(TypeError) as exc_info:
                loader.load_site()

            error_msg = str(exc_info.value)
            assert "is not a render_engine.Site instance" in error_msg
            assert "NoneType" in error_msg

    def test_non_site_object_class(self, valid_pyproject_path):
        """Test TypeError when loaded object is a class instead of Site."""
        class NotASite:
            pass

        module = MagicMock()
        module.app = NotASite

        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=module):
            with pytest.raises(TypeError) as exc_info:
                loader.load_site()

            error_msg = str(exc_info.value)
            assert "is not a render_engine.Site instance" in error_msg


# ============================================================================
# Edge Cases and Special Scenarios
# ============================================================================


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_sys_path_modification_adds_project_root(self, valid_pyproject_path, mock_module_with_site):
        """Test that project root is added to sys.path for imports."""
        original_sys_path = sys.path.copy()
        loader = SiteLoader(project_root=valid_pyproject_path)

        try:
            with patch("importlib.import_module", return_value=mock_module_with_site):
                loader.load_site()
                assert str(valid_pyproject_path) in sys.path
        finally:
            sys.path = original_sys_path

    def test_sys_path_not_duplicated(self, valid_pyproject_path, mock_module_with_site):
        """Test that project root is not added to sys.path if already present."""
        original_sys_path = sys.path.copy()
        sys.path.insert(0, str(valid_pyproject_path))
        original_length = len(sys.path)

        try:
            loader = SiteLoader(project_root=valid_pyproject_path)
            with patch("importlib.import_module", return_value=mock_module_with_site):
                loader.load_site()
                # sys.path should not grow (no duplicate added)
                assert len(sys.path) <= original_length + 1
        finally:
            sys.path = original_sys_path

    def test_multiple_collections_mixed_types(
        self, valid_pyproject_path, mock_site, mock_module_with_site
    ):
        """Test filtering with many mixed object types."""
        col1 = Mock(spec=Collection)
        col2 = Mock(spec=Collection)
        col3 = Mock(spec=Collection)

        mock_site.route_list = {
            "col1": col1,
            "static": "string",
            "col2": col2,
            "number": 42,
            "col3": col3,
            "none_val": None,
            "callable": lambda: None,
            "mock": Mock(),  # Regular mock, not Collection
        }

        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            collections = loader.get_collections()
            assert len(collections) == 3
            assert set(collections.keys()) == {"col1", "col2", "col3"}

    def test_get_collections_called_multiple_times_reuses_cache(
        self, valid_pyproject_path, mock_site, mock_module_with_site
    ):
        """Test that get_collections reuses cached site."""
        collection = Mock(spec=Collection)
        mock_site.route_list = {"blog": collection}

        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site) as mock_import:
            collections1 = loader.get_collections()
            collections2 = loader.get_collections()
            collections3 = loader.get_collection_names()

            # import_module should only be called once (first call to get_collections)
            assert mock_import.call_count == 1
            assert collections1 == collections2

    def test_malformed_toml_raises_error(self, temp_project_dir):
        """Test that malformed TOML raises appropriate error."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("[invalid toml content {{}")

        loader = SiteLoader(project_root=temp_project_dir)

        # tomllib will raise a parsing error
        with pytest.raises(Exception):  # Could be ValueError or similar
            loader.load_site()

    def test_pyproject_with_only_render_engine_no_cli(self, temp_project_dir):
        """Test pyproject with render-engine section but no cli subsection."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text("[tool.render-engine]\nsite_name = 'My Site'\n")

        loader = SiteLoader(project_root=temp_project_dir)

        with pytest.raises(KeyError) as exc_info:
            loader.load_site()

        error_msg = str(exc_info.value)
        assert "[tool.render-engine.cli]" in error_msg

    def test_get_collection_with_empty_slug(self, valid_pyproject_path, mock_site, mock_module_with_site):
        """Test get_collection with empty string slug."""
        mock_site.route_list = {}
        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            result = loader.get_collection("")
            assert result is None

    def test_collection_names_maintains_order(
        self, valid_pyproject_path, mock_site, mock_module_with_site
    ):
        """Test that get_collection_names returns consistent ordering."""
        # Create collections with specific order
        collections = {
            f"col_{i}": Mock(spec=Collection)
            for i in range(10)
        }
        mock_site.route_list = collections

        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            names1 = loader.get_collection_names()
            names2 = loader.get_collection_names()

            # Order should be consistent
            assert names1 == names2


# ============================================================================
# Integration-like Tests
# ============================================================================


class TestIntegration:
    """Integration-style tests combining multiple operations."""

    def test_full_workflow_load_and_access_collections(
        self, valid_pyproject_path, mock_site, mock_module_with_site
    ):
        """Test complete workflow: load site and access collections."""
        blog = Mock(spec=Collection)
        blog.slug = "blog"
        pages = Mock(spec=Collection)
        pages.slug = "pages"

        mock_site.route_list = {
            "blog": blog,
            "pages": pages,
            "static": "files",
        }

        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            # Load site
            site = loader.load_site()
            assert site is not None

            # Get all collections
            collections = loader.get_collections()
            assert len(collections) == 2

            # Get specific collection
            blog_collection = loader.get_collection("blog")
            assert blog_collection is blog

            # Get collection names
            names = loader.get_collection_names()
            assert set(names) == {"blog", "pages"}

    def test_workflow_with_invalid_config_then_fix(
        self, temp_project_dir, mock_site, mock_module_with_site
    ):
        """Test error recovery: invalid config then fixed."""
        pyproject = temp_project_dir / "pyproject.toml"

        # Start with invalid config (missing module)
        pyproject.write_text('[tool.render-engine.cli]\nsite = "app"\n')

        loader = SiteLoader(project_root=temp_project_dir)

        # Should fail
        with pytest.raises(KeyError):
            loader.load_site()

        # Fix the config
        pyproject.write_text(
            '[tool.render-engine.cli]\nmodule = "routes"\nsite = "app"\n'
        )

        # Create new loader (old one still has error state)
        loader2 = SiteLoader(project_root=temp_project_dir)

        # Should succeed now
        with patch("importlib.import_module", return_value=mock_module_with_site):
            site = loader2.load_site()
            assert site is not None

    def test_multiple_loaders_independent_caches(
        self, temp_project_dir
    ):
        """Test that multiple loader instances have independent caches."""
        # Create first valid pyproject
        pyproject1_dir = temp_project_dir / "proj1"
        pyproject1_dir.mkdir()
        pyproject1 = pyproject1_dir / "pyproject.toml"
        pyproject1.write_text(
            '[tool.render-engine.cli]\nmodule = "routes"\nsite = "app"\n'
        )

        # Create second valid pyproject
        pyproject2_dir = temp_project_dir / "proj2"
        pyproject2_dir.mkdir()
        pyproject2 = pyproject2_dir / "pyproject.toml"
        pyproject2.write_text(
            '[tool.render-engine.cli]\nmodule = "other_routes"\nsite = "other_site"\n'
        )

        loader1 = SiteLoader(project_root=pyproject1_dir)
        loader2 = SiteLoader(project_root=pyproject2_dir)

        with patch("importlib.import_module") as mock_import:
            # Create distinct mock sites
            mock_site1 = Mock(spec=Site)
            mock_site1.route_list = {}
            module1 = MagicMock()
            module1.app = mock_site1

            mock_site2 = Mock(spec=Site)
            mock_site2.route_list = {}
            module2 = MagicMock()
            module2.other_site = mock_site2

            def import_side_effect(module_name):
                if module_name == "routes":
                    return module1
                else:
                    return module2

            mock_import.side_effect = import_side_effect

            site1 = loader1.load_site()
            site2 = loader2.load_site()

            # Each loader should have its own cached site
            assert loader1._site is site1
            assert loader2._site is site2
            assert site1 is not site2


# ============================================================================
# Parametrized Tests
# ============================================================================


class TestParametrized:
    """Parametrized tests for different configurations."""

    @pytest.mark.parametrize("module_name", ["routes", "app", "main", "config", "site_module"])
    def test_load_site_with_different_module_names(self, temp_project_dir, module_name, mock_site):
        """Test loading with various module names."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text(
            f'[tool.render-engine.cli]\nmodule = "{module_name}"\nsite = "app"\n'
        )

        module = MagicMock()
        module.app = mock_site

        loader = SiteLoader(project_root=temp_project_dir)

        with patch("importlib.import_module", return_value=module) as mock_import:
            site = loader.load_site()
            assert site is mock_site
            mock_import.assert_called_once_with(module_name)

    @pytest.mark.parametrize("site_name", ["app", "site", "my_site", "application", "root"])
    def test_load_site_with_different_site_names(self, temp_project_dir, site_name, mock_site):
        """Test loading with various site variable names."""
        pyproject = temp_project_dir / "pyproject.toml"
        pyproject.write_text(
            f'[tool.render-engine.cli]\nmodule = "routes"\nsite = "{site_name}"\n'
        )

        module = MagicMock()
        setattr(module, site_name, mock_site)

        loader = SiteLoader(project_root=temp_project_dir)

        with patch("importlib.import_module", return_value=module):
            site = loader.load_site()
            assert site is mock_site

    @pytest.mark.parametrize(
        "route_list,expected_count",
        [
            ({}, 0),
            ({"col": Mock(spec=Collection)}, 1),
            (
                {
                    "col1": Mock(spec=Collection),
                    "col2": Mock(spec=Collection),
                },
                2,
            ),
            ({"col": Mock(spec=Collection), "static": "files"}, 1),
            (
                {
                    "col1": Mock(spec=Collection),
                    "col2": Mock(spec=Collection),
                    "col3": Mock(spec=Collection),
                    "static": "x",
                    "other": 42,
                },
                3,
            ),
        ],
        ids=[
            "empty",
            "single_collection",
            "multiple_collections",
            "mixed_single",
            "mixed_multiple",
        ],
    )
    def test_get_collections_various_route_lists(
        self, valid_pyproject_path, mock_site, mock_module_with_site, route_list, expected_count
    ):
        """Test get_collections with various route_list compositions."""
        mock_site.route_list = route_list
        loader = SiteLoader(project_root=valid_pyproject_path)

        with patch("importlib.import_module", return_value=mock_module_with_site):
            collections = loader.get_collections()
            assert len(collections) == expected_count
