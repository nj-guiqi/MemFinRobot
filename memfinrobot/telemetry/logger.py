"""可观测日志记录器"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TurnLog:
    """单轮对话日志"""
    turn_id: int
    timestamp: str
    user_query: str
    assistant_response: str
    
    # 意图分类
    intent: Optional[str] = None
    
    # 记忆召回
    recalled_memories: List[Dict[str, Any]] = field(default_factory=list)
    recall_scores: List[float] = field(default_factory=list)
    
    # 工具调用
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    
    # 合规审校
    compliance_violations: List[Dict[str, Any]] = field(default_factory=list)
    compliance_modified: bool = False
    
    # 性能指标
    latency_ms: Optional[float] = None
    token_count: Optional[int] = None


class TelemetryLogger:
    """
    可观测日志记录器
    
    记录每轮对话的：
    - 意图分类结果
    - 召回的记忆条目（含分数、来源、时间）
    - 工具调用（入参/出参/耗时/错误）
    - 合规审校命中规则与改写结果
    """
    
    def __init__(
        self,
        log_dir: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """
        初始化日志记录器
        
        Args:
            log_dir: 日志目录
            session_id: 会话ID
        """
        if log_dir is None:
            log_dir = str(Path(__file__).parent.parent.parent / "data" / "logs")
        
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.turns: List[TurnLog] = []
        self._current_turn: Optional[TurnLog] = None
    
    def start_turn(self, turn_id: int, user_query: str) -> None:
        """开始记录一轮对话"""
        self._current_turn = TurnLog(
            turn_id=turn_id,
            timestamp=datetime.now().isoformat(),
            user_query=user_query,
            assistant_response="",
        )
    
    def log_intent(self, intent: str) -> None:
        """记录意图分类"""
        if self._current_turn:
            self._current_turn.intent = intent
    
    def log_recall(
        self,
        memories: List[Dict[str, Any]],
        scores: List[float],
    ) -> None:
        """记录记忆召回"""
        if self._current_turn:
            self._current_turn.recalled_memories = memories
            self._current_turn.recall_scores = scores
    
    def log_tool_call(
        self,
        tool_name: str,
        params: Dict[str, Any],
        result: Any,
        latency_ms: float,
        error: Optional[str] = None,
    ) -> None:
        """记录工具调用"""
        if self._current_turn:
            self._current_turn.tool_calls.append({
                "tool_name": tool_name,
                "params": params,
                "result": str(result)[:500],  # 截断长结果
                "latency_ms": latency_ms,
                "error": error,
            })
    
    def log_compliance(
        self,
        violations: List[Dict[str, Any]],
        modified: bool,
    ) -> None:
        """记录合规审校"""
        if self._current_turn:
            self._current_turn.compliance_violations = violations
            self._current_turn.compliance_modified = modified
    
    def end_turn(
        self,
        assistant_response: str,
        latency_ms: Optional[float] = None,
        token_count: Optional[int] = None,
    ) -> None:
        """结束记录一轮对话"""
        if self._current_turn:
            self._current_turn.assistant_response = assistant_response
            self._current_turn.latency_ms = latency_ms
            self._current_turn.token_count = token_count
            self.turns.append(self._current_turn)
            self._current_turn = None
            
            # 保存日志
            self._save_log()
    
    def _save_log(self) -> None:
        """保存日志到文件"""
        log_file = os.path.join(self.log_dir, f"session_{self.session_id}.json")
        
        data = {
            "session_id": self.session_id,
            "turns": [asdict(turn) for turn in self.turns],
        }
        
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_session_summary(self) -> Dict[str, Any]:
        """获取会话摘要"""
        total_tool_calls = sum(len(t.tool_calls) for t in self.turns)
        total_violations = sum(len(t.compliance_violations) for t in self.turns)
        avg_latency = (
            sum(t.latency_ms or 0 for t in self.turns) / len(self.turns)
            if self.turns else 0
        )
        
        return {
            "session_id": self.session_id,
            "total_turns": len(self.turns),
            "total_tool_calls": total_tool_calls,
            "total_compliance_violations": total_violations,
            "average_latency_ms": avg_latency,
        }


# 全局实例
_telemetry_logger: Optional[TelemetryLogger] = None


def get_telemetry_logger(
    log_dir: Optional[str] = None,
    session_id: Optional[str] = None,
) -> TelemetryLogger:
    """获取全局日志记录器"""
    global _telemetry_logger
    
    if _telemetry_logger is None:
        _telemetry_logger = TelemetryLogger(log_dir, session_id)
    
    return _telemetry_logger
