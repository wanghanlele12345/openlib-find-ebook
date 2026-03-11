---
name: openlib-book-finder
description: An end-to-end automated tool for searching, downloading, and converting books from Anna's Archive to a structured local library. Features local-first checking, intelligent categorization, and macOS system workflow integration.
---

# Openlib Book Finder (Automated Workflow)

This skill provides a comprehensive pipeline for managing a digital library. It is optimized for the "I Read Alone" (我独自阅读) directory structure on macOS.

## Standard Workflows

### Phase 1: Local Library Pre-Check
Before any online action, ALWAYS scan `/Users/mac/Documents/HW/我独自阅读` recursively.
- **Goal**: Prevent redundant downloads.
- **Action**: Use `check_local_library`. If found, confirm with the user before proceeding.

### Phase 2: Online Acquisition
If the book is not found locally:
1.  **Search**: Use `search_books` (defaulting to EPUB).
2.  **LLM Verification & Selection**: 
    - **Crucial Step**: The LLM agent MUST analyze the list of search results.
    - **Check Criteria**: Compare author names, check file sizes (avoid scanned PDFs > 30-40MB), and verify the publication year/language.
    - **Pick MD5**: Select the specific MD5 hash or link that best matches the user's intent.
3.  **Resolve**: Use `resolve_download_link` on the selected MD5/link.
4.  **Categorize**: Automatically determine the book's `category` (e.g., Science, Philosophy, Fiction) and `author`.
5.  **Download**: Use `download_book` to save it to `/Users/mac/Documents/HW/我独自阅读/{category}/{author}/`.

### Phase 3: Automated Post-Processing
After download, automatically trigger conversion:
- **Action**: Use `convert_and_split`.
- **EPUB**: Invokes `/Library/Services/Convert EPUB to Markdown.workflow`. This will unzip, convert, and split the book into individual chapter `.md` files in a dedicated sub-folder.
- **PDF**: Falls back to `MarkItDown` library for general markdown conversion.

## CLI Quick Call

For maximum efficiency, you can skip individual tool calls and run the entire search-download-convert workflow directly from the command line:

```bash
/Users/mac/.gemini/skills/openlib-book-finder/venv/bin/python /Users/mac/.gemini/skills/openlib-book-finder/mcp_server.py "<Book Name>" "<Category>"
```
This is the preferred way for complex "find and save" requests.

## Troubleshooting
- **Cloudflare**: The scraper uses Stealth Playwright to handle 'Just a moment' challenges. If a mirror is slow, it automatically rotates to others.
- **File Errors**: Handles long filenames by cleaning metadata and using short, safe names.
- **Dependencies**: Requires `pandoc`, `pypandoc`, and `markitdown` for full functionality.
