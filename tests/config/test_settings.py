"""配置测试"""

import pytest
import os
import json
import tempfile

from memfinrobot.config.settings import (
    Settings,
    LLMConfig,
    EmbeddingConfig,
    MemoryConfig,
    ComplianceConfig,
    get_settings,
    init_settings,
)


class TestLLMConfig:
    """LLMConfig测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = LLMConfig()
        
        assert config.model == "qwen-plus"
        assert config.temperature == 0.7
    
    def test_to_dict(self):
        """测试转换为字典"""
        config = LLMConfig(
            model="qwen-turbo",
            temperature=0.5,
        )
        
        data = config.to_dict()
        
        assert data["model"] == "qwen-turbo"
        assert data["generate_cfg"]["temperature"] == 0.5


class TestSettings:
    """Settings测试"""
    
    def test_default_settings(self):
        """测试默认配置"""
        settings = Settings()
        
        assert settings.llm is not None
        assert settings.embedding is not None
        assert settings.memory is not None
    
    def test_settings_from_file(self):
        """测试从文件加载配置"""
        config_data = {
            "llm": {
                "model": "test-model",
                "temperature": 0.3,
            },
            "memory": {
                "max_window_size": 20,
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            f.flush()
            
            settings = Settings.from_file(f.name)
            
            assert settings.llm.model == "test-model"
            assert settings.memory.max_window_size == 20
            
            os.unlink(f.name)
    
    def test_settings_to_dict(self):
        """测试转换为字典"""
        settings = Settings()
        data = settings.to_dict()
        
        assert "llm" in data
        assert "memory" in data


class TestGetSettings:
    """get_settings测试"""
    
    def test_get_settings_singleton(self):
        """测试单例模式"""
        settings1 = get_settings()
        settings2 = get_settings()
        
        assert settings1 is settings2
