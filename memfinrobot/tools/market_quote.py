# -*- coding: utf-8 -*-
"""行情查询工具 - 支持真实数据接入"""

import os
import re
import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from qwen_agent.tools.base import register_tool

from memfinrobot.tools.base import MemFinBaseTool
from memfinrobot.memory.schemas import ToolResult
from memfinrobot.config.settings import get_settings

logger = logging.getLogger(__name__)


# ============================================================================
# 字段归一化定义（稳定契约）
# ============================================================================
NORMALIZED_FIELDS = [
    "name",        # 证券名称
    "symbol",      # 证券代码
    "type",        # 类型：stock/fund/index
    "price",       # 最新价
    "prev_close",  # 昨收
    "open",        # 今开
    "high",        # 最高
    "low",         # 最低
    "change",      # 涨跌额
    "change_pct",  # 涨跌幅(%)
    "volume",      # 成交量
    "amount",      # 成交额
    "asof",        # 数据时间
]


# ============================================================================
# A股代码推断规则
# ============================================================================
def infer_exchange(symbol: str) -> str:
    """
    根据证券代码推断交易所
    
    规则：
    - 6/5/9 开头 -> SH（上海）
    - 0/3/1/2 开头 -> SZ（深圳）
    
    Args:
        symbol: 证券代码（纯数字，如 '000001'）
        
    Returns:
        交易所前缀：'sh' 或 'sz'
    """
    if not symbol:
        return "sz"
    
    first_char = symbol[0]
    if first_char in ("6", "5", "9"):
        return "sh"
    else:
        return "sz"


def parse_symbol(symbol: str) -> Tuple[str, str]:
    """
    解析证券代码，返回(交易所前缀, 纯代码)
    
    支持格式：
    - '000001' -> 自动推断
    - 'sh600000' / 'sz000001' -> 显式前缀
    - '600000.SH' / '000001.SZ' -> 后缀格式
    
    Returns:
        (exchange, code) 如 ('sz', '000001')
    """
    symbol = symbol.strip().lower()
    
    # 处理带前缀格式：sh600000 / sz000001
    if symbol.startswith(("sh", "sz")):
        return symbol[:2], symbol[2:]
    
    # 处理后缀格式：600000.sh / 000001.sz
    if "." in symbol:
        parts = symbol.split(".")
        code = parts[0]
        exchange = parts[1] if len(parts) > 1 else infer_exchange(code)
        return exchange, code
    
    # 纯代码，自动推断
    return infer_exchange(symbol), symbol


# ============================================================================
# Provider 抽象基类
# ============================================================================
class MarketDataProvider(ABC):
    """行情数据提供者抽象基类"""
    
    name: str = "base"
    
    @abstractmethod
    def get_quote(self, symbol: str, market: str = "stock") -> Dict[str, Any]:
        """
        获取行情数据
        
        Args:
            symbol: 证券代码
            market: 市场类型 (stock/fund/index)
            
        Returns:
            归一化后的行情数据字典
        """
        raise NotImplementedError
    
    def normalize_data(self, raw_data: Dict[str, Any], market: str) -> Dict[str, Any]:
        """将原始数据归一化为统一格式"""
        normalized = {}
        for field in NORMALIZED_FIELDS:
            normalized[field] = raw_data.get(field)
        
        # 确保 type 字段
        if normalized.get("type") is None:
            normalized["type"] = market
            
        return normalized


