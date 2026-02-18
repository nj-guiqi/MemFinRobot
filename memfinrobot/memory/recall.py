"""记忆召回模块 - 多路召回与融合"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from memfinrobot.memory.schemas import MemoryItem, RecallResult, UserProfile
from memfinrobot.memory.embedding import EmbeddingModel, get_embedding_model

logger = logging.getLogger(__name__)


class MemoryRecall:
    """
    记忆召回器
    
    支持多路召回：
    - 向量相似度召回 (semantic)
    - 关键词/实体召回 (keyword)
    - 画像规则召回 (profile)
    """
    
    def __init__(
        self,
        embedding_model: Optional[EmbeddingModel] = None,
        top_k: int = 10,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.3,
        profile_weight: float = 0.1,
    ):
        """
        初始化召回器
        
        Args:
            embedding_model: 向量嵌入模型
            top_k: 召回数量
            semantic_weight: 语义召回权重
            keyword_weight: 关键词召回权重
            profile_weight: 画像召回权重
        """
        self.embedding_model = embedding_model
        self.top_k = top_k
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.profile_weight = profile_weight
    
    def recall(
        self,
        query: str,
        memory_items: List[MemoryItem],
        embeddings: Optional[Dict[str, np.ndarray]] = None,
        user_profile: Optional[UserProfile] = None,
        session_id: Optional[str] = None,
    ) -> RecallResult:
        """
        多路召回记忆
        
        Args:
            query: 查询文本
            memory_items: 可召回的记忆条目
            embeddings: 记忆条目的向量表示
            user_profile: 用户画像
            session_id: 当前会话ID（用于过滤）
            
        Returns:
            RecallResult 包含召回的记忆条目和分数
        """
        if not memory_items:
            return RecallResult()
        
        # 1. 语义召回
        semantic_results = self._semantic_recall(query, memory_items, embeddings)
        
        # 2. 关键词召回
        keyword_results = self._keyword_recall(query, memory_items)
        
        # 3. 画像规则召回
        profile_results = self._profile_recall(memory_items, user_profile)
        
        # 4. 融合结果
        merged = self._merge_results(
            semantic_results,
            keyword_results,
            profile_results,
            memory_items,
        )
        
        # 5. 取TopK
        sorted_results = sorted(merged.items(), key=lambda x: x[1][0], reverse=True)
        top_results = sorted_results[:self.top_k]
        
        # 6. 构建返回结果
        items = []
        scores = []
        sources = []
        
        for item_id, (score, source) in top_results:
            item = next((m for m in memory_items if m.id == item_id), None)
            if item:
                items.append(item)
                scores.append(score)
                sources.append(source)
        
        return RecallResult(
            items=items,
            scores=scores,
            sources=sources,
        )
    
    def _semantic_recall(
        self,
        query: str,
        memory_items: List[MemoryItem],
        embeddings: Optional[Dict[str, np.ndarray]] = None,
    ) -> Dict[str, float]:
        """向量相似度召回"""
        results = {}
        
        if self.embedding_model is None:
            return results
        
        try:
            # 编码查询
            query_embedding = self.embedding_model.encode(query)
            if query_embedding.ndim > 1:
                query_embedding = query_embedding[0]
            
            # 计算相似度
            for item in memory_items:
                item_embedding = None
                
                # 优先使用预计算的向量
                if embeddings and item.id in embeddings:
                    item_embedding = embeddings[item.id]
                elif item.embedding:
                    item_embedding = np.array(item.embedding)
                
                if item_embedding is not None:
                    score = float(np.dot(query_embedding, item_embedding))
                    results[item.id] = score
                    
        except Exception as e:
            logger.warning(f"Semantic recall failed: {e}")
        
        return results
    
    def _keyword_recall(
        self,
        query: str,
        memory_items: List[MemoryItem],
    ) -> Dict[str, float]:
        """关键词召回"""
        results = {}
        
        # 简单的关键词匹配
        query_lower = query.lower()
        query_terms = set(query_lower.split())
        
        for item in memory_items:
            content = (item.hierarchical_content or item.content).lower()
            
            # 计算匹配度
            match_count = 0
            for term in query_terms:
                if term in content:
                    match_count += 1
            
            # 实体匹配加分
            entity_match = 0
            for entity in item.entities:
                if entity.lower() in query_lower:
                    entity_match += 1
            
            if match_count > 0 or entity_match > 0:
                score = (match_count / max(len(query_terms), 1)) + entity_match * 0.5
                results[item.id] = min(score, 1.0)
        
        return results
    
    def _profile_recall(
        self,
        memory_items: List[MemoryItem],
        user_profile: Optional[UserProfile] = None,
    ) -> Dict[str, float]:
        """画像规则召回"""
        results = {}
        
        if user_profile is None:
            return results
        
        for item in memory_items:
            score = 0.0
            
            # 风险相关内容对风险偏好高的用户更重要
            if item.risk_related and user_profile.risk_level.value == "high":
                score += 0.3
            
            # 主题匹配
            if user_profile.preferred_topics:
                topic_match = len(set(item.topics) & set(user_profile.preferred_topics))
                score += topic_match * 0.2
            
            if score > 0:
                results[item.id] = min(score, 1.0)
        
        return results
    
    def _merge_results(
        self,
        semantic: Dict[str, float],
        keyword: Dict[str, float],
        profile: Dict[str, float],
        memory_items: List[MemoryItem],
    ) -> Dict[str, Tuple[float, str]]:
        """融合多路召回结果"""
        merged: Dict[str, Tuple[float, str]] = {}
        
        all_ids = set(semantic.keys()) | set(keyword.keys()) | set(profile.keys())
        
        for item_id in all_ids:
            sem_score = semantic.get(item_id, 0.0)
            kw_score = keyword.get(item_id, 0.0)
            prof_score = profile.get(item_id, 0.0)
            
            # 加权融合
            final_score = (
                sem_score * self.semantic_weight +
                kw_score * self.keyword_weight +
                prof_score * self.profile_weight
            )
            
            # 确定主要来源
            sources = []
            if sem_score > 0:
                sources.append("semantic")
            if kw_score > 0:
                sources.append("keyword")
            if prof_score > 0:
                sources.append("profile")
            
            merged[item_id] = (final_score, "+".join(sources) if sources else "unknown")
        
        return merged


class ContextPacker:
    """上下文打包器 - 按token预算打包召回结果"""
    
    def __init__(
        self,
        max_tokens: int = 4000,
        chars_per_token: float = 2.5,  # 中文约2-3字符/token
    ):
        """
        初始化打包器
        
        Args:
            max_tokens: 最大token数
            chars_per_token: 每token对应的字符数估计
        """
        self.max_tokens = max_tokens
        self.chars_per_token = chars_per_token
    
    def pack(
        self,
        recall_result: RecallResult,
        profile: Optional[UserProfile] = None,
        short_term_context: Optional[str] = None,
    ) -> RecallResult:
        """
        按优先级打包上下文
        
        优先级：画像 > 长期关键记忆 > 短期窗口 > 知识库引用
        
        Args:
            recall_result: 召回结果
            profile: 用户画像
            short_term_context: 短期上下文
            
        Returns:
            打包后的RecallResult
        """
        max_chars = int(self.max_tokens * self.chars_per_token)
        parts = []
        current_chars = 0
        profile_context = ""
        short_context = short_term_context or ""
        
        # 1. 画像信息（最高优先级）
        if profile and profile.risk_level.value != "unknown":
            profile_text = self._format_profile(profile)
            if current_chars + len(profile_text) < max_chars:
                parts.append(f"[用户画像]\n{profile_text}")
                current_chars += len(profile_text)
                profile_context = profile_text
        
        # 2. 召回的记忆（按分数排序）
        items_included = []
        scores_included = []
        sources_included = []
        
        for item, score, source in zip(
            recall_result.items,
            recall_result.scores,
            recall_result.sources,
        ):
            content = item.hierarchical_content or item.content
            if current_chars + len(content) < max_chars:
                parts.append(f"[相关记忆 | 来源:{source} | 相关度:{score:.2f}]\n{content}")
                current_chars += len(content)
                items_included.append(item)
                scores_included.append(score)
                sources_included.append(source)
        
        # 3. 短期上下文
        if short_term_context and current_chars + len(short_term_context) < max_chars:
            parts.append(f"[近期对话]\n{short_term_context}")
            current_chars += len(short_term_context)
        
        # 构建打包结果
        packed_context = "\n\n".join(parts)
        token_count = int(current_chars / self.chars_per_token)
        
        return RecallResult(
            items=items_included,
            scores=scores_included,
            sources=sources_included,
            short_term_context=short_context,
            profile_context=profile_context,
            packed_context=packed_context,
            token_count=token_count,
        )
    
    def _format_profile(self, profile: UserProfile) -> str:
        """格式化用户画像"""
        lines = []
        
        if profile.risk_level.value != "unknown":
            lines.append(f"- 风险承受能力: {profile.risk_level.value}")
        if profile.investment_horizon.value != "unknown":
            lines.append(f"- 投资期限: {profile.investment_horizon.value}")
        if hasattr(profile, "liquidity_need") and profile.liquidity_need.value != "unknown":
            lines.append(f"- 流动性需求: {profile.liquidity_need.value}")
        if profile.investment_goal.value != "unknown":
            lines.append(f"- 投资目标: {profile.investment_goal.value}")
        if profile.preferred_topics:
            lines.append(f"- 关注主题: {', '.join(profile.preferred_topics)}")
        if profile.forbidden_assets:
            lines.append(f"- 回避资产: {', '.join(profile.forbidden_assets)}")
        
        return "\n".join(lines) if lines else "暂无画像信息"
