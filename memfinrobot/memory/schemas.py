"""Memory layer data schemas."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class RiskLevel(Enum):
    """Risk tolerance level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class InvestmentHorizon(Enum):
    """Investment horizon."""

    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    UNKNOWN = "unknown"


class InvestmentGoal(Enum):
    """Investment goal."""

    STABLE_GROWTH = "stable_growth"
    CASH_FLOW = "cash_flow"
    THEME_INVESTMENT = "theme_investment"
    LEARNING = "learning"
    UNKNOWN = "unknown"


class LiquidityNeed(Enum):
    """Liquidity need level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


@dataclass
class MemoryItem:
    """Single long-term memory item."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    hierarchical_content: str = ""
    embedding: Optional[List[float]] = None

    turn_index: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str = ""
    user_id: str = ""

    topics: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    risk_related: bool = False

    h_length: int = 0
    confidence: float = 0.0
    source_indices: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
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
        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data.pop("embedding", None)
        return cls(**data)


@dataclass
class UserProfile:
    """User profile used for recall and constraints."""

    user_id: str = ""

    risk_level: RiskLevel = RiskLevel.UNKNOWN
    risk_level_confidence: float = 0.0
    risk_level_evidence: List[str] = field(default_factory=list)

    investment_horizon: InvestmentHorizon = InvestmentHorizon.UNKNOWN
    investment_horizon_confidence: float = 0.0

    liquidity_need: LiquidityNeed = LiquidityNeed.UNKNOWN
    liquidity_need_confidence: float = 0.0

    investment_goal: InvestmentGoal = InvestmentGoal.UNKNOWN

    preferred_topics: List[str] = field(default_factory=list)
    forbidden_assets: List[str] = field(default_factory=list)
    max_acceptable_loss: Optional[float] = None

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "risk_level": self.risk_level.value,
            "risk_level_confidence": self.risk_level_confidence,
            "risk_level_evidence": self.risk_level_evidence,
            "investment_horizon": self.investment_horizon.value,
            "investment_horizon_confidence": self.investment_horizon_confidence,
            "liquidity_need": self.liquidity_need.value,
            "liquidity_need_confidence": self.liquidity_need_confidence,
            "investment_goal": self.investment_goal.value,
            "preferred_topics": self.preferred_topics,
            "forbidden_assets": self.forbidden_assets,
            "max_acceptable_loss": self.max_acceptable_loss,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        if "risk_level" in data:
            data["risk_level"] = RiskLevel(data["risk_level"])
        if "investment_horizon" in data:
            data["investment_horizon"] = InvestmentHorizon(data["investment_horizon"])
        if "liquidity_need" in data:
            data["liquidity_need"] = LiquidityNeed(data["liquidity_need"])
        if "investment_goal" in data:
            data["investment_goal"] = InvestmentGoal(data["investment_goal"])
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


@dataclass
class RecallResult:
    """Recall result passed into generation and tracing."""

    items: List[MemoryItem] = field(default_factory=list)
    scores: List[float] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)

    short_term_context: str = ""
    profile_context: str = ""
    packed_context: str = ""
    token_count: int = 0

    def to_context_string(self) -> str:
        if self.packed_context:
            return self.packed_context

        context_parts: List[str] = []
        for item, score, source in zip(self.items, self.scores, self.sources):
            context_parts.append(
                f"[source:{source}, score:{score:.2f}] {item.hierarchical_content or item.content}"
            )
        return "\n\n".join(context_parts)


@dataclass
class ToolResult:
    """Unified wrapper for tool invocation result."""

    success: bool = True
    data: Any = None
    source: str = ""
    asof: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
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
    """In-memory session state."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""

    dialogue_history: List[Dict[str, str]] = field(default_factory=list)
    turn_count: int = 0

    memory_ids: List[str] = field(default_factory=list)
    profile: Optional[UserProfile] = None

    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)

    def add_turn(self, role: str, content: str) -> None:
        self.dialogue_history.append({"role": role, "content": content})
        self.turn_count += 1
        self.last_active = datetime.now()

    def get_recent_history(self, n: int = 10) -> List[Dict[str, str]]:
        return self.dialogue_history[-n:] if n > 0 else self.dialogue_history


@dataclass
class WindowSelectionResult:
    """Window selection output."""

    selected_indices: List[int] = field(default_factory=list)
    confidence: float = 0.0
    debug_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RefinedMemory:
    """Refined memory content from selected windows."""

    refined_texts: List[str] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    source_indices: List[int] = field(default_factory=list)
