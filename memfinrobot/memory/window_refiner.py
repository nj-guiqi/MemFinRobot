"""窗口内容精炼器：将选中历史片段精炼为长期记忆条目。"""

import ast
import json
import logging
from typing import Any, List, Optional

from memfinrobot.memory.schemas import RefinedMemory
from memfinrobot.prompts.templates import REFINE_PROMPT

logger = logging.getLogger(__name__)


class WindowRefiner:
    """将选中窗口内容提炼成可写入长期记忆的要点。"""

    def __init__(self, llm_client: Optional[Any] = None, max_refine_length: int = 2000):
        self.llm_client = llm_client
        self.max_refine_length = max_refine_length

    def refine(
        self,
        selected_texts: List[str],
        current_query: str,
        source_indices: Optional[List[int]] = None,
    ) -> RefinedMemory:
        if not selected_texts:
            return RefinedMemory(refined_texts=[], citations=[], source_indices=source_indices or [])

        if self.llm_client is None:
            return self._fallback_refine(selected_texts, source_indices)

        try:
            refined_texts = self._llm_refine(selected_texts, current_query)
            citations = [
                {"index": idx, "original": text}
                for idx, text in zip(source_indices or range(len(selected_texts)), selected_texts)
            ]
            return RefinedMemory(
                refined_texts=refined_texts,
                citations=citations,
                source_indices=source_indices or list(range(len(selected_texts))),
            )
        except Exception as exc:
            logger.warning(f"Refine failed: {exc}, using fallback")
            return self._fallback_refine(selected_texts, source_indices)

    def _llm_refine(self, selected_texts: List[str], current_query: str) -> List[str]:
        selected_content = "\n".join([f"[{idx}] {text}" for idx, text in enumerate(selected_texts)])
        if len(selected_content) > self.max_refine_length:
            selected_content = selected_content[: self.max_refine_length] + "..."

        prompt = REFINE_PROMPT.format(selected_content=selected_content, current_query=current_query)
        messages = [{"role": "user", "content": prompt}]

        response = self.llm_client.chat(
            messages=messages,
            stream=True,
            extra_generate_cfg={"temperature": 0.2},
        )

        response_text = self._extract_response_text(response)
        if not response_text:
            return []

        parsed_json = self._try_parse_list(response_text)
        if parsed_json is not None:
            return parsed_json

        return [response_text.strip()] if response_text.strip() else []

    def _try_parse_list(self, response_text: str) -> Optional[List[str]]:
        text = response_text.strip()
        if not text:
            return []

        try:
            obj = json.loads(text)
            if isinstance(obj, list):
                return [str(item) for item in obj]
        except Exception:
            pass

        try:
            obj = ast.literal_eval(text)
            if isinstance(obj, list):
                return [str(item) for item in obj]
        except Exception:
            pass

        if "```" in text:
            inner = text.replace("```json", "").replace("```", "").strip()
            try:
                obj = json.loads(inner)
                if isinstance(obj, list):
                    return [str(item) for item in obj]
            except Exception:
                pass

        return None

    def _extract_response_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response

        if isinstance(response, list):
            for msg in reversed(response):
                if hasattr(msg, "content") and msg.content:
                    return str(msg.content)
                if isinstance(msg, dict) and msg.get("content"):
                    return str(msg["content"])
            return ""

        if hasattr(response, "__iter__"):
            last_text = ""
            for chunk in response:
                if not chunk:
                    continue
                if isinstance(chunk, list):
                    msg = chunk[-1]
                    if hasattr(msg, "content") and msg.content:
                        last_text = str(msg.content)
                    elif isinstance(msg, dict) and msg.get("content"):
                        last_text = str(msg["content"])
                else:
                    if hasattr(chunk, "content") and chunk.content:
                        last_text = str(chunk.content)
                    elif isinstance(chunk, dict) and chunk.get("content"):
                        last_text = str(chunk["content"])
                    else:
                        last_text = str(chunk)
            return last_text

        return str(response)

    def _fallback_refine(self, selected_texts: List[str], source_indices: Optional[List[int]] = None) -> RefinedMemory:
        refined_texts = [text[:200] + "..." if len(text) > 200 else text for text in selected_texts]
        citations = [
            {"index": idx, "original": text}
            for idx, text in zip(source_indices or range(len(selected_texts)), selected_texts)
        ]

        return RefinedMemory(
            refined_texts=refined_texts,
            citations=citations,
            source_indices=source_indices or list(range(len(selected_texts))),
        )

    def build_hierarchical_content(self, refined_memory: RefinedMemory, current_content: str) -> str:
        if not refined_memory.refined_texts:
            return current_content
        refined_str = " ".join(refined_memory.refined_texts)
        return f"{refined_str} | [context] | {current_content}"
