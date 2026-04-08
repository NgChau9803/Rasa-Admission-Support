"""
Main scraper engine for the SOICT website.
Handles API discovery, content extraction, and browser fallback.
"""

import time
import json
import requests
from html import unescape

import config
from html_to_markdown import html_to_markdown, assess_content_quality


def fetch_categories() -> dict:
    """
    Fetch all categories from the WordPress API and build an ID-to-name map.
    
    Returns:
        Dict mapping category ID (int) to category name (str)
    """
    print("[Discovery] Fetching categories...")
    categories = {}
    page = 1

    while True:
        params = {
            "per_page": 100,
            "page": page,
            "_fields": "id,name,slug,count",
        }
        response = requests.get(
            config.CATEGORIES_ENDPOINT,
            params=params,
            headers=config.HEADERS,
        )
        if response.status_code != 200:
            break

        data = response.json()
        if not data:
            break

        for cat in data:
            categories[cat["id"]] = {
                "name": unescape(cat["name"]),
                "slug": cat["slug"],
                "count": cat["count"],
            }

        page += 1
        time.sleep(config.API_DELAY)

    print(f"[Discovery] Found {len(categories)} categories")
    return categories


def fetch_posts(category_ids: list = None) -> list:
    """
    Fetch posts from the WordPress API, optionally filtered by categories.
    
    Args:
        category_ids: List of category IDs to filter by. If None, uses config.TARGET_CATEGORIES
        
    Returns:
        List of post dicts with content
    """
    if category_ids is None:
        category_ids = list(config.TARGET_CATEGORIES.keys())

    all_posts = []

    for cat_id in category_ids:
        cat_name = config.TARGET_CATEGORIES.get(cat_id, f"Category {cat_id}")
        print(f"\n[Posts] Fetching category: {cat_name} (ID: {cat_id})")
        page = 1

        while True:
            params = {
                "per_page": config.PER_PAGE,
                "page": page,
                "categories": cat_id,
                "_fields": "id,title,link,modified,slug,categories,content",
            }

            try:
                response = requests.get(
                    config.POSTS_ENDPOINT,
                    params=params,
                    headers=config.HEADERS,
                )
            except requests.RequestException as e:
                print(f"  [ERROR] Request failed: {e}")
                break

            if response.status_code == 400:
                # No more pages
                break
            elif response.status_code != 200:
                print(f"  [WARN] Status {response.status_code}")
                break

            data = response.json()
            if not data:
                break

            for post in data:
                post["_source_type"] = "post"
                post["_primary_category"] = cat_id
                all_posts.append(post)

            total_pages = int(response.headers.get("X-WP-TotalPages", 1))
            print(f"  Page {page}/{total_pages} - Got {len(data)} posts")

            if page >= total_pages:
                break

            page += 1
            time.sleep(config.API_DELAY)

    # Deduplicate (posts can appear in multiple categories)
    seen_ids = set()
    unique_posts = []
    for post in all_posts:
        if post["id"] not in seen_ids:
            seen_ids.add(post["id"])
            unique_posts.append(post)

    print(f"\n[Posts] Total unique posts: {len(unique_posts)}")
    return unique_posts


def fetch_pages() -> list:
    """
    Fetch all pages from the WordPress API.
    
    Returns:
        List of page dicts with content
    """
    print("\n[Pages] Fetching all pages...")
    all_pages = []
    page = 1

    while True:
        params = {
            "per_page": config.PER_PAGE,
            "page": page,
            "_fields": "id,title,link,modified,slug,content,parent",
        }

        try:
            response = requests.get(
                config.PAGES_ENDPOINT,
                params=params,
                headers=config.HEADERS,
            )
        except requests.RequestException as e:
            print(f"  [ERROR] Request failed: {e}")
            break

        if response.status_code == 400:
            break
        elif response.status_code != 200:
            print(f"  [WARN] Status {response.status_code}")
            break

        data = response.json()
        if not data:
            break

        for pg in data:
            pg["_source_type"] = "page"
        all_pages.extend(data)

        total_pages = int(response.headers.get("X-WP-TotalPages", 1))
        print(f"  Page {page}/{total_pages} - Got {len(data)} pages")

        if page >= total_pages:
            break

        page += 1
        time.sleep(config.API_DELAY)

    print(f"[Pages] Total pages: {len(all_pages)}")
    return all_pages


