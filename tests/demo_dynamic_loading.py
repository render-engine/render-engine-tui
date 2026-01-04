#!/usr/bin/env python3
"""Test script to demonstrate dynamic collection loading from render-engine sites.

This script shows how the Content Editor TUI discovers collections from
[tool.render-engine] configuration in pyproject.toml.

Usage:
    # Test with kjaymiller.com site
    python test_dynamic_loading.py /Users/jay.miller/kjaymiller.com

    # Test with current directory
    python test_dynamic_loading.py
"""

import sys
from pathlib import Path
from render_engine_tui.site_loader import SiteLoader


def main(project_root: str = None):
    """Demonstrate dynamic collection loading.

    Args:
        project_root: Path to render-engine project (defaults to current directory)
    """
    try:
        # Initialize configuration loader
        if project_root:
            config = RenderEngineConfig(Path(project_root))
            print(f"Loading configuration from: {project_root}")
        else:
            config = RenderEngineConfig()
            print(f"Loading configuration from: {config.project_root}")

        print("\n" + "=" * 80)
        print("STEP 1: Read pyproject.toml")
        print("=" * 80)

        # Show configuration
        raw_config = config.config
        print(f"\n[tool.render-engine] configuration:")
        for key, value in raw_config.items():
            print(f"  {key}: {value}")

        # Show site reference
        module_name, site_name = config.get_site_reference()
        print(f"\nSite reference:")
        print(f"  Module: {module_name}")
        print(f"  Site variable: {site_name}")
        print(f"  Full import: from {module_name} import {site_name}")

        print("\n" + "=" * 80)
        print("STEP 2: Dynamically Import Site")
        print("=" * 80)

        # Load the site
        site = config.load_site()
        print(f"\nSuccessfully imported: {module_name}.{site_name}")
        print(f"Site instance: {site}")
        print(f"Site type: {type(site)}")

        # Show site metadata
        print(f"\nSite metadata:")
        print(f"  SITE_TITLE: {site.site_vars.get('SITE_TITLE', 'Not set')}")
        print(f"  SITE_URL: {site.site_vars.get('SITE_URL', 'Not set')}")
        print(f"  Output path: {site.output_path}")
        print(f"  Template path: {site.template_path}")

        print("\n" + "=" * 80)
        print("STEP 3: Query Site for Collections")
        print("=" * 80)

        # Show all routes
        print(f"\nAll routes in site.route_list ({len(site.route_list)}):")
        for slug, entry in site.route_list.items():
            print(f"  - {slug}: {type(entry).__name__}")

        # Get collections only
        collections = config.get_collections()
        print(f"\nFiltered Collections ({len(collections)}):")
        for slug, collection in collections.items():
            print(f"  - {slug}: {collection._title}")

        print("\n" + "=" * 80)
        print("STEP 4: Extract Collection Metadata")
        print("=" * 80)

        # Get detailed metadata
        metadata = config.get_collection_metadata()
        for slug, meta in metadata.items():
            print(f"\n{slug.upper()}:")
            print(f"  Title: {meta['title']}")
            print(f"  Parser: {meta['parser']}")
            print(f"  Content Manager: {meta['content_manager']}")
            print(f"  Routes: {meta['routes']}")
            print(f"  Has Archive: {meta['has_archive']}")
            print(f"  Items per page: {meta['items_per_page']}")

        print("\n" + "=" * 80)
        print("STEP 5: Filter PostgreSQL Collections")
        print("=" * 80)

        # Get only PostgreSQL collections
        try:
            pg_collections = config.get_postgres_collections()
            print(f"\nPostgreSQL Collections ({len(pg_collections)}):")
            for slug, collection in pg_collections.items():
                print(f"  - {slug}: {collection._title}")
                print(f"    Content Manager: {collection.ContentManager.__name__}")

                # Try to get database table
                if hasattr(collection, '_metadata_attrs'):
                    table = collection._metadata_attrs().get('table', slug)
                    print(f"    Database table: {table}")
        except ImportError as e:
            print(f"\nNote: render-engine-pg not installed, skipping PostgreSQL filter")
            print(f"  Error: {e}")

        print("\n" + "=" * 80)
        print("STEP 6: Generate UI Mappings")
        print("=" * 80)

        # Generate mappings for DatabaseManager
        print("\nAVAILABLE_COLLECTIONS mapping:")
        available_collections = {
            slug: meta['title']
            for slug, meta in metadata.items()
        }
        for slug, title in available_collections.items():
            print(f"  \"{slug}\": \"{title}\"")

        print("\nJUNCTION_TABLES mapping:")
        junction_tables = {
            slug: f"{slug}_tags"
            for slug in metadata.keys()
        }
        for slug, table in junction_tables.items():
            print(f"  \"{slug}\": \"{table}\"")

        print("\nID_COLUMN_NAMES mapping:")
        id_columns = {
            slug: f"{slug}_id"
            for slug in metadata.keys()
        }
        for slug, column in id_columns.items():
            print(f"  \"{slug}\": \"{column}\"")

        print("\n" + "=" * 80)
        print("SUCCESS!")
        print("=" * 80)
        print(f"\nDiscovered {len(collections)} collections from render-engine site.")
        print("These collections can be used in the Content Editor TUI.")

    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("\nMake sure you're running from a render-engine project directory")
        print("or provide a path to one as an argument.")
        sys.exit(1)

    except KeyError as e:
        print(f"\nError: {e}")
        print("\nYour pyproject.toml is missing [tool.render-engine] configuration.")
        print("\nAdd this to your pyproject.toml:")
        print("  [tool.render-engine.cli]")
        print("  module = \"routes\"")
        print("  site = \"app\"")
        sys.exit(1)

    except ImportError as e:
        print(f"\nError: {e}")
        print("\nCould not import the site module.")
        print("Make sure the module specified in [tool.render-engine.cli] exists")
        print("and can be imported from the project root.")
        sys.exit(1)

    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()
