from fastmcp import FastMCP
from playwright.async_api import async_playwright
from playwright_stealth import stealth
from scraper import Scraper
import asyncio
import os

# Create an MCP server
mcp = FastMCP("Playwright MCP", dependencies=["playwright", "playwright-stealth", "beautifulsoup4"])

# Reuse existing Scraper logic
scraper = Scraper()

@mcp.tool()
async def search_books(query: str, file_type: str = ""):
    """
    Search for books on Anna's Archive mirrors.
    """
    return await scraper.search(query, file_type)

@mcp.tool()
async def get_book_details(url: str):
    """
    Get detailed information and mirror links for a specific book.
    """
    return await scraper.get_book_info(url)

@mcp.tool()
async def resolve_download_link(url: str):
    """
    Use Playwright with stealth to resolve a slow download link or mirror.
    """
    return await scraper.resolve_mirror_link(url)

@mcp.tool()
async def check_local_library(query: str):
    """
    Search for a book in the local library recursively.
    """
    root_dir = os.getenv("OPENLIB_BOOK_PATH", os.path.join(os.getcwd(), "Downloads"))
    path = await scraper.check_local_book(query, root_dir)
    if path:
        return {"status": "found", "file_path": path}
    else:
        return {"status": "not_found"}

@mcp.tool()
async def download_book(url: str, category: str, author: str, filename: str = None):
    """
    Download a book from a direct or resolved URL into a structured folder.
    CRITICAL: The 'author' parameter MUST follow the project's 'Chinese (English)' convention.
    Example: '斯坦尼斯拉斯·迪昂 (Stanislas Dehaene)'. 
    If you (the Agent) only have the English name, use your LLM capabilities to find the common Chinese translation.
    Format: {OPENLIB_BOOK_PATH}/category/author/filename
    """
    root_dir = os.getenv("OPENLIB_BOOK_PATH", os.path.join(os.getcwd(), "Downloads"))
    target_dir = scraper.prepare_structured_dir(root_dir, category, author)
    file_path = await scraper.download_file(url, dest_folder=target_dir, filename=filename)
    if file_path:
        return {"status": "success", "file_path": file_path}
    else:
        return {"status": "error", "message": "Download failed"}

@mcp.tool()
async def convert_and_split(file_path: str):
    """
    Post-process a downloaded book: convert to markdown and split into chapters.
    The final output folder will be renamed to follow 'Chinese (English)' convention 
    if you provide the translated title later.
    """
    md_content = await scraper.convert_to_markdown(file_path)
    if not md_content:
        return {"status": "error", "message": "Conversion to markdown failed"}
        
    # Create a subfolder for chapters: {book_name}_markdown
    base_dir = os.path.dirname(file_path)
    book_name = os.path.basename(file_path).rsplit('.', 1)[0]
    target_dir = os.path.join(base_dir, f"{book_name}_markdown")
    
    chapter_dir = scraper.split_into_chapters(md_content, target_dir)
    return {"status": "success", "markdown_dir": chapter_dir}

@mcp.tool()
async def navigate_to(url: str):
    """
    Navigate to a URL using Playwright and return the page content.
    Useful for general web browsing and debugging.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=scraper.headers["User-Agent"])
        page = await context.new_page()
        await stealth(page)
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            content = await page.content()
            title = await page.title()
            return {"title": title, "content": content, "url": page.url}
        finally:
            await browser.close()

@mcp.tool()
async def take_screenshot(url: str, filename: str = "screenshot.png"):
    """
    Take a screenshot of a page.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=scraper.headers["User-Agent"])
        page = await context.new_page()
        await stealth(page)
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.screenshot(path=filename, full_page=True)
            return {"status": "success", "message": f"Screenshot saved to {filename}"}
        finally:
            await browser.close()

if __name__ == "__main__":
    mcp.run()
