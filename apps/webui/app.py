"""Streamlit demo for MemFinRobot."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.webui.observer import DemoTurnObserver
from memfinrobot.agent.memfin_agent import MemFinFnCallAgent
from memfinrobot.config.settings import Settings, init_settings
from memfinrobot.tools import get_default_tools


PAGE_TITLE = "MemFinRobot Demo"
WELCOME_MESSAGE = (
    "你好，我是 MemFinRobot。你可以直接和我聊投资问题，我会在右侧实时展示本轮的"
    "记忆召回、画像更新、工具调用和合规轨迹。"
)
STARTER_PROMPTS = [
    "我风险偏好比较稳健，帮我看看沪深300ETF适不适合作为底仓？",
    "最近红利基金为什么又被很多人提起？",
    "如果我希望最大回撤控制在10%以内，资产配置应该怎么想？",
]


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at 8% 12%, rgba(198, 145, 72, 0.18), transparent 24%),
                radial-gradient(circle at 92% 10%, rgba(44, 82, 130, 0.14), transparent 20%),
                radial-gradient(circle at 60% 100%, rgba(13, 148, 136, 0.10), transparent 28%),
                linear-gradient(180deg, #f8f4ee 0%, #edf2f7 52%, #e9eff5 100%);
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1520px;
        }
        .hero-card, .panel-card {
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.90), rgba(255, 255, 255, 0.78));
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 22px;
            box-shadow: 0 20px 55px rgba(15, 23, 42, 0.08);
            backdrop-filter: blur(14px);
        }
        .hero-card {
            padding: 1.45rem 1.7rem;
            margin-bottom: 1rem;
            position: relative;
            overflow: hidden;
        }
        .hero-card::after {
            content: "";
            position: absolute;
            inset: auto -10% -55% 45%;
            height: 220px;
            background: radial-gradient(circle, rgba(194, 151, 82, 0.18), transparent 62%);
            pointer-events: none;
        }
        .panel-card {
            padding: 1.05rem 1.15rem 0.4rem 1.15rem;
        }
        .eyebrow {
            color: #9a6700;
            font-size: 0.82rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.35rem;
        }
        .hero-title {
            font-size: 2.15rem;
            font-weight: 800;
            color: #17212f;
            margin-bottom: 0.45rem;
        }
        .hero-subtitle {
            color: #475569;
            line-height: 1.65;
            margin-bottom: 0;
            max-width: 920px;
        }
        .section-title {
            font-size: 1.02rem;
            font-weight: 700;
            color: #17212f;
            margin: 0.1rem 0 0.75rem 0;
        }
        .small-muted {
            color: #64748b;
            font-size: 0.9rem;
        }
        .trace-chip {
            display: inline-block;
            padding: 0.24rem 0.62rem;
            margin: 0.1rem 0.4rem 0.1rem 0;
            border-radius: 999px;
            background: linear-gradient(180deg, #fff7ed, #ffedd5);
            color: #9a3412;
            font-size: 0.78rem;
            font-weight: 600;
            border: 1px solid rgba(249, 115, 22, 0.15);
        }
        .memory-item {
            padding: 0.9rem 0.95rem;
            margin-bottom: 0.8rem;
            border-radius: 16px;
            background: linear-gradient(180deg, rgba(255, 248, 240, 0.72), rgba(248, 250, 252, 0.96));
            border: 1px solid rgba(191, 219, 254, 0.4);
        }
        .memory-meta {
            color: #475569;
            font-size: 0.8rem;
            margin-bottom: 0.4rem;
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(23, 33, 47, 0.95), rgba(31, 41, 55, 0.92));
            border-right: 1px solid rgba(255, 255, 255, 0.06);
        }
        [data-testid="stSidebar"] * {
            color: #e5edf6;
        }
        [data-testid="stSidebar"] .stButton button {
            border-radius: 14px;
            border: 1px solid rgba(255, 255, 255, 0.12);
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.10), rgba(255, 255, 255, 0.06));
            color: #f8fafc;
        }
        [data-testid="stSidebar"] .stTextInput input {
            background: rgba(255, 255, 255, 0.08);
            color: #f8fafc;
            border-radius: 12px;
        }
        [data-testid="stChatMessage"] {
            border-radius: 18px;
        }
        [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
            background: linear-gradient(180deg, rgba(37, 99, 235, 0.10), rgba(59, 130, 246, 0.05));
            border: 1px solid rgba(96, 165, 250, 0.18);
        }
        [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
            background: linear-gradient(180deg, rgba(255, 250, 240, 0.92), rgba(255, 255, 255, 0.74));
            border: 1px solid rgba(194, 151, 82, 0.14);
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.35rem;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid rgba(148, 163, 184, 0.18);
            padding-left: 0.95rem;
            padding-right: 0.95rem;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(180deg, #1f3a5f, #2c5282);
            color: white;
        }
        .stMetric {
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.76), rgba(248, 250, 252, 0.92));
            border: 1px solid rgba(148, 163, 184, 0.16);
            border-radius: 16px;
            padding: 0.35rem 0.7rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def build_agent(settings: Settings, observer: DemoTurnObserver) -> MemFinFnCallAgent:
    return MemFinFnCallAgent(
        function_list=get_default_tools(settings=settings),
        llm=settings.llm.to_dict(),
        settings=settings,
        observer=observer,
    )


def new_demo_identity() -> Dict[str, str]:
    suffix = uuid.uuid4().hex[:8]
    return {
        "user_id": f"demo_user_{suffix}",
        "session_id": f"demo_session_{suffix}",
    }


def initialize_runtime(config_path: Optional[str]) -> None:
    settings = init_settings(config_path)
    observer = DemoTurnObserver()
    agent = build_agent(settings, observer)
    identity = new_demo_identity()
    st.session_state.runtime = {
        "config_path": config_path,
        "settings": settings,
        "agent": agent,
        "observer": observer,
        "user_id": identity["user_id"],
        "session_id": identity["session_id"],
        "messages": [{"role": "assistant", "content": WELCOME_MESSAGE}],
        "turn_records": [],
        "active_turn_id": None,
    }


def ensure_runtime() -> None:
    config_path = st.session_state.get("config_path_input") or "config.json"
    runtime = st.session_state.get("runtime")
    if runtime is None or runtime.get("config_path") != config_path:
        initialize_runtime(config_path)


def reset_demo_session() -> None:
    runtime = st.session_state["runtime"]
    identity = new_demo_identity()
    runtime["observer"].reset()
    runtime["user_id"] = identity["user_id"]
    runtime["session_id"] = identity["session_id"]
    runtime["messages"] = [{"role": "assistant", "content": WELCOME_MESSAGE}]
    runtime["turn_records"] = []
    runtime["active_turn_id"] = None


def metrics_summary(runtime: Dict[str, Any]) -> Dict[str, Any]:
    turn_records = runtime["turn_records"]
    current_user_id = runtime["user_id"]
    memories = runtime["agent"].memory_manager.memory_writer.get_all_memories(user_id=current_user_id)
    total_tools = sum(len(record.get("tools") or []) for record in turn_records)
    latest_latency_ms = 0.0
    if turn_records:
        latest_latency_ms = float(
            (turn_records[-1].get("turn_end") or {}).get("latency_ms", 0.0)
        )
    return {
        "turns": len(turn_records),
        "memories": len(memories),
        "tool_calls": total_tools,
        "latest_latency_ms": latest_latency_ms,
    }


def shorten(text: str, max_len: int = 220) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def render_sidebar() -> None:
    runtime = st.session_state["runtime"]
    settings = runtime["settings"]
    summary = metrics_summary(runtime)

    with st.sidebar:
        st.markdown("### 控制台")
        st.text_input("配置文件", key="config_path_input")
        col1, col2 = st.columns(2)
        if col1.button("重新加载配置", use_container_width=True):
            initialize_runtime(st.session_state.get("config_path_input") or "config.json")
            st.rerun()
        if col2.button("新建演示会话", use_container_width=True):
            reset_demo_session()
            st.rerun()

        st.caption(f"Python: `{sys.executable}`")
        st.caption(f"配置来源: `{settings.source_config_path or '<defaults>'}`")

        st.markdown("---")
        st.markdown("### 当前状态")
        st.markdown(f"- 用户ID：`{runtime['user_id']}`")
        st.markdown(f"- 会话ID：`{runtime['session_id']}`")
        st.markdown(f"- 对话轮数：`{summary['turns']}`")
        st.markdown(f"- 长期记忆数：`{summary['memories']}`")
        st.markdown(f"- 工具调用数：`{summary['tool_calls']}`")
        st.markdown(f"- 最近耗时：`{summary['latest_latency_ms']:.0f} ms`")

        st.markdown("---")
        st.markdown("### 示例问题")
        for idx, prompt in enumerate(STARTER_PROMPTS):
            if st.button(prompt, key=f"starter_{idx}", use_container_width=True):
                st.session_state.pending_prompt = prompt


def render_header() -> None:
    st.markdown(
        """
        <div class="hero-card">
          <div class="eyebrow">Memory-Augmented Wealth Copilot</div>
          <div class="hero-title">MemFinRobot:你的长期陪伴投资咨询助手</div>
          <p class="hero-subtitle">
            左侧完成用户与 MemFinRobot 的自然对话，右侧实时展开本轮行为轨迹：
            包括短期上下文、长期记忆召回、用户画像、工具调用和合规处理结果。
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chat_panel(runtime: Dict[str, Any]) -> None:
    # st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">对话区</div>', unsafe_allow_html=True)
    for message in runtime["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    st.markdown("</div>", unsafe_allow_html=True)


def render_recall_section(record: Dict[str, Any]) -> None:
    recall = record.get("recall") or {}
    items = recall.get("items") or []
    short_term_turns = recall.get("short_term_turns") or []

    stat_cols = st.columns(4)
    stat_cols[0].metric("召回条目", len(items))
    stat_cols[1].metric("工具调用", len(record.get("tools") or []))
    stat_cols[2].metric("上下文Token", int(recall.get("token_count") or 0))
    stat_cols[3].metric("耗时", f"{float((record.get('turn_end') or {}).get('latency_ms', 0.0)):.0f} ms")

    if short_term_turns:
        with st.expander("短期对话记忆", expanded=True):
            for turn in short_term_turns:
                st.markdown(f"**{turn.get('role', 'unknown')}**：{turn.get('content', '')}")
    else:
        st.info("本轮没有可展示的短期对话记忆。")

    profile_context = recall.get("profile_context", "")
    if profile_context:
        with st.expander("画像记忆", expanded=True):
            st.markdown(profile_context)

    if items:
        st.markdown("**长期记忆召回**")
        for item in items:
            st.markdown(
                f"""
                <div class="memory-item">
                  <div class="memory-meta">Top {item.get("rank")} · 来源 {item.get("source") or "semantic"} · 分数 {float(item.get("score") or 0.0):.3f} · turn {item.get("turn_index")}</div>
                  <div>{item.get("content") or "暂无内容"}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("本轮未召回长期记忆。")

    packed_context = recall.get("packed_context", "")
    if packed_context:
        with st.expander("注入到模型的完整上下文"):
            st.code(packed_context, language="markdown")


def render_tools_section(record: Dict[str, Any]) -> None:
    tools = record.get("tools") or []
    if not tools:
        st.info("本轮没有工具调用。")
        return

    for idx, tool in enumerate(tools, start=1):
        with st.expander(f"{idx}. {tool.get('tool_name') or 'unknown'} · {float(tool.get('latency_ms') or 0.0):.0f} ms", expanded=(idx == 1)):
            st.markdown("**参数**")
            st.json(tool.get("args") or {})
            st.markdown("**结果摘要**")
            st.code(tool.get("result_excerpt") or "", language="json")


def render_compliance_section(record: Dict[str, Any]) -> None:
    compliance = record.get("compliance") or {}
    if not compliance:
        st.info("本轮没有额外的合规轨迹。")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("是否合规", "是" if compliance.get("is_compliant", True) else "否")
    col2.metric("有无改写", "是" if compliance.get("needs_modification") else "否")
    col3.metric("补充风险提示", "是" if compliance.get("risk_disclaimer_added") else "否")

    if compliance.get("violations"):
        st.markdown("**违规/提醒项**")
        st.json(compliance["violations"])

    if compliance.get("suitability_warning"):
        st.markdown("**适当性提醒**")
        st.warning(compliance["suitability_warning"])


def render_profile_panel(runtime: Dict[str, Any], record: Optional[Dict[str, Any]]) -> None:
    profile = runtime["agent"].get_user_profile(runtime["user_id"]).to_dict()
    snapshot = (record or {}).get("profile_snapshot") or profile

    st.markdown("**当前画像快照**")
    st.json(snapshot)

    chips: List[str] = []
    if profile.get("risk_level") and profile["risk_level"] != "unknown":
        chips.append(f"风险偏好 {profile['risk_level']}")
    if profile.get("investment_horizon") and profile["investment_horizon"] != "unknown":
        chips.append(f"投资期限 {profile['investment_horizon']}")
    if profile.get("liquidity_need") and profile["liquidity_need"] != "unknown":
        chips.append(f"流动性 {profile['liquidity_need']}")
    if profile.get("investment_goal") and profile["investment_goal"] != "unknown":
        chips.append(f"目标 {profile['investment_goal']}")
    if profile.get("preferred_topics"):
        chips.extend([f"偏好 {item}" for item in profile["preferred_topics"]])
    if profile.get("forbidden_assets"):
        chips.extend([f"规避 {item}" for item in profile["forbidden_assets"]])

    if chips:
        st.markdown("".join(f'<span class="trace-chip">{chip}</span>' for chip in chips), unsafe_allow_html=True)
    else:
        st.caption("用户画像还在建立中。")


def render_memory_bank(runtime: Dict[str, Any]) -> None:
    memories = runtime["agent"].memory_manager.memory_writer.get_all_memories(user_id=runtime["user_id"])
    memories = sorted(memories, key=lambda item: (item.turn_index, item.timestamp), reverse=True)
    if not memories:
        st.info("当前用户还没有长期记忆。")
        return

    st.caption(f"共 {len(memories)} 条长期记忆")
    for memory in memories:
        with st.expander(f"turn {memory.turn_index} · {shorten(memory.content, 48)}", expanded=False):
            meta = {
                "id": memory.id,
                "session_id": memory.session_id,
                "topics": memory.topics,
                "entities": memory.entities,
                "source_indices": memory.source_indices,
                "timestamp": memory.timestamp.isoformat() if memory.timestamp else None,
            }
            st.json(meta)
            st.markdown("**原始记忆**")
            st.write(memory.content)
            if memory.hierarchical_content:
                st.markdown("**分层表征**")
                st.code(memory.hierarchical_content, language="markdown")


def render_trace_panel(runtime: Dict[str, Any]) -> None:
    records = runtime["turn_records"]
    # st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">行为轨迹</div>', unsafe_allow_html=True)

    if not records:
        st.markdown(
            '<p class="small-muted">发送第一条消息后，这里会开始展示召回记忆、画像快照、工具调用和合规处理。</p>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    turn_ids = [record["turn_pair_id"] for record in records]
    default_turn_id = runtime.get("active_turn_id") or turn_ids[-1]
    selected_turn_id = st.selectbox(
        "查看轮次",
        options=turn_ids,
        index=turn_ids.index(default_turn_id) if default_turn_id in turn_ids else len(turn_ids) - 1,
        format_func=lambda value: f"第 {value} 轮",
    )
    runtime["active_turn_id"] = selected_turn_id
    record = next(item for item in records if item["turn_pair_id"] == selected_turn_id)

    tabs = st.tabs(["召回与推理", "工具调用", "用户画像", "长期记忆库", "合规结果"])
    with tabs[0]:
        render_recall_section(record)
    with tabs[1]:
        render_tools_section(record)
    with tabs[2]:
        render_profile_panel(runtime, record)
    with tabs[3]:
        render_memory_bank(runtime)
    with tabs[4]:
        render_compliance_section(record)

    st.markdown("</div>", unsafe_allow_html=True)


def handle_prompt(prompt: str) -> None:
    runtime = st.session_state["runtime"]
    runtime["messages"].append({"role": "user", "content": prompt})

    with st.spinner("MemFinRobot 正在分析问题、召回记忆并组织回答..."):
        response = runtime["agent"].handle_turn(
            user_message=prompt,
            session_id=runtime["session_id"],
            user_id=runtime["user_id"],
        )

    runtime["messages"].append({"role": "assistant", "content": response})
    latest_turn_id = runtime["observer"].latest_turn_id()
    latest_payload = runtime["observer"].get_turn_payload(latest_turn_id)
    latest_payload["turn_pair_id"] = latest_turn_id
    latest_payload["user_text"] = prompt
    latest_payload["assistant_text"] = response
    runtime["turn_records"].append(latest_payload)
    runtime["active_turn_id"] = latest_turn_id


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, layout="wide", page_icon=":material/monitoring:")
    inject_styles()

    if "config_path_input" not in st.session_state:
        st.session_state.config_path_input = "config.json"

    ensure_runtime()
    render_sidebar()
    render_header()

    runtime = st.session_state["runtime"]
    chat_col, trace_col = st.columns([1.75, 0.8], gap="large")
    with chat_col:
        render_chat_panel(runtime)
    with trace_col:
        render_trace_panel(runtime)

    pending_prompt = st.session_state.pop("pending_prompt", None)
    prompt = pending_prompt or st.chat_input("例如：帮我分析一下 510300 是否适合作为稳健配置的一部分")
    if prompt:
        handle_prompt(prompt)
        st.rerun()


if __name__ == "__main__":
    main()
