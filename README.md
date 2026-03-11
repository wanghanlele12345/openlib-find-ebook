# OpenLib Book Finder (Gemini CLI Extension)

这是一个为 Gemini CLI 量身定制的高自动化电子书获取与管理工具。它集成了搜索、智能绕过 Cloudflare 验证、自动分类归档以及 EPUB 转 Markdown 等功能。

## 🌟 核心特性

- **智能绕过 Cloudflare (Bot Detection)**：集成 Stealth Playwright 模拟真实用户行为（随机延迟、鼠标轨迹、UA 伪装），大幅提高从 Anna's Archive 下载时的成功率。
- **语义化目录管理**：
    - **中英双语对齐**：自动识别现有目录（如 `Science` -> `科学`），优先按中文分类归档。
    - **智能命名规范**：利用 LLM 自动将作者和书籍重命名为 `中文名 (英文名)` 格式，确保书库整洁。
- **全自动后处理**：
    - 支持 **EPUB 转 Markdown** 并自动按章节拆分。
    - 遵循“我独自阅读”目录结构规范。
- **MCP 架构集成**：作为 Model Context Protocol (MCP) 服务器运行，完美适配 Gemini CLI 的工具调用机制。

## 🛠️ 安装要求

1. **Python 环境**：Python 3.10+
2. **系统工具**：
   - `pandoc` (用于 Markdown 转换)
   - macOS 用户建议安装 `Convert EPUB to Markdown.workflow` 以获得最佳转换效果。
3. **Playwright 浏览器**：
   ```bash
   pip install playwright
   playwright install chromium
   ```

## 🚀 快速开始

### 安装扩展
```bash
gemini extensions install https://github.com/wanghanlele12345/openlib-find-ebook.git
```

### 常用指令
- "帮我下载《脑与意识》，作者是斯坦尼斯拉斯·迪昂，放在心理学目录下，并转成 markdown。"
- "在 openlib 上搜一下关于计算神经科学的书。"

## 📦 技术栈

- **Playwright & Playwright-Stealth**: 浏览器自动化与反爬绕过。
- **FastMCP**: 高效的 MCP 扩展开发框架。
- **BeautifulSoup4**: 网页解析。
- **Httpx**: 异步 HTTP 请求。

## 📄 开源协议
MIT
