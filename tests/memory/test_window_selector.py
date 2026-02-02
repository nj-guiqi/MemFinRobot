"""窗口选择器测试"""

import pytest

from memfinrobot.memory.window_selector import WindowSelector
from memfinrobot.memory.schemas import WindowSelectionResult


class TestWindowSelector:
    """WindowSelector测试"""
    
    @pytest.fixture
    def selector(self):
        """创建选择器实例（无LLM）"""
        return WindowSelector(
            llm_client=None,
            max_window_size=10,
            vote_times=3,
            confidence_threshold=0.6,
        )
    
    def test_init(self, selector):
        """测试初始化"""
        assert selector.max_window_size == 10
        assert selector.vote_times == 3
        assert selector.confidence_threshold == 0.6
    
    def test_select_empty_history(self, selector):
        """测试空历史"""
        result = selector.select(
            dialogue_history=[],
            current_query="你好",
        )
        
        assert isinstance(result, WindowSelectionResult)
        assert result.selected_indices == []
        assert result.confidence == 1.0
    
    def test_select_fallback(self, selector, sample_dialogue_history):
        """测试回退策略"""
        result = selector.select(
            dialogue_history=sample_dialogue_history,
            current_query="债券基金风险大吗？",
        )
        
        assert isinstance(result, WindowSelectionResult)
        assert len(result.selected_indices) > 0
        assert result.debug_info.get("reason") == "fallback"
    
    def test_fallback_selection(self, selector):
        """测试回退选择方法"""
        history = ["对话1", "对话2", "对话3", "对话4", "对话5"]
        result = selector._fallback_selection(history, offset=0)
        
        # 默认选择最近3轮
        assert len(result.selected_indices) == 3
        assert result.selected_indices == [2, 3, 4]
        assert result.confidence == 0.5
    
    def test_fallback_with_offset(self, selector):
        """测试带偏移的回退选择"""
        history = ["对话1", "对话2", "对话3"]
        result = selector._fallback_selection(history, offset=5)
        
        # 索引应该加上偏移量
        assert all(idx >= 5 for idx in result.selected_indices)
