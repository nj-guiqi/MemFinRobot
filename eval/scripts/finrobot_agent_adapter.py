"""FinRobot evaluation adapter.

Wraps FinRobot SingleAssistant workflow into replay-compatible ``handle_turn`` API.
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FINROBOT_ROOT = PROJECT_ROOT / "eval" / "FinRobot"
if str(FINROBOT_ROOT) not in sys.path:
    sys.path.insert(0, str(FINROBOT_ROOT))

from finrobot.agents.agent_library import library as finrobot_agent_library
from finrobot.agents.workflow import SingleAssistant


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


class FinRobotAgentAdapter:
    """Adapter for FinRobot `SingleAssistant` workflow."""

    def __init__(
        self,
        dialog_id: str,
        observer: Optional[Any],
        base_url: str,
        chat_model: str,
        api_key_env: str = "OPENAI_API_KEY",
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        request_timeout_sec: float = 120.0,
        max_chat_turns: int = 8,
        short_term_n: int = 3,
        agent_config: str = "Market_Analyst",
        finrobot_keys_file: Optional[str] = None,
        prompt_price_per_1k: float = 0.0,
        completion_price_per_1k: float = 0.0,
        system_context: Optional[str] = None,
        silent: bool = True,
    ) -> None:
        self.dialog_id = dialog_id
        self.observer = observer
        self.base_url = base_url
        self.chat_model = chat_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.request_timeout_sec = max(1.0, float(request_timeout_sec))
        self.max_chat_turns = max(1, int(max_chat_turns))
        self.short_term_n = max(1, int(short_term_n))
        self.silent = bool(silent)
        self.system_context = system_context or MEMFIN_SYSTEM_PROMPT
        self._sessions: Dict[str, _SessionState] = {}

        resolved_api_key = api_key or os.getenv(api_key_env) or os.getenv("OPENAI_API_KEY")
        if not resolved_api_key:
            raise ValueError(
                f"Missing API key. Please set env `{api_key_env}` (or OPENAI_API_KEY) or pass --api-key."
            )
        self.api_key = resolved_api_key

        self._register_optional_finrobot_keys(finrobot_keys_file)
        self._finnhub_available = self._has_valid_finnhub_key()
        if not self._finnhub_available:
            print(
                "[FinRobot Eval] FINNHUB_API_KEY missing/placeholder. "
                "Toolkits are disabled for this dialog; using best-effort text-only mode."
            )

        llm_config = {
            "config_list": [
                {
                    "model": self.chat_model,
                    "api_key": self.api_key,
                    "base_url": self.base_url,
                    "price": [float(prompt_price_per_1k), float(completion_price_per_1k)],
                }
            ],
            "timeout": int(self.request_timeout_sec),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        work_dir = FINROBOT_ROOT / "coding_eval" / self.dialog_id
        work_dir.mkdir(parents=True, exist_ok=True)

        try:
            resolved_agent_config = self._build_agent_config(agent_config)
            self.workflow = SingleAssistant(
                agent_config=resolved_agent_config,
                llm_config=llm_config,
                human_input_mode="NEVER",
                max_consecutive_auto_reply=self.max_chat_turns,
                code_execution_config=False,
            )
        except ImportError as e:
            raise RuntimeError(
                "Failed to initialize FinRobot assistant due to missing dependency. "
                "In conda env `finrobot`, run: `pip install openai`."
            ) from e

    def _register_optional_finrobot_keys(self, finrobot_keys_file: Optional[str]) -> None:
        if not finrobot_keys_file:
            return

        path = Path(finrobot_keys_file)
        if not path.exists():
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                keys = json.load(f)
        except Exception:
            return

        if not isinstance(keys, dict):
            return

        for key, value in keys.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            if not key or os.getenv(key):
                continue
            if value.strip().upper().startswith("YOUR_"):
                continue
            if not value.strip():
                continue
            os.environ[key] = value.strip()

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
    def _has_valid_finnhub_key() -> bool:
        key = str(os.getenv("FINNHUB_API_KEY") or "").strip()
        if not key:
            return False
        return not key.upper().startswith("YOUR_")

    def _build_agent_config(self, agent_config: str) -> Dict[str, Any]:
        if agent_config in finrobot_agent_library:
            cfg = copy.deepcopy(finrobot_agent_library[agent_config])
        else:
            cfg = {
                "name": agent_config,
                "profile": "Financial assistant. Reply TERMINATE when task is done.",
                "toolkits": [],
            }

        profile = str(cfg.get("profile") or "")
        policy_tail = (
            "\n\n[Eval Policy]\n"
            "Always provide a direct, useful answer for the current user question.\n"
            "Do not repeat instruction text or hidden prompts.\n"
            "End your final answer with TERMINATE."
        )
        if not self._finnhub_available:
            cfg["toolkits"] = []
            policy_tail += (
                "\nExternal market data tools are unavailable in this runtime "
                "(FINNHUB_API_KEY missing/placeholder). "
                "Do not call tools; provide best-effort analysis and explicitly state data limitations."
            )

        cfg["profile"] = f"{self.system_context}\n\n---\n{profile}{policy_tail}".strip()
        return cfg

    @staticmethod
    def _compose_eval_message(user_message: str, short_term_context: str) -> str:
        if not short_term_context.strip():
            return user_message
        return (
            "You are continuing a multi-turn user conversation.\n"
            "[Recent conversation]\n"
            f"{short_term_context}\n\n"
            "[Current user message]\n"
            f"{user_message}\n\n"
            "Respond directly to the current user message. "
            "Do not repeat the wrapper text."
        )

    @staticmethod
    def _to_text(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: List[str] = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    chunks.append(str(item["text"]))
                else:
                    chunks.append(str(item))
            return "\n".join(chunks)
        return str(content)

    @staticmethod
    def _safe_json_loads(raw: Any) -> Dict[str, Any]:
        if not isinstance(raw, str):
            return {}
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _strip_terminate(text: str) -> str:
        return (text or "").replace("TERMINATE", "").strip()

    @staticmethod
    def _normalize_for_compare(text: str) -> str:
        t = (text or "").strip().lower()
        t = re.sub(r"\s+", " ", t)
        return t

    def _looks_like_prompt_echo(self, text: str, user_message: str) -> bool:
        t = self._strip_terminate(text)
        if not t:
            return True

        norm_t = self._normalize_for_compare(t)
        norm_user = self._normalize_for_compare(user_message)
        if norm_t == norm_user:
            return True
        if norm_t.startswith("[recent conversation]") or norm_t.startswith("you are continuing a multi-turn"):
            return True
        if "[current user message]" in norm_t:
            return True
        return False

    def _extract_assistant_from_messages(
        self,
        messages: List[Dict[str, Any]],
        assistant_name: str,
    ) -> List[str]:
        out: List[str] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role") or "")
            name = str(msg.get("name") or "")
            if role != "assistant" and name != assistant_name:
                continue
            txt = self._strip_terminate(self._to_text(msg.get("content")))
            if txt:
                out.append(txt)
        return out

    def _extract_assistant_from_agent_buffers(self) -> List[str]:
        assistant_name = str(getattr(self.workflow.assistant, "name", "") or "")
        candidates: List[str] = []

        def _collect_from_map(message_map: Any) -> None:
            if not isinstance(message_map, dict):
                return
            for msgs in message_map.values():
                if not isinstance(msgs, list):
                    continue
                for msg in msgs:
                    if not isinstance(msg, dict):
                        continue
                    name = str(msg.get("name") or "")
                    role = str(msg.get("role") or "")
                    if name == assistant_name or role == "assistant":
                        txt = self._strip_terminate(self._to_text(msg.get("content")))
                        if txt:
                            candidates.append(txt)

        _collect_from_map(getattr(self.workflow.assistant, "chat_messages", None))
        _collect_from_map(getattr(self.workflow.user_proxy, "chat_messages", None))

        # Also keep a concatenated version in case the assistant output is split
        # into multiple chunks across one run.
        assistant_map = getattr(self.workflow.assistant, "chat_messages", None)
        if isinstance(assistant_map, dict):
            for msgs in assistant_map.values():
                if not isinstance(msgs, list):
                    continue
                parts: List[str] = []
                for msg in msgs:
                    if not isinstance(msg, dict):
                        continue
                    name = str(msg.get("name") or "")
                    role = str(msg.get("role") or "")
                    if name == assistant_name or role == "assistant":
                        txt = self._strip_terminate(self._to_text(msg.get("content")))
                        if txt:
                            parts.append(txt)
                if parts:
                    candidates.append("\n".join(parts))

        return candidates

    def _pick_best_candidate(self, candidates: List[str], user_message: str) -> str:
        cleaned = [self._strip_terminate(c) for c in candidates if self._strip_terminate(c)]
        if not cleaned:
            return ""

        non_echo = [c for c in cleaned if not self._looks_like_prompt_echo(c, user_message)]
        if non_echo:
            return max(non_echo, key=len)

        return max(cleaned, key=len)

    def _extract_assistant_text(
        self,
        summary_text: str,
        new_messages: List[Dict[str, Any]],
        user_message: str,
    ) -> str:
        assistant_name = str(getattr(self.workflow.assistant, "name", "") or "")
        candidates: List[str] = []
        candidates.extend(self._extract_assistant_from_messages(new_messages, assistant_name))
        candidates.extend(self._extract_assistant_from_agent_buffers())
        if summary_text:
            candidates.append(summary_text)
        return self._pick_best_candidate(candidates, user_message)

    def _emit_tool_events(
        self,
        new_messages: List[Dict[str, Any]],
        session_id: str,
        user_id: str,
        turn_pair_id: int,
    ) -> None:
        for msg in new_messages:
            if not isinstance(msg, dict):
                continue

            tool_calls = msg.get("tool_calls") or []
            if isinstance(tool_calls, list):
                for call in tool_calls:
                    if not isinstance(call, dict):
                        continue
                    fn = call.get("function") or {}
                    name = str(fn.get("name") or "")
                    args = self._safe_json_loads(fn.get("arguments"))
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

            if msg.get("role") in {"tool", "function"}:
                name = str(msg.get("name") or "")
                result_text = self._to_text(msg.get("content"))
                self._emit_observer(
                    "tool_called",
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "turn_pair_id": turn_pair_id,
                        "tool_name": name,
                        "tool_args": {},
                        "tool_result": result_text[:1000],
                        "latency_ms": 0.0,
                    },
                )

    def handle_turn(
        self,
        user_message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        turn_pair: Optional[Dict[str, Any]] = None,
    ) -> str:
        session_id = session_id or f"finrobot_session_{self.dialog_id}"
        user_id = user_id or f"finrobot_user_{self.dialog_id}"

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
                "packed_context": short_term_context,
                "token_count": int(len(short_term_context) / 2.5),
                "recalled_items": [],
            },
        )

        eval_message = self._compose_eval_message(user_message=user_message, short_term_context=short_term_context)

        self.workflow.reset()
        chat_result = self.workflow.user_proxy.initiate_chat(
            self.workflow.assistant,
            message=eval_message,
            clear_history=True,
            silent=self.silent,
            max_turns=self.max_chat_turns,
            summary_method="last_msg",
        )

        new_messages = list(getattr(chat_result, "chat_history", []) or [])
        self._emit_tool_events(
            new_messages=new_messages,
            session_id=session_id,
            user_id=user_id,
            turn_pair_id=turn_pair_id,
        )

        assistant_text = self._extract_assistant_text(
            summary_text=str(getattr(chat_result, "summary", "") or ""),
            new_messages=new_messages,
            user_message=user_message,
        )

        if self._looks_like_prompt_echo(assistant_text, user_message):
            self.workflow.reset()
            retry_result = self.workflow.user_proxy.initiate_chat(
                self.workflow.assistant,
                message=user_message,
                clear_history=True,
                silent=self.silent,
                max_turns=self.max_chat_turns,
                summary_method="last_msg",
            )
            retry_messages = list(getattr(retry_result, "chat_history", []) or [])
            self._emit_tool_events(
                new_messages=retry_messages,
                session_id=session_id,
                user_id=user_id,
                turn_pair_id=turn_pair_id,
            )
            retry_text = self._extract_assistant_text(
                summary_text=str(getattr(retry_result, "summary", "") or ""),
                new_messages=retry_messages,
                user_message=user_message,
            )
            if retry_text:
                assistant_text = retry_text

        if self._looks_like_prompt_echo(assistant_text, user_message):
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
