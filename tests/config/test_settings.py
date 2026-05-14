"""配置测试"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from memfinrobot.config.settings import (
    Settings,
    LLMConfig,
    get_settings,
    init_settings,
)


class TestLLMConfig:
    """LLMConfig测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = LLMConfig()
        
        assert config.model == "qwen3.5-plus"
        assert config.temperature == 0.7
    
    def test_to_dict(self):
        """测试转换为字典"""
        config = LLMConfig(
            model="qwen-turbo",
            model_type="oai",
            model_server="https://dashscope.aliyuncs.com/api/v1",
            use_raw_api=True,
            temperature=0.5,
            extra_body={"enable_thinking": False},
        )
        
        data = config.to_dict()
        
        assert data["model"] == "qwen-turbo"
        assert data["model_type"] == "oai"
        assert data["model_server"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert data["generate_cfg"]["temperature"] == 0.5
        assert data["generate_cfg"]["use_raw_api"] is True
        assert data["generate_cfg"]["extra_body"] == {"enable_thinking": False}

    def test_to_dict_native_dashscope_url(self):
        """测试原生 DashScope URL 归一化"""
        with patch.dict(os.environ, {"DASHSCOPE_HTTP_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1"}):
            config = LLMConfig(
                model="qwen3.5-plus",
                model_server="dashscope",
            )

            data = config.to_dict()

            assert data["base_http_api_url"] == "https://dashscope.aliyuncs.com/api/v1"


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
        config_text = """
        {
          // line comment
          "llm": {
            "model": "test-model",
            "temperature": 0.3
          },
          /* block comment */
          "memory": {
            "max_window_size": 20
          }
        }
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(config_text)
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

    def test_init_settings_loads_project_config_by_default(self):
        """测试默认自动加载项目根目录配置"""
        project_config = Path(__file__).resolve().parents[2] / "config.json"

        with patch.dict(os.environ, {}, clear=False):
            settings = init_settings()

        assert settings.source_config_path == str(project_config.resolve())
