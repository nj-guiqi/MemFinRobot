"""工具模块 - qwen-agent Tool实现"""

from memfinrobot.tools.market_quote import MarketQuoteTool
from memfinrobot.tools.product_lookup import ProductLookupTool
from memfinrobot.tools.knowledge_retrieval import KnowledgeRetrievalTool
from memfinrobot.tools.risk_template import RiskTemplateTool
from memfinrobot.tools.portfolio_calc import PortfolioCalcTool
from memfinrobot.tools.web_search import Search
from memfinrobot.tools.web_visit import Visit
from memfinrobot.tools.python_excute import PythonInterpreter

__all__ = [
    "MarketQuoteTool",
    "ProductLookupTool", 
    "RiskTemplateTool",
    "PortfolioCalcTool",
    "Search",
    "Visit",
    "PythonInterpreter",
]
# 未加入knowledge_retri 后续开发

# 工具注册表（便于按名称获取）
TOOL_REGISTRY = {
    "market_quote": MarketQuoteTool,
    "product_lookup": ProductLookupTool,
    "risk_template": RiskTemplateTool,
    "portfolio_calc": PortfolioCalcTool,
    "search": Search,
    "visit": Visit,
    "PythonInterpreter": PythonInterpreter,
}


def get_default_tools():
    """获取默认工具列表"""
    return [
        MarketQuoteTool(),
        ProductLookupTool(),
        KnowledgeRetrievalTool(),
        RiskTemplateTool(),
        PortfolioCalcTool(),
        Search(),
        Visit(),
        PythonInterpreter(),
    ]
