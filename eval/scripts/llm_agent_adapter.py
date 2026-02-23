"""Simple LLM 评测适配器：仅调用 OpenAI 风格接口，不使用 Memory/工具。"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from openai import OpenAI

from memfinrobot.agent.memfin_agent import MEMFIN_SYSTEM_PROMPT


class LlmAgentAdapter:
    """简单 LLM 代理，按轮独立回答。"""

    def __init__(
        self,
        dialog_id: str,
        observer: Optional[Any],
        base_url: str,
        chat_model: str,
        api_key_env: str = "DASHSCOPE_API_KEY",
        api_key: Optional[str] = None,
        enable_thinking: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_context: Optional[str] = None,
        request_timeout_sec: float = 120.0,
    ) -> None:
        self.dialog_id = dialog_id
        self.observer = observer
        self.base_url = base_url
        self.chat_model = chat_model
        self.enable_thinking = enable_thinking
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_context = system_context or MEMFIN_SYSTEM_PROMPT
        self.request_timeout_sec = max(1.0, float(request_timeout_sec))

        resolved_api_key = api_key or os.getenv(api_key_env) or os.getenv("DASHSCOPE_API_KEY")
        if not resolved_api_key:
            raise ValueError(
                f"Missing API key. Please set env `{api_key_env}` (or DASHSCOPE_API_KEY) or pass --api-key."
            )

        self.client = OpenAI(
            api_key=resolved_api_key,
            base_url=self.base_url,
            timeout=self.request_timeout_sec,
            max_retries=2,
        )

    def _emit_observer(self, event: str, payload: Dict[str, Any]) -> None:
        if self.observer is None:
            return
        try:
            if hasattr(self.observer, "on_event"):
                self.observer.on_event(event, payload)
            elif callable(self.observer):
                self.observer(event, payload)
        except Exception:
            pass

    def _chat_once(self, user_message: str) -> str:
        kwargs: Dict[str, Any] = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": self.system_context},
                {"role": "user", "content": user_message},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
            "timeout": self.request_timeout_sec,
        }
        if self.enable_thinking:
            kwargs["extra_body"] = {"enable_thinking": True}

        completion = self.client.chat.completions.create(**kwargs)
        return completion.choices[0].message.content or ""

    def handle_turn(
        self,
        user_message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        turn_pair: Optional[Dict[str, Any]] = None,
    ) -> str:
        _ = turn_pair
        session_id = session_id or f"llm_session_{self.dialog_id}"
        user_id = user_id or f"llm_user_{self.dialog_id}"
        turn_pair_id = int((turn_pair or {}).get("turn_pair_id") or 0)

        turn_start = time.perf_counter()
        self._emit_observer(
            "turn_start",
            {
                "session_id": session_id,
                "user_id": user_id,
                "turn_pair_id": turn_pair_id,
                "query": user_message,
            },
        )

        # 对齐评测 trace：无 memory 时仍显式给空 recall。
        self._emit_observer(
            "recall_done",
            {
                "session_id": session_id,
                "user_id": user_id,
                "turn_pair_id": turn_pair_id,
                "query": user_message,
                "short_term_context": "",
                "short_term_turns": [],
                "profile_context": "",
                "packed_context": "",
                "token_count": 0,
                "recalled_items": [],
            },
        )

        assistant_text = self._chat_once(user_message=user_message)

        self._emit_observer(
            "profile_snapshot",
            {
                "session_id": session_id,
                "user_id": user_id,
                "turn_pair_id": turn_pair_id,
                "profile": {},
            },
        )
        self._emit_observer(
            "compliance_done",
            {
                "session_id": session_id,
                "user_id": user_id,
                "turn_pair_id": turn_pair_id,
                "needs_modification": False,
                "is_compliant": True,
                "violations": [],
                "risk_disclaimer_added": False,
                "suitability_warning": None,
            },
        )

        latency_ms = (time.perf_counter() - turn_start) * 1000
        self._emit_observer(
            "turn_end",
            {
                "session_id": session_id,
                "user_id": user_id,
                "turn_pair_id": turn_pair_id,
                "query": user_message,
                "final_content": assistant_text,
                "latency_ms": latency_ms,
            },
        )
        return assistant_text
