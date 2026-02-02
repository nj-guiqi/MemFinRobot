"""动态窗口选择器 - 基于LLM选择与当前查询最相关的历史片段"""

import logging
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from memfinrobot.memory.schemas import WindowSelectionResult

logger = logging.getLogger(__name__)


# 窗口选择提示词模板
WINDOW_SELECTION_PROMPT = """你是一个对话历史分析助手。给定一段对话历史和当前查询，你需要识别出与当前查询最相关的历史对话轮次索引。

任务：分析对话历史，找出对理解当前查询最重要的历史轮次。

规则：
1. 返回最相关的历史轮次索引列表（从0开始）
2. 如果当前查询是独立的，不依赖历史，返回空列表 []
3. 只返回Python列表格式，如 [0, 2, 5] 或 []

示例：
- 如果历史[0]和[3]与当前查询相关，返回: [0, 3]
- 如果查询独立，返回: []

对话历史:
{dialogue_history}

当前查询: {current_query}

请直接返回相关历史轮次的索引列表:"""


class WindowSelector:
    """
    动态窗口选择器
    
    基于LLM选择"与当前query最相关的历史片段索引"
    支持多次采样+投票以降低不确定性
    """
    
    def __init__(
        self,
        llm_client: Optional[Any] = None,
        max_window_size: int = 15,
        vote_times: int = 5,
        confidence_threshold: float = 0.6,
        temperature: float = 0.3,
    ):
        """
        初始化窗口选择器
        
        Args:
            llm_client: LLM客户端（需实现chat方法）
            max_window_size: 最大窗口大小
            vote_times: 投票次数
            confidence_threshold: 置信度阈值
            temperature: 采样温度
        """
        self.llm_client = llm_client
        self.max_window_size = max_window_size
        self.vote_times = vote_times
        self.confidence_threshold = confidence_threshold
        self.temperature = temperature
    
    def select(
        self,
        dialogue_history: List[str],
        current_query: str,
    ) -> WindowSelectionResult:
        """
        选择与当前查询最相关的历史窗口
        
        Args:
            dialogue_history: 对话历史列表
            current_query: 当前查询
            
        Returns:
            WindowSelectionResult 包含选中的索引、置信度和调试信息
        """
        if not dialogue_history:
            return WindowSelectionResult(
                selected_indices=[],
                confidence=1.0,
                debug_info={"reason": "empty_history"}
            )
        
        # 截取最近的历史窗口
        recent_history = dialogue_history[-self.max_window_size:]
        offset = max(0, len(dialogue_history) - self.max_window_size)
        
        # 如果没有LLM客户端，使用回退策略
        if self.llm_client is None:
            return self._fallback_selection(recent_history, offset)
        
        # 多次采样投票
        predictions = []
        for _ in range(self.vote_times):
            try:
                indices = self._single_selection(recent_history, current_query)
                if indices is not None:
                    predictions.append(tuple(indices))
            except Exception as e:
                logger.warning(f"Window selection failed: {e}")
                continue
        
        if not predictions:
            logger.warning("All window selection attempts failed, using fallback")
            return self._fallback_selection(recent_history, offset)
        
        # 投票统计
        counts = Counter(predictions)
        best_win, freq = counts.most_common(1)[0]
        confidence = freq / self.vote_times
        
        # 调整索引偏移
        adjusted_indices = [idx + offset for idx in best_win]
        
        # 判断置信度
        if confidence < self.confidence_threshold:
            logger.info(f"Low confidence ({confidence:.2f}), using fallback")
            return WindowSelectionResult(
                selected_indices=adjusted_indices,
                confidence=confidence,
                debug_info={
                    "reason": "low_confidence",
                    "predictions": [list(p) for p in predictions],
                    "vote_counts": dict(counts),
                }
            )
        
        logger.info(f"High confidence ({confidence:.2f}), selected: {adjusted_indices}")
        return WindowSelectionResult(
            selected_indices=adjusted_indices,
            confidence=confidence,
            debug_info={
                "reason": "vote_success",
                "predictions": [list(p) for p in predictions],
                "vote_counts": {str(k): v for k, v in counts.items()},
            }
        )
    
    def _single_selection(
        self,
        dialogue_history: List[str],
        current_query: str,
    ) -> Optional[List[int]]:
        """单次LLM选择"""
        # 格式化历史对话
        formatted_history = "\n".join([
            f"[{idx}] {turn}" for idx, turn in enumerate(dialogue_history)
        ])
        
        prompt = WINDOW_SELECTION_PROMPT.format(
            dialogue_history=formatted_history,
            current_query=current_query,
        )
        
        # 调用LLM
        messages = [{"role": "user", "content": prompt}]
        
        response = self.llm_client.chat(
            messages=messages,
            stream=False,
            extra_generate_cfg={"temperature": self.temperature},
        )
        
        # 解析响应
        if hasattr(response, '__iter__'):
            for r in response:
                if r:
                    response_text = r[-1].content if hasattr(r[-1], 'content') else str(r[-1])
                    break
        else:
            response_text = str(response)
        
        try:
            # 尝试解析为Python列表
            result = eval(response_text.strip())
            if isinstance(result, list):
                return [int(idx) for idx in result if 0 <= int(idx) < len(dialogue_history)]
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {response_text}, error: {e}")
        
        return None
    
    def _fallback_selection(
        self,
        dialogue_history: List[str],
        offset: int = 0,
    ) -> WindowSelectionResult:
        """回退策略：选择最近的几轮对话"""
        fallback_size = min(3, len(dialogue_history))
        indices = list(range(len(dialogue_history) - fallback_size, len(dialogue_history)))
        adjusted_indices = [idx + offset for idx in indices]
        
        return WindowSelectionResult(
            selected_indices=adjusted_indices,
            confidence=0.5,
            debug_info={"reason": "fallback", "fallback_size": fallback_size}
        )
