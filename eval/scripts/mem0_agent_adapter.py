"""Mem0 评测适配器：提供与 replay 兼容的 handle_turn 接口。"""

from __future__ import annotations

import os
import sys
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

# 确保优先使用仓库内 mem0 实现
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEM0_ROOT = PROJECT_ROOT / "eval" / "mem0"
if str(MEM0_ROOT) not in sys.path:
    sys.path.insert(0, str(MEM0_ROOT))

from mem0 import Memory  # type: ignore
from memfinrobot.agent.memfin_agent import MEMFIN_SYSTEM_PROMPT

_MEM0_INIT_LOCK = threading.Lock()


@dataclass
class _SessionState:
    turn_count: int = 0
    short_history: List[Dict[str, str]] = field(default_factory=list)


class Mem0AgentAdapter:
    """将 mem0 + OpenAI 兼容接口封装为评测所需的 agent 形态。"""

    def __init__(
        self,
        dialog_id: str,
        observer: Optional[Any],
        mem_store_dir: Path,
        base_url: str,
        chat_model: str,
        api_key_env: str = "DASHSCOPE_API_KEY",
        api_key: Optional[str] = None,
        enable_thinking: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        recall_limit: int = 10,
        short_term_n: int = 3,
        embedder_provider: str = "openai",
        embedding_model: str = "text-embedding-v3",
        embedding_dims: int = 1024,
        vector_store_provider: str = "qdrant",
        mem0_infer: bool = True,
        system_context: Optional[str] = None,
        request_timeout_sec: float = 120.0,
    ) -> None:
        self.dialog_id = dialog_id
        self.observer = observer
        self.mem_store_dir = Path(mem_store_dir)
        self.base_url = base_url
        self.chat_model = chat_model
        self.enable_thinking = enable_thinking
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.recall_limit = recall_limit
        self.short_term_n = short_term_n
        self.mem0_infer = mem0_infer
        self.system_context = system_context or MEMFIN_SYSTEM_PROMPT
        self.request_timeout_sec = max(1.0, float(request_timeout_sec))

        self._sessions: Dict[str, _SessionState] = {}

        resolved_api_key = api_key or os.getenv(api_key_env) or os.getenv("DASHSCOPE_API_KEY")
        if not resolved_api_key:
            raise ValueError(
                f"Missing API key. Please set env `{api_key_env}` (or DASHSCOPE_API_KEY) or pass --api-key."
            )
        self.api_key = resolved_api_key

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.request_timeout_sec,
            max_retries=2,
        )

        self.mem_store_dir.mkdir(parents=True, exist_ok=True)
        self.memory = self._init_memory_client(
            embedder_provider=embedder_provider,
            embedding_model=embedding_model,
            embedding_dims=embedding_dims,
            vector_store_provider=vector_store_provider,
        )

    def _init_memory_client(
        self,
        embedder_provider: str,
        embedding_model: str,
        embedding_dims: int,
        vector_store_provider: str,
    ) -> Any:
        """初始化 mem0 Memory，并将内部迁移目录隔离到当前 dialog。"""
        cfg = self._build_mem0_config(
            embedder_provider=embedder_provider,
            embedding_model=embedding_model,
            embedding_dims=embedding_dims,
            vector_store_provider=vector_store_provider,
        )

        isolated_mem0_dir = str(self.mem_store_dir / "mem0_runtime")
        Path(isolated_mem0_dir).mkdir(parents=True, exist_ok=True)

        import mem0.memory.main as mem0_main_module  # type: ignore
        import mem0.memory.setup as mem0_setup_module  # type: ignore

        old_env_mem0_dir = os.environ.get("MEM0_DIR")
        old_env_openai_timeout = os.environ.get("MEM0_OPENAI_TIMEOUT_SEC")
        old_setup_mem0_dir = getattr(mem0_setup_module, "mem0_dir", None)
        old_main_mem0_dir = getattr(mem0_main_module, "mem0_dir", None)

        with _MEM0_INIT_LOCK:
            try:
                os.environ["MEM0_DIR"] = isolated_mem0_dir
                os.environ["MEM0_OPENAI_TIMEOUT_SEC"] = str(self.request_timeout_sec)
                mem0_setup_module.mem0_dir = isolated_mem0_dir
                mem0_main_module.mem0_dir = isolated_mem0_dir
                mem0_setup_module.setup_config()
                memory = Memory.from_config(cfg)
            finally:
                if old_env_mem0_dir is None:
                    os.environ.pop("MEM0_DIR", None)
                else:
                    os.environ["MEM0_DIR"] = old_env_mem0_dir
                if old_env_openai_timeout is None:
                    os.environ.pop("MEM0_OPENAI_TIMEOUT_SEC", None)
                else:
                    os.environ["MEM0_OPENAI_TIMEOUT_SEC"] = old_env_openai_timeout
                if old_setup_mem0_dir is not None:
                    mem0_setup_module.mem0_dir = old_setup_mem0_dir
                if old_main_mem0_dir is not None:
                    mem0_main_module.mem0_dir = old_main_mem0_dir

        return memory

    def _build_mem0_config(
        self,
        embedder_provider: str,
        embedding_model: str,
        embedding_dims: int,
        vector_store_provider: str,
    ) -> Dict[str, Any]:
        vector_cfg: Dict[str, Any]
        if vector_store_provider == "qdrant":
            vector_cfg = {
                "path": str(self.mem_store_dir / "qdrant"),
                "collection_name": f"mem0_eval_{self.dialog_id}",
                "embedding_model_dims": embedding_dims,
                "on_disk": True,
            }
        elif vector_store_provider == "faiss":
            vector_cfg = {
                "path": str(self.mem_store_dir / "faiss"),
                "collection_name": f"mem0_eval_{self.dialog_id}",
                "embedding_model_dims": embedding_dims,
            }
        else:
            raise ValueError(f"Unsupported vector_store_provider: {vector_store_provider}")

        cfg: Dict[str, Any] = {
            "version": "v1.1",
            "history_db_path": str(self.mem_store_dir / "history.db"),
            "llm": {
                "provider": "openai",
                "config": {
                    "model": self.chat_model,
                    "api_key": self.api_key,
                    "openai_base_url": self.base_url,
                    "temperature": 0.1,
                    "max_tokens": 2000,
                },
            },
            "embedder": {
                "provider": embedder_provider,
                "config": {},
            },
            "vector_store": {
                "provider": vector_store_provider,
                "config": vector_cfg,
            },
        }

        # 优先支持 OpenAI 兼容嵌入；其他 provider 走其默认配置
        if embedder_provider == "openai":
            cfg["embedder"]["config"] = {
                "model": embedding_model,
                "api_key": self.api_key,
                "openai_base_url": self.base_url,
                "embedding_dims": embedding_dims,
            }
        elif embedder_provider == "huggingface":
            cfg["embedder"]["config"] = {
                "model": embedding_model,
                "embedding_dims": embedding_dims,
            }

        return cfg

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

    def _format_recall_items(self, search_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = search_result.get("results") or []
        formatted: List[Dict[str, Any]] = []
        for idx, item in enumerate(results):
            metadata = item.get("metadata") or {}
            formatted.append(
                {
                    "rank": idx + 1,
                    "id": str(item.get("id") or ""),
                    "content": str(item.get("memory") or ""),
                    "score": float(item.get("score") or 0.0),
                    "source": str(metadata.get("source") or "long_term"),
                    "turn_index": int(metadata.get("turn_pair_id") or 0),
                    "session_id": str(metadata.get("session_id") or ""),
                    "metadata": metadata,
                }
            )
        return formatted

    def _build_packed_context(self, recall_items: List[Dict[str, Any]], short_term_context: str) -> str:
        lines: List[str] = []
        if short_term_context:
            lines.append("[近期对话]")
            lines.append(short_term_context)
        if recall_items:
            lines.append("[长期记忆召回]")
            for it in recall_items:
                lines.append(f"- score={it['score']:.4f} | {it['content']}")
        return "\n".join(lines)

    def _chat(self, user_message: str, packed_context: str) -> str:
        system_text = self.system_context
        if packed_context:
            system_text += f"\n\n---\n相关历史记忆与短期上下文：\n{packed_context}\n---"

        kwargs: Dict[str, Any] = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": system_text},
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

    def _store_memory(
        self,
        user_id: str,
        user_message: str,
        assistant_message: str,
        session_id: str,
        turn_pair_id: int,
        turn_pair: Optional[Dict[str, Any]],
    ) -> None:
        gt_tags = (turn_pair or {}).get("gt_turn_tags") or {}
        metadata: Dict[str, Any] = {
            "dialog_id": self.dialog_id,
            "session_id": session_id,
            "turn_pair_id": turn_pair_id,
            "source": "long_term",
            "memory_required_keys_gt": gt_tags.get("memory_required_keys_gt") or [],
            "risk_disclosure_required_gt": gt_tags.get("risk_disclosure_required_gt") or [],
        }
        messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message},
        ]
        try:
            self.memory.add(messages, user_id=user_id, metadata=metadata, infer=self.mem0_infer)
        except Exception:
            # 兜底：至少将原始对话写入记忆，避免整轮失败
            self.memory.add(messages, user_id=user_id, metadata=metadata, infer=False)

    def handle_turn(
        self,
        user_message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        turn_pair: Optional[Dict[str, Any]] = None,
    ) -> str:
        session_id = session_id or f"mem0_session_{self.dialog_id}"
        user_id = user_id or f"mem0_user_{self.dialog_id}"

        session = self._get_or_create_session(session_id)
        turn_pair_id = session.turn_count + 1
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

        search_result = self.memory.search(query=user_message, user_id=user_id, limit=self.recall_limit)
        recall_items = self._format_recall_items(search_result)
        short_term_context = self._build_short_term_context(session)
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

        assistant_text = self._chat(user_message=user_message, packed_context=packed_context)
        self._store_memory(
            user_id=user_id,
            user_message=user_message,
            assistant_message=assistant_text,
            session_id=session_id,
            turn_pair_id=turn_pair_id,
            turn_pair=turn_pair,
        )

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
