"""
CLI entry point for the SOICT website scraper.
Usage: python run_scraper.py [options]
"""

import argparse
import os
import sys
import time
import io

# Fix Windows console encoding for Vietnamese characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add the data directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from scraper import fetch_categories, fetch_posts, fetch_pages, process_items
from output_writer import write_markdown_file, write_manifest


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape SOICT website for RAG chatbot data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_scraper.py                      # Scrape all target categories + pages
  python run_scraper.py --categories 34      # Scrape only Tuyển sinh
  python run_scraper.py --categories 34 27   # Scrape Tuyển sinh + Giới thiệu
  python run_scraper.py --pages-only         # Scrape only pages
  python run_scraper.py --posts-only         # Scrape only posts
  python run_scraper.py --force-browser      # Force browser for all items
  python run_scraper.py --no-browser         # Skip browser fallback entirely
        """,
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        type=int,
        default=None,
        help="Category IDs to scrape (default: all target categories)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=config.OUTPUT_DIR,
        help=f"Output directory (default: {config.OUTPUT_DIR})",
    )
    parser.add_argument(
        "--pages-only",
        action="store_true",
        help="Scrape only pages, no posts",
    )
    parser.add_argument(
        "--posts-only",
        action="store_true",
        help="Scrape only posts, no pages",
    )
    parser.add_argument(
        "--force-browser",
        action="store_true",
        help="Force browser extraction for all items (slow)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Skip browser fallback entirely (faster but may miss some content)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    start_time = time.time()

    print("=" * 60)
    print("  SOICT Website Scraper")
    print("  Target: soict.hust.edu.vn")
    print("=" * 60)

    # Step 1: Fetch category map
    category_map = fetch_categories()

    # Step 2: Collect items to process
    all_items = []

    if not args.pages_only:
        cat_ids = args.categories or list(config.TARGET_CATEGORIES.keys())
        # Validate category IDs
        valid_cats = [c for c in cat_ids if c in config.TARGET_CATEGORIES]
        if not valid_cats:
            print(f"[WARN] No valid category IDs found in {cat_ids}")
            print(f"       Valid categories: {list(config.TARGET_CATEGORIES.keys())}")
        else:
            posts = fetch_posts(valid_cats)
            all_items.extend(posts)

    if not args.posts_only:
        pages = fetch_pages()
        all_items.extend(pages)

    if not all_items:
        print("[ERROR] No items found to process!")
        sys.exit(1)

    # Step 3: Process items (extract, clean, convert)
    if args.no_browser:
        # Temporarily set a very high threshold to skip browser fallback
        config.MAX_SHORTCODE_RATIO = 999
        config.MIN_MARKDOWN_LENGTH = 0

    processed = process_items(all_items, category_map)

    # Step 4: Write output files
    print(f"\n{'='*60}")
    print("Writing output files...")
    print(f"{'='*60}\n")

    manifest_items = []
    posts_dir = os.path.join(args.output_dir, "posts")
    pages_dir = os.path.join(args.output_dir, "pages")

    for item in processed:
        metadata = item["metadata"]
        markdown = item["markdown"]

        # Determine output subdirectory
        if metadata["source_type"] == "post":
            out_dir = posts_dir
        else:
            out_dir = pages_dir

        filepath = write_markdown_file(markdown, metadata, out_dir)
        rel_path = os.path.relpath(filepath, args.output_dir)

        manifest_entry = {
            "title": metadata["title"],
            "slug": metadata["slug"],
            "url": metadata["url"],
            "last_modified": metadata["last_modified"],
            "categories": metadata["categories"],
            "source_type": metadata["source_type"],
            "extraction_method": metadata.get("extraction_method", "api"),
            "file_path": rel_path,
            "content_length": len(markdown),
        }
        manifest_items.append(manifest_entry)

        print(f"  ✓ {rel_path} ({len(markdown)} chars)")

    # Step 5: Write manifest
    manifest_path = write_manifest(manifest_items, args.output_dir)

    # Summary
    elapsed = time.time() - start_time
    api_count = sum(1 for m in manifest_items if m["extraction_method"] == "api")
    browser_count = sum(1 for m in manifest_items if m["extraction_method"] == "browser")

    print(f"\n{'='*60}")
    print("  SCRAPING COMPLETE")
    print(f"{'='*60}")
    print(f"  Total items:      {len(manifest_items)}")
    print(f"  API extracted:    {api_count}")
    print(f"  Browser fallback: {browser_count}")
    print(f"  Output dir:       {args.output_dir}")
    print(f"  Manifest:         {manifest_path}")
    print(f"  Time elapsed:     {elapsed:.1f}s")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
