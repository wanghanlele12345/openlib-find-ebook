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
async def find_and_save_book(query: str, category: str = "其他", author: str = None, extension: str = "epub", max_size_mb: float = 30.0):
    """
    Complete workflow with an integrated selection logic.
    Searches for a book, filters for quality (size, format), and downloads/converts.
    """
    def log(msg):
        print(f"[*] {msg}", file=sys.stderr)

    log(f"Starting search for: {query} (Preferred Ext: {extension})")
    
    # 1. Search
    results = await scraper.search(query, file_type=extension)
    if not results:
        return json.dumps({"status": "error", "message": f"No books found for '{query}'"}, ensure_ascii=False)
    
    # 2. Heuristic Filter (Avoiding Scanned versions by size)
    # This acts as a first pass for the LLM to verify later
    filtered_results = []
    for r in results:
        # Extract size from info (e.g., '49.1MB')
        size_match = re.search(r'(\d+\.?\d*)MB', r['info'])
        size_mb = float(size_match.group(1)) if size_match else 0.0
        
        # If it's a non-fiction book and size is > 40MB, it's likely a scan
        is_scanned = size_mb > max_size_mb and "non-fiction" in r['info'].lower()
        r['is_likely_scan'] = is_scanned
        r['size_mb'] = size_mb
        filtered_results.append(r)

    # In this automated tool, we'll pick the best one based on size and relevance
    # But for full 'LLM Verification', the Agent calling this tool should look at the results.
    # We will pick the first one that isn't a likely scan, or the smallest one if all are large.
    best_match = None
    for r in filtered_results:
        if not r['is_likely_scan']:
            best_match = r
            break
    
    if not best_match:
        best_match = sorted(filtered_results, key=lambda x: x['size_mb'])[0]
        log(f"Warning: All versions exceed {max_size_mb}MB. Picking the smallest: {best_match['size_mb']}MB")

    book_title = best_match['title']
    book_author = author or best_match['author'] or "未知作者"
    
    log(f"Selected: {book_title} by {book_author} ({best_match['size_mb']}MB)")
    
    # 3. Resolve
    info = await scraper.get_book_info(best_match['link'])
    if not info or not info.get('mirrors'):
        return json.dumps({"status": "error", "message": f"No mirrors for {book_title}"}, ensure_ascii=False)
    
    resolved_link = None
    for mirror in info['mirrors']:
        resolved_link = await scraper.resolve_mirror_link(mirror)
        if resolved_link: break
            
    if not resolved_link:
        return json.dumps({"status": "error", "message": f"Failed to resolve download link"}, ensure_ascii=False)
    
    # 4. Download
    target_dir = scraper.prepare_structured_dir(DEFAULT_ROOT, category, book_author)
    filename = "".join([c for c in book_title if c.isalnum() or c in "._- "]).strip() + f".{extension}"
    file_path = await scraper.download_file(resolved_link, dest_folder=target_dir, filename=filename)
    
    if not file_path:
        return json.dumps({"status": "error", "message": "Download failed"}, ensure_ascii=False)
        
    # 5. Convert
    log(f"Converting to Markdown...")
    conv_result = await scraper.convert_to_markdown(file_path)
    
    return json.dumps({
        "status": "success",
        "book": best_match,
        "file_path": file_path,
        "conversion": conv_result
    }, indent=2, ensure_ascii=False)

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
