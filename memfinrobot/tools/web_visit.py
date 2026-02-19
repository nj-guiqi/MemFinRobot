import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from typing import Any, Dict, List, Optional, Union

import requests
from qwen_agent.tools.base import BaseTool, register_tool

VISIT_SERVER_TIMEOUT = int(os.getenv("VISIT_SERVER_TIMEOUT", "50"))
WEBCONTENT_MAXLENGTH = int(os.getenv("WEBCONTENT_MAXLENGTH", "150000"))
VISIT_SERVER_MAX_RETRIES = int(os.getenv("VISIT_SERVER_MAX_RETRIES", "2"))
JINA_API_KEYS = os.getenv("JINA_API_KEYS", "")

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
        # Rough fallback: one token is usually around 3-4 chars for mixed content.
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
        timeout_total = int(os.getenv("VISIT_TOTAL_TIMEOUT", "900"))

        # Keep simple concurrency for multiple urls.
        results: List[str] = [""] * len(urls)
        max_workers = min(4, len(urls))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._readpage_and_summarize, url, goal): idx
                for idx, url in enumerate(urls)
            }
            for future in as_completed(future_map):
                idx = future_map[future]
                if time.time() - start_time > timeout_total:
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
            # Fallback: return truncated evidence + heuristic summary.
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
        if JINA_API_KEYS:
            headers["Authorization"] = f"Bearer {JINA_API_KEYS}"

        for attempt in range(3):
            try:
                response = requests.get(
                    f"https://r.jina.ai/{normalized}",
                    headers=headers,
                    timeout=VISIT_SERVER_TIMEOUT,
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
            response = requests.get(normalized, headers=headers, timeout=VISIT_SERVER_TIMEOUT)
            response.raise_for_status()
            cleaned = _clean_html(response.text)
            return cleaned if cleaned else "[visit] Failed to read page."
        except Exception:
            return "[visit] Failed to read page."

    def _html_readpage(self, url: str) -> str:
        # Prefer Jina extraction first.
        content = self._jina_readpage(url)
        if content and not content.startswith("[visit] Failed to read page"):
            return content[:WEBCONTENT_MAXLENGTH]

        # Fallback to direct web fetch.
        content = self._direct_readpage(url)
        if content and not content.startswith("[visit] Failed to read page"):
            return content[:WEBCONTENT_MAXLENGTH]

        return "[visit] Failed to read page."

    def _extract_by_llm(self, content: str, goal: str) -> Optional[Dict[str, Any]]:
        api_key = os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("API_BASE")
        model_name = os.getenv("SUMMARY_MODEL_NAME", "")

        if not api_key or not model_name:
            return None

        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=api_key, base_url=base_url)
        except Exception:
            return None

        prompt = EXTRACTOR_PROMPT.format(webpage_content=content, goal=goal)
        messages = [{"role": "user", "content": prompt}]

        raw = ""
        for _ in range(max(1, VISIT_SERVER_MAX_RETRIES)):
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
