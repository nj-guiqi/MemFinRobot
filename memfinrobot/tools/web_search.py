import json
import os
import re
from typing import Any, Dict, List, Optional, Union

import requests
from qwen_agent.tools.base import BaseTool, register_tool

SERPER_ENDPOINT = "https://google.serper.dev/search"
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("WEB_SEARCH_TIMEOUT", "15"))
_ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _looks_like_env_name(text: str) -> bool:
    return bool(_ENV_NAME_RE.match(text or ""))


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
        self.cfg = cfg or {}
        self.api_key = self._resolve_secret(
            primary_key="serper_api_key_env",
            fallback_env_key="serper_api_key_env_fallback",
            default_envs=["SERPER_API_KEY", "SERPER_KEY_ID"],
        )
        self.timeout_seconds = self._resolve_int(
            env_or_value_key="timeout_seconds_env",
            default_key="timeout_seconds_default",
            hard_default=DEFAULT_TIMEOUT_SECONDS,
        )

    def _resolve_from_cfg_env_or_value(self, key: str) -> str:
        raw = str(self.cfg.get(key, "")).strip()
        if not raw:
            return ""

        env_val = os.getenv(raw, "")
        if env_val:
            return env_val

        # If this looks like an env var name but is not set, treat as missing.
        if _looks_like_env_name(raw):
            return ""

        # Otherwise treat as a direct literal value from config.
        return raw

    def _resolve_secret(self, primary_key: str, fallback_env_key: str, default_envs: List[str]) -> str:
        value = self._resolve_from_cfg_env_or_value(primary_key)
        if value:
            return value

        fallback_env_name = str(self.cfg.get(fallback_env_key, "")).strip()
        if fallback_env_name:
            env_val = os.getenv(fallback_env_name, "")
            if env_val:
                return env_val

        for env_name in default_envs:
            env_val = os.getenv(env_name, "")
            if env_val:
                return env_val

        return ""

    def _resolve_int(self, env_or_value_key: str, default_key: str, hard_default: int) -> int:
        raw = str(self.cfg.get(env_or_value_key, "")).strip()
        if raw:
            env_val = os.getenv(raw, "")
            candidate = env_val or raw
            try:
                if not _looks_like_env_name(candidate):
                    return int(candidate)
            except ValueError:
                pass

        try:
            return int(self.cfg.get(default_key, hard_default))
        except (TypeError, ValueError):
            return hard_default

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
        api_key = self.api_key or os.getenv("SERPER_API_KEY") or os.getenv("SERPER_KEY_ID")
        if not api_key:
            return (
                "[search] missing Serper key. Please set SERPER_API_KEY/SERPER_KEY_ID "
                "or configure tools.web_search.serper_api_key_env in config.json."
            )

        payload = {"q": query, "num": max(1, min(num, 10))}
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

        try:
            response = requests.post(
                SERPER_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
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
