"""Prompt template tests."""

from memfinrobot.prompts.templates import render_system_prompt


def test_render_system_prompt_includes_current_time() -> None:
    prompt = render_system_prompt("2026-05-14 15:30:00 CST")

    assert "2026-05-14 15:30:00 CST" in prompt
    assert "## 当前时间" in prompt
