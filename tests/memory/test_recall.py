"""记忆召回测试"""

import pytest
import numpy as np

from memfinrobot.memory.recall import MemoryRecall, ContextPacker
from memfinrobot.memory.schemas import MemoryItem, RecallResult, UserProfile, RiskLevel


class TestMemoryRecall:
    """MemoryRecall测试"""
    
    @pytest.fixture
    def recall(self):
        """创建召回器实例"""
        return MemoryRecall(
            embedding_model=None,
            top_k=5,
        )
    
    @pytest.fixture
    def sample_items(self):
        """示例记忆条目列表"""
        return [
            MemoryItem(
                id="item-1",
                content="用户询问了ETF的交易规则",
                topics=["ETF"],
                entities=["510300"],
            ),
            MemoryItem(
                id="item-2",
                content="用户说自己是保守型投资者",
                topics=["风险偏好"],
                risk_related=True,
            ),
            MemoryItem(
                id="item-3",
                content="用户咨询了债券基金的收益",
                topics=["债券基金", "收益"],
            ),
        ]
    
    def test_init(self, recall):
        """测试初始化"""
        assert recall.top_k == 5
        assert recall.semantic_weight == 0.6
    
    def test_recall_empty_items(self, recall):
        """测试空记忆列表"""
        result = recall.recall(
            query="你好",
            memory_items=[],
        )
        
        assert isinstance(result, RecallResult)
        assert len(result.items) == 0
    
    def test_keyword_recall(self, recall, sample_items):
        """测试关键词召回"""
        results = recall._keyword_recall(
            query="ETF交易",
            memory_items=sample_items,
        )
        
        assert "item-1" in results
        assert results["item-1"] > 0
    
    def test_profile_recall(self, recall, sample_items, sample_user_profile):
        """测试画像召回"""
        sample_user_profile.preferred_topics = ["ETF"]
        
        results = recall._profile_recall(
            memory_items=sample_items,
            user_profile=sample_user_profile,
        )
        
        # 有匹配主题的项应该被召回
        assert len(results) > 0
    
    def test_merge_results(self, recall, sample_items):
        """测试结果融合"""
        semantic = {"item-1": 0.8, "item-2": 0.6}
        keyword = {"item-1": 0.5, "item-3": 0.7}
        profile = {"item-2": 0.3}
        
        merged = recall._merge_results(
            semantic, keyword, profile, sample_items
        )
        
        assert "item-1" in merged
        assert "item-2" in merged
        assert "item-3" in merged
        
        # item-1 应该分数最高（语义+关键词）
        assert merged["item-1"][0] > merged["item-3"][0]


class TestContextPacker:
    """ContextPacker测试"""
    
    @pytest.fixture
    def packer(self):
        """创建打包器实例"""
        return ContextPacker(max_tokens=1000)
    
    def test_pack_empty_result(self, packer):
        """测试空结果打包"""
        result = RecallResult()
        packed = packer.pack(result)
        
        assert packed.packed_context == ""
    
    def test_pack_with_profile(self, packer, sample_user_profile):
        """测试带画像的打包"""
        result = RecallResult()
        packed = packer.pack(result, profile=sample_user_profile)
        
        assert "用户画像" in packed.packed_context
        assert "风险承受能力" in packed.packed_context
    
    def test_format_profile(self, packer, sample_user_profile):
        """测试画像格式化"""
        formatted = packer._format_profile(sample_user_profile)
        
        assert "medium" in formatted
        assert "指数基金" in formatted or "ETF" in formatted
