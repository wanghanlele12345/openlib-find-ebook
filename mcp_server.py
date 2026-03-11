import os, sys, glob
base_dir = os.path.dirname(os.path.abspath(__file__))
site_packages_pattern = os.path.join(base_dir, "venv", "lib", "python*", "site-packages")
site_packages_dirs = glob.glob(site_packages_pattern)
if site_packages_dirs:
    sys.path.insert(0, site_packages_dirs[0])

from fastmcp import FastMCP
from scraper import Scraper
import asyncio
import json

# Initialize FastMCP
mcp = FastMCP("Openlib Book Finder")
scraper = Scraper()

# Default path from environment or common location
DEFAULT_ROOT = "/Users/mac/Documents/HW/我独自阅读"

@mcp.tool()
async def search_books(query: str, extension: str = "epub"):
    """Search for books on Anna's Archive. Returns a list of potential matches."""
    results = await scraper.search(query, file_type=extension)
    return json.dumps(results, indent=2, ensure_ascii=False)

@mcp.tool()
async def resolve_download_link(md5_or_url: str):
    """Resolves a book's MD5 or detail URL to a direct download link."""
    url = md5_or_url
    if not url.startswith("http"):
        url = f"https://annas-archive.gl/md5/{md5_or_url}"
    
    info = await scraper.get_book_info(url)
    if not info or not info.get('mirrors'):
        return "No mirror links found for this book."
    
    # Try the first mirror
    resolved = await scraper.resolve_mirror_link(info['mirrors'][0])
    return json.dumps({"info": info, "resolved_link": resolved}, indent=2, ensure_ascii=False)

@mcp.tool()
async def download_book(url: str, category: str, author: str, filename: str = None):
    """Downloads a book and saves it in a structured directory: root/category/author/filename."""
    target_dir = scraper.prepare_structured_dir(DEFAULT_ROOT, category, author)
    file_path = await scraper.download_file(url, dest_folder=target_dir, filename=filename)
    if file_path:
        return f"Success: Book downloaded to {file_path}"
    return "Error: Download failed."

@mcp.tool()
async def convert_and_split(file_path: str):
    """Converts a book (EPUB/PDF) to Markdown and splits it into chapters."""
    result = await scraper.convert_to_markdown(file_path)
    if result:
        return result
    return "Error: Conversion failed."

@mcp.tool()
async def find_and_save_book(query: str, category: str = "其他", author: str = None, extension: str = "epub"):
    """
    Complete workflow: Search for a book, download it to the specified category, 
    and convert it to Markdown.
    """
    # Redirect print to stderr for MCP safety
    def log(msg):
        print(f"[*] {msg}", file=sys.stderr)

    log(f"Starting full workflow for: {query}")
    
    # 1. Search
    results = await scraper.search(query, file_type=extension)
    if not results:
        return f"Error: No books found for query '{query}'"
    
    book = results[0] # Take first result
    book_title = book['title']
    book_author = author or book['author'] or "未知作者"
    
    log(f"Found book: {book_title} by {book_author}")
    
    # 2. Get info and resolve link
    info = await scraper.get_book_info(book['link'])
    if not info or not info.get('mirrors'):
        return f"Error: Could not find download mirrors for {book_title}"
    
    resolved_link = None
    for mirror in info['mirrors']:
        log(f"Attempting to resolve mirror: {mirror}")
        resolved_link = await scraper.resolve_mirror_link(mirror)
        if resolved_link:
            break
            
    if not resolved_link:
        return f"Error: Failed to resolve a working download link for {book_title}"
    
    # 3. Download
    target_dir = scraper.prepare_structured_dir(DEFAULT_ROOT, category, book_author)
    filename = "".join([c for c in book_title if c.isalnum() or c in "._- "]).strip() + f".{extension}"
    
    log(f"Downloading to: {target_dir}")
    file_path = await scraper.download_file(resolved_link, dest_folder=target_dir, filename=filename)
    
    if not file_path:
        return f"Error: Download failed for {book_title}"
        
    # 4. Convert
    log(f"Converting {file_path} to Markdown...")
    conv_result = await scraper.convert_to_markdown(file_path)
    
    status = {
        "status": "success",
        "title": book_title,
        "author": book_author,
        "category": category,
        "file_path": file_path,
        "conversion": conv_result
    }
    
    return json.dumps(status, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    # If arguments are provided, run as a CLI tool
    if len(sys.argv) > 1 and sys.argv[1] != "run":
        async def main():
            query = sys.argv[1]
            cat = sys.argv[2] if len(sys.argv) > 2 else "哲学"
            result = await find_and_save_book(query, category=cat)
            print(result)
        asyncio.run(main())
    else:
        # Run as MCP server, suppressing the banner on stdout
        import logging
        logging.getLogger("fastmcp").setLevel(logging.ERROR)
        mcp.run()
