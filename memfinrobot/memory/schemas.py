"""记忆层数据结构定义"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class RiskLevel(Enum):
    """风险承受能力等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class InvestmentHorizon(Enum):
    """投资期限"""
    SHORT = "short"      # 短期 < 1年
    MEDIUM = "medium"    # 中期 1-3年
    LONG = "long"        # 长期 > 3年
    UNKNOWN = "unknown"


class InvestmentGoal(Enum):
    """投资目标"""
    STABLE_GROWTH = "stable_growth"       # 稳健增值
    CASH_FLOW = "cash_flow"               # 现金流
    THEME_INVESTMENT = "theme_investment"  # 主题投资
    LEARNING = "learning"                  # 学习投教
    UNKNOWN = "unknown"


@dataclass
class MemoryItem:
    """单条记忆条目"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""                      # 原始内容
    hierarchical_content: str = ""         # 分层表征内容 (精炼记忆 | [context] | 当前轮内容)
    embedding: Optional[List[float]] = None  # 向量表征
    
    # 元数据
    turn_index: int = 0                    # 对话轮次索引
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str = ""                   # 会话ID
    user_id: str = ""                      # 用户ID
    
    # 语义标签
    topics: List[str] = field(default_factory=list)      # 主题标签
    entities: List[str] = field(default_factory=list)    # 实体 (股票代码、基金代码等)
    risk_related: bool = False             # 是否涉及风险相关内容
    
    # 处理元信息
    h_length: int = 0                      # 分层窗口长度
    confidence: float = 0.0                # 置信度
    source_indices: List[int] = field(default_factory=list)  # 来源轮次索引
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "hierarchical_content": self.hierarchical_content,
            "turn_index": self.turn_index,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "topics": self.topics,
            "entities": self.entities,
            "risk_related": self.risk_related,
            "h_length": self.h_length,
            "confidence": self.confidence,
            "source_indices": self.source_indices,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        """从字典创建"""
        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        # 排除embedding以避免加载大量数据
        data.pop("embedding", None)
        return cls(**data)


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str = ""
    
    # 核心画像字段
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    risk_level_confidence: float = 0.0
    risk_level_evidence: List[str] = field(default_factory=list)  # 证据轮次
    
    investment_horizon: InvestmentHorizon = InvestmentHorizon.UNKNOWN
    investment_horizon_confidence: float = 0.0
    
    investment_goal: InvestmentGoal = InvestmentGoal.UNKNOWN
    
    # 偏好与约束
    preferred_topics: List[str] = field(default_factory=list)     # 偏好主题
    forbidden_assets: List[str] = field(default_factory=list)     # 禁忌资产类型
    max_acceptable_loss: Optional[float] = None                    # 最大可接受亏损比例
    
    # 元信息
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "risk_level": self.risk_level.value,
            "risk_level_confidence": self.risk_level_confidence,
            "risk_level_evidence": self.risk_level_evidence,
            "investment_horizon": self.investment_horizon.value,
            "investment_horizon_confidence": self.investment_horizon_confidence,
            "investment_goal": self.investment_goal.value,
            "preferred_topics": self.preferred_topics,
            "forbidden_assets": self.forbidden_assets,
            "max_acceptable_loss": self.max_acceptable_loss,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """从字典创建"""
        if "risk_level" in data:
            data["risk_level"] = RiskLevel(data["risk_level"])
        if "investment_horizon" in data:
            data["investment_horizon"] = InvestmentHorizon(data["investment_horizon"])
        if "investment_goal" in data:
            data["investment_goal"] = InvestmentGoal(data["investment_goal"])
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


@dataclass
class RecallResult:
    """记忆召回结果"""
    items: List[MemoryItem] = field(default_factory=list)
    scores: List[float] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)  # 召回来源 (semantic/keyword/profile)
    
    # 打包后的上下文
    short_term_context: str = ""
    profile_context: str = ""
    packed_context: str = ""
    token_count: int = 0
    
    def to_context_string(self) -> str:
        """转换为可用于LLM的上下文字符串"""
        if self.packed_context:
            return self.packed_context
        
        context_parts = []
        for item, score, source in zip(self.items, self.scores, self.sources):
            context_parts.append(
                f"[来源:{source}, 相关度:{score:.2f}] {item.hierarchical_content or item.content}"
            )
        return "\n\n".join(context_parts)


@dataclass
class ToolResult:
    """工具调用结果的统一封装"""
    success: bool = True
    data: Any = None
    source: str = ""                       # 数据来源
    asof: Optional[datetime] = None        # 数据时间
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "data": self.data,
            "source": self.source,
            "asof": self.asof.isoformat() if self.asof else None,
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass 
class SessionState:
    """会话状态"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    
    # 对话历史
    dialogue_history: List[Dict[str, str]] = field(default_factory=list)
    turn_count: int = 0
    
    # 记忆索引
    memory_ids: List[str] = field(default_factory=list)
    
    # 用户画像引用
    profile: Optional[UserProfile] = None
    
    # 会话元信息
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    
    def add_turn(self, role: str, content: str) -> None:
        """添加一轮对话"""
        self.dialogue_history.append({"role": role, "content": content})
        self.turn_count += 1
        self.last_active = datetime.now()
    
    def get_recent_history(self, n: int = 10) -> List[Dict[str, str]]:
        """获取最近n轮对话历史"""
        return self.dialogue_history[-n:] if n > 0 else self.dialogue_history


@dataclass
class WindowSelectionResult:
    """窗口选择结果"""
    selected_indices: List[int] = field(default_factory=list)
    confidence: float = 0.0
    debug_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RefinedMemory:
    """精炼后的记忆条目"""
    refined_texts: List[str] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)  # 原文引用
    source_indices: List[int] = field(default_factory=list)
