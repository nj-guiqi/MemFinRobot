"""LangMem evaluation adapter.

Wraps LangGraph + LangMem memory tools into replay-compatible ``handle_turn`` API.
"""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LANGMEM_ROOT = PROJECT_ROOT / "eval" / "langmem"
LANGMEM_SRC = LANGMEM_ROOT / "src"
if str(LANGMEM_SRC) not in sys.path:
    sys.path.insert(0, str(LANGMEM_SRC))

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.prebuilt import create_react_agent
from langgraph.store.memory import InMemoryStore
from langmem import create_manage_memory_tool, create_search_memory_tool


def _load_memfin_system_prompt() -> str:
    try:
        from memfinrobot.agent.memfin_agent import MEMFIN_SYSTEM_PROMPT as prompt  # type: ignore

        if isinstance(prompt, str) and prompt.strip():
            return prompt
    except Exception:
        pass

    prompt_file = PROJECT_ROOT / "memfinrobot" / "agent" / "memfin_agent.py"
    try:
        text = prompt_file.read_text(encoding="utf-8")
        match = re.search(r'MEMFIN_SYSTEM_PROMPT\s*=\s*"""(.*?)"""', text, re.S)
        if match:
            parsed = match.group(1).strip()
            if parsed:
                return parsed
    except Exception:
        pass

    return (
        "You are a prudent and compliant financial assistant. "
        "Provide direct, structured, and risk-aware answers."
    )


MEMFIN_SYSTEM_PROMPT = _load_memfin_system_prompt()


@dataclass
class _SessionState:
    turn_count: int = 0
    short_history: List[Dict[str, str]] = field(default_factory=list)


