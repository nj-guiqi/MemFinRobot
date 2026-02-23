"""产品信息查询工具：支持真实数据接入与 mock 回退。"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from qwen_agent.tools.base import register_tool

from memfinrobot.config.settings import get_settings
from memfinrobot.memory.schemas import ToolResult
from memfinrobot.tools.base import MemFinBaseTool
from memfinrobot.tools.market_quote import ProviderFactory


@register_tool("product_lookup")
class ProductLookupTool(MemFinBaseTool):
    name: str = "product_lookup"
    description: str = "查询金融产品信息，优先使用真实数据，失败后回退 mock。"
    parameters: dict = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "产品代码"},
            "product_type": {
                "type": "string",
                "enum": ["fund", "stock", "bond"],
                "description": "产品类型",
            },
            "info_type": {
                "type": "string",
                "enum": ["basic", "fee", "performance", "risk"],
                "description": "信息类型",
            },
            "provider": {
                "type": "string",
                "description": "数据源，可选 tencent/akshare/mock",
            },
            "fallback_provider": {
                "type": "string",
                "description": "降级数据源，默认取配置中的 fallback_provider",
            },
        },
        "required": ["symbol"],
    }

    _mock_funds = {
        "000001": {
            "name": "华夏成长混合",
            "type": "混合型",
            "manager": "张三",
            "company": "华夏基金",
            "inception_date": "2001-12-18",
            "size": 125.36,
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
            "name": "沪深300ETF",
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
            "market_cap": 1856.23,
            "pe_ratio": 5.23,
            "pb_ratio": 0.56,
            "dividend_yield": 5.12,
            "roe": 12.35,
            "revenue": 1568.23,
            "net_profit": 356.78,
        },
    }

    def __init__(self):
        super().__init__()
        self._config = get_settings().market_data

    def _call_impl(self, params: dict, **kwargs) -> ToolResult:
        symbol = str(params.get("symbol", "")).strip()
        product_type = str(params.get("product_type", "fund")).strip().lower()
        info_type = str(params.get("info_type", "basic")).strip().lower()

        if not symbol:
            return ToolResult(success=False, source="product_lookup", errors=["missing required param: symbol"])

        provider_name = self._get_provider_name(params)
        fallback_name = params.get("fallback_provider") or self._config.fallback_provider

        if provider_name == "mock":
            return self._lookup_mock(symbol, product_type, info_type)

        warnings: List[str] = []
        try:
            quote_data = self._get_quote(symbol, product_type, provider_name)
            data = self._format_real_data(symbol, product_type, info_type, quote_data, warnings)
            warnings.append("real-time quote data from public provider")
            return ToolResult(
                success=True,
                data=data,
                source=provider_name,
                asof=datetime.now(),
                warnings=warnings,
            )
        except Exception as exc:
            warnings.append(f"primary provider failed ({provider_name}): {exc}")

        # 降级：优先尝试 fallback provider 的实时数据，再降级到 mock
        if fallback_name and fallback_name not in (provider_name, "mock"):
            try:
                quote_data = self._get_quote(symbol, product_type, fallback_name)
                data = self._format_real_data(symbol, product_type, info_type, quote_data, warnings)
                warnings.append(f"fallback real provider used: {fallback_name}")
                return ToolResult(
                    success=True,
                    data=data,
                    source=fallback_name,
                    asof=datetime.now(),
                    warnings=warnings,
                )
            except Exception as exc:
                warnings.append(f"fallback provider failed ({fallback_name}): {exc}")

        mock_result = self._lookup_mock(symbol, product_type, info_type)
        mock_result.warnings = warnings + mock_result.warnings + ["fallback to mock data"]
        return mock_result

    def _get_provider_name(self, params: dict) -> str:
        if params.get("provider"):
            return str(params["provider"])
        env_provider = os.getenv("MEMFIN_PRODUCT_LOOKUP_PROVIDER")
        if env_provider:
            return env_provider
        # 最简方案：默认与行情工具一致
        return self._config.provider

    def _get_quote(self, symbol: str, product_type: str, provider_name: str) -> Dict[str, Any]:
        market_map = {"stock": "stock", "fund": "fund", "bond": "stock"}
        market = market_map.get(product_type, "fund")
        provider = ProviderFactory.get_provider(provider_name, timeout=self._config.timeout_seconds)
        return provider.get_quote(symbol, market)

    def _format_real_data(
        self,
        symbol: str,
        product_type: str,
        info_type: str,
        quote: Dict[str, Any],
        warnings: List[str],
    ) -> Dict[str, Any]:
        name = quote.get("name") or symbol
        base = {
            "name": name,
            "symbol": quote.get("symbol") or symbol,
            "product_type": product_type,
            "asof": quote.get("asof"),
        }

        if info_type == "fee":
            # 实时行情源通常没有费率，最简单策略是 fund 走 mock 费率补全。
            fee_data = {}
            if product_type == "fund":
                _, code = self._normalize_symbol(symbol)
                fee_data = self._mock_funds.get(code, {}).get("fee", {})
            if not fee_data:
                warnings.append("fee data is not available from quote provider")
            else:
                warnings.append("fee data from mock supplement")
            return {**base, "fee": fee_data}

        if info_type == "performance":
            return {
                **base,
                "performance": {
                    "latest_price": quote.get("price"),
                    "day_change": quote.get("change"),
                    "day_change_pct": quote.get("change_pct"),
                    "high": quote.get("high"),
                    "low": quote.get("low"),
                    "volume": quote.get("volume"),
                },
            }

        if info_type == "risk":
            change_pct = quote.get("change_pct")
            risk_level = "unknown"
            if isinstance(change_pct, (int, float)):
                abs_pct = abs(change_pct)
                if abs_pct >= 5:
                    risk_level = "high"
                elif abs_pct >= 2:
                    risk_level = "medium"
                else:
                    risk_level = "low"
            return {
                **base,
                "risk_level": risk_level,
                "risk_hint": "estimated by intraday volatility (change_pct)",
                "change_pct": change_pct,
            }

        # basic
        return {
            **base,
            "latest_price": quote.get("price"),
            "change": quote.get("change"),
            "change_pct": quote.get("change_pct"),
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "volume": quote.get("volume"),
            "amount": quote.get("amount"),
        }

    def _lookup_mock(self, symbol: str, product_type: str, info_type: str) -> ToolResult:
        _, code = self._normalize_symbol(symbol)

        if product_type == "fund" and code in self._mock_funds:
            data = self._mock_funds[code].copy()
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
                warnings=["using mock product data"],
            )

        if product_type == "stock" and code in self._mock_stocks:
            data = self._mock_stocks[code].copy()
            if info_type == "risk":
                data = {
                    "name": data["name"],
                    "risk_level": "medium",
                    "risk_hint": "mock risk estimation",
                }
            return ToolResult(
                success=True,
                data=data,
                source="mock_data",
                asof=datetime.now(),
                warnings=["using mock product data"],
            )

        return ToolResult(
            success=False,
            data=None,
            source="mock_data",
            errors=[f"product info not found for symbol: {symbol}"],
        )

    @staticmethod
    def _normalize_symbol(symbol: str):
        lower = symbol.strip().lower()
        if lower.startswith(("sh", "sz")):
            return lower[:2], lower[2:]
        if "." in lower:
            code, exchange = lower.split(".", 1)
            return exchange, code
        return "", lower
