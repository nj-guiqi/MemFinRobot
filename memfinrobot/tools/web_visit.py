import json
import os
import re
from html import unescape
from typing import Dict, List, Optional, Union

import requests
from qwen_agent.tools.base import BaseTool, register_tool

DEFAULT_TIMEOUT_SECONDS = int(os.getenv("WEB_VISIT_TIMEOUT", "20"))
MAX_CONTENT_LENGTH = int(os.getenv("WEBCONTENT_MAXLENGTH", "12000"))

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def _clean_html(html_text: str) -> str:
    text = TAG_RE.sub(" ", html_text)
    text = unescape(text)
    return SPACE_RE.sub(" ", text).strip()


@register_tool("visit", allow_overwrite=True)
class Visit(BaseTool):
    name = "visit"
    description = "Visit webpage(s) and return extracted text content."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": "A single URL or a list of URLs.",
            },
            "goal": {
                "type": "string",
                "description": "Optional reading goal, used for context in output.",
            },
        },
        "required": ["url"],
    }

    def __init__(self, cfg: Optional[dict] = None):
        super().__init__(cfg)

    def _parse_params(self, params: Union[str, dict]) -> Dict:
        if isinstance(params, dict):
            return params
        if isinstance(params, str):
            raw = params.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, dict) else {"url": raw}
            except json.JSONDecodeError:
                return {"url": raw}
        return {}

    def _normalize_url(self, url: str) -> str:
        cleaned = url.strip()
        if not cleaned:
            return cleaned
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            return cleaned
        return f"https://{cleaned}"

    def _fetch_content(self, url: str) -> str:
        normalized = self._normalize_url(url)
        if not normalized:
            return "[visit] empty url."

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        # First try r.jina.ai for cleaner readable text.
        try_urls = [f"https://r.jina.ai/{normalized}", normalized]

        last_error = ""
        for candidate in try_urls:
            try:
                response = requests.get(candidate, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS)
                response.raise_for_status()
                text = response.text
                if candidate == normalized:
                    text = _clean_html(text)
                text = text.strip()
                if not text:
                    continue
                return text[:MAX_CONTENT_LENGTH]
            except Exception as exc:
                last_error = str(exc)

        return f"[visit] failed to fetch url: {normalized}. Error: {last_error}"

    def call(self, params: Union[str, dict], **kwargs) -> str:
        parsed = self._parse_params(params)
        raw_urls = parsed.get("url")
        goal = str(parsed.get("goal", "")).strip()

        if not raw_urls:
            return "[visit] invalid params: missing 'url'."

        if isinstance(raw_urls, str):
            urls = [raw_urls]
        elif isinstance(raw_urls, list):
            urls = [str(u).strip() for u in raw_urls if str(u).strip()]
        else:
            return "[visit] invalid 'url' type, expected string or list."

        if not urls:
            return "[visit] empty url list."

        sections: List[str] = []
        if goal:
            sections.append(f"Goal: {goal}")

        for idx, url in enumerate(urls, start=1):
            content = self._fetch_content(url)
            sections.append(f"[{idx}] URL: {url}\n{content}")

        return "\n\n=======\n\n".join(sections)
