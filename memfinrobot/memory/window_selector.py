"""动态窗口选择器：基于 LLM 选择与当前查询最相关的历史片段。"""

import ast
import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from memfinrobot.memory.schemas import WindowSelectionResult

logger = logging.getLogger(__name__)


WINDOW_SELECTION_PROMPT = """你是一个对话历史分析助手。给定一段对话历史和当前查询，你需要识别出与当前查询最相关的历史对话轮次索引。

任务：分析对话历史，找出对理解当前查询最重要的历史轮次。

规则：
1. 返回最相关的历史轮次索引列表（从 0 开始）
2. 如果当前查询是独立的，不依赖历史，返回空列表 []
3. 只返回 Python 列表格式，如 [0, 2, 5] 或 []

示例：
- 如果历史[0]和[3]与当前查询相关，返回: [0, 3]
- 如果查询独立，返回: []

对话历史:
{dialogue_history}

当前查询: {current_query}

请直接返回相关历史轮次的索引列表:"""


class WindowSelector:
    """通过多次采样投票，选择最相关历史窗口。"""

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        max_window_size: int = 15,
        vote_times: int = 5,
        confidence_threshold: float = 0.6,
        temperature: float = 0.3,
    ):
        self.llm_client = llm_client
        self.max_window_size = max_window_size
        self.vote_times = vote_times
        self.confidence_threshold = confidence_threshold
        self.temperature = temperature

    def select(self, dialogue_history: List[str], current_query: str) -> WindowSelectionResult:
        if not dialogue_history:
            return WindowSelectionResult(selected_indices=[], confidence=1.0, debug_info={"reason": "empty_history"})

        recent_history = dialogue_history[-self.max_window_size :]
        offset = max(0, len(dialogue_history) - self.max_window_size)

        if self.llm_client is None:
            return self._fallback_selection(recent_history, offset)

        predictions = []
        for _ in range(self.vote_times):
            try:
                indices = self._single_selection(recent_history, current_query)
                if indices is not None:
                    predictions.append(tuple(indices))
            except Exception as exc:
                logger.warning(f"Window selection failed: {exc}")

        if not predictions:
            logger.warning("All window selection attempts failed, using fallback")
            return self._fallback_selection(recent_history, offset)

        counts = Counter(predictions)
        best_win, freq = counts.most_common(1)[0]
        confidence = freq / self.vote_times
        adjusted_indices = [idx + offset for idx in best_win]

        if confidence < self.confidence_threshold:
            logger.info(f"Low confidence ({confidence:.2f}), using low-confidence result")
            return WindowSelectionResult(
                selected_indices=adjusted_indices,
                confidence=confidence,
                debug_info={
                    "reason": "low_confidence",
                    "predictions": [list(p) for p in predictions],
                    "vote_counts": {str(k): v for k, v in counts.items()},
                },
            )

        logger.info(f"High confidence ({confidence:.2f}), selected: {adjusted_indices}")
        return WindowSelectionResult(
            selected_indices=adjusted_indices,
            confidence=confidence,
            debug_info={
                "reason": "vote_success",
                "predictions": [list(p) for p in predictions],
                "vote_counts": {str(k): v for k, v in counts.items()},
            },
        )

    def _single_selection(self, dialogue_history: List[str], current_query: str) -> Optional[List[int]]:
        formatted_history = "\n".join([f"[{idx}] {turn}" for idx, turn in enumerate(dialogue_history)])
        prompt = WINDOW_SELECTION_PROMPT.format(dialogue_history=formatted_history, current_query=current_query)

        messages = [{"role": "user", "content": prompt}]
        # 使用流式，兼容 use_raw_api 场景
        response = self.llm_client.chat(
            messages=messages,
            stream=True,
            extra_generate_cfg={"temperature": self.temperature},
        )

        response_text = self._extract_response_text(response)
        if not response_text:
            return None

        try:
            result = ast.literal_eval(response_text.strip())
            if isinstance(result, list):
                return [int(idx) for idx in result if 0 <= int(idx) < len(dialogue_history)]
        except Exception as exc:
            logger.warning(f"Failed to parse LLM response: {response_text}, error: {exc}")
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

    def _fallback_selection(self, dialogue_history: List[str], offset: int = 0) -> WindowSelectionResult:
        fallback_size = min(3, len(dialogue_history))
        indices = list(range(len(dialogue_history) - fallback_size, len(dialogue_history)))
        adjusted_indices = [idx + offset for idx in indices]

        return WindowSelectionResult(
            selected_indices=adjusted_indices,
            confidence=0.5,
            debug_info={"reason": "fallback", "fallback_size": fallback_size},
        )
