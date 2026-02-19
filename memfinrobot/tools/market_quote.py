# -*- coding: utf-8 -*-
"""行情查询工具：支持最新行情与历史行情。"""

import logging
import os
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from qwen_agent.tools.base import register_tool

from memfinrobot.config.settings import get_settings
from memfinrobot.memory.schemas import ToolResult
from memfinrobot.tools.base import MemFinBaseTool

logger = logging.getLogger(__name__)


NORMALIZED_FIELDS = [
    "name",
    "symbol",
    "type",
    "price",
    "prev_close",
    "open",
    "high",
    "low",
    "change",
    "change_pct",
    "volume",
    "amount",
    "asof",
]


def infer_exchange(symbol: str) -> str:
    if not symbol:
        return "sz"
    return "sh" if symbol[0] in ("6", "5", "9") else "sz"


def parse_symbol(symbol: str) -> Tuple[str, str]:
    symbol = symbol.strip().lower()
    if symbol.startswith(("sh", "sz")):
        return symbol[:2], symbol[2:]
    if "." in symbol:
        code, maybe_exchange = symbol.split(".", 1)
        exchange = maybe_exchange if maybe_exchange else infer_exchange(code)
        return exchange, code
    return infer_exchange(symbol), symbol


def _normalize_date(date_str: str) -> str:
    raw = date_str.strip()
    if not raw:
        raise ValueError("empty date")
    if "-" in raw:
        dt = datetime.strptime(raw, "%Y-%m-%d")
    else:
        dt = datetime.strptime(raw, "%Y%m%d")
    return dt.strftime("%Y%m%d")


