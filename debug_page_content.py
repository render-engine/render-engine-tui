#!/usr/bin/env python
"""Debug script to understand how Page objects expose content.

This script creates Page objects with different parsers and inspects
their content-related attributes to understand:
1. What `content` stores (raw vs processed)
2. What `_content` returns (property)
3. Whether there's a `_raw_content` or `raw_content` attribute
"""

from render_engine import Page
from render_engine_markdown import MarkdownPageParser
from render_engine_parser import BasePageParser


def inspect_page(page: Page, label: str):
    """Inspect all content-related attributes of a Page."""
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"{'='*60}")

    # Show all attributes
    attrs = [attr for attr in dir(page) if not attr.startswith('__')]
    print(f"\nAll attributes: {attrs[:20]}...")  # First 20 to avoid clutter

    # Inspect specific content attributes
    print("\n--- Content Storage ---")
    if hasattr(page, 'content'):
        print(f"page.content (raw): {repr(page.content[:100])}...")
        print(f"type(page.content): {type(page.content)}")
    else:
        print("page.content: NOT PRESENT")

    print("\n--- Content Property (_content) ---")
    if hasattr(page, '_content'):
        content_val = page._content
        print(f"page._content (property): {repr(str(content_val)[:100])}...")
        print(f"type(page._content): {type(content_val)}")
    else:
        print("page._content: NOT PRESENT")

    # Check for other content attributes
    print("\n--- Other Content Attributes ---")
    for attr in ['_raw_content', 'raw_content', 'rendered_content']:
        if hasattr(page, attr):
            val = getattr(page, attr)
            print(f"page.{attr}: {repr(str(val)[:100] if val else None)}...")
        else:
            print(f"page.{attr}: NOT PRESENT")


def main():
    """Test different parser types."""

    # Test content with markdown
    markdown_content = """---
title: Test Post
slug: test-post
date: 2025-01-01
---

# Hello World

This is **markdown** content with _formatting_.

- List item 1
- List item 2
"""

    print("\n" + "="*60)
    print("TESTING: BasePageParser (no processing)")
    print("="*60)
    base_page = Page(content=markdown_content, Parser=BasePageParser)
    inspect_page(base_page, "BasePageParser Page")

    print("\n" + "="*60)
    print("TESTING: MarkdownPageParser (processes markdown)")
    print("="*60)
    md_page = Page(content=markdown_content, Parser=MarkdownPageParser)
    inspect_page(md_page, "MarkdownPageParser Page")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("\nBasePageParser:")
    print(f"  content attribute: {type(base_page.content).__name__}")
    print(f"  _content property: {type(base_page._content).__name__}")

    print("\nMarkdownPageParser:")
    print(f"  content attribute: {type(md_page.content).__name__}")
    print(f"  _content property: {type(md_page._content).__name__}")

    print("\n" + "="*60)
    print("KEY FINDINGS")
    print("="*60)
    print("""
For TUI preview (showing editable raw markdown):
- Use: page.content (always contains raw markdown string)
- NOT: page._content (property that calls Parser.parse(), returns processed HTML)

The _content property is defined in Page class (page.py:246):
    @property
    def _content(self) -> Any:
        return self.Parser.parse(self.content, extras=...)

So:
- page.content = raw markdown string (stored during __init__)
- page._content = Parser.parse(page.content) = processed HTML/content
""")


if __name__ == "__main__":
    main()
