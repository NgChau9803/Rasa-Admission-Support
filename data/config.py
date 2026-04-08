"""
Configuration for the SOICT website scraper.
"""

# Base URL
BASE_URL = "https://soict.hust.edu.vn"
API_BASE = f"{BASE_URL}/wp-json/wp/v2"

# API endpoints
POSTS_ENDPOINT = f"{API_BASE}/posts"
PAGES_ENDPOINT = f"{API_BASE}/pages"
CATEGORIES_ENDPOINT = f"{API_BASE}/categories"

# Target categories (focused scope)
TARGET_CATEGORIES = {
    27: "Giới thiệu",
    34: "Tuyển sinh",
    13: "Đào tạo",
    17: "Hệ đại học",
    16: "Hệ thạc sỹ",
    335: "Hệ kỹ sư",
    14: "Sinh viên",
    211: "Biểu mẫu",
}

# Pagination
PER_PAGE = 50  # Max allowed by WP REST API is 100

# Rate limiting (seconds)
API_DELAY = 1.0       # Delay between API requests
BROWSER_DELAY = 3.0   # Delay between browser requests

# Output paths
import os
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
POSTS_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "posts")
PAGES_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "pages")

# Content quality thresholds
MIN_MARKDOWN_LENGTH = 50  # Minimum characters for valid markdown content
MAX_SHORTCODE_RATIO = 0.3  # If shortcode artifacts exceed this ratio, use browser fallback

# Flatsome shortcode patterns that indicate poor API extraction
SHORTCODE_PATTERNS = [
    "[ux_", "[section", "[row", "[col", "[text_box",
    "[gap", "[banner", "[icon_box", "[tabbed_content",
    "[ux-menu", "[scroll-to",
]

# Request headers
HEADERS = {
    "User-Agent": "SOICT-Chatbot-Scraper/1.0 (Educational Project; contact: soict-admin)",
    "Accept": "application/json",
}
