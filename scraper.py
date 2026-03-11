import os, sys, glob
base_dir = os.path.dirname(os.path.abspath(__file__))
site_packages_pattern = os.path.join(base_dir, "venv", "lib", "python*", "site-packages")
site_packages_dirs = glob.glob(site_packages_pattern)
if site_packages_dirs:
    sys.path.insert(0, site_packages_dirs[0])

from playwright.async_api import async_playwright
from playwright_stealth import stealth
import httpx
from bs4 import BeautifulSoup
import os
import re
import json
import asyncio
import random
from typing import List, Optional, Dict

class Scraper:
    def __init__(self):
        self.mirrors = [
            "https://annas-archive.gl",
            "https://annas-archive.pk",
            "https://annas-archive.li",
            "https://annas-archive.org",
            "https://annas-archive.se",
        ]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
        }
        self.browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--window-position=0,0",
            "--ignore-certificate-errors",
            "--ignore-certificate-errors-spki-list",
            "--disable-dev-shm-usage",
        ]

    async def resolve_mirror_link(self, mirror_url: str) -> Optional[str]:
        """
        Attempts to resolve a slow_download or mirror link using Playwright with Stealth.
        """
        print(f"Resolving mirror link: {mirror_url}")
        
        # If it's already an IPFS link or direct link, return as is
        if "ipfs" in mirror_url or mirror_url.lower().endswith(('.pdf', '.epub', '.mobi', '.azw3')):
            return mirror_url

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=self.browser_args)
            
            # Context with more human-like parameters
            context = await browser.new_context(
                user_agent=self.headers["User-Agent"],
                viewport={'width': 1920, 'height': 1080},
                device_scale_factor=1,
                has_touch=False,
                is_mobile=False,
                locale="zh-CN",
                timezone_id="Asia/Shanghai"
            )
            
            page = await context.new_page()
            try:
                from playwright_stealth import stealth
                await stealth(page)
            except:
                pass
            
            try:
                # 1. First attempt on original mirror
                for attempt in range(2):
                    try:
                        resolved = await self._browser_resolve_step(page, mirror_url)
                        if resolved:
                            return resolved
                    except Exception as e:
                        if attempt == 0:
                            print(f"Retrying resolution after error: {e}")
                            await asyncio.sleep(3)
                            continue
                        raise
                
                # 2. Mirror rotation if primary fails
                parsed = httpx.URL(mirror_url)
                path = f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path
                
                for base in self.mirrors:
                    # Skip original host
                    if parsed.host in base: continue
                    alt_url = f"{base}{path}"
                    print(f"Retrying on mirror: {base}")
                    try:
                        resolved = await self._browser_resolve_step(page, alt_url)
                        if resolved:
                            return resolved
                    except:
                        continue
                        
            except Exception as e:
                print(f"Browser resolution error: {e}")
            finally:
                await browser.close()
                
        return None

    async def check_local_book(self, query: str, root_dir: Optional[str] = None) -> Optional[str]:
        """
        Search for a book in the local directory recursively.
        """
        root_dir = root_dir or os.getenv("OPENLIB_BOOK_PATH", os.path.join(os.getcwd(), "Downloads"))
        if not os.path.exists(root_dir):
            return None
            
        query_lower = query.lower()
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if query_lower in file.lower():
                    return os.path.join(root, file)
        return None

    def prepare_structured_dir(self, root_dir: str, category: str, author: str) -> str:
        """
        Simply creates and returns the path: root_dir/category/author.
        All logic for choosing the correct category and author names (translations, 
        matching existing folders) is handled by the LLM agent before calling this tool.
        """
        # Clean names for folder safety but preserve Chinese and common punctuation
        def clean_path_name(name: str) -> str:
            # Allow: Chinese, Alphanumeric, Space, (), ., -, ·
            # Replace: / \ : * ? " < > | with _
            cleaned = re.sub(r'[\\/:*?"<>|]', '_', name)
            return cleaned.strip()

        target_cat = clean_path_name(category) or "其他"
        author_dir = clean_path_name(author) or "未知作者"
        
        target_path = os.path.join(root_dir, target_cat, author_dir)
        if not os.path.exists(target_path):
            os.makedirs(target_path, exist_ok=True)
        return target_path

    async def convert_to_markdown(self, file_path: str) -> Optional[str]:
        """
        Converts EPUB or PDF to Markdown using system scripts or libraries.
        Includes post-processing to fix image paths.
        """
        ext = file_path.lower().split('.')[-1]
        
        try:
            if ext == 'epub':
                workflow_path = "/Library/Services/Convert EPUB to Markdown.workflow"
                if os.path.exists(workflow_path):
                    print(f"Calling system workflow for conversion: {workflow_path}")
                    cmd = f'automator -i "{file_path}" "{workflow_path}"'
                    process = await asyncio.create_subprocess_shell(
                        cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    if process.returncode == 0:
                        target_dir = file_path.rsplit('.', 1)[0]
                        # Post-process image paths in the target directory
                        self._fix_image_paths(target_dir)
                        return f"Success: Chapters saved in {target_dir}"
                    else:
                        print(f"Workflow error: {stderr.decode()}")
                        return None
                else:
                    import pypandoc
                    return pypandoc.convert_file(file_path, 'md')
            elif ext == 'pdf':
                from markitdown import MarkItDown
                mid = MarkItDown()
                result = mid.convert(file_path)
                return result.text_content
            else:
                return None
        except Exception as e:
            print(f"Conversion error: {e}")
            return None

    def _fix_image_paths(self, target_dir: str):
        """
        Scans all Markdown files and updates image paths to point to 'html/images/'.
        """
        if not os.path.exists(target_dir):
            return
            
        print(f"Fixing image paths in {target_dir}...")
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".md"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        # Replace ../images/ or images/ with html/images/
                        # Using regex to match various Markdown image syntax
                        new_content = re.sub(r'!\[.*?\]\((\.\.\/|)?images\/', '![](html/images/', content)
                        
                        if new_content != content:
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(new_content)
                    except Exception as e:
                        print(f"Error fixing {file}: {e}")

    def split_into_chapters(self, md_content: str, target_dir: str):
        """
        Splits markdown content into chapters (only used if manual conversion happens).
        If the system workflow was used, this might be redundant.
        """
        if md_content and md_content.startswith("Success: Chapters saved in"):
            return md_content.split("saved in ")[1]
            
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            
        # Basic chapter splitting by # or ## headers
        chapters = re.split(r'\n(?=# |## )', md_content)
        
        for i, chapter in enumerate(chapters):
            if not chapter.strip():
                continue
                
            # Try to get chapter title from first line
            first_line = chapter.strip().split('\n')[0]
            title = "".join([c for c in first_line if c.isalnum() or c in "._- "]).strip()
            title = title.replace("#", "").strip()
            
            if not title:
                title = f"Chapter_{i+1}"
            
            # Ensure filename isn't too long
            filename = f"{i+1:02d}_{title[:50]}.md"
            chapter_path = os.path.join(target_dir, filename)
            
            with open(chapter_path, "w", encoding="utf-8") as f:
                f.write(chapter)
        
        return target_dir

    async def download_file(self, url: str, dest_folder: str, filename: Optional[str] = None) -> Optional[str]:
        """
        Downloads a file from the given URL to the specified folder.
        """
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            try:
                async with client.stream("GET", url, headers=self.headers) as response:
                    if response.status_code != 200:
                        print(f"Download failed with status code: {response.status_code}")
                        return None
                    
                    # Try to get filename from Content-Disposition header
                    if not filename:
                        cd = response.headers.get("Content-Disposition")
                        if cd and "filename=" in cd:
                            filename = re.findall("filename=\"?(.+?)\"?(?:;|$)", cd)[0]
                        else:
                            # Fallback to URL path
                            filename = url.split("/")[-1].split("?")[0] or "downloaded_file"
                    
                    # Clean filename
                    filename = "".join([c for c in filename if c.isalnum() or c in "._- "]).strip()
                    file_path = os.path.join(dest_folder, filename)
                    
                    print(f"Downloading to: {file_path}")
                    with open(file_path, "wb") as f:
                        async for chunk in response.aiter_bytes():
                            f.write(chunk)
                    
                    return file_path
            except Exception as e:
                print(f"Download error: {e}")
                return None

    async def _browser_resolve_step(self, page, url: str) -> Optional[str]:
        try:
            # Human-like delay before navigation
            await asyncio.sleep(random.uniform(1.0, 3.0))
            
            # Navigate with a longer timeout and better wait condition
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Simulate slight mouse movement
            await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            
            # Handle Cloudflare / "Verify you are human" challenge
            for attempt in range(6): # Check for 30 seconds
                title = await page.title()
                content = await page.content()
                
                # Check for "Just a moment" or "checking your browser" or "Human" challenge
                if any(x in title for x in ["Just a moment", "Attention Required"]) or \
                   any(x in content.lower() for x in ["checking your browser", "verify you are human", "cf-challenge"]):
                    
                    print(f"Cloudflare challenge detected (Attempt {attempt+1})...")
                    
                    # Try to find and click the checkbox if it's there
                    try:
                        # Common Cloudflare checkbox selectors
                        checkbox_selectors = [
                            "input[type='checkbox']",
                            "div#cf-turnstile-wrapper iframe",
                            "#challenge-stage iframe"
                        ]
                        for selector in checkbox_selectors:
                            element = await page.query_selector(selector)
                            if element:
                                print(f"Found challenge element with selector: {selector}. Attempting to focus...")
                                # Instead of direct click (which might be in iframe), we wait
                                # If it's an iframe, we might need more complex logic, but often
                                # just waiting or moving the mouse helps.
                                await page.mouse.move(random.randint(0, 100), random.randint(0, 100))
                                break
                    except:
                        pass
                        
                    await asyncio.sleep(random.uniform(5.0, 7.0))
                else:
                    # Challenge likely passed
                    break
            
            # Additional wait for JS to render the download link
            await asyncio.sleep(random.uniform(2.0, 4.0))
            
            # Wait for either the download link or some indicating text
            target_selector = 'p.mb-4.text-xl.font-bold a'
            try:
                await page.wait_for_selector(target_selector, timeout=15000)
            except:
                # If target selector not found, it might be a different page structure
                pass
            
            html = await page.content()
            return self._parse_resolution_page(html, page.url)
            
        except Exception as e:
            print(f"Step failed for {url}: {e}")
            return None

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'[\U0001F300-\U0001F9FF]', '', text)
        text = re.sub(r'[\U00002600-\U000026FF]', '', text)
        text = re.sub(r'[\U00002700-\U000027BF]', '', text)
        text = re.sub(r'[\U0001F600-\U0001F64F]', '', text)
        text = re.sub(r'[\U0001F680-\U0001F6FF]', '', text)
        text = re.sub(r'🔍', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def get_md5(self, url: str) -> str:
        parts = url.split('/')
        return parts[-1] if parts else ""

    def get_format(self, info: str) -> str:
        info_lower = info.lower()
        if 'pdf' in info_lower: return 'pdf'
        if 'cbr' in info_lower: return 'cbr'
        if 'cbz' in info_lower: return 'cbz'
        return 'epub'

    def is_cloudflare_blocked(self, response) -> bool:
        if response.headers.get("cf-mitigated") == "challenge":
            return True
        
        body = response.text.lower()
        markers = [
            "checking your browser", "cloudflare", "cf-browser-verification",
            "just a moment", "enable javascript and cookies", "ray id:",
            "attention required", "ddos protection"
        ]
        return any(marker in body for marker in markers)

    async def _request_with_mirrors(self, path: str):
        last_error = None
        for base_url in self.mirrors:
            # Clean up the base_url and path to ensure single slash
            base_url = base_url.rstrip("/")
            if not path.startswith("/"):
                path = "/" + path
            url = f"{base_url}{path}"
            try:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    response = await client.get(url, headers=self.headers)
                    if response.status_code == 200 and not self.is_cloudflare_blocked(response):
                        return response, base_url
                    print(f"Mirror {base_url} failed or blocked (Status: {response.status_code})")
            except Exception as e:
                print(f"Mirror {base_url} error: {e}")
                last_error = e
        
        raise Exception(f"All mirrors failed. Last error: {last_error}")

    async def search(self, query: str, file_type: str = "") -> List[Dict]:
        encoded_query = query.replace(" ", "+")
        path = f"/search?q={encoded_query}"
        if file_type:
            path += f"&ext={file_type}"

        response, current_base = await self._request_with_mirrors(path)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        book_containers = soup.select('div.flex.pt-3.pb-3.border-b')
        if not book_containers:
            book_containers = soup.select('div[class*="flex"][class*="border-b"]')
        
        results = []
        for container in book_containers:
            main_link = container.select_one('a[href^="/md5/"]')
            if main_link and main_link.select_one('img'):
                main_link = container.select_one('a.js-vim-focus')
            
            thumb_img = container.select_one('a[href^="/md5/"] img')
            
            if not main_link or not main_link.get('href'):
                continue
                
            title = self.clean_text(main_link.get_text())
            link = current_base + main_link.get('href')
            md5 = self.get_md5(main_link.get('href'))
            thumbnail = thumb_img.get('src') if thumb_img else None
            
            info_el = container.select_one('div.text-gray-800')
            info = info_el.get_text().strip() if info_el else ""
            
            author = "unknown"
            publisher = "unknown"
            meta_links = container.find_all('a', href=re.compile(r'/search\?q='))
            if len(meta_links) >= 1:
                author = self.clean_text(meta_links[0].get_text())
            if len(meta_links) >= 2:
                publisher = self.clean_text(meta_links[1].get_text())

            results.append({
                "title": title, "author": author, "thumbnail": thumbnail,
                "link": link, "md5": md5, "publisher": publisher,
                "info": info, "format": self.get_format(info)
            })
            
        return results

    async def get_book_info(self, url: str) -> Optional[Dict]:
        # Extract path from URL to use mirrors
        parsed = httpx.URL(url)
        path = f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path
        
        response, current_base = await self._request_with_mirrors(path)
        current_base = current_base.rstrip("/")
        soup = BeautifulSoup(response.text, 'html.parser')
        main = soup.select_one('div.main-inner')
        if not main:
            return None
            
        title_el = main.select_one('div.font-semibold.text-2xl')
        title = self.clean_text(title_el.get_text().split('<span')[0]) if title_el else "Unknown"
        
        mirrors = []
        slow_links = main.select('ul.list-inside a[href*="/slow_download/"]')
        for l in slow_links:
            href = l.get('href')
            if not href.startswith("/"):
                href = "/" + href
            mirrors.append(current_base + href)
            
        ext_links = main.select('ul.list-inside a[href*="ipfs"]')
        for l in ext_links:
            if l.get('href').startswith('http'):
                mirrors.append(l.get('href'))

        return {
            "title": title, "link": url, "md5": self.get_md5(url), "mirrors": mirrors,
        }


    def _parse_resolution_page(self, html: str, current_url: str) -> Optional[str]:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Check for slow download page direct link
        slow_download_p = soup.select_one('p.mb-4.text-xl.font-bold')
        if slow_download_p:
            a_tag = slow_download_p.find('a')
            if a_tag and a_tag.get('href'):
                return a_tag.get('href')
        
        # Check for Libgen mirrors etc
        get_link = soup.select_one('a[href*="get.php"], a[href*="/get/"]')
        if get_link:
            return get_link.get('href')
        
        # IPFS mirrors
        ipfs_link = soup.select_one('a[href*="ipfs"]')
        if ipfs_link:
            return ipfs_link.get('href')

        # If it looks like a final PDF/EPUB URL after redirects
        if current_url.lower().endswith(('.pdf', '.epub', '.mobi', '.azw3')):
            return current_url
            
        return None
