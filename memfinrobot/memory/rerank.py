"""记忆重排模块 - 使用Reranker或LLM进行重排"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from memfinrobot.memory.schemas import MemoryItem, RecallResult

logger = logging.getLogger(__name__)


class MemoryReranker:
    """
    记忆重排器
    
    支持：
    - BGE Reranker
    - LLM Rerank
    - 简单的规则重排
    """
    
    def __init__(
        self,
        reranker_model_path: str = "",
        device: str = "cuda",
        threshold: float = 0.35,
        use_llm_rerank: bool = False,
        llm_client: Optional[Any] = None,
    ):
        """
        初始化重排器
        
        Args:
            reranker_model_path: Reranker模型路径
            device: 运行设备
            threshold: 分数阈值
            use_llm_rerank: 是否使用LLM重排
            llm_client: LLM客户端
        """
        self.reranker_model_path = reranker_model_path
        self.device = device
        self.threshold = threshold
        self.use_llm_rerank = use_llm_rerank
        self.llm_client = llm_client
        
        self.reranker = None
        self._initialized = False
    
    def _lazy_init(self) -> None:
        """延迟初始化Reranker模型"""
        if self._initialized:
            return
        
        if self.reranker_model_path:
            try:
                from FlagEmbedding import FlagReranker
                
                logger.info(f"Loading Reranker from {self.reranker_model_path}")
                self.reranker = FlagReranker(
                    self.reranker_model_path,
                    device=self.device,
                )
                logger.info("Reranker loaded successfully")
            except ImportError:
                logger.warning("FlagEmbedding not installed, reranker disabled")
            except Exception as e:
                logger.warning(f"Failed to load reranker: {e}")
        
        self._initialized = True
    
    def rerank(
        self,
        query: str,
        recall_result: RecallResult,
    ) -> RecallResult:
        """
        重排召回结果
        
        Args:
            query: 查询文本
            recall_result: 召回结果
            
        Returns:
            重排后的RecallResult
        """
        if not recall_result.items:
            return recall_result
        
        # 尝试使用Reranker模型
        self._lazy_init()
        
        if self.reranker is not None:
            return self._rerank_with_model(query, recall_result)
        elif self.use_llm_rerank and self.llm_client is not None:
            return self._rerank_with_llm(query, recall_result)
        else:
            return self._rerank_with_rules(query, recall_result)
    
    def _rerank_with_model(
        self,
        query: str,
        recall_result: RecallResult,
    ) -> RecallResult:
        """使用Reranker模型重排"""
        try:
            # 构建query-document对
            pairs = [
                (query, item.hierarchical_content or item.content)
                for item in recall_result.items
            ]
            
            # 计算重排分数
            scores = self.reranker.compute_score(pairs, normalize=True)
            
            if isinstance(scores, np.ndarray):
                scores = scores.tolist()
            elif not isinstance(scores, list):
                scores = [scores]
            
            # 过滤低分项
            filtered_items = []
            filtered_scores = []
            filtered_sources = []
            
            for item, score, source in zip(
                recall_result.items,
                scores,
                recall_result.sources,
            ):
                if score > self.threshold:
                    filtered_items.append(item)
                    filtered_scores.append(score)
                    filtered_sources.append(source)
            
            # 按分数排序
            sorted_indices = np.argsort(filtered_scores)[::-1]
            
            return RecallResult(
                items=[filtered_items[i] for i in sorted_indices],
                scores=[filtered_scores[i] for i in sorted_indices],
                sources=[filtered_sources[i] for i in sorted_indices],
            )
            
        except Exception as e:
            logger.warning(f"Rerank with model failed: {e}")
            return recall_result
    
    def _rerank_with_llm(
        self,
        query: str,
        recall_result: RecallResult,
    ) -> RecallResult:
        """使用LLM重排（V0简化实现）"""
        # V0版本暂不实现LLM重排，直接返回原结果
        return recall_result
    
    def _rerank_with_rules(
        self,
        query: str,
        recall_result: RecallResult,
    ) -> RecallResult:
        """使用简单规则重排"""
        # 基于时间衰减和原始分数的简单重排
        items = recall_result.items
        scores = recall_result.scores
        sources = recall_result.sources
        
        if not items:
            return recall_result
        
        # 计算调整后的分数
        adjusted_scores = []
        for i, (item, score) in enumerate(zip(items, scores)):
            # 时间衰减因子（简化版本）
            time_factor = 1.0 - (i * 0.02)  # 越靠后的轮次略微降权
            adjusted_score = score * max(time_factor, 0.5)
            adjusted_scores.append(adjusted_score)
        
        # 排序
        sorted_indices = np.argsort(adjusted_scores)[::-1]
        
        return RecallResult(
            items=[items[i] for i in sorted_indices],
            scores=[adjusted_scores[i] for i in sorted_indices],
            sources=[sources[i] for i in sorted_indices],
        )


def deduplicate_memories(
    items: List[MemoryItem],
    scores: List[float],
    similarity_threshold: float = 0.95,
) -> Tuple[List[MemoryItem], List[float]]:
    """
    去重记忆条目
    
    相同事实多条命中时合并（保留最高分的）
    
    Args:
        items: 记忆条目列表
        scores: 对应分数
        similarity_threshold: 相似度阈值
        
    Returns:
        去重后的条目和分数
    """
    if not items:
        return [], []
    
    # 简单的基于内容的去重
    seen_contents = {}
    deduped_items = []
    deduped_scores = []
    
    for item, score in zip(items, scores):
        content = item.hierarchical_content or item.content
        content_key = content[:100]  # 使用前100字符作为key
        
        if content_key not in seen_contents:
            seen_contents[content_key] = (item, score)
            deduped_items.append(item)
            deduped_scores.append(score)
        else:
            # 保留分数更高的
            existing_item, existing_score = seen_contents[content_key]
            if score > existing_score:
                # 替换
                idx = deduped_items.index(existing_item)
                deduped_items[idx] = item
                deduped_scores[idx] = score
                seen_contents[content_key] = (item, score)
    
    return deduped_items, deduped_scores
