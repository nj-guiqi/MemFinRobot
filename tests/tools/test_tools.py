"""工具测试"""

import pytest
import json
import sys
import os

from memfinrobot.tools.market_quote import MarketQuoteTool
from memfinrobot.tools.product_lookup import ProductLookupTool
from memfinrobot.tools.knowledge_retrieval import KnowledgeRetrievalTool
from memfinrobot.tools.risk_template import RiskTemplateTool
from memfinrobot.tools.portfolio_calc import PortfolioCalcTool
from memfinrobot.tools.web_search import Search
from memfinrobot.tools.web_visit import Visit
from memfinrobot.tools.python_excute import PythonInterpreter


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


class TestWebSearchTool:
    """WebSearch 工具测试"""

    @pytest.fixture
    def tool(self):
        return Search()

    def test_search_missing_key(self, tool, monkeypatch):
        """未配置 key 时应返回明确报错"""
        monkeypatch.delenv("SERPER_API_KEY", raising=False)
        monkeypatch.delenv("SERPER_KEY_ID", raising=False)

        result = tool.call({"query": "OpenAI"})
        assert "missing Serper key" in result

    def test_search_success_with_mock(self, tool, monkeypatch):
        """单查询成功路径（mock，不走真实网络）"""
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "organic": [
                        {
                            "title": "Result A",
                            "link": "https://example.com/a",
                            "snippet": "snippet a",
                        },
                        {
                            "title": "Result B",
                            "link": "https://example.com/b",
                            "snippet": "snippet b",
                        },
                    ]
                }

        def fake_post(*args, **kwargs):
            return FakeResponse()

        monkeypatch.setenv("SERPER_API_KEY", "test-key")
        monkeypatch.setattr("memfinrobot.tools.web_search.requests.post", fake_post)

        result = tool.call({"query": "OpenAI", "num": 2})
        assert "Query: OpenAI" in result
        assert "Result A" in result
        assert "https://example.com/a" in result

    def test_search_success_real_api(self, tool, monkeypatch):
        """单查询成功路径（真实 API，可选）"""
        api_key = os.getenv("SERPER_API_KEY") or os.getenv("SERPER_KEY_ID")
        if not api_key:
            pytest.skip("SERPER_API_KEY / SERPER_KEY_ID 未配置，跳过真实检索测试")

        monkeypatch.delenv("SERPER_KEY_ID", raising=False)
        monkeypatch.setenv("SERPER_API_KEY", api_key)

        result = tool.call({"query": "OpenAI", "num": 3})
        assert "missing Serper key" not in result
        assert "request failed" not in result
        assert "Query: OpenAI" in result
        assert "URL:" in result

    def test_search_multi_queries(self, tool, monkeypatch):
        """多查询应按分隔符拼接"""
        monkeypatch.setattr(tool, "_search_once", lambda q, n: f"Query: {q}")
        result = tool.call({"query": ["q1", "q2"]})
        assert "Query: q1" in result
        assert "Query: q2" in result
        assert "=======" in result


class TestWebVisitTool:
    """WebVisit 工具测试"""

    @pytest.fixture
    def tool(self):
        return Visit()

    def test_visit_missing_url(self, tool):
        """缺少 url 参数"""
        result = tool.call({"goal": "test"})
        assert "missing 'url'" in result

    def test_visit_real_single_url(self, tool, monkeypatch):
        """真实网页读取：单 URL"""
        monkeypatch.setenv("VISIT_SERVER_TIMEOUT", "15")
        monkeypatch.setenv("VISIT_TOTAL_TIMEOUT", "60")

        result = tool.call({"url": "http://www.phys.ruc.edu.cn/", "goal": "查看学院最近的新闻"})
        print(result)
        # assert "The useful information in https://example.com" in result
        assert "Evidence in page:" in result
        assert "Summary:" in result
        assert "could not be accessed" not in result

    def test_visit_real_multi_urls(self, tool, monkeypatch):
        """真实网页读取：多 URL"""
        monkeypatch.setenv("VISIT_SERVER_TIMEOUT", "15")
        monkeypatch.setenv("VISIT_TOTAL_TIMEOUT", "90")

        result = tool.call(
            {
                "url": ["https://example.com", "https://www.iana.org/domains/reserved"],
                "goal": "提取页面主题",
            }
        )
        print(result)
        assert "https://example.com" in result
        assert "https://www.iana.org/domains/reserved" in result
        assert "=======" in result
        assert "could not be accessed" not in result

    def test_visit_real_url_without_scheme(self, tool, monkeypatch):
        """真实网页读取：URL 自动补全 https"""
        monkeypatch.setenv("VISIT_SERVER_TIMEOUT", "15")
        monkeypatch.setenv("VISIT_TOTAL_TIMEOUT", "60")

        result = tool.call({"url": "example.com", "goal": "提取站点用途"})
        print(result)
        assert "The useful information in example.com" in result
        assert "Evidence in page:" in result
        assert "Summary:" in result


class TestPythonInterpreterTool:
    """PythonInterpreter 工具测试"""

    def test_python_interpreter_success(self, monkeypatch):
        """?? Python ???????????"""
        monkeypatch.setenv("MEMFIN_PYTHON_PATH", sys.executable)
        tool = PythonInterpreter()

        code = (
            "import re\n"
            "import requests\n"
            "resp = requests.get('https://www.baidu.com', timeout=10)\n"
            "enc = resp.apparent_encoding or resp.encoding or 'utf-8'\n"
            "text = resp.content.decode(enc, errors='replace')\n"
            "m = re.search(r'<title>(.*?)</title>', text, re.I | re.S)\n"
            "title = m.group(1).strip() if m else text[:80]\n"
            "print('encoding=' + str(enc))\n"
            "print('title=' + title)\n"
            "print('??????')\n"
        )
        result = tool.call({"code": code})
        print(result)
        assert "stdout:" in result
        assert "encoding=" in result
        assert "??????" in result

    def test_python_interpreter_missing_code(self, monkeypatch):
        """缺少 code 参数"""
        monkeypatch.setenv("MEMFIN_PYTHON_PATH", sys.executable)
        tool = PythonInterpreter()

        result = tool.call({})
        assert "missing 'code'" in result

    def test_python_interpreter_invalid_path(self):
        """解释器路径不存在"""
        tool = PythonInterpreter(cfg={"python_path": "D:/not_exists_python_env"})
        result = tool.call({"code": "print('x')"})
        assert "python executable not found" in result
