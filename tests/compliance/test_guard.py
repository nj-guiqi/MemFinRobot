"""合规审校器测试"""

import pytest

from memfinrobot.compliance.guard import ComplianceGuard, ComplianceResult
from memfinrobot.memory.schemas import UserProfile, RiskLevel


class TestComplianceGuard:
    """ComplianceGuard测试"""
    
    @pytest.fixture
    def guard(self):
        """创建审校器实例"""
        return ComplianceGuard()
    
    def test_check_clean_content(self, guard):
        """测试干净的内容"""
        result = guard.check(
            content="沪深300ETF是一种跟踪沪深300指数的基金产品。",
            force_disclaimer=False,
        )
        
        assert result.is_compliant
        assert len(result.violations) == 0
    
    def test_check_forbidden_phrase(self, guard):
        """测试禁语检测"""
        result = guard.check(
            content="这个产品保证收益，绝对稳赚不赔！",
            force_disclaimer=False,
        )
        
        assert not result.is_compliant
        assert len(result.violations) > 0
    
    def test_check_trading_advice(self, guard):
        """测试交易建议检测"""
        result = guard.check(
            content="建议在10.5元买入，12元卖出。",
            force_disclaimer=False,
        )
        
        assert len(result.violations) > 0
        assert result.needs_modification
    
    def test_add_risk_disclaimer(self, guard):
        """测试添加风险提示"""
        result = guard.check(
            content="这是一只不错的基金。",
            force_disclaimer=True,
        )
        
        assert result.risk_disclaimer_added
        assert "风险提示" in result.modified_content
    
    def test_suitability_check_mismatch(self, guard):
        """测试适当性检查不匹配"""
        profile = UserProfile(
            user_id="user-001",
            risk_level=RiskLevel.LOW,
        )
        
        result = guard.check(
            content="股票投资是一种高波动的投资方式，可以考虑配置一些个股。",
            user_profile=profile,
            force_disclaimer=True,
        )
        
        assert result.suitability_warning is not None
        assert "风险承受能力" in result.suitability_warning
    
    def test_suitability_check_incomplete_profile(self, guard):
        """测试画像不完整提示"""
        profile = UserProfile(
            user_id="user-001",
            risk_level=RiskLevel.UNKNOWN,
        )
        
        result = guard.check(
            content="基金投资是一种间接投资方式。",
            user_profile=profile,
            force_disclaimer=True,
        )
        
        assert result.suitability_warning is not None
    
    def test_detect_content_risk_level(self, guard):
        """测试内容风险等级检测"""
        # 高风险内容
        level = guard._detect_content_risk_level("股票和期权都是高波动产品")
        assert level == "high"
        
        # 低风险内容
        level = guard._detect_content_risk_level("货币基金是低风险产品")
        assert level == "low"
        
        # 中等风险
        level = guard._detect_content_risk_level("指数基金ETF跟踪市场指数")
        assert level == "medium"
    
    def test_filter_response(self, guard):
        """测试便捷过滤方法"""
        content = guard.filter_response(
            content="这个股票必涨！",
        )
        
        assert "必涨" not in content or "（" in content
        assert "风险提示" in content


class TestComplianceResult:
    """ComplianceResult测试"""
    
    def test_compliant_result(self):
        """测试合规结果"""
        result = ComplianceResult(
            is_compliant=True,
            original_content="测试内容",
            modified_content="测试内容",
        )
        
        assert result.is_compliant
        assert not result.needs_modification
    
    def test_non_compliant_result(self):
        """测试不合规结果"""
        result = ComplianceResult(
            is_compliant=False,
            needs_modification=True,
            original_content="保证收益",
            modified_content="（投资收益不确定，无法保证）",
            violations=[{"type": "promise_return"}],
        )
        
        assert not result.is_compliant
        assert result.needs_modification
        assert len(result.violations) > 0
