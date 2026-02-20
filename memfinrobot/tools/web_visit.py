import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from typing import Any, Dict, List, Optional, Union

import requests
from qwen_agent.tools.base import BaseTool, register_tool

DEFAULT_VISIT_SERVER_TIMEOUT = int(os.getenv("VISIT_SERVER_TIMEOUT", "50"))
DEFAULT_WEBCONTENT_MAXLENGTH = int(os.getenv("WEBCONTENT_MAXLENGTH", "150000"))
DEFAULT_VISIT_SERVER_MAX_RETRIES = int(os.getenv("VISIT_SERVER_MAX_RETRIES", "2"))
DEFAULT_VISIT_TOTAL_TIMEOUT = int(os.getenv("VISIT_TOTAL_TIMEOUT", "900"))
_ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")

EXTRACTOR_PROMPT = """You are a web content extraction assistant.
Given webpage content and user goal, return a JSON object with keys:
- evidence: the most relevant original content for the goal
- summary: concise summary for the goal
Only return valid JSON.

User goal:
{goal}

Webpage content:
{webpage_content}
"""


def _looks_like_env_name(text: str) -> bool:
    return bool(_ENV_NAME_RE.match(text or ""))


def truncate_to_tokens(text: str, max_tokens: int = 95000) -> str:
    """Best-effort token truncation. Falls back to char truncation if tiktoken is unavailable."""
    try:
        import tiktoken  # type: ignore

        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return encoding.decode(tokens[:max_tokens])
    except Exception:
        approx_chars = max_tokens * 4
        return text[:approx_chars]


def _clean_html(html_text: str) -> str:
    text = TAG_RE.sub(" ", html_text)
    text = unescape(text)
    return SPACE_RE.sub(" ", text).strip()


