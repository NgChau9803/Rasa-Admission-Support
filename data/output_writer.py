"""
Output writer for scraped SOICT content.
Writes Markdown files with YAML front-matter metadata and generates a manifest.
"""

import os
import json
import re
from datetime import datetime


def sanitize_filename(slug: str) -> str:
    """
    Convert a URL slug to a safe filename.
    
    Args:
        slug: WordPress post/page slug
        
    Returns:
        Safe filename string
    """
    # Remove any characters that aren't alphanumeric, hyphens, or underscores
    safe = re.sub(r'[^\w\-]', '-', slug)
    # Collapse multiple hyphens
    safe = re.sub(r'-+', '-', safe)
    # Trim to reasonable length
    safe = safe[:100].strip('-')
    return safe


def write_markdown_file(
    content: str,
    metadata: dict,
    output_dir: str,
) -> str:
    """
    Write a single Markdown file with YAML front-matter.
    
    Args:
        content: Markdown content body
        metadata: Dict with keys: title, url, last_modified, categories, source_type
        output_dir: Directory to write the file to
        
    Returns:
        Path to the written file
    """
    os.makedirs(output_dir, exist_ok=True)

    slug = metadata.get("slug", "untitled")
    filename = f"{sanitize_filename(slug)}.md"
    filepath = os.path.join(output_dir, filename)

    # Build YAML front-matter
    front_matter = build_front_matter(metadata)

    # Combine front-matter and content
    full_content = f"{front_matter}\n{content}\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(full_content)

    return filepath


def build_front_matter(metadata: dict) -> str:
    """
    Build YAML front-matter string from metadata dict.
    
    Args:
        metadata: Content metadata
        
    Returns:
        YAML front-matter string with --- delimiters
    """
    lines = ["---"]

    title = metadata.get("title", "Untitled")
    # Escape quotes in title
    title = title.replace('"', '\\"')
    lines.append(f'title: "{title}"')

    if "url" in metadata:
        lines.append(f'url: "{metadata["url"]}"')

    if "last_modified" in metadata:
        lines.append(f'last_modified: "{metadata["last_modified"]}"')

    if "categories" in metadata and metadata["categories"]:
        cats = metadata["categories"]
        if isinstance(cats, list):
            cats_str = ", ".join(f'"{c}"' for c in cats)
            lines.append(f"categories: [{cats_str}]")
        else:
            lines.append(f'categories: ["{cats}"]')

    if "source_type" in metadata:
        lines.append(f'source_type: "{metadata["source_type"]}"')

    if "wp_id" in metadata:
        lines.append(f"wp_id: {metadata['wp_id']}")

    scrape_date = datetime.now().strftime("%Y-%m-%d")
    lines.append(f'scrape_date: "{scrape_date}"')

    if "extraction_method" in metadata:
        lines.append(f'extraction_method: "{metadata["extraction_method"]}"')

    lines.append("---")
    return "\n".join(lines)


def write_manifest(items: list, output_dir: str) -> str:
    """
    Write a manifest.json index of all scraped documents.
    
    Args:
        items: List of dicts, each with metadata about a scraped item
        output_dir: Root output directory
        
    Returns:
        Path to the manifest file
    """
    manifest_path = os.path.join(output_dir, "manifest.json")

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "total_items": len(items),
        "items": items,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return manifest_path
