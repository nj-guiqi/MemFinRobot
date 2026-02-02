"""向量嵌入模块 - 集成BGE-M3模型"""

import logging
from typing import List, Optional, Union
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """BGE-M3 向量嵌入模型封装"""
    
    def __init__(
        self,
        model_path: str = r"D:\project\MemFinRobot\models\bge-m3",
        device: str = "cuda",
        batch_size: int = 32,
        max_length: int = 512,
        normalize: bool = True,
    ):
        """
        初始化Embedding模型
        
        Args:
            model_path: 模型路径
            device: 运行设备 (cuda/cpu)
            batch_size: 批处理大小
            max_length: 最大序列长度
            normalize: 是否归一化向量
        """
        self.model_path = model_path
        self.device = device
        self.batch_size = batch_size
        self.max_length = max_length
        self.normalize = normalize
        self.model = None
        self._initialized = False
    
    def _lazy_init(self) -> None:
        """延迟初始化模型"""
        if self._initialized:
            return
        
        try:
            from FlagEmbedding import BGEM3FlagModel
            
            logger.info(f"Loading BGE-M3 model from {self.model_path}")
            self.model = BGEM3FlagModel(
                self.model_path,
                use_fp16=True if self.device == "cuda" else False,
                device=self.device,
            )
            self._initialized = True
            logger.info("BGE-M3 model loaded successfully")
            
        except ImportError:
            logger.warning("FlagEmbedding not installed, using mock embedding")
            self.model = None
            self._initialized = True
        except Exception as e:
            logger.warning(f"Failed to load BGE-M3 model: {e}, using mock embedding")
            self.model = None
            self._initialized = True
    
    def encode(
        self,
        texts: Union[str, List[str]],
        return_dense: bool = True,
        return_sparse: bool = False,
        return_colbert: bool = False,
    ) -> Union[np.ndarray, dict]:
        """
        编码文本为向量
        
        Args:
            texts: 单个文本或文本列表
            return_dense: 是否返回稠密向量
            return_sparse: 是否返回稀疏向量
            return_colbert: 是否返回ColBERT向量
            
        Returns:
            向量数组或包含多种向量的字典
        """
        self._lazy_init()
        
        if isinstance(texts, str):
            texts = [texts]
        
        if self.model is None:
            # Mock embedding for testing
            dim = 1024  # BGE-M3 默认维度
            embeddings = np.random.randn(len(texts), dim).astype(np.float32)
            if self.normalize:
                embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
            return embeddings
        
        # 使用BGE-M3模型编码
        result = self.model.encode(
            texts,
            batch_size=self.batch_size,
            max_length=self.max_length,
            return_dense=return_dense,
            return_sparse=return_sparse,
            return_colbert_vecs=return_colbert,
        )
        
        if return_dense and not return_sparse and not return_colbert:
            embeddings = result["dense_vecs"]
            if self.normalize:
                embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
            return embeddings
        
        return result
    
    def encode_queries(self, queries: Union[str, List[str]]) -> np.ndarray:
        """编码查询文本"""
        return self.encode(queries, return_dense=True)
    
    def encode_documents(self, documents: Union[str, List[str]]) -> np.ndarray:
        """编码文档文本"""
        return self.encode(documents, return_dense=True)
    
    def similarity(self, query_embedding: np.ndarray, doc_embeddings: np.ndarray) -> np.ndarray:
        """
        计算查询与文档的相似度
        
        Args:
            query_embedding: 查询向量 [dim] 或 [1, dim]
            doc_embeddings: 文档向量 [n, dim]
            
        Returns:
            相似度分数 [n]
        """
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        # 余弦相似度
        scores = np.dot(query_embedding, doc_embeddings.T).flatten()
        return scores


# 全局实例
_embedding_model: Optional[EmbeddingModel] = None


def get_embedding_model(
    model_path: Optional[str] = None,
    device: str = "cuda",
) -> EmbeddingModel:
    """获取全局Embedding模型实例"""
    global _embedding_model
    
    if _embedding_model is None:
        if model_path is None:
            model_path = r"D:\project\MemFinRobot\models\bge-m3"
        _embedding_model = EmbeddingModel(model_path=model_path, device=device)
    
    return _embedding_model
