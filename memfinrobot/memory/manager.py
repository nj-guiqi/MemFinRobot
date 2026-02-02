"""记忆管理器 - 统一管理记忆的读写和召回"""

import logging
from typing import Any, Dict, List, Optional

from memfinrobot.memory.schemas import (
    MemoryItem,
    RecallResult,
    RefinedMemory,
    SessionState,
    UserProfile,
    WindowSelectionResult,
)
from memfinrobot.memory.window_selector import WindowSelector
from memfinrobot.memory.window_refiner import WindowRefiner
from memfinrobot.memory.memory_writer import MemoryWriter
from memfinrobot.memory.recall import MemoryRecall, ContextPacker
from memfinrobot.memory.rerank import MemoryReranker, deduplicate_memories
from memfinrobot.memory.embedding import EmbeddingModel, get_embedding_model
from memfinrobot.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    记忆管理器
    
    整合WindowSelector、WindowRefiner、MemoryWriter、MemoryRecall、MemoryReranker
    提供统一的记忆读写和召回接口
    """
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm_client: Optional[Any] = None,
        embedding_model: Optional[EmbeddingModel] = None,
    ):
        """
        初始化记忆管理器
        
        Args:
            settings: 配置对象
            llm_client: LLM客户端（用于窗口选择和精炼）
            embedding_model: 向量嵌入模型
        """
        self.settings = settings or get_settings()
        self.llm_client = llm_client
        
        # 初始化embedding模型
        if embedding_model:
            self.embedding_model = embedding_model
        else:
            self.embedding_model = get_embedding_model(
                model_path=self.settings.embedding.model_path,
                device=self.settings.embedding.device,
            )
        
        # 初始化各组件
        self.window_selector = WindowSelector(
            llm_client=llm_client,
            max_window_size=self.settings.memory.max_window_size,
            vote_times=self.settings.memory.vote_times,
            confidence_threshold=self.settings.memory.confidence_threshold,
        )
        
        self.window_refiner = WindowRefiner(
            llm_client=llm_client,
        )
        
        self.memory_writer = MemoryWriter(
            storage_path=self.settings.memory.storage_path,
            embedding_model=self.embedding_model,
            storage_backend=self.settings.memory.storage_backend,
        )
        
        self.memory_recall = MemoryRecall(
            embedding_model=self.embedding_model,
            top_k=self.settings.memory.top_k_recall,
        )
        
        self.memory_reranker = MemoryReranker(
            reranker_model_path=self.settings.reranker.model_path,
            device=self.settings.reranker.device,
            threshold=self.settings.reranker.threshold,
        )
        
        self.context_packer = ContextPacker(
            max_tokens=self.settings.memory.max_ref_token,
        )
        
        # 用户画像缓存
        self._profiles: Dict[str, UserProfile] = {}
    
    def process_turn(
        self,
        session_state: SessionState,
        user_message: str,
        assistant_message: str,
    ) -> List[str]:
        """
        处理一轮对话，完成记忆的写入
        
        这是流式写入的核心方法：
        1. 从对话历史中选择相关窗口
        2. 精炼选中的窗口内容
        3. 构建分层表征
        4. 写入长期记忆
        
        Args:
            session_state: 会话状态
            user_message: 用户消息
            assistant_message: 助手回复
            
        Returns:
            写入的记忆ID列表
        """
        # 获取对话历史
        dialogue_history = [
            turn["content"] for turn in session_state.dialogue_history
            if turn["role"] in ["user", "assistant"]
        ]
        
        # 当前轮内容
        current_content = f"用户: {user_message}\n助手: {assistant_message}"
        
        # 1. 窗口选择
        selection_result = self.window_selector.select(
            dialogue_history=dialogue_history,
            current_query=user_message,
        )
        
        # 2. 获取选中的窗口内容
        selected_texts = [
            dialogue_history[idx]
            for idx in selection_result.selected_indices
            if 0 <= idx < len(dialogue_history)
        ]
        
        # 3. 精炼窗口内容
        refined_memory = self.window_refiner.refine(
            selected_texts=selected_texts,
            current_query=user_message,
            source_indices=selection_result.selected_indices,
        )
        
        # 4. 构建分层表征
        hierarchical_content = self.window_refiner.build_hierarchical_content(
            refined_memory=refined_memory,
            current_content=current_content,
        )
        
        # 5. 提取实体和主题（简化版本）
        entities = self._extract_entities(current_content)
        topics = self._extract_topics(current_content)
        
        # 6. 写入长期记忆
        memory_ids = self.memory_writer.write(
            refined_memory=refined_memory,
            current_content=current_content,
            hierarchical_content=hierarchical_content,
            session_id=session_state.session_id,
            user_id=session_state.user_id,
            turn_index=session_state.turn_count,
            topics=topics,
            entities=entities,
        )
        
        # 更新会话状态
        session_state.memory_ids.extend(memory_ids)
        
        logger.info(
            f"Processed turn {session_state.turn_count}, "
            f"selected {len(selection_result.selected_indices)} windows, "
            f"confidence: {selection_result.confidence:.2f}"
        )
        
        return memory_ids
    
    def recall_for_query(
        self,
        query: str,
        session_state: SessionState,
        include_short_term: bool = True,
    ) -> RecallResult:
        """
        为当前查询召回相关记忆
        
        Args:
            query: 当前查询
            session_state: 会话状态
            include_short_term: 是否包含短期上下文
            
        Returns:
            打包后的召回结果
        """
        # 获取用户的所有长期记忆
        memory_items = self.memory_writer.get_all_memories(
            user_id=session_state.user_id
        )
        
        # 获取用户画像
        profile = self.get_profile(session_state.user_id)
        
        # 1. 多路召回
        recall_result = self.memory_recall.recall(
            query=query,
            memory_items=memory_items,
            embeddings=self.memory_writer._embeddings,
            user_profile=profile,
            session_id=session_state.session_id,
        )
        
        # 2. 重排
        recall_result = self.memory_reranker.rerank(
            query=query,
            recall_result=recall_result,
        )
        
        # 3. 去重
        items, scores = deduplicate_memories(
            recall_result.items,
            recall_result.scores,
        )
        recall_result.items = items
        recall_result.scores = scores
        recall_result.sources = recall_result.sources[:len(items)]
        
        # 4. 构建短期上下文
        short_term_context = None
        if include_short_term:
            recent_history = session_state.get_recent_history(n=3)
            if recent_history:
                short_term_context = "\n".join([
                    f"{turn['role']}: {turn['content']}"
                    for turn in recent_history
                ])
        
        # 5. 打包
        packed_result = self.context_packer.pack(
            recall_result=recall_result,
            profile=profile,
            short_term_context=short_term_context,
        )
        
        return packed_result
    
    def get_profile(self, user_id: str) -> UserProfile:
        """获取用户画像"""
        if user_id not in self._profiles:
            self._profiles[user_id] = UserProfile(user_id=user_id)
        return self._profiles[user_id]
    
    def update_profile(
        self,
        user_id: str,
        updates: Dict[str, Any],
    ) -> UserProfile:
        """更新用户画像"""
        profile = self.get_profile(user_id)
        
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        from datetime import datetime
        profile.updated_at = datetime.now()
        
        return profile
    
    def _extract_entities(self, content: str) -> List[str]:
        """提取实体（简化版本）"""
        import re
        
        entities = []
        
        # 股票代码 (6位数字)
        stock_codes = re.findall(r'\b\d{6}\b', content)
        entities.extend(stock_codes)
        
        # 基金代码 (6位数字)
        fund_codes = re.findall(r'\b\d{6}\b', content)
        entities.extend([f"F{code}" for code in fund_codes if code not in stock_codes])
        
        return list(set(entities))
    
    def _extract_topics(self, content: str) -> List[str]:
        """提取主题（简化版本）"""
        topics = []
        
        # 简单的关键词匹配
        topic_keywords = {
            "股票": ["股票", "A股", "个股", "股价"],
            "基金": ["基金", "ETF", "指数基金", "货基"],
            "债券": ["债券", "国债", "转债", "利率"],
            "行情": ["行情", "涨跌", "走势", "K线"],
            "风险": ["风险", "亏损", "回撤", "波动"],
            "配置": ["配置", "仓位", "分散", "组合"],
        }
        
        content_lower = content.lower()
        for topic, keywords in topic_keywords.items():
            if any(kw in content_lower for kw in keywords):
                topics.append(topic)
        
        return topics
    
    def create_session(self, user_id: str) -> SessionState:
        """创建新会话"""
        return SessionState(user_id=user_id)
    
    def clear_session_memories(self, session_id: str) -> int:
        """清除会话记忆"""
        memories = self.memory_writer.get_session_memories(session_id)
        count = 0
        for memory in memories:
            if self.memory_writer.delete_memory(memory.id):
                count += 1
        return count
