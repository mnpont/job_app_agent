"""
A tool that fetches the text of a job posting from a URL.

Every tool file in this folder follows the same shape:
    SPEC  - a dictionary describing the tool to Claude (name, description,
            and what arguments it expects)
    run() - the actual Python function that does the work when Claude
            asks for this tool

tools/__init__.py automatically finds every file in this folder and wires
up SPEC + run for you - you never need to register a tool by hand.

How this tool works:
    1. Jina Reader  - sends the URL to r.jina.ai, a free service that
                      renders the page server-side and returns clean text.
                      This is the primary strategy and handles JS-heavy pages
                      like LinkedIn well.
    2. Direct fetch - if Jina fails or returns too little text, we fall back
                      to fetching the URL ourselves with requests and
                      stripping the HTML tags with BeautifulSoup. Works on
                      simple career pages that don't need JavaScript to load.
    3. Manual paste - if both automated methods fail, we pause and ask the
                      user to paste the job description into the terminal.
                      This guarantees Claude always gets the content it needs,
                      even on pages that actively block scraping.

Optional: set JINA_API_KEY in your .env file to use an authenticated Jina
request (higher rate limits). The tool works without it.

Required packages (add to your pip install):
    requests
    beautifulsoup4
"""

import os
import sys

import requests

SPEC = {
    "name": "fetch_job_posting",
    "description": (
        "Fetch the full text of a job posting from a URL. Use this whenever "
        "the user provides a job posting URL (including LinkedIn job URLs) "
        "instead of pasted text. Tries Jina Reader first (works well on "
        "LinkedIn and JS-heavy pages), then falls back to a direct HTTP "
        "fetch, then prompts the user to paste the text manually if both fail."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The full URL of the job posting page.",
            }
        },
        "required": ["url"],
    },
}


def _fetch_via_jina(url):
    """
    Ask Jina Reader (r.jina.ai) to fetch and render the page for us.
    Jina handles JavaScript-rendered pages like LinkedIn, returning plain text.
    If JINA_API_KEY is set in the environment, it's sent as a Bearer token
    for authenticated access (higher rate limits).
    """
    headers = {"Accept": "text/plain"}
    api_key = os.environ.get("JINA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    resp = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.text


def _fetch_direct(url):
    """
    Fetch the raw HTML ourselves and strip all tags to get visible text.
    Works on simple career pages that render content without JavaScript.
    We strip script/style/nav/header/footer tags first to reduce noise.
    """
    from bs4 import BeautifulSoup
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _read_manual():
    """
    Last resort: ask the user to paste the job description directly.
    We read from /dev/tty instead of stdin because agent_loop.py already
    consumed stdin to get the original URL. /dev/tty always points to the
    user's actual terminal, bypassing that.
    """
    print("\nCould not fetch the job posting automatically.")
    print("Paste the job description below, then press Ctrl+D when done:")
    try:
        with open("/dev/tty", "r") as tty:
            return tty.read()
    except OSError:
        # /dev/tty unavailable (e.g. non-Unix system) - fall back to stdin
        return sys.stdin.read()


def run(tool_input):
    # tool_input is a dict matching input_schema, e.g. {"url": "https://..."}
    url = tool_input.get("url", "").strip()
    if not url:
        return "Error: no URL provided."

    # Strategy 1: Jina Reader - best shot at LinkedIn and other JS-heavy pages
    try:
        text = _fetch_via_jina(url)
        if len(text.split()) >= 100:  # sanity check - real postings are never this short
            return text
    except Exception:
        pass

    # Strategy 2: direct HTTP fetch - works on simpler, non-JS career pages
    try:
        text = _fetch_direct(url)
        if len(text.split()) >= 100:
            return text
    except Exception:
        pass

    # Strategy 3: manual fallback - guaranteed to work
    return _read_manual()
