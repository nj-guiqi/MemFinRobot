"""产品信息查询工具"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from qwen_agent.tools.base import register_tool

from memfinrobot.tools.base import MemFinBaseTool
from memfinrobot.memory.schemas import ToolResult


@register_tool("product_lookup")
class ProductLookupTool(MemFinBaseTool):
    """
    产品信息查询工具
    
    查询基金、股票、债券的基础信息
    V0版本使用Mock数据
    """
    
    name: str = "product_lookup"
    description: str = "查询金融产品的基础信息，包括基金要素、股票基本面、债券条款等"
    parameters: dict = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "产品代码"
            },
            "product_type": {
                "type": "string",
                "enum": ["fund", "stock", "bond"],
                "description": "产品类型：fund（基金）、stock（股票）、bond（债券）"
            },
            "info_type": {
                "type": "string",
                "enum": ["basic", "fee", "performance", "risk"],
                "description": "信息类型：basic（基本信息）、fee（费用）、performance（业绩）、risk（风险）"
            }
        },
        "required": ["symbol"]
    }
    
    # Mock数据
    _mock_funds = {
        "000001": {
            "name": "华夏成长混合",
            "type": "混合型",
            "manager": "张三",
            "company": "华夏基金",
            "inception_date": "2001-12-18",
            "size": 125.36,  # 亿元
            "risk_level": "中高风险",
            "fee": {
                "management_fee": 1.5,
                "custody_fee": 0.25,
                "purchase_fee": 1.5,
                "redemption_fee": 0.5,
            },
            "performance": {
                "ytd": 5.23,
                "1y": 12.56,
                "3y": 35.12,
                "since_inception": 1256.78,
            },
        },
        "510300": {
            "name": "华泰柏瑞沪深300ETF",
            "type": "指数型ETF",
            "manager": "李四",
            "company": "华泰柏瑞基金",
            "inception_date": "2012-05-28",
            "size": 856.23,
            "risk_level": "中风险",
            "tracking_index": "沪深300",
            "tracking_error": 0.05,
            "fee": {
                "management_fee": 0.5,
                "custody_fee": 0.1,
            },
            "performance": {
                "ytd": 3.56,
                "1y": 8.23,
                "3y": 15.67,
            },
        },
    }
    
    _mock_stocks = {
        "000001": {
            "name": "平安银行",
            "industry": "银行",
            "market_cap": 1856.23,  # 亿元
            "pe_ratio": 5.23,
            "pb_ratio": 0.56,
            "dividend_yield": 5.12,
            "roe": 12.35,
            "revenue": 1568.23,  # 亿元
            "net_profit": 356.78,  # 亿元
        },
    }
    
    def _call_impl(self, params: dict, **kwargs) -> ToolResult:
        """查询产品信息"""
        symbol = params.get("symbol", "")
        product_type = params.get("product_type", "fund")
        info_type = params.get("info_type", "basic")
        
        # 根据产品类型查找
        if product_type == "fund" and symbol in self._mock_funds:
            data = self._mock_funds[symbol].copy()
            
            # 根据信息类型筛选
            if info_type == "fee":
                data = {"name": data["name"], "fee": data.get("fee", {})}
            elif info_type == "performance":
                data = {"name": data["name"], "performance": data.get("performance", {})}
            elif info_type == "risk":
                data = {"name": data["name"], "risk_level": data.get("risk_level", "")}
            
            return ToolResult(
                success=True,
                data=data,
                source="mock_data",
                asof=datetime.now(),
                warnings=["当前为模拟数据，仅供测试使用"],
            )
            
        elif product_type == "stock" and symbol in self._mock_stocks:
            data = self._mock_stocks[symbol].copy()
            
            return ToolResult(
                success=True,
                data=data,
                source="mock_data",
                asof=datetime.now(),
                warnings=["当前为模拟数据，仅供测试使用"],
            )
        
        return ToolResult(
            success=False,
            data=None,
            source="mock_data",
            errors=[f"未找到产品 {symbol} 的信息"],
        )
