import json
import os
from typing import Dict, List, Optional, Union

import requests
from qwen_agent.tools.base import BaseTool, register_tool

SERPER_ENDPOINT = "https://google.serper.dev/search"
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("WEB_SEARCH_TIMEOUT", "15"))


@register_tool("search", allow_overwrite=True)
class Search(BaseTool):
    name = "search"
    description = (
        "Search the web for one or multiple queries and return concise result snippets."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": "A single query string or a list of query strings.",
            },
            "num": {
                "type": "integer",
                "description": "Number of results per query. Default 5, max 10.",
            },
        },
        "required": ["query"],
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
                return parsed if isinstance(parsed, dict) else {"query": raw}
            except json.JSONDecodeError:
                return {"query": raw}
        return {}

    def _search_once(self, query: str, num: int) -> str:
        api_key = os.getenv("SERPER_API_KEY") or os.getenv("SERPER_KEY_ID")
        if not api_key:
            return (
                "[search] missing Serper key. Please set SERPER_API_KEY or "
                "SERPER_KEY_ID."
            )

        payload = {"q": query, "num": max(1, min(num, 10))}
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

        try:
            response = requests.post(
                SERPER_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except Exception as exc:
            return f"[search] request failed for query '{query}': {exc}"

        try:
            data = response.json()
        except Exception as exc:
            return f"[search] invalid response for query '{query}': {exc}"

        organic = data.get("organic") or []
        if not organic:
            return f"Query: {query}\nNo organic results."

        lines = [f"Query: {query}"]
        for idx, item in enumerate(organic[:num], start=1):
            title = item.get("title", "(no title)")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            lines.append(f"{idx}. {title}\nURL: {link}\nSnippet: {snippet}")
        return "\n\n".join(lines)

    def call(self, params: Union[str, dict], **kwargs) -> str:
        parsed = self._parse_params(params)
        query = parsed.get("query")
        num = int(parsed.get("num", 5))

        if not query:
            return "[search] invalid params: missing 'query'."

        if isinstance(query, str):
            queries = [query]
        elif isinstance(query, list):
            queries = [str(q).strip() for q in query if str(q).strip()]
        else:
            return "[search] invalid 'query' type, expected string or list."

        if not queries:
            return "[search] empty query list."

        results = [self._search_once(q, num) for q in queries]
        return "\n\n=======\n\n".join(results)
