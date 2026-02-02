"""pytest配置和共享fixtures"""

import os
import sys
import pytest
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from memfinrobot.config.settings import Settings, LLMConfig, MemoryConfig, EmbeddingConfig
from memfinrobot.memory.schemas import (
    MemoryItem, 
    UserProfile, 
    SessionState,
    RiskLevel,
    InvestmentHorizon,
)


@pytest.fixture
def test_settings():
    """测试用配置"""
    settings = Settings()
    settings.llm = LLMConfig(
        model="mock-model",
        model_server="mock",
        api_key="test-key",
    )
    settings.embedding = EmbeddingConfig(
        model_path="",  # 使用mock
        device="cpu",
    )
    settings.memory = MemoryConfig(
        storage_path=str(project_root / "tests" / "test_data" / "memory"),
        storage_backend="file",
    )
    return settings


@pytest.fixture
def sample_memory_item():
    """示例记忆条目"""
    return MemoryItem(
        id="test-memory-001",
        content="用户询问了沪深300ETF的费率",
        hierarchical_content="用户关注ETF费用 | [context] | 用户询问了沪深300ETF的费率",
        turn_index=1,
        session_id="test-session-001",
        user_id="test-user-001",
        topics=["ETF", "费用"],
        entities=["510300"],
    )


@pytest.fixture
def sample_user_profile():
    """示例用户画像"""
    return UserProfile(
        user_id="test-user-001",
        risk_level=RiskLevel.MEDIUM,
        risk_level_confidence=0.8,
        investment_horizon=InvestmentHorizon.MEDIUM,
        preferred_topics=["指数基金", "ETF"],
    )


@pytest.fixture
def sample_session_state(sample_user_profile):
    """示例会话状态"""
    session = SessionState(
        session_id="test-session-001",
        user_id="test-user-001",
        profile=sample_user_profile,
    )
    session.add_turn("user", "你好，我想了解一下沪深300ETF")
    session.add_turn("assistant", "您好！沪深300ETF是跟踪沪深300指数的交易型开放式基金...")
    return session


@pytest.fixture
def sample_dialogue_history():
    """示例对话历史"""
    return [
        "用户: 你好，我想了解一下基金投资",
        "助手: 您好！基金是一种间接投资方式...",
        "用户: 我的风险承受能力比较低，适合什么基金？",
        "助手: 对于低风险偏好的投资者，建议关注债券基金和货币基金...",
        "用户: 那债券基金的收益怎么样？",
    ]


@pytest.fixture(scope="session")
def test_data_dir():
    """测试数据目录"""
    data_dir = project_root / "tests" / "test_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
