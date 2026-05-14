"""Observer utilities for the Streamlit demo."""

from __future__ import annotations

import copy
from threading import Lock
from typing import Any, Dict, List


class DemoTurnObserver:
    """Collect agent events and expose turn-level payloads for the UI."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._turn_payload: Dict[int, Dict[str, Any]] = {}
            self._event_log: List[Dict[str, Any]] = []

    def on_event(self, event: str, payload: Dict[str, Any]) -> None:
        turn_id = int(payload.get("turn_pair_id") or 0)
        with self._lock:
            self._event_log.append(
                {
                    "event": event,
                    "turn_pair_id": turn_id,
                    "payload": copy.deepcopy(payload),
                }
            )

            if turn_id <= 0:
                return

            bucket = self._turn_payload.setdefault(turn_id, {"tools": [], "events": []})
            bucket["events"].append({"event": event, "payload": copy.deepcopy(payload)})

            if event == "turn_start":
                bucket["query"] = payload.get("query", "")
            elif event == "recall_done":
                bucket["recall"] = {
                    "query": payload.get("query", ""),
                    "short_term_context": payload.get("short_term_context", ""),
                    "short_term_turns": payload.get("short_term_turns", []),
                    "profile_context": payload.get("profile_context", ""),
                    "packed_context": payload.get("packed_context", ""),
                    "token_count": payload.get("token_count", 0),
                    "items": [
                        {
                            "rank": idx + 1,
                            "item_id": item.get("id", ""),
                            "content": item.get("content", ""),
                            "score": item.get("score", 0.0),
                            "source": item.get("source", ""),
                            "turn_index": item.get("turn_index", 0),
                            "session_id": item.get("session_id", ""),
                        }
                        for idx, item in enumerate(payload.get("recalled_items") or [])
                    ],
                }
            elif event == "tool_called":
                bucket["tools"].append(
                    {
                        "tool_name": payload.get("tool_name", ""),
                        "args": payload.get("tool_args", {}),
                        "result_excerpt": payload.get("tool_result", ""),
                        "latency_ms": payload.get("latency_ms", 0.0),
                    }
                )
            elif event == "compliance_done":
                bucket["compliance"] = {
                    "needs_modification": payload.get("needs_modification", False),
                    "is_compliant": payload.get("is_compliant", True),
                    "violations": payload.get("violations", []),
                    "risk_disclaimer_added": payload.get("risk_disclaimer_added", False),
                    "suitability_warning": payload.get("suitability_warning"),
                }
            elif event == "profile_snapshot":
                bucket["profile_snapshot"] = payload.get("profile", {})
            elif event == "turn_end":
                bucket["turn_end"] = {
                    "latency_ms": payload.get("latency_ms", 0.0),
                    "final_content": payload.get("final_content", ""),
                }

    def latest_turn_id(self) -> int:
        with self._lock:
            return max(self._turn_payload.keys(), default=0)

    def list_turn_ids(self) -> List[int]:
        with self._lock:
            return sorted(self._turn_payload.keys())

    def get_turn_payload(self, turn_pair_id: int) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._turn_payload.get(turn_pair_id, {}))

    def get_all_turn_payloads(self) -> Dict[int, Dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._turn_payload)

    def get_event_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._event_log)
