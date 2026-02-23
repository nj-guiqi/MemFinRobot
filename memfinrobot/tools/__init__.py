"""Tool module exports and default registry."""

from typing import Any, Dict, Optional

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

TOOL_REGISTRY = {
    "market_quote": MarketQuoteTool,
    "product_lookup": ProductLookupTool,
    "risk_template": RiskTemplateTool,
    "portfolio_calc": PortfolioCalcTool,
    "search": Search,
    "visit": Visit,
    "PythonInterpreter": PythonInterpreter,
}


def get_default_tools(settings: Optional[Any] = None):
    """Build default tool instances, optionally using tool configs from Settings."""
    tools_cfg: Dict[str, Any] = {}
    if settings is not None and hasattr(settings, "tools") and isinstance(settings.tools, dict):
        tools_cfg = settings.tools

    # 未接入knowledge_retri
    return [
        MarketQuoteTool(),
        ProductLookupTool(),
        RiskTemplateTool(),
        PortfolioCalcTool(),
        Search(cfg=tools_cfg.get("web_search") or {}),
        Visit(cfg=tools_cfg.get("web_visit") or {}),
        PythonInterpreter(cfg=tools_cfg.get("python_interpreter") or {}),
    ]
