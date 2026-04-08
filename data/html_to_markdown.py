"""
HTML to Markdown converter with Flatsome cleanup.
Handles WordPress/Flatsome theme HTML and converts to clean GitHub Flavored Markdown.
"""

import re
from bs4 import BeautifulSoup, Comment
from markdownify import markdownify as md, MarkdownConverter


class SoictMarkdownConverter(MarkdownConverter):
    """Custom markdownify converter with better table and link handling."""

    def convert_table(self, el, text, convert_as_inline):
        """Ensure tables are converted to proper GFM format."""
        return super().convert_table(el, text, convert_as_inline)

    def convert_a(self, el, text, convert_as_inline):
        """Clean up links - keep meaningful ones, strip empty anchors."""
        href = el.get("href", "")
        if not href or href.startswith("#") or not text.strip():
            return text
        # Clean up escaped characters in URL
        href = href.replace("\\/", "/")
        return f"[{text.strip()}]({href})"


def clean_html_before_conversion(html_content: str) -> str:
    """
    Pre-process HTML to remove Flatsome noise before Markdown conversion.
    
    Args:
        html_content: Raw HTML string from WordPress API or browser
        
    Returns:
        Cleaned HTML string ready for Markdown conversion
    """
    soup = BeautifulSoup(html_content, "lxml")

    # 1. Remove all <style> blocks
    for style in soup.find_all("style"):
        style.decompose()

    # 2. Remove all <script> blocks
    for script in soup.find_all("script"):
        script.decompose()

    # 3. Remove HTML comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # 4. Remove SVG elements (decorative dividers)
    for svg in soup.find_all("svg"):
        svg.decompose()

    # 5. Remove Flatsome shape dividers
    for divider in soup.find_all("div", class_=re.compile(r"ux-shape-divider")):
        divider.decompose()

    # 6. Remove empty gap elements
    for gap in soup.find_all("div", class_=re.compile(r"gap-element")):
        gap.decompose()

    # 7. Remove scroll-to spans (navigation markers)
    for scroll in soup.find_all("span", class_="scroll-to"):
        scroll.decompose()

    # 8. Remove decorative images (icons, logos repeated)
    for img in soup.find_all("img"):
        src = img.get("src", "")
        # Keep content images, remove decorative icons
        if any(pattern in src for pattern in ["star-icon", "star-2.png", "Frame-100000"]):
            img.decompose()

    # 9. Remove border dividers
    for border in soup.find_all("div", class_="is-border"):
        border.decompose()

    # 10. Remove screen reader only content
    for sr in soup.find_all("div", class_="screen-reader-response"):
        sr.decompose()

    # 11. Remove forms (contact forms)
    for form in soup.find_all("form"):
        form.decompose()
    for wpcf7 in soup.find_all("div", class_=re.compile(r"wpcf7")):
        wpcf7.decompose()

    # 12. Remove height-fix invisible elements
    for hfix in soup.find_all("div", class_="height-fix"):
        hfix.decompose()

    # 13. Unwrap Flatsome layout containers but keep their text content
    layout_classes = [
        "section-content", "col-inner", "icon-box-text",
        "banner-layers", "text-box-content", "box-text-inner",
    ]
    for cls in layout_classes:
        for container in soup.find_all("div", class_=re.compile(cls)):
            container.unwrap()

    return str(soup)


def html_to_markdown(html_content: str, page_url: str = "") -> str:
    """
    Convert HTML content to clean GitHub Flavored Markdown.
    
    Args:
        html_content: HTML string to convert
        page_url: Optional URL of the page (for resolving relative links)
        
    Returns:
        Clean Markdown string
    """
    # Step 1: Clean HTML
    cleaned_html = clean_html_before_conversion(html_content)

    # Step 2: Convert to Markdown using markdownify
    markdown_text = md(
        cleaned_html,
        heading_style="ATX",
        bullets="-",
        strip=["img", "input", "button", "select", "textarea", "noscript"],
    )

    # Step 3: Post-process Markdown
    markdown_text = post_process_markdown(markdown_text)

    return markdown_text


def post_process_markdown(text: str) -> str:
    """
    Clean up the generated Markdown text.
    
    Args:
        text: Raw Markdown string
        
    Returns:
        Cleaned Markdown string
    """
    # Remove excessive blank lines (more than 2 consecutive)
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    # Remove lines that are only whitespace
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        if line.strip() == "" and cleaned_lines and cleaned_lines[-1].strip() == "":
            continue  # Skip consecutive blank lines
        cleaned_lines.append(line.rstrip())
    text = "\n".join(cleaned_lines)

    # Remove leftover HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&nbsp;", " ")
    text = text.replace("&#8211;", "–")
    text = text.replace("&#8230;", "…")

    # Remove leftover inline styles
    text = re.sub(r'\{[^}]*style=[^}]*\}', '', text)
    
    # Remove leftover CSS class references
    text = re.sub(r'\{[^}]*class=[^}]*\}', '', text)

    # Clean up shortcode remnants
    text = re.sub(r'\[/?ux_[^\]]*\]', '', text)
    text = re.sub(r'\[/?section[^\]]*\]', '', text)
    text = re.sub(r'\[/?row[^\]]*\]', '', text)
    text = re.sub(r'\[/?col[^\]]*\]', '', text)
    text = re.sub(r'\[/?text_box[^\]]*\]', '', text)
    text = re.sub(r'\[/?gap[^\]]*\]', '', text)
    text = re.sub(r'\[/?banner[^\]]*\]', '', text)
    text = re.sub(r'\[/?icon_box[^\]]*\]', '', text)

    # Final trim
    text = text.strip()

    return text


def assess_content_quality(html_content: str, markdown_content: str) -> dict:
    """
    Assess if the API-extracted content is good enough or needs browser fallback.
    
    Args:
        html_content: Original HTML
        markdown_content: Converted Markdown
        
    Returns:
        Dict with 'needs_browser': bool and 'reason': str
    """
    from config import MIN_MARKDOWN_LENGTH, SHORTCODE_PATTERNS, MAX_SHORTCODE_RATIO

    result = {"needs_browser": False, "reason": ""}

    # Check 1: Markdown too short
    if len(markdown_content.strip()) < MIN_MARKDOWN_LENGTH:
        result["needs_browser"] = True
        result["reason"] = f"Content too short ({len(markdown_content)} chars)"
        return result

    # Check 2: Too many shortcode remnants in the HTML
    html_lower = html_content.lower()
    shortcode_count = sum(html_lower.count(pattern.lower()) for pattern in SHORTCODE_PATTERNS)
    total_tags = html_lower.count("<")
    
    if total_tags > 0:
        shortcode_ratio = shortcode_count / max(total_tags, 1)
        if shortcode_ratio > MAX_SHORTCODE_RATIO:
            result["needs_browser"] = True
            result["reason"] = f"High shortcode ratio ({shortcode_ratio:.2f})"
            return result

    # Check 3: Too much CSS/style content relative to text
    style_blocks = len(re.findall(r'<style[^>]*>.*?</style>', html_content, re.DOTALL))
    if style_blocks > 10 and len(markdown_content) < 500:
        result["needs_browser"] = True
        result["reason"] = f"Many style blocks ({style_blocks}) with little content"
        return result

    return result
