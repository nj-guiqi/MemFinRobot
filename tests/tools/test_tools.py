"""工具测试"""

import pytest
import json

from memfinrobot.tools.market_quote import MarketQuoteTool
from memfinrobot.tools.product_lookup import ProductLookupTool
from memfinrobot.tools.knowledge_retrieval import KnowledgeRetrievalTool
from memfinrobot.tools.risk_template import RiskTemplateTool
from memfinrobot.tools.portfolio_calc import PortfolioCalcTool


class TestMarketQuoteTool:
    """MarketQuoteTool测试"""
    
    @pytest.fixture
    def tool(self):
        return MarketQuoteTool()
    
    def test_query_existing_stock(self, tool):
        """测试查询存在的股票（使用mock数据保证稳定性）"""
        result = tool.call({"symbol": "000001", "provider": "mock"})
        data = json.loads(result)
        
        assert data["success"] is True
        assert data["data"]["name"] == "平安银行"
        assert "price" in data["data"]
    
    def test_query_nonexistent_stock(self, tool):
        """测试查询不存在的股票"""
        result = tool.call({"symbol": "999999", "provider": "mock"})
        data = json.loads(result)
        
        assert data["success"] is False
        assert len(data["errors"]) > 0
    
    def test_query_with_fields(self, tool):
        """测试指定字段查询"""
        result = tool.call({
            "symbol": "000001",
            "fields": ["price", "change"],
            "provider": "mock"
        })
        data = json.loads(result)
        
        assert data["success"] is True
        assert "price" in data["data"]


class TestProductLookupTool:
    """ProductLookupTool测试"""
    
    @pytest.fixture
    def tool(self):
        return ProductLookupTool()
    
    def test_lookup_fund(self, tool):
        """测试查询基金"""
        result = tool.call({
            "symbol": "510300",
            "product_type": "fund"
        })
        data = json.loads(result)
        
        assert data["success"] is True
        assert "沪深300" in data["data"]["name"]
    
    def test_lookup_fund_fee(self, tool):
        """测试查询基金费用"""
        result = tool.call({
            "symbol": "000001",
            "product_type": "fund",
            "info_type": "fee"
        })
        data = json.loads(result)
        
        assert data["success"] is True
        assert "fee" in data["data"]


class TestKnowledgeRetrievalTool:
    """KnowledgeRetrievalTool测试"""
    
    @pytest.fixture
    def tool(self):
        return KnowledgeRetrievalTool()
    
    def test_retrieve_education(self, tool):
        """测试检索投教内容"""
        result = tool.call({
            "query": "基金投资入门",
            "category": "education"
        })
        data = json.loads(result)
        
        assert data["success"] is True
        assert data["data"]["total"] > 0
    
    def test_retrieve_regulation(self, tool):
        """测试检索监管规则"""
        result = tool.call({
            "query": "适当性",
            "category": "regulation"
        })
        data = json.loads(result)
        
        assert data["success"] is True
    
    def test_retrieve_no_results(self, tool):
        """测试无结果的检索"""
        result = tool.call({
            "query": "完全不相关的内容xyz123",
        })
        data = json.loads(result)
        
        assert data["success"] is True
        assert data["data"]["total"] == 0


class TestRiskTemplateTool:
    """RiskTemplateTool测试"""
    
    @pytest.fixture
    def tool(self):
        return RiskTemplateTool()
    
    def test_general_template(self, tool):
        """测试通用风险提示"""
        result = tool.call({
            "product_type": "general",
            "template_type": "standard"
        })
        data = json.loads(result)
        
        assert data["success"] is True
        assert "风险提示" in data["data"]["risk_disclaimer"]
    
    def test_high_risk_template(self, tool):
        """测试高风险产品提示"""
        result = tool.call({
            "product_type": "stock",
            "risk_level": "high",
            "template_type": "detailed"
        })
        data = json.loads(result)
        
        assert data["success"] is True
        assert "特别提示" in data["data"]["risk_disclaimer"]


class TestPortfolioCalcTool:
    """PortfolioCalcTool测试"""
    
    @pytest.fixture
    def tool(self):
        return PortfolioCalcTool()
    
    def test_calc_return(self, tool):
        """测试收益率计算"""
        result = tool.call({
            "calc_type": "return",
            "initial_value": 100,
            "final_value": 120
        })
        data = json.loads(result)
        
        assert data["success"] is True
        assert data["data"]["total_return"] == 0.2
    
    def test_calc_volatility(self, tool):
        """测试波动率计算"""
        values = [100, 102, 99, 103, 101, 105]
        result = tool.call({
            "calc_type": "volatility",
            "values": values
        })
        data = json.loads(result)
        
        assert data["success"] is True
        assert "annual_volatility" in data["data"]
    
    def test_calc_max_drawdown(self, tool):
        """测试最大回撤计算"""
        values = [100, 110, 105, 95, 100, 90, 95]
        result = tool.call({
            "calc_type": "max_drawdown",
            "values": values
        })
        data = json.loads(result)
        
        assert data["success"] is True
        assert data["data"]["max_drawdown"] > 0
    
    def test_calc_sharpe(self, tool):
        """测试夏普比率计算"""
        values = [100, 101, 102, 101, 103, 104, 103, 105]
        result = tool.call({
            "calc_type": "sharpe",
            "values": values,
            "risk_free_rate": 0.02
        })
        data = json.loads(result)
        
        assert data["success"] is True
        assert "sharpe_ratio" in data["data"]