# ============================================================================
# 腾讯行情 Provider
# ============================================================================
class TencentProvider(MarketDataProvider):
    """
    腾讯行情数据提供者
    
    接口：http://qt.gtimg.cn/q=
    特点：免Key、速度快、实时性好
    """
    
    name: str = "tencent"
    BASE_URL = "http://qt.gtimg.cn/q="
    
    # 字段位置映射（基于 ~ 分割后的数组索引）
    FIELD_INDEX = {
        "name": 1,
        "code": 2,
        "price": 3,
        "prev_close": 4,
        "open": 5,
        "volume_hand": 6,      # 成交量（手）
        "time_str": 30,        # 时间戳字符串
        "change": 31,
        "change_pct": 32,
        "high": 33,
        "low": 34,
        "volume": 36,          # 成交量
        "amount_wan": 37,      # 成交额（万）
    }
    
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
    
    def get_quote(self, symbol: str, market: str = "stock") -> Dict[str, Any]:
        """获取腾讯行情数据"""
        exchange, code = parse_symbol(symbol)
        url = f"{self.BASE_URL}{exchange}{code}"
        
        try:
            req = Request(url)
            req.add_header("User-Agent", "Mozilla/5.0")
            
            with urlopen(req, timeout=self.timeout) as response:
                content = response.read().decode("gbk", errors="ignore")
            
            return self._parse_response(content, symbol, market)
            
        except (URLError, HTTPError) as e:
            logger.warning(f"腾讯行情请求失败: {url}, 错误: {e}")
            raise ConnectionError(f"腾讯行情接口请求失败: {e}")
    
    def _parse_response(self, content: str, symbol: str, market: str) -> Dict[str, Any]:
        """解析腾讯行情接口返回数据"""
        # 格式: v_sz000001="1~平安银行~000001~10.52~..."
        match = re.search(r'v_\w+="([^"]*)"', content)
        if not match:
            raise ValueError(f"无法解析行情数据: {content[:100]}")
        
        data_str = match.group(1)
        if not data_str or data_str == "":
            raise ValueError(f"证券代码 {symbol} 无数据")
        
        fields = data_str.split("~")
        if len(fields) < 35:
            raise ValueError(f"数据字段不完整，期望至少35个字段，实际 {len(fields)}")
        
        raw_data = {}
        
        # 提取基础字段
        raw_data["name"] = fields[self.FIELD_INDEX["name"]] if len(fields) > 1 else None
        raw_data["symbol"] = fields[self.FIELD_INDEX["code"]] if len(fields) > 2 else symbol
        
        # 提取数值字段（安全转换）
        raw_data["price"] = self._safe_float(fields, self.FIELD_INDEX["price"])
        raw_data["prev_close"] = self._safe_float(fields, self.FIELD_INDEX["prev_close"])
        raw_data["open"] = self._safe_float(fields, self.FIELD_INDEX["open"])
        raw_data["high"] = self._safe_float(fields, self.FIELD_INDEX["high"])
        raw_data["low"] = self._safe_float(fields, self.FIELD_INDEX["low"])
        raw_data["change"] = self._safe_float(fields, self.FIELD_INDEX["change"])
        raw_data["change_pct"] = self._safe_float(fields, self.FIELD_INDEX["change_pct"])
        
        # 成交量和成交额
        raw_data["volume"] = self._safe_float(fields, self.FIELD_INDEX["volume"])
        amount_wan = self._safe_float(fields, self.FIELD_INDEX["amount_wan"])
        raw_data["amount"] = amount_wan * 10000 if amount_wan else None  # 万 -> 元
        
        # 时间戳
        if len(fields) > self.FIELD_INDEX["time_str"]:
            raw_data["asof"] = self._parse_time(fields[self.FIELD_INDEX["time_str"]])
        else:
            raw_data["asof"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return self.normalize_data(raw_data, market)
    
    def _safe_float(self, fields: List[str], index: int) -> Optional[float]:
        """安全转换浮点数"""
        try:
            if index < len(fields) and fields[index]:
                return float(fields[index])
        except (ValueError, TypeError):
            pass
        return None
    
    def _parse_time(self, time_str: str) -> str:
        """解析时间字符串（格式：20231225150355）"""
        try:
            if len(time_str) >= 14:
                dt = datetime.strptime(time_str[:14], "%Y%m%d%H%M%S")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================================
# AkShare Provider（备选数据源）
# ============================================================================
class AkShareProvider(MarketDataProvider):
    """
    AkShare 数据提供者
    
    特点：品类全（股票/ETF/指数/基金），社区常用
    风险：非官方数据源，需要安装 akshare 包
    """
    
    name: str = "akshare"
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._ak = None
    
    def _get_ak(self):
        """延迟导入 akshare"""
        if self._ak is None:
            try:
                import akshare as ak
                self._ak = ak
            except ImportError:
                raise ImportError(
                    "akshare 未安装，请运行: pip install akshare"
                )
        return self._ak
    
    def get_quote(self, symbol: str, market: str = "stock") -> Dict[str, Any]:
        """获取 AkShare 行情数据"""
        ak = self._get_ak()
        _, code = parse_symbol(symbol)
        
        try:
            if market == "index":
                return self._get_index_quote(ak, code)
            elif market == "fund":
                return self._get_fund_quote(ak, code)
            else:
                return self._get_stock_quote(ak, code)
        except Exception as e:
            logger.warning(f"AkShare 请求失败: {symbol}, 错误: {e}")
            raise ConnectionError(f"AkShare 接口请求失败: {e}")
    
    def _get_stock_quote(self, ak, code: str) -> Dict[str, Any]:
        """获取股票实时行情"""
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code]
        
        if row.empty:
            raise ValueError(f"未找到股票代码 {code}")
        
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
        return self.normalize_data(raw_data, "stock")
    
    def _get_index_quote(self, ak, code: str) -> Dict[str, Any]:
        """获取指数实时行情"""
        df = ak.stock_zh_index_spot_em()
        row = df[df["代码"] == code]
        
        if row.empty:
            raise ValueError(f"未找到指数代码 {code}")
        
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
        return self.normalize_data(raw_data, "index")
    
    def _get_fund_quote(self, ak, code: str) -> Dict[str, Any]:
        """获取基金/ETF实时行情"""
        # ETF 使用股票行情接口
        df = ak.fund_etf_spot_em()
        row = df[df["代码"] == code]
        
        if row.empty:
            # 尝试作为场外基金查询
            raise ValueError(f"未找到基金代码 {code}")
        
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
        return self.normalize_data(raw_data, "fund")
    
    def _safe_value(self, value) -> Optional[float]:
        """安全获取数值"""
        import pandas as pd
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


