"""
Dedicated scraper for administrative procedures and custom URLs.
Specifically targets the Student Handbook SPA (sv-ctt.hust.edu.vn) and 
additional forms/procedures omitted by the main WP API scraper.
"""

import os
import sys
import time
import re
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright
import config
from html_to_markdown import html_to_markdown
from output_writer import write_markdown_file

def scrape_sv_ctt_handbook(browser):
    """
    Scrapes the Student Handbook (Sổ tay sinh viên) from sv-ctt.hust.edu.vn
    This is an SPA, so we navigate the index, collect links, and scrape each article.
    """
    base_url = "https://sv-ctt.hust.edu.vn"
    index_url = f"{base_url}/#/so-tay-sv"
    
    print(f"\n[Handbook] Fetching index: {index_url}")
    page = browser.new_page()
    page.goto(index_url, wait_until="networkidle")
    time.sleep(3) # Wait for Vue rendering
    
    # Collect article links
    links = page.query_selector_all('a')
    article_urls = {}
    for l in links:
        href = l.get_attribute('href')
        if href and '/so-tay-sv/' in href:
            text = l.inner_text().strip()
            # href comes as `#/so-tay-sv/...`
            full_url = urljoin(base_url, href)
            # Use link text or fallback to URL part
            title = text.split("\n")[0] if "\n" in text else text
            
            # Filter out generic pagination / action texts
            if len(title) > 5 and not "Chi tiết" in title:
                article_urls[full_url] = title

    print(f"[Handbook] Found {len(article_urls)} articles.")
    
    results = []
    for url, title in article_urls.items():
        print(f"  -> Scraping: {title}")
        page.goto(url, wait_until="networkidle")
        time.sleep(2) # Give Vue routing time to paint
        
        # Look for the main article content based on Element UI classes
        content_el = page.query_selector(".app-main") or page.query_selector(".el-card__body") or page.query_selector("body")
        
        if content_el:
            html = content_el.inner_html()
            markdown = html_to_markdown(html, url)
            
            metadata = {
                "title": f"Sổ tay SV: {title}",
                "url": url,
                "categories": ["Sổ tay sinh viên", "Thủ tục hành chính"],
                "source_type": "handbook",
                "slug": f"sotaysv-{url.split('/')[-1]}",
                "extraction_method": "playwright_spa"
            }
            results.append({"metadata": metadata, "markdown": markdown})
        time.sleep(1)

    page.close()
    return results

def scrape_custom_urls(browser, urls):
    """
    Scrapes specific WordPress URLs that were missed or are important procedures.
    """
    results = []
    page = browser.new_page()
    
    for url in urls:
        print(f"\n[Custom] Fetching: {url}")
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(2)
            
            # Attempt to extract title
            title_el = str(page.title())
            title = title_el.replace(" - Viện CNTT & TT", "").replace(" - HUST", "").strip()
            
            # Find content area
            content_html = ""
            selectors = [
                "article .entry-content",
                ".entry-content",
                ".page-wrapper .row",
                "article",
                "main"
            ]
            
            for selector in selectors:
                el = page.query_selector(selector)
                if el:
                    content_html = el.inner_html()
                    if len(content_html) > 100:
                        break
            
            if content_html:
                markdown = html_to_markdown(content_html, url)
                metadata = {
                    "title": title,
                    "url": url,
                    "categories": ["Thủ tục hành chính", "Biểu mẫu"],
                    "source_type": "page",
                    "slug": f"custom-{url.split('/')[-1].replace('.html', '')}",
                    "extraction_method": "playwright"
                }
                results.append({"metadata": metadata, "markdown": markdown})
                print(f"  -> Success: {len(markdown)} chars")
            else:
                print("  -> Failed to find content block")
                
        except Exception as e:
            print(f"  -> Error: {e}")
            
    page.close()
    return results

def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    print("=" * 60)
    print("  SOICT Administrative & SPA Scraper")
    print("=" * 60)
    
    # Crucial administrative procedure links extracted from gap analysis
    custom_urls = [
        "https://soict.hust.edu.vn/hddk_hethong_qtdh",
        "https://soict.hust.edu.vn/doncongnhan_hptuongduong",
        "https://soict.hust.edu.vn/donxindangky_hocphan_tuongduongthaythe",
        "https://soict.hust.edu.vn/donxindangky_lopday",
        "https://soict.hust.edu.vn/donxinhuy_dangkylop",
        "https://soict.hust.edu.vn/donxinmolop_Project",
        "https://soict.hust.edu.vn/donxinmolop_bosung_canhan",
        "https://soict.hust.edu.vn/donxinmolop_bosung_tapthe",
        "https://soict.hust.edu.vn/donxinmuon_hoso",
        "https://soict.hust.edu.vn/quy-trinh-dang-ky-va-xac-nhan-hoc-phan-tuong-duong-thay-the.html",
        "https://soict.hust.edu.vn/sv_cntt_canbiet",
        "https://soict.hust.edu.vn/template_datn",
    ]
    
    all_results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # 1. Scrape specific custom forms / procedures from SOICT domain
        results = scrape_custom_urls(browser, custom_urls)
        all_results.extend(results)
        
        # 2. Scrape the full student handbook SPA
        results = scrape_sv_ctt_handbook(browser)
        all_results.extend(results)
        
        browser.close()
        
    print(f"\n{'='*60}")
    print("Writing output files...")
    
    out_dir = os.path.join(config.OUTPUT_DIR, "procedures")
    os.makedirs(out_dir, exist_ok=True)
    
    for item in all_results:
        metadata = item["metadata"]
        markdown = item["markdown"]
        filepath = write_markdown_file(markdown, metadata, out_dir)
        print(f"  ✓ {os.path.basename(filepath)} ({len(markdown)} chars)")
        
    print(f"{'='*60}")
    print(f"Administrative Scrape Complete! Saved {len(all_results)} files to {out_dir}")

if __name__ == "__main__":
    main()