class MarketDataProvider(ABC):
    name: str = "base"

    @abstractmethod
    def get_quote(self, symbol: str, market: str = "stock") -> Dict[str, Any]:
        raise NotImplementedError

    def get_history(
        self,
        symbol: str,
        market: str = "stock",
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError(f"provider {self.name} does not support history")

    def normalize_data(self, raw_data: Dict[str, Any], market: str) -> Dict[str, Any]:
        normalized = {field: raw_data.get(field) for field in NORMALIZED_FIELDS}
        if normalized.get("type") is None:
            normalized["type"] = market
        return normalized


class TencentProvider(MarketDataProvider):
    name: str = "tencent"
    BASE_URL = "http://qt.gtimg.cn/q="

    FIELD_INDEX = {
        "name": 1,
        "code": 2,
        "price": 3,
        "prev_close": 4,
        "open": 5,
        "time_str": 30,
        "change": 31,
        "change_pct": 32,
        "high": 33,
        "low": 34,
        "volume": 36,
        "amount_wan": 37,
    }

    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout

    def get_quote(self, symbol: str, market: str = "stock") -> Dict[str, Any]:
        exchange, code = parse_symbol(symbol)
        url = f"{self.BASE_URL}{exchange}{code}"
        try:
            req = Request(url)
            req.add_header("User-Agent", "Mozilla/5.0")
            with urlopen(req, timeout=self.timeout) as response:
                content = response.read().decode("gbk", errors="ignore")
            return self._parse_response(content, symbol, market)
        except (URLError, HTTPError) as exc:
            raise ConnectionError(f"Tencent quote request failed: {exc}")

    def _parse_response(self, content: str, symbol: str, market: str) -> Dict[str, Any]:
        match = re.search(r'v_\w+="([^"]*)"', content)
        if not match:
            raise ValueError(f"cannot parse tencent quote response: {content[:100]}")

        fields = match.group(1).split("~")
        if len(fields) < 35:
            raise ValueError(f"incomplete tencent quote fields: {len(fields)}")

        raw_data = {
            "name": fields[self.FIELD_INDEX["name"]],
            "symbol": fields[self.FIELD_INDEX["code"]] or symbol,
            "price": self._safe_float(fields, self.FIELD_INDEX["price"]),
            "prev_close": self._safe_float(fields, self.FIELD_INDEX["prev_close"]),
            "open": self._safe_float(fields, self.FIELD_INDEX["open"]),
            "high": self._safe_float(fields, self.FIELD_INDEX["high"]),
            "low": self._safe_float(fields, self.FIELD_INDEX["low"]),
            "change": self._safe_float(fields, self.FIELD_INDEX["change"]),
            "change_pct": self._safe_float(fields, self.FIELD_INDEX["change_pct"]),
            "volume": self._safe_float(fields, self.FIELD_INDEX["volume"]),
            "amount": None,
            "asof": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        amount_wan = self._safe_float(fields, self.FIELD_INDEX["amount_wan"])
        if amount_wan is not None:
            raw_data["amount"] = amount_wan * 10000

        if len(fields) > self.FIELD_INDEX["time_str"]:
            raw_data["asof"] = self._parse_time(fields[self.FIELD_INDEX["time_str"]])
        return self.normalize_data(raw_data, market)

    @staticmethod
    def _safe_float(fields: List[str], index: int) -> Optional[float]:
        try:
            if index < len(fields) and fields[index]:
                return float(fields[index])
        except (ValueError, TypeError):
            return None
        return None

    @staticmethod
    def _parse_time(time_str: str) -> str:
        try:
            if len(time_str) >= 14:
                return datetime.strptime(time_str[:14], "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class AkShareProvider(MarketDataProvider):
    name: str = "akshare"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._ak = None

    def _get_ak(self):
        if self._ak is None:
            try:
                import akshare as ak  # type: ignore
            except ImportError as exc:
                raise ImportError("akshare is not installed, run: pip install akshare") from exc
            self._ak = ak
        return self._ak

    def get_quote(self, symbol: str, market: str = "stock") -> Dict[str, Any]:
        ak = self._get_ak()
        _, code = parse_symbol(symbol)

        if market == "index":
            df = ak.stock_zh_index_spot_em()
        elif market == "fund":
            df = ak.fund_etf_spot_em()
        else:
            df = ak.stock_zh_a_spot_em()

        row = df[df["代码"] == code]
        if row.empty:
            raise ValueError(f"symbol not found in akshare spot: {code}")

        row = row.iloc[0]
        raw_data = {
            "name": row.get("名称"),
            "symbol": code,
            "price": self._safe_value(row.get("最新价")),
            "prev_close": self._safe_value(row.get("昨收")),
            "open": self._safe_value(row.get("今开")),
            "high": self._safe_value(row.get("最高")),
            "low": self._safe_value(row.get("最低")),
            "change": self._safe_value(row.get("涨跌额")),
            "change_pct": self._safe_value(row.get("涨跌幅")),
            "volume": self._safe_value(row.get("成交量")),
            "amount": self._safe_value(row.get("成交额")),
            "asof": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return self.normalize_data(raw_data, market)

    def get_history(
        self,
        symbol: str,
        market: str = "stock",
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        ak = self._get_ak()
        _, code = parse_symbol(symbol)

        period_map = {"daily": "daily", "weekly": "weekly", "monthly": "monthly"}
        period_value = period_map.get(period, "daily")

        end = _normalize_date(end_date) if end_date else datetime.now().strftime("%Y%m%d")
        if start_date:
            start = _normalize_date(start_date)
        else:
            days = max(limit * 3, 30)
            start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        if market == "fund":
            df = ak.fund_etf_hist_em(symbol=code, period=period_value, start_date=start, end_date=end, adjust="")
        else:
            # stock/index use stock_zh_a_hist for simplicity in this minimal implementation
            df = ak.stock_zh_a_hist(symbol=code, period=period_value, start_date=start, end_date=end, adjust="")

        if df is None or df.empty:
            raise ValueError(f"empty history data for symbol: {symbol}")

        items: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            change_pct = self._safe_value(row.get("涨跌幅"))
            close_price = self._safe_value(row.get("收盘"))
            open_price = self._safe_value(row.get("开盘"))
            change = None
            if close_price is not None and open_price is not None:
                change = close_price - open_price

            item = {
                "date": str(row.get("日期")),
                "open": open_price,
                "close": close_price,
                "high": self._safe_value(row.get("最高")),
                "low": self._safe_value(row.get("最低")),
                "volume": self._safe_value(row.get("成交量")),
                "amount": self._safe_value(row.get("成交额")),
                "change": change,
                "change_pct": change_pct,
            }
            items.append(item)

        if limit > 0:
            items = items[-limit:]
        return items

    @staticmethod
    def _safe_value(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (ValueError, TypeError):
            return None


class MockProvider(MarketDataProvider):
    name: str = "mock"

    MOCK_DATA = {
        "000001": {
            "name": "平安银行",
            "symbol": "000001",
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
            "symbol": "510300",
            "type": "fund",
            "price": 3.856,
            "change": 0.023,
            "change_pct": 0.60,
            "volume": 85000000,
            "amount": 327680000,
            "high": 3.870,
            "low": 3.845,
            "open": 3.850,
            "prev_close": 3.833,
        },
        "000300": {
            "name": "沪深300",
            "symbol": "000300",
            "type": "index",
            "price": 3856.23,
            "change": 23.15,
            "change_pct": 0.60,
            "volume": 25000000000,
            "amount": 320000000000,
            "high": 3880.00,
            "low": 3830.00,
            "open": 3840.00,
            "prev_close": 3833.08,
        },
    }

    def __init__(self, timeout: float = 0.0):
        self.timeout = timeout

    def get_quote(self, symbol: str, market: str = "stock") -> Dict[str, Any]:
        _, code = parse_symbol(symbol)
        if code not in self.MOCK_DATA:
            raise ValueError(f"symbol not found in mock provider: {code}")
        data = self.MOCK_DATA[code].copy()
        data["asof"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.normalize_data(data, market)

    def get_history(
        self,
        symbol: str,
        market: str = "stock",
        period: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        _, code = parse_symbol(symbol)
        if code not in self.MOCK_DATA:
            raise ValueError(f"symbol not found in mock provider: {code}")

        base = self.MOCK_DATA[code]
        close = float(base.get("price") or 10.0)
        now = datetime.now()
        size = max(limit, 30)

        series: List[Dict[str, Any]] = []
        for i in range(size):
            day = now - timedelta(days=size - i)
            drift = ((i % 7) - 3) * 0.003
            open_price = round(close * (1 - drift / 2), 4)
            close_price = round(close * (1 + drift), 4)
            high_price = round(max(open_price, close_price) * 1.01, 4)
            low_price = round(min(open_price, close_price) * 0.99, 4)
            change = round(close_price - open_price, 4)
            change_pct = round((change / open_price) * 100, 4) if open_price else 0.0
            volume = int((base.get("volume") or 1000000) * (0.9 + (i % 5) * 0.05))
            amount = float(volume) * close_price

            series.append(
                {
                    "date": day.strftime("%Y-%m-%d"),
                    "open": open_price,
                    "close": close_price,
                    "high": high_price,
                    "low": low_price,
                    "volume": volume,
                    "amount": amount,
                    "change": change,
                    "change_pct": change_pct,
                }
            )

        if limit > 0:
            series = series[-limit:]
        return series


class ProviderFactory:
    _providers = {
        "tencent": TencentProvider,
        "akshare": AkShareProvider,
        "mock": MockProvider,
    }
    _instances: Dict[str, MarketDataProvider] = {}

    @classmethod
    def get_provider(cls, name: str, **kwargs) -> MarketDataProvider:
        if name not in cls._instances:
            if name not in cls._providers:
                raise ValueError(f"unknown provider: {name}")
            cls._instances[name] = cls._providers[name](**kwargs)
        return cls._instances[name]

    @classmethod
    def register_provider(cls, name: str, provider_class):
        cls._providers[name] = provider_class


class QuoteCache:
    def __init__(self, ttl_seconds: float = 2.0):
        self.ttl = ttl_seconds
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        if key in self._cache:
            timestamp, data = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            del self._cache[key]
        return None

    def set(self, key: str, data: Dict[str, Any]) -> None:
        self._cache[key] = (time.time(), data)

    def clear(self) -> None:
        self._cache.clear()


@register_tool("market_quote")
class MarketQuoteTool(MemFinBaseTool):
    name: str = "market_quote"
    description: str = "查询证券最新行情或历史行情。"
    parameters: dict = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "证券代码，如 000001、510300"},
            "market": {
                "type": "string",
                "enum": ["stock", "fund", "index"],
                "description": "市场类型",
            },
            "mode": {
                "type": "string",
                "enum": ["latest", "history"],
                "description": "latest=最新行情，history=历史行情",
            },
            "period": {
                "type": "string",
                "enum": ["daily", "weekly", "monthly"],
                "description": "历史行情周期，默认 daily",
            },
            "start_date": {"type": "string", "description": "历史开始日期，YYYY-MM-DD 或 YYYYMMDD"},
            "end_date": {"type": "string", "description": "历史结束日期，YYYY-MM-DD 或 YYYYMMDD"},
            "limit": {"type": "integer", "description": "历史返回条数，默认 30"},
            "fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "需要返回的字段列表",
            },
            "provider": {
                "type": "string",
                "description": "数据源，可选 tencent/akshare/mock",
            },
        },
        "required": ["symbol"],
    }

    def __init__(self):
        super().__init__()
        self._cache = QuoteCache()
        self._config = None

    @property
    def config(self):
        if self._config is None:
            self._config = get_settings().market_data
        return self._config

    def _get_provider_name(self, params: dict) -> str:
        if params.get("provider"):
            return params["provider"]
        env_provider = os.getenv("MEMFIN_MARKET_QUOTE_PROVIDER")
        if env_provider:
            return env_provider
        return self.config.provider

    def _call_impl(self, params: dict, **kwargs) -> ToolResult:
        symbol = params.get("symbol", "").strip()
        market = params.get("market", "stock")
        fields = params.get("fields", [])
        mode = params.get("mode", "latest")

        if not symbol:
            return ToolResult(success=False, source="market_quote", errors=["missing required param: symbol"])

        if mode == "history":
            return self._query_history(symbol=symbol, market=market, fields=fields, params=params)
        return self._query_latest(symbol=symbol, market=market, fields=fields, params=params)

    def _query_latest(self, symbol: str, market: str, fields: List[str], params: dict) -> ToolResult:
        cache_key = f"latest:{symbol}:{market}"
        cached = self._cache.get(cache_key)
        if cached:
            return self._build_latest_result(cached, fields, "cache", [])

        provider_name = self._get_provider_name(params)
        fallback_name = self.config.fallback_provider

        warnings: List[str] = []
        data: Optional[Dict[str, Any]] = None
        source = provider_name

        try:
            provider = ProviderFactory.get_provider(provider_name, timeout=self.config.timeout_seconds)
            data = provider.get_quote(symbol, market)
            source = provider_name
        except Exception as exc:
            warnings.append(f"primary provider failed ({provider_name}): {exc}")
            if fallback_name and fallback_name != provider_name:
                fallback = ProviderFactory.get_provider(fallback_name)
                data = fallback.get_quote(symbol, market)
                source = fallback_name
                warnings.append(f"fallback provider used: {fallback_name}")
            else:
                return ToolResult(success=False, source=provider_name, errors=[str(exc)], warnings=warnings)

        if data:
            self._cache.set(cache_key, data)
        return self._build_latest_result(data or {}, fields, source, warnings)

    def _query_history(self, symbol: str, market: str, fields: List[str], params: dict) -> ToolResult:
        period = params.get("period", "daily")
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        limit = int(params.get("limit", 30) or 30)
        limit = max(1, min(limit, 500))

        provider_name = self._get_provider_name(params)
        fallback_name = self.config.fallback_provider

        warnings: List[str] = []
        items: Optional[List[Dict[str, Any]]] = None
        source = provider_name

        try:
            provider = ProviderFactory.get_provider(provider_name, timeout=self.config.timeout_seconds)
            items = provider.get_history(
                symbol=symbol,
                market=market,
                period=period,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
            source = provider_name
        except Exception as exc:
            warnings.append(f"primary provider history failed ({provider_name}): {exc}")
            if fallback_name and fallback_name != provider_name:
                fallback = ProviderFactory.get_provider(fallback_name)
                items = fallback.get_history(
                    symbol=symbol,
                    market=market,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                )
                source = fallback_name
                warnings.append(f"fallback provider used: {fallback_name}")
            else:
                return ToolResult(success=False, source=provider_name, errors=[str(exc)], warnings=warnings)

        filtered_items = self._filter_history_items(items or [], fields)
        if source == "mock":
            warnings.append("using mock history data")
        else:
            warnings.append("history data from public provider, schema may vary")

        data = {
            "symbol": symbol,
            "market": market,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "count": len(filtered_items),
            "items": filtered_items,
        }
        return ToolResult(success=True, data=data, source=source, asof=datetime.now(), warnings=warnings)

    def _build_latest_result(
        self,
        data: Dict[str, Any],
        fields: List[str],
        source: str,
        warnings: List[str],
    ) -> ToolResult:
        if fields:
            filtered = {k: v for k, v in data.items() if k in fields or k in ["name", "symbol", "type"]}
        else:
            filtered = data

        all_warnings = warnings.copy()
        if source == "mock":
            all_warnings.append("using mock latest quote data")
        elif source != "cache":
            all_warnings.append("latest quote from public provider")

        asof = None
        if data.get("asof"):
            try:
                asof = datetime.strptime(data["asof"], "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                asof = datetime.now()
        else:
            asof = datetime.now()

        return ToolResult(success=True, data=filtered, source=source, asof=asof, warnings=all_warnings)

    @staticmethod
    def _filter_history_items(items: List[Dict[str, Any]], fields: List[str]) -> List[Dict[str, Any]]:
        if not fields:
            return items
        keep = set(fields)
        keep.add("date")
        return [{k: v for k, v in item.items() if k in keep} for item in items]
