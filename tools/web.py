"""Web tools - search and fetch."""

import re, json, html
import requests as req

_session = req.Session()
_session.trust_env = False

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web and return results with links. Use for finding current information, documentation, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch a URL and return its content as text/markdown. Use for reading web pages, documentation, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch"
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "Max content length to return (default 5000)"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Optional prompt to extract specific information from the fetched content"
                    }
                },
                "required": ["url"]
            }
        }
    }
]

TOOL_NAMES = [d["function"]["name"] for d in TOOL_DEFS]

def execute(name, args, work_dir=None):
    if name == "web_search":
        return _search(args)
    elif name == "web_fetch":
        return _fetch(args)
    return f"Unknown tool: {name}"

def _search(args):
    query = args.get("query", "")
    if not query:
        return "Error: No query provided"

    # Try SearXNG first (faster, more reliable)
    _s = req.Session()
    _s.trust_env = False
    try:
        searxng_url = "http://localhost:8888/search"
        resp = _s.get(searxng_url, params={"q": query, "format": "json"}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for i, item in enumerate(data.get("results", [])[:8], 1):
                title = item.get("title", "")
                url = item.get("url", "")
                snippet = item.get("content", "")
                result = f"{i}. {title}\n   {url}"
                if snippet:
                    result += f"\n   {snippet}"
                results.append(result)
            if results:
                header = f"Web search results for: {query}\n{'─' * 50}"
                return header + "\n" + "\n\n".join(results)
    except Exception:
        pass  # Fall through to DuckDuckGo

    # Fallback: DuckDuckGo HTML search
    try:
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        }
        resp = _s.post(url, data={"q": query}, headers=headers, timeout=15)
        resp.raise_for_status()

        results = []
        blocks = re.findall(r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL)

        if not blocks:
            blocks = re.findall(r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
            blocks = [(b[0], b[1], "") for b in blocks]

        for i, (link, title, snippet) in enumerate(blocks[:8], 1):
            title = re.sub(r'<[^>]+>', '', title).strip()
            title = html.unescape(title)
            snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            snippet = html.unescape(snippet)

            real_url = link
            url_match = re.search(r'uddg=([^&]+)', link)
            if url_match:
                from urllib.parse import unquote
                real_url = unquote(url_match.group(1))

            result = f"{i}. {title}\n   {real_url}"
            if snippet:
                result += f"\n   {snippet}"
            results.append(result)

        if not results:
            return f"No results found for: {query}"

        header = f"Web search results for: {query}\n{'─' * 50}"
        return header + "\n" + "\n\n".join(results)

    except Exception as e:
        return f"Search error: {e}"

def _fetch(args):
    url = args.get("url", "")
    max_length = args.get("max_length", 5000)
    prompt = args.get("prompt", "")

    if not url:
        return "Error: No URL provided"

    # Ensure HTTPS
    if url.startswith("http://"):
        url = url.replace("http://", "https://", 1)

    try:
        _s = req.Session()
        _s.trust_env = False
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = _s.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")

        # Handle different content types
        if "json" in content_type:
            try:
                data = resp.json()
                text = json.dumps(data, indent=2, ensure_ascii=False)
            except Exception:
                text = resp.text
        elif "html" in content_type:
            text = _html_to_text(resp.text)
        else:
            text = resp.text

        # Truncate
        if len(text) > max_length:
            text = text[:max_length] + f"\n\n... (truncated, {len(resp.text)} total chars)"

        header = f"Content from: {url}\nContent-Type: {content_type}\n{'─' * 50}"
        if prompt:
            header += f"\n[PROMPT: {prompt}]"
        return f"{header}\n{text}"

    except req.exceptions.HTTPError as e:
        return f"HTTP error {e.response.status_code}: {url}"
    except req.exceptions.ConnectionError:
        return f"Connection error: {url}"
    except req.exceptions.Timeout:
        return f"Timeout fetching: {url}"
    except Exception as e:
        return f"Fetch error: {e}"

def _html_to_text(html_str):
    """Convert HTML to readable text."""
    # Remove scripts and styles
    text = re.sub(r'<script[^>]*>.*?</script>', '', html_str, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    # Convert common tags
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<h[1-6][^>]*>', '\n\n## ', text, flags=re.IGNORECASE)
    text = re.sub(r'</h[1-6]>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', '\n- ', text, flags=re.IGNORECASE)
    # Handle links
    text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'\2 (\1)', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = html.unescape(text)
    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()
