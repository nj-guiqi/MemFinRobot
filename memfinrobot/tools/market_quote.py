"""行情查询工具"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from qwen_agent.tools.base import register_tool

from memfinrobot.tools.base import MemFinBaseTool
from memfinrobot.memory.schemas import ToolResult


@register_tool("market_quote")
class MarketQuoteTool(MemFinBaseTool):
    """
    行情查询工具
    
    查询股票、基金、指数的行情信息
    V0版本使用Mock数据
    """
    
    name: str = "market_quote"
    description: str = "查询股票、基金或指数的行情信息，包括价格、涨跌幅、成交量等"
    parameters: dict = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "证券代码，如'000001'（平安银行）、'510300'（沪深300ETF）"
            },
            "market": {
                "type": "string",
                "enum": ["stock", "fund", "index"],
                "description": "市场类型：stock（股票）、fund（基金）、index（指数）"
            },
            "fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "需要查询的字段列表，如['price', 'change', 'volume']"
            }
        },
        "required": ["symbol"]
    }
    
    # Mock数据
    _mock_data = {
        "000001": {
            "name": "平安银行",
            "type": "stock",
            "price": 10.52,
            "change": 0.15,
            "change_pct": 1.45,
            "volume": 125000000,
            "amount": 1312500000,
            "high": 10.68,
            "low": 10.35,
            "open": 10.40,
            "prev_close": 10.37,
        },
        "510300": {
            "name": "沪深300ETF",
            "type": "fund",
            "price": 3.856,
            "change": 0.023,
            "change_pct": 0.60,
            "volume": 85000000,
            "amount": 327680000,
            "nav": 3.8542,
        },
        "000300": {
            "name": "沪深300",
            "type": "index",
            "price": 3856.23,
            "change": 23.15,
            "change_pct": 0.60,
            "volume": 25000000000,
            "amount": 320000000000,
        },
    }
    
    def _call_impl(self, params: dict, **kwargs) -> ToolResult:
        """查询行情"""
        symbol = params.get("symbol", "")
        market = params.get("market", "stock")
        fields = params.get("fields", [])
        
        # 查找Mock数据
        if symbol in self._mock_data:
            data = self._mock_data[symbol].copy()
            
            # 如果指定了字段，只返回指定字段
            if fields:
                data = {k: v for k, v in data.items() if k in fields or k in ["name", "type"]}
            
            return ToolResult(
                success=True,
                data=data,
                source="mock_data",
                asof=datetime.now(),
                warnings=["当前为模拟数据，仅供测试使用"],
            )
        else:
            return ToolResult(
                success=False,
                data=None,
                source="mock_data",
                errors=[f"未找到证券代码 {symbol} 的行情数据"],
            )
