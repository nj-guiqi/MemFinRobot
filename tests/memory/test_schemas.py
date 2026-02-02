"""记忆数据结构测试"""

import pytest
from datetime import datetime

from memfinrobot.memory.schemas import (
    MemoryItem,
    UserProfile,
    RecallResult,
    SessionState,
    RiskLevel,
    InvestmentHorizon,
    InvestmentGoal,
    WindowSelectionResult,
    RefinedMemory,
    ToolResult,
)


class TestMemoryItem:
    """MemoryItem测试"""
    
    def test_create_memory_item(self):
        """测试创建记忆条目"""
        item = MemoryItem(
            content="测试内容",
            turn_index=1,
            session_id="session-001",
            user_id="user-001",
        )
        
        assert item.content == "测试内容"
        assert item.turn_index == 1
        assert item.id is not None
        assert isinstance(item.timestamp, datetime)
    
    def test_memory_item_to_dict(self, sample_memory_item):
        """测试转换为字典"""
        data = sample_memory_item.to_dict()
        
        assert "id" in data
        assert "content" in data
        assert data["topics"] == ["ETF", "费用"]
    
    def test_memory_item_from_dict(self, sample_memory_item):
        """测试从字典创建"""
        data = sample_memory_item.to_dict()
        restored = MemoryItem.from_dict(data)
        
        assert restored.id == sample_memory_item.id
        assert restored.content == sample_memory_item.content


class TestUserProfile:
    """UserProfile测试"""
    
    def test_create_user_profile(self):
        """测试创建用户画像"""
        profile = UserProfile(
            user_id="user-001",
            risk_level=RiskLevel.HIGH,
            investment_horizon=InvestmentHorizon.LONG,
        )
        
        assert profile.risk_level == RiskLevel.HIGH
        assert profile.investment_horizon == InvestmentHorizon.LONG
    
    def test_user_profile_to_dict(self, sample_user_profile):
        """测试转换为字典"""
        data = sample_user_profile.to_dict()
        
        assert data["risk_level"] == "medium"
        assert data["investment_horizon"] == "medium"
    
    def test_user_profile_from_dict(self, sample_user_profile):
        """测试从字典创建"""
        data = sample_user_profile.to_dict()
        restored = UserProfile.from_dict(data)
        
        assert restored.risk_level == RiskLevel.MEDIUM


class TestSessionState:
    """SessionState测试"""
    
    def test_create_session(self):
        """测试创建会话"""
        session = SessionState(user_id="user-001")
        
        assert session.user_id == "user-001"
        assert session.turn_count == 0
        assert len(session.dialogue_history) == 0
    
    def test_add_turn(self):
        """测试添加对话轮次"""
        session = SessionState(user_id="user-001")
        session.add_turn("user", "你好")
        session.add_turn("assistant", "您好！")
        
        assert session.turn_count == 2
        assert len(session.dialogue_history) == 2
        assert session.dialogue_history[0]["role"] == "user"
    
    def test_get_recent_history(self, sample_session_state):
        """测试获取最近历史"""
        history = sample_session_state.get_recent_history(n=1)
        
        assert len(history) == 1
        assert history[0]["role"] == "assistant"


class TestRecallResult:
    """RecallResult测试"""
    
    def test_empty_recall_result(self):
        """测试空召回结果"""
        result = RecallResult()
        
        assert len(result.items) == 0
        assert result.packed_context == ""
    
    def test_recall_result_to_context(self, sample_memory_item):
        """测试转换为上下文字符串"""
        result = RecallResult(
            items=[sample_memory_item],
            scores=[0.85],
            sources=["semantic"],
        )
        
        context = result.to_context_string()
        assert "semantic" in context
        assert "0.85" in context


class TestWindowSelectionResult:
    """WindowSelectionResult测试"""
    
    def test_create_selection_result(self):
        """测试创建选择结果"""
        result = WindowSelectionResult(
            selected_indices=[0, 2, 4],
            confidence=0.8,
            debug_info={"reason": "vote_success"},
        )
        
        assert result.selected_indices == [0, 2, 4]
        assert result.confidence == 0.8


class TestToolResult:
    """ToolResult测试"""
    
    def test_success_tool_result(self):
        """测试成功的工具结果"""
        result = ToolResult(
            success=True,
            data={"price": 10.5},
            source="market_data",
            asof=datetime.now(),
        )
        
        assert result.success
        assert result.data["price"] == 10.5
    
    def test_error_tool_result(self):
        """测试错误的工具结果"""
        result = ToolResult(
            success=False,
            errors=["数据获取失败"],
        )
        
        assert not result.success
        assert "数据获取失败" in result.errors
