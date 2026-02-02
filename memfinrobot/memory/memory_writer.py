"""记忆写入器 - 将精炼后的记忆写入长期记忆库"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from memfinrobot.memory.schemas import MemoryItem, RefinedMemory
from memfinrobot.memory.embedding import EmbeddingModel, get_embedding_model

logger = logging.getLogger(__name__)


class MemoryWriter:
    """
    记忆写入器
    
    负责将精炼后的记忆条目写入长期记忆库
    支持文件存储（V0）和向量存储
    """
    
    def __init__(
        self,
        storage_path: str = "",
        embedding_model: Optional[EmbeddingModel] = None,
        storage_backend: str = "file",  # file / sqlite / faiss
    ):
        """
        初始化记忆写入器
        
        Args:
            storage_path: 存储路径
            embedding_model: 向量嵌入模型
            storage_backend: 存储后端类型
        """
        self.storage_path = storage_path or str(
            Path(__file__).parent.parent.parent / "data" / "memory_store"
        )
        self.embedding_model = embedding_model
        self.storage_backend = storage_backend
        
        # 确保存储目录存在
        os.makedirs(self.storage_path, exist_ok=True)
        
        # 内存中的记忆索引
        self._memory_index: Dict[str, MemoryItem] = {}
        self._embeddings: Dict[str, np.ndarray] = {}
        
        # 加载已有记忆
        self._load_existing_memories()
    
    def _load_existing_memories(self) -> None:
        """加载已有的记忆数据"""
        index_file = os.path.join(self.storage_path, "memory_index.json")
        if os.path.exists(index_file):
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item_data in data:
                        item = MemoryItem.from_dict(item_data)
                        self._memory_index[item.id] = item
                logger.info(f"Loaded {len(self._memory_index)} memory items")
            except Exception as e:
                logger.warning(f"Failed to load existing memories: {e}")
    
    def write(
        self,
        refined_memory: RefinedMemory,
        current_content: str,
        hierarchical_content: str,
        session_id: str,
        user_id: str,
        turn_index: int,
        topics: Optional[List[str]] = None,
        entities: Optional[List[str]] = None,
    ) -> List[str]:
        """
        写入一条记忆
        
        Args:
            refined_memory: 精炼后的记忆
            current_content: 当前轮原始内容
            hierarchical_content: 分层表征内容
            session_id: 会话ID
            user_id: 用户ID
            turn_index: 对话轮次索引
            topics: 主题标签
            entities: 实体列表
            
        Returns:
            写入的记忆ID列表
        """
        # 创建记忆条目
        memory_item = MemoryItem(
            content=current_content,
            hierarchical_content=hierarchical_content,
            turn_index=turn_index,
            timestamp=datetime.now(),
            session_id=session_id,
            user_id=user_id,
            topics=topics or [],
            entities=entities or [],
            h_length=len(refined_memory.source_indices),
            confidence=0.0,  # 可在后续更新
            source_indices=refined_memory.source_indices,
        )
        
        # 生成向量嵌入
        if self.embedding_model is not None:
            try:
                embedding = self.embedding_model.encode(hierarchical_content)
                if embedding.ndim > 1:
                    embedding = embedding[0]
                memory_item.embedding = embedding.tolist()
                self._embeddings[memory_item.id] = embedding
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")
        
        # 存储记忆
        self._memory_index[memory_item.id] = memory_item
        self._save_to_storage()
        
        logger.info(f"Written memory item {memory_item.id} for turn {turn_index}")
        return [memory_item.id]
    
    def write_batch(
        self,
        items: List[MemoryItem],
    ) -> List[str]:
        """批量写入记忆条目"""
        memory_ids = []
        
        # 批量生成向量
        if self.embedding_model is not None:
            texts = [item.hierarchical_content or item.content for item in items]
            try:
                embeddings = self.embedding_model.encode(texts)
                for item, embedding in zip(items, embeddings):
                    item.embedding = embedding.tolist()
                    self._embeddings[item.id] = embedding
            except Exception as e:
                logger.warning(f"Failed to generate batch embeddings: {e}")
        
        # 存储
        for item in items:
            self._memory_index[item.id] = item
            memory_ids.append(item.id)
        
        self._save_to_storage()
        logger.info(f"Written {len(items)} memory items in batch")
        return memory_ids
    
    def _save_to_storage(self) -> None:
        """保存到存储"""
        if self.storage_backend == "file":
            self._save_to_file()
        else:
            # V0只实现文件存储
            self._save_to_file()
    
    def _save_to_file(self) -> None:
        """保存到文件"""
        index_file = os.path.join(self.storage_path, "memory_index.json")
        data = [item.to_dict() for item in self._memory_index.values()]
        
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 保存向量（如果有）
        if self._embeddings:
            embeddings_file = os.path.join(self.storage_path, "embeddings.npy")
            ids_file = os.path.join(self.storage_path, "embedding_ids.json")
            
            ids = list(self._embeddings.keys())
            embeddings = np.array([self._embeddings[id_] for id_ in ids])
            
            np.save(embeddings_file, embeddings)
            with open(ids_file, "w", encoding="utf-8") as f:
                json.dump(ids, f)
    
    def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """获取单条记忆"""
        return self._memory_index.get(memory_id)
    
    def get_all_memories(self, user_id: Optional[str] = None) -> List[MemoryItem]:
        """获取所有记忆（可按用户过滤）"""
        if user_id:
            return [
                item for item in self._memory_index.values()
                if item.user_id == user_id
            ]
        return list(self._memory_index.values())
    
    def get_session_memories(self, session_id: str) -> List[MemoryItem]:
        """获取会话的所有记忆"""
        return [
            item for item in self._memory_index.values()
            if item.session_id == session_id
        ]
    
    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if memory_id in self._memory_index:
            del self._memory_index[memory_id]
            if memory_id in self._embeddings:
                del self._embeddings[memory_id]
            self._save_to_storage()
            return True
        return False
    
    def clear_user_memories(self, user_id: str) -> int:
        """清除用户的所有记忆"""
        to_delete = [
            id_ for id_, item in self._memory_index.items()
            if item.user_id == user_id
        ]
        for id_ in to_delete:
            del self._memory_index[id_]
            if id_ in self._embeddings:
                del self._embeddings[id_]
        
        self._save_to_storage()
        return len(to_delete)