# ============================================================================
# Mock Provider（测试/兜底）
# ============================================================================
class MockProvider(MarketDataProvider):
    """Mock 数据提供者，用于测试和兜底"""
    
    name: str = "mock"
    
    # Mock数据
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
    
    def get_quote(self, symbol: str, market: str = "stock") -> Dict[str, Any]:
        """获取 Mock 数据"""
        _, code = parse_symbol(symbol)
        
        if code in self.MOCK_DATA:
            data = self.MOCK_DATA[code].copy()
            data["asof"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return self.normalize_data(data, market)
        else:
            raise ValueError(f"Mock数据中未找到证券代码 {code}")


# ============================================================================
# Provider 工厂
# ============================================================================
class ProviderFactory:
    """Provider 工厂类"""
    
    _providers = {
        "tencent": TencentProvider,
        "akshare": AkShareProvider,
        "mock": MockProvider,
    }
    
    _instances: Dict[str, MarketDataProvider] = {}
    
    @classmethod
    def get_provider(cls, name: str, **kwargs) -> MarketDataProvider:
        """获取 Provider 实例（单例模式）"""
        if name not in cls._instances:
            if name not in cls._providers:
                raise ValueError(f"未知的数据源: {name}")
            cls._instances[name] = cls._providers[name](**kwargs)
        return cls._instances[name]
    
    @classmethod
    def register_provider(cls, name: str, provider_class):
        """注册自定义 Provider"""
        cls._providers[name] = provider_class


# ============================================================================
# 限频缓存
# ============================================================================
class QuoteCache:
    """行情数据缓存（内存级，用于限频）"""
    
    def __init__(self, ttl_seconds: float = 2.0):
        self.ttl = ttl_seconds
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """获取缓存数据"""
        if key in self._cache:
            timestamp, data = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, data: Dict[str, Any]) -> None:
        """设置缓存数据"""
        self._cache[key] = (time.time(), data)
    
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()


