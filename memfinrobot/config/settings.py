"""项目配置定义"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


@dataclass
class LLMConfig:
    """LLM配置"""
    model: str = "qwen-plus"
    model_type: str = ""
    model_server: str = "dashscope"
    api_key: str = ""
    use_raw_api: bool = False
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 0.9
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "model_server": self.model_server,
            "api_key": self.api_key or os.getenv("DASHSCOPE_API_KEY", ""),
            "generate_cfg": {
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "top_p": self.top_p,
            }
        }


@dataclass
class EmbeddingConfig:
    """Embedding模型配置"""
    model_path: str = r"D:\project\MemFinRobot\models\bge-m3"
    device: str = "cuda"  # cuda / cpu
    batch_size: int = 32
    max_length: int = 512
    normalize: bool = True


@dataclass
class RerankerConfig:
    """Reranker模型配置"""
    model_path: str = ""  # 暂时置空
    device: str = "cuda"
    threshold: float = 0.35


@dataclass
class MemoryConfig:
    """记忆模块配置"""
    # 窗口选择配置
    max_window_size: int = 15           # 最大窗口大小
    vote_times: int = 5                 # 投票次数
    confidence_threshold: float = 0.6  # 置信度阈值
    
    # 召回配置
    top_k_recall: int = 10              # 召回数量
    max_ref_token: int = 4000           # 最大引用token数
    
    # 存储配置
    storage_backend: str = "file"       # file / sqlite / faiss
    storage_path: str = ""              # 存储路径
    
    # 向量配置
    embedding_dim: int = 1024           # BGE-M3 embedding维度


@dataclass
class MarketDataConfig:
    """行情数据配置"""
    # 数据源选择
    provider: str = "tencent"              # 默认数据源: tencent / akshare / mock
    fallback_provider: str = "mock"        # 降级数据源
    
    # 超时与重试
    timeout_seconds: float = 8.0           # 请求超时时间
    retry_times: int = 1                   # 失败重试次数
    
    # 限频配置
    rate_limit_seconds: float = 1.0        # 同一symbol的请求间隔（秒）
    cache_ttl_seconds: float = 2.0         # 内存缓存有效期（秒）
    
    # 调试与日志
    enable_source_tracking: bool = True    # 在结果中标注数据来源


@dataclass
class ComplianceConfig:
    """合规配置"""
    # 禁语列表
    forbidden_phrases: List[str] = field(default_factory=lambda: [
        "保证收益", "必涨", "稳赚", "内幕", "荐股",
        "买入", "卖出", "具体点位", "建仓", "加仓",
    ])
    
    # 风险提示模板
    risk_disclaimer: str = (
        "【风险提示】以上内容仅供参考，不构成投资建议。"
        "投资有风险，入市需谨慎。请根据自身风险承受能力谨慎决策。"
    )
    
    # 适当性检查
    enable_suitability_check: bool = True


@dataclass
class Settings:
    """全局配置"""
    # 项目路径
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)
    data_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent / "data")
    
    # 各模块配置
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    reranker: RerankerConfig = field(default_factory=RerankerConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    compliance: ComplianceConfig = field(default_factory=ComplianceConfig)
    market_data: MarketDataConfig = field(default_factory=MarketDataConfig)
    
    # Prompt模板路径
    prompt_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "prompts")
    
    def __post_init__(self):
        """初始化后处理"""
        # 确保路径为Path对象
        if isinstance(self.project_root, str):
            self.project_root = Path(self.project_root)
        if isinstance(self.data_dir, str):
            self.data_dir = Path(self.data_dir)
        if isinstance(self.prompt_dir, str):
            self.prompt_dir = Path(self.prompt_dir)
        
        # 设置默认存储路径
        if not self.memory.storage_path:
            self.memory.storage_path = str(self.data_dir / "memory_store")
    
    @classmethod
    def from_file(cls, config_path: str) -> "Settings":
        """从配置文件加载"""
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        
        settings = cls()
        
        if "llm" in config_data:
            settings.llm = LLMConfig(**config_data["llm"])
        if "embedding" in config_data:
            settings.embedding = EmbeddingConfig(**config_data["embedding"])
        if "reranker" in config_data:
            settings.reranker = RerankerConfig(**config_data["reranker"])
        if "memory" in config_data:
            settings.memory = MemoryConfig(**config_data["memory"])
        if "compliance" in config_data:
            settings.compliance = ComplianceConfig(**config_data["compliance"])
        if "market_data" in config_data:
            settings.market_data = MarketDataConfig(**config_data["market_data"])
        
        return settings
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "project_root": str(self.project_root),
            "data_dir": str(self.data_dir),
            "llm": {
                "model": self.llm.model,
                "model_server": self.llm.model_server,
                "temperature": self.llm.temperature,
                "max_tokens": self.llm.max_tokens,
            },
            "embedding": {
                "model_path": self.embedding.model_path,
                "device": self.embedding.device,
            },
            "memory": {
                "max_window_size": self.memory.max_window_size,
                "vote_times": self.memory.vote_times,
                "confidence_threshold": self.memory.confidence_threshold,
                "top_k_recall": self.memory.top_k_recall,
            },
        }


# 全局配置单例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取全局配置"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def init_settings(config_path: Optional[str] = None) -> Settings:
    """初始化全局配置"""
    global _settings
    if config_path:
        _settings = Settings.from_file(config_path)
    else:
        _settings = Settings()
    return _settings