@register_tool("visit", allow_overwrite=True)
class Visit(BaseTool):
    name = "visit"
    description = "Visit webpage(s), extract evidence and summary for a given goal."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": ["string", "array"],
                "items": {"type": "string"},
                "minItems": 1,
                "description": "URL or URL list to visit.",
            },
            "goal": {
                "type": "string",
                "description": "The information extraction goal.",
            },
        },
        "required": ["url", "goal"],
    }

    def __init__(self, cfg: Optional[Dict[str, Any]] = None):
        super().__init__(cfg)
        self.cfg = cfg or {}

        self.jina_api_keys = self._resolve_value(
            key="jina_api_keys_env",
            default_envs=["JINA_API_KEYS"],
            hard_default="",
        )
        self.visit_server_timeout = self._resolve_int(
            env_or_value_key="visit_server_timeout_env",
            default_key="visit_server_timeout_default",
            hard_default=DEFAULT_VISIT_SERVER_TIMEOUT,
        )
        self.visit_server_max_retries = self._resolve_int(
            env_or_value_key="visit_server_max_retries_env",
            default_key="visit_server_max_retries_default",
            hard_default=DEFAULT_VISIT_SERVER_MAX_RETRIES,
        )
        self.visit_total_timeout = self._resolve_int(
            env_or_value_key="visit_total_timeout_env",
            default_key="visit_total_timeout_default",
            hard_default=DEFAULT_VISIT_TOTAL_TIMEOUT,
        )
        self.webcontent_maxlength = self._resolve_int(
            env_or_value_key="webcontent_maxlength_env",
            default_key="webcontent_maxlength_default",
            hard_default=DEFAULT_WEBCONTENT_MAXLENGTH,
        )

        self.summary_api_key = self._resolve_value(
            key="summary_api_key_env",
            default_envs=["API_KEY", "OPENAI_API_KEY"],
            hard_default="",
        )
        self.summary_base_url = self._resolve_value(
            key="summary_base_url_env",
            default_envs=["API_BASE"],
            hard_default="",
        )
        self.summary_model_name = self._resolve_value(
            key="summary_model_name_env",
            default_envs=["SUMMARY_MODEL_NAME"],
            hard_default="",
        )

    def _resolve_from_cfg_env_or_value(self, key: str) -> str:
        raw = str(self.cfg.get(key, "")).strip()
        if not raw:
            return ""

        env_val = os.getenv(raw, "")
        if env_val:
            return env_val

        if _looks_like_env_name(raw):
            return ""

        return raw

    def _resolve_value(self, key: str, default_envs: List[str], hard_default: str = "") -> str:
        value = self._resolve_from_cfg_env_or_value(key)
        if value:
            return value

        for env_name in default_envs:
            env_val = os.getenv(env_name, "")
            if env_val:
                return env_val

        return hard_default

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

    def _parse_params(self, params: Union[str, dict]) -> Dict[str, Any]:
        if isinstance(params, dict):
            return params
        if isinstance(params, str):
            raw = params.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {"url": raw}
        return {}

    def _normalize_url(self, url: str) -> str:
        u = url.strip()
        if not u:
            return u
        if u.startswith("http://") or u.startswith("https://"):
            return u
        return f"https://{u}"

    def call(self, params: Union[str, dict], **kwargs) -> str:
        parsed = self._parse_params(params)
        raw_url = parsed.get("url")
        goal = str(parsed.get("goal", "")).strip()

        if not raw_url:
            return "[Visit] Invalid request format: missing 'url' field"
        if not goal:
            goal = "Extract the key information relevant to the user query."

        if isinstance(raw_url, str):
            urls = [raw_url]
        elif isinstance(raw_url, list):
            urls = [str(u).strip() for u in raw_url if str(u).strip()]
        else:
            return "[Visit] Invalid request format: 'url' must be string or array"

        if not urls:
            return "[Visit] Empty url list"

        start_time = time.time()

        results: List[str] = [""] * len(urls)
        max_workers = min(4, len(urls))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._readpage_and_summarize, url, goal): idx
                for idx, url in enumerate(urls)
            }
            for future in as_completed(future_map):
                idx = future_map[future]
                if time.time() - start_time > self.visit_total_timeout:
                    results[idx] = self._build_failure_output(urls[idx], goal)
                    continue
                try:
                    results[idx] = future.result()
                except Exception as exc:
                    results[idx] = f"Error fetching {urls[idx]}: {exc}"

        return "\n=======\n".join(results).strip()

    def _readpage_and_summarize(self, url: str, goal: str) -> str:
        content = self._html_readpage(url)
        if not content or content.startswith("[visit] Failed to read page"):
            return self._build_failure_output(url, goal)

        content = truncate_to_tokens(content, max_tokens=95000)
        parsed = self._extract_by_llm(content, goal)

        if parsed is None:
            evidence = content[:4000]
            summary = content[:600]
        else:
            evidence = str(parsed.get("evidence", "")).strip()
            summary = str(parsed.get("summary", "")).strip()
            if not evidence:
                evidence = content[:4000]
            if not summary:
                summary = content[:600]

        useful_information = (
            f"The useful information in {url} for user goal {goal} as follows:\n\n"
            f"Evidence in page:\n{evidence}\n\n"
            f"Summary:\n{summary}\n"
        )
        return useful_information

    def _build_failure_output(self, url: str, goal: str) -> str:
        useful_information = (
            f"The useful information in {url} for user goal {goal} as follows:\n\n"
            "Evidence in page:\n"
            "The provided webpage content could not be accessed. Please check the URL or file format.\n\n"
            "Summary:\n"
            "The webpage content could not be processed, and therefore, no information is available.\n"
        )
        return useful_information

    def _jina_readpage(self, url: str) -> str:
        normalized = self._normalize_url(url)
        if not normalized:
            return "[visit] Failed to read page."

        headers = {}
        if self.jina_api_keys:
            headers["Authorization"] = f"Bearer {self.jina_api_keys}"

        for attempt in range(3):
            try:
                response = requests.get(
                    f"https://r.jina.ai/{normalized}",
                    headers=headers,
                    timeout=self.visit_server_timeout,
                )
                if response.status_code == 200 and response.text.strip():
                    return response.text
            except Exception:
                pass
            if attempt < 2:
                time.sleep(0.5)

        return "[visit] Failed to read page."

    def _direct_readpage(self, url: str) -> str:
        normalized = self._normalize_url(url)
        if not normalized:
            return "[visit] Failed to read page."
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        try:
            response = requests.get(normalized, headers=headers, timeout=self.visit_server_timeout)
            response.raise_for_status()
            cleaned = _clean_html(response.text)
            return cleaned if cleaned else "[visit] Failed to read page."
        except Exception:
            return "[visit] Failed to read page."

    def _html_readpage(self, url: str) -> str:
        content = self._jina_readpage(url)
        if content and not content.startswith("[visit] Failed to read page"):
            return content[: self.webcontent_maxlength]

        content = self._direct_readpage(url)
        if content and not content.startswith("[visit] Failed to read page"):
            return content[: self.webcontent_maxlength]

        return "[visit] Failed to read page."

    def _extract_by_llm(self, content: str, goal: str) -> Optional[Dict[str, Any]]:
        api_key = self.summary_api_key
        base_url = self.summary_base_url
        model_name = self.summary_model_name

        if not api_key or not model_name:
            return None

        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=api_key, base_url=base_url or None)
        except Exception:
            return None

        prompt = EXTRACTOR_PROMPT.format(webpage_content=content, goal=goal)
        messages = [{"role": "user", "content": prompt}]

        raw = ""
        for _ in range(max(1, self.visit_server_max_retries)):
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.2,
                )
                raw = response.choices[0].message.content or ""
                data = self._parse_json_object(raw)
                if data is not None:
                    return data
            except Exception:
                continue

        return None

    def _parse_json_object(self, raw: str) -> Optional[Dict[str, Any]]:
        text = (raw or "").strip()
        if not text:
            return None

        text = text.replace("```json", "").replace("```", "").strip()
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except Exception:
            pass

        left = text.find("{")
        right = text.rfind("}")
        if left == -1 or right == -1 or left > right:
            return None
        try:
            data = json.loads(text[left : right + 1])
            return data if isinstance(data, dict) else None
        except Exception:
            return None