# ============================================================================
# 行情查询工具
# ============================================================================
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
    
    def __init__(self):
        super().__init__()
        self._cache = QuoteCache()
        self._config = None
    
    @property
    def config(self):
        """获取配置（延迟加载）"""
        if self._config is None:
            settings = get_settings()
            self._config = settings.market_data
        return self._config
    
    def _get_provider_name(self, params: dict) -> str:
        """
        确定使用的数据源
        
        优先级：
        1. params.provider（显式指定）
        2. 环境变量 MEMFIN_MARKET_QUOTE_PROVIDER
        3. 配置文件 config.market_data.provider
        4. 默认值 'tencent'
        """
        # 1. 参数显式指定
        if params.get("provider"):
            return params["provider"]
        
        # 2. 环境变量
        env_provider = os.getenv("MEMFIN_MARKET_QUOTE_PROVIDER")
        if env_provider:
            return env_provider
        
        # 3. 配置文件
        return self.config.provider
    
    def _call_impl(self, params: dict, **kwargs) -> ToolResult:
        """查询行情"""
        symbol = params.get("symbol", "")
        market = params.get("market", "stock")
        fields = params.get("fields", [])
        
        if not symbol:
            return ToolResult(
                success=False,
                data=None,
                source="market_quote",
                errors=["缺少必要参数: symbol"],
            )
        
        # 检查缓存
        cache_key = f"{symbol}_{market}"
        cached_data = self._cache.get(cache_key)
        if cached_data:
            return self._build_result(cached_data, fields, "cache", [])
        
        # 获取数据源
        provider_name = self._get_provider_name(params)
        fallback_name = self.config.fallback_provider
        
        warnings = []
        data = None
        source = provider_name
        
        # 尝试主数据源
        try:
            provider = ProviderFactory.get_provider(
                provider_name, 
                timeout=self.config.timeout_seconds
            )
            data = provider.get_quote(symbol, market)
            source = provider_name
        except Exception as e:
            logger.warning(f"主数据源 {provider_name} 失败: {e}")
            warnings.append(f"主数据源({provider_name})请求失败: {str(e)}")
            
            # 尝试降级数据源
            if fallback_name and fallback_name != provider_name:
                try:
                    fallback = ProviderFactory.get_provider(fallback_name)
                    data = fallback.get_quote(symbol, market)
                    source = fallback_name
                    warnings.append(f"已降级到备选数据源: {fallback_name}")
                except Exception as fallback_error:
                    logger.error(f"降级数据源 {fallback_name} 也失败: {fallback_error}")
                    return ToolResult(
                        success=False,
                        data=None,
                        source=provider_name,
                        errors=[f"所有数据源均失败，最后错误: {str(fallback_error)}"],
                        warnings=warnings,
                    )
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    source=provider_name,
                    errors=[f"数据源请求失败: {str(e)}"],
                    warnings=warnings,
                )
        
        # 缓存数据
        if data:
            self._cache.set(cache_key, data)
        
        return self._build_result(data, fields, source, warnings)
    
    def _build_result(
        self, 
        data: Dict[str, Any], 
        fields: List[str], 
        source: str,
        warnings: List[str]
    ) -> ToolResult:
        """构建返回结果"""
        # 如果指定了字段，只返回指定字段
        if fields:
            filtered_data = {
                k: v for k, v in data.items() 
                if k in fields or k in ["name", "symbol", "type"]
            }
        else:
            filtered_data = data
        
        # 添加数据来源说明
        all_warnings = warnings.copy()
        if source != "mock":
            all_warnings.append("数据来自公开接口，口径可能变化，仅供参考")
        else:
            all_warnings.append("当前为模拟数据，仅供测试使用")
        
        # 解析 asof 时间
        asof = None
        if data.get("asof"):
            try:
                asof = datetime.strptime(data["asof"], "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                asof = datetime.now()
        else:
            asof = datetime.now()
        
        return ToolResult(
            success=True,
            data=filtered_data,
            source=source,
            asof=asof,
            warnings=all_warnings,
        )