class LangMemAgentAdapter:
    """Adapter for LangMem memory tools + LangGraph react agent."""

    def __init__(
        self,
        dialog_id: str,
        observer: Optional[Any],
        base_url: str,
        chat_model: str,
        api_key_env: str = "DASHSCOPE_API_KEY",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        request_timeout_sec: float = 120.0,
        recall_limit: int = 10,
        short_term_n: int = 3,
        embedding_model: str = "text-embedding-v4",
        embedding_dims: int = 1024,
        system_context: Optional[str] = None,
    ) -> None:
        self.dialog_id = dialog_id
        self.observer = observer
        self.base_url = base_url
        self.chat_model = chat_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.request_timeout_sec = max(1.0, float(request_timeout_sec))
        self.recall_limit = max(1, int(recall_limit))
        self.short_term_n = max(1, int(short_term_n))
        self.system_context = system_context or MEMFIN_SYSTEM_PROMPT
        self.embedding_model = embedding_model
        self.embedding_dims = int(embedding_dims)
        self._sessions: Dict[str, _SessionState] = {}

        resolved_api_key = api_key or os.getenv(api_key_env) or os.getenv("DASHSCOPE_API_KEY")
        if not resolved_api_key:
            raise ValueError(
                f"Missing API key. Please set env `{api_key_env}` (or DASHSCOPE_API_KEY) or pass --api-key."
            )
        self.api_key = resolved_api_key

        # LangGraph's `openai:...` embedding provider reads these env vars.
        os.environ["OPENAI_API_KEY"] = self.api_key
        os.environ["OPENAI_BASE_URL"] = self.base_url

        # DashScope's embedding endpoint does not accept token-id inputs.
        # `check_embedding_ctx_length=False` keeps payload as plain strings.
        embedding_client = OpenAIEmbeddings(
            model=self.embedding_model,
            api_key=self.api_key,
            base_url=self.base_url,
            check_embedding_ctx_length=False,
        )
        self.store = InMemoryStore(
            index={
                "dims": self.embedding_dims,
                "embed": embedding_client,
            }
        )
        self.namespace_template = ("memories", "{langgraph_user_id}")
        self.namespace_prefix = ("memories",)

        llm = ChatOpenAI(
            model=self.chat_model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=self.temperature,
            timeout=self.request_timeout_sec,
            max_retries=2,
            max_tokens=self.max_tokens,
        )
        self.agent = create_react_agent(
            llm,
            tools=[
                create_manage_memory_tool(
                    namespace=self.namespace_template,
                    instructions=(
                        "Use this tool to store stable user facts, preferences, risk tolerance, "
                        "constraints, and any profile-like detail that may be useful in later turns."
                    ),
                ),
                create_search_memory_tool(namespace=self.namespace_template),
            ],
            store=self.store,
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

    def _get_or_create_session(self, session_id: str) -> _SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = _SessionState()
        return self._sessions[session_id]

    def _build_short_term_context(self, session: _SessionState) -> str:
        recent = session.short_history[-(self.short_term_n * 2) :]
        return "\n".join(f"{t['role']}: {t['content']}" for t in recent if t.get("content"))

    @staticmethod
    def _to_text(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    if "text" in item:
                        parts.append(str(item["text"]))
                    elif "content" in item:
                        parts.append(str(item["content"]))
                    else:
                        parts.append(str(item))
                else:
                    parts.append(str(item))
            return "\n".join([p for p in parts if p])
        return str(content)

    def _memory_namespace(self, user_id: str) -> tuple[str, ...]:
        return self.namespace_prefix + (user_id,)

    def _search_memories(self, user_id: str, query: str) -> List[Any]:
        namespace = self._memory_namespace(user_id=user_id)
        try:
            return list(
                self.store.search(
                    namespace,
                    query=query,
                    limit=self.recall_limit,
                )
            )
        except Exception:
            try:
                return list(self.store.search(namespace, limit=self.recall_limit))
            except Exception:
                return []

    @staticmethod
    def _extract_item_field(item: Any, key: str, default: Any) -> Any:
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    def _format_recall_items(self, items: List[Any]) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for idx, item in enumerate(items):
            key = self._extract_item_field(item, "key", "")
            value = self._extract_item_field(item, "value", {}) or {}
            score = self._extract_item_field(item, "score", 0.0)
            if not isinstance(value, dict):
                value = {"content": str(value)}
            content = value.get("content")
            if isinstance(content, (dict, list)):
                content_text = self._to_text(content)
            else:
                content_text = str(content or "")
            formatted.append(
                {
                    "rank": idx + 1,
                    "id": str(key or ""),
                    "content": content_text,
                    "score": float(score or 0.0),
                    "source": "langmem_store",
                    "turn_index": 0,
                    "session_id": "",
                }
            )
        return formatted

    def _build_packed_context(self, recall_items: List[Dict[str, Any]], short_term_context: str) -> str:
        lines: List[str] = []
        if short_term_context:
            lines.append("[Recent conversation]")
            lines.append(short_term_context)
        if recall_items:
            lines.append("[Retrieved memories]")
            for it in recall_items:
                lines.append(f"- score={it['score']:.4f} | {it['content']}")
        return "\n".join(lines)

    def _invoke_agent(
        self,
        user_message: str,
        packed_context: str,
        session_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        system_prompt = self.system_context
        if packed_context:
            system_prompt += f"\n\n---\nContext for this turn:\n{packed_context}\n---"

        return self.agent.invoke(
            {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ]
            },
            config={
                "configurable": {
                    "thread_id": session_id,
                    "langgraph_user_id": user_id,
                }
            },
        )

    def _iter_messages(self, result: Dict[str, Any]) -> List[Any]:
        if not isinstance(result, dict):
            return []
        msgs = result.get("messages")
        if isinstance(msgs, list):
            return msgs
        return []

    @staticmethod
    def _message_role(msg: Any) -> str:
        if isinstance(msg, dict):
            return str(msg.get("role") or msg.get("type") or "")
        role = getattr(msg, "type", None) or getattr(msg, "role", None) or ""
        role = str(role)
        role_map = {
            "human": "user",
            "ai": "assistant",
            "tool": "tool",
            "system": "system",
        }
        return role_map.get(role, role)

    @staticmethod
    def _message_name(msg: Any) -> str:
        if isinstance(msg, dict):
            return str(msg.get("name") or "")
        return str(getattr(msg, "name", "") or "")

    def _message_content(self, msg: Any) -> str:
        if isinstance(msg, dict):
            return self._to_text(msg.get("content"))
        return self._to_text(getattr(msg, "content", ""))

    @staticmethod
    def _message_tool_calls(msg: Any) -> List[Dict[str, Any]]:
        if isinstance(msg, dict):
            calls = msg.get("tool_calls")
            return list(calls) if isinstance(calls, list) else []
        calls = getattr(msg, "tool_calls", None)
        return list(calls) if isinstance(calls, list) else []

    def _emit_tool_events(
        self,
        messages: List[Any],
        session_id: str,
        user_id: str,
        turn_pair_id: int,
    ) -> None:
        for msg in messages:
            role = self._message_role(msg)

            tool_calls = self._message_tool_calls(msg)
            for call in tool_calls:
                if not isinstance(call, dict):
                    continue
                name = str(call.get("name") or "")
                args = call.get("args") if isinstance(call.get("args"), dict) else {}
                if not name:
                    fn = call.get("function") or {}
                    if isinstance(fn, dict):
                        name = str(fn.get("name") or "")
                if not name:
                    continue
                self._emit_observer(
                    "tool_called",
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "turn_pair_id": turn_pair_id,
                        "tool_name": name,
                        "tool_args": args,
                        "tool_result": "",
                        "latency_ms": 0.0,
                    },
                )

            if role == "tool":
                self._emit_observer(
                    "tool_called",
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "turn_pair_id": turn_pair_id,
                        "tool_name": self._message_name(msg),
                        "tool_args": {},
                        "tool_result": self._message_content(msg)[:1000],
                        "latency_ms": 0.0,
                    },
                )

    def _extract_assistant_text(self, messages: List[Any]) -> str:
        candidates: List[str] = []
        for msg in messages:
            role = self._message_role(msg)
            if role != "assistant":
                continue
            text = self._message_content(msg).strip()
            if text:
                candidates.append(text)
        if not candidates:
            return ""
        return candidates[-1]

    def handle_turn(
        self,
        user_message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        turn_pair: Optional[Dict[str, Any]] = None,
    ) -> str:
        session_id = session_id or f"langmem_session_{self.dialog_id}"
        user_id = user_id or f"langmem_user_{self.dialog_id}"

        session = self._get_or_create_session(session_id)
        turn_pair_id = int((turn_pair or {}).get("turn_pair_id") or (session.turn_count + 1))
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

        short_term_context = self._build_short_term_context(session)
        raw_items = self._search_memories(user_id=user_id, query=user_message)
        recall_items = self._format_recall_items(raw_items)
        packed_context = self._build_packed_context(recall_items, short_term_context)
        self._emit_observer(
            "recall_done",
            {
                "session_id": session_id,
                "user_id": user_id,
                "turn_pair_id": turn_pair_id,
                "query": user_message,
                "short_term_context": short_term_context,
                "short_term_turns": session.short_history[-(self.short_term_n * 2) :],
                "profile_context": "",
                "packed_context": packed_context,
                "token_count": int(len(packed_context) / 2.5),
                "recalled_items": [
                    {
                        "id": it["id"],
                        "content": it["content"],
                        "score": it["score"],
                        "source": it["source"],
                        "turn_index": it["turn_index"],
                        "session_id": it["session_id"],
                    }
                    for it in recall_items
                ],
            },
        )

        result = self._invoke_agent(
            user_message=user_message,
            packed_context=packed_context,
            session_id=session_id,
            user_id=user_id,
        )
        messages = self._iter_messages(result)
        self._emit_tool_events(
            messages=messages,
            session_id=session_id,
            user_id=user_id,
            turn_pair_id=turn_pair_id,
        )
        assistant_text = self._extract_assistant_text(messages)
        if not assistant_text:
            assistant_text = "I am unable to produce a valid response for this turn."

        session.short_history.append({"role": "user", "content": user_message})
        session.short_history.append({"role": "assistant", "content": assistant_text})
        if len(session.short_history) > 40:
            session.short_history = session.short_history[-40:]
        session.turn_count += 1

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