def extract_content_api(item: dict, category_map: dict) -> dict:
    """
    Extract and convert content from a WordPress API item.
    
    Args:
        item: Post or page dict from the API
        category_map: ID-to-name mapping for categories
        
    Returns:
        Dict with 'markdown', 'metadata', 'needs_browser', 'quality_info'
    """
    title = unescape(item["title"]["rendered"])
    html_content = item["content"]["rendered"]
    source_type = item.get("_source_type", "post")

    # Resolve category names
    cat_ids = item.get("categories", [])
    cat_names = []
    for cid in cat_ids:
        if cid in category_map:
            cat_names.append(category_map[cid]["name"])
        elif cid in config.TARGET_CATEGORIES:
            cat_names.append(config.TARGET_CATEGORIES[cid])

    # Convert HTML to Markdown
    markdown = html_to_markdown(html_content, item.get("link", ""))

    # Assess quality
    quality = assess_content_quality(html_content, markdown)

    metadata = {
        "title": title,
        "url": item.get("link", ""),
        "last_modified": item.get("modified", ""),
        "categories": cat_names,
        "source_type": source_type,
        "slug": item.get("slug", "untitled"),
        "wp_id": item.get("id"),
        "extraction_method": "api",
    }

    return {
        "markdown": markdown,
        "metadata": metadata,
        "needs_browser": quality["needs_browser"],
        "quality_info": quality,
    }


def extract_content_browser(url: str) -> str:
    """
    Extract content using a headless browser (Playwright) for Flatsome-heavy pages.
    
    Args:
        url: Full URL of the page to render
        
    Returns:
        Extracted HTML content from the page's main content area
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [WARN] Playwright not available, skipping browser extraction")
        return ""

    print(f"  [Browser] Rendering: {url}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait for content to render
            page.wait_for_timeout(2000)

            # Try to find the main content area
            content_html = ""
            selectors = [
                "article .entry-content",
                ".entry-content",
                ".page-wrapper .row",
                "article",
                ".post-content",
                "main",
            ]

            for selector in selectors:
                element = page.query_selector(selector)
                if element:
                    content_html = element.inner_html()
                    if len(content_html) > 100:
                        break

            browser.close()
            return content_html

    except Exception as e:
        print(f"  [ERROR] Browser extraction failed: {e}")
        return ""


def process_items(items: list, category_map: dict) -> list:
    """
    Process a list of API items: extract content, apply quality checks,
    and use browser fallback when needed.
    
    Args:
        items: List of post/page dicts
        category_map: Category ID-to-name mapping
        
    Returns:
        List of processed item dicts with 'markdown' and 'metadata'
    """
    processed = []
    browser_needed = []

    print(f"\n{'='*60}")
    print(f"Processing {len(items)} items...")
    print(f"{'='*60}\n")

    for i, item in enumerate(items, 1):
        title = unescape(item["title"]["rendered"])
        print(f"[{i}/{len(items)}] {title}")

        result = extract_content_api(item, category_map)

        if result["needs_browser"]:
            reason = result["quality_info"]["reason"]
            print(f"  → Needs browser fallback: {reason}")
            browser_needed.append((item, result))
        else:
            char_count = len(result["markdown"])
            print(f"  → API extraction OK ({char_count} chars)")
            processed.append(result)

    # Process browser fallback items
    if browser_needed:
        print(f"\n{'='*60}")
        print(f"Browser fallback for {len(browser_needed)} items...")
        print(f"{'='*60}\n")

        for i, (item, api_result) in enumerate(browser_needed, 1):
            title = unescape(item["title"]["rendered"])
            url = item.get("link", "")
            print(f"[{i}/{len(browser_needed)}] {title}")

            browser_html = extract_content_browser(url)
            if browser_html:
                markdown = html_to_markdown(browser_html, url)
                if len(markdown.strip()) > len(api_result["markdown"].strip()):
                    api_result["markdown"] = markdown
                    api_result["metadata"]["extraction_method"] = "browser"
                    print(f"  → Browser extraction better ({len(markdown)} chars)")
                else:
                    print(f"  → Keeping API result (browser wasn't better)")
            else:
                print(f"  → Browser extraction failed, keeping API result")

            api_result["needs_browser"] = False
            processed.append(api_result)

            time.sleep(config.BROWSER_DELAY)

    return processed
