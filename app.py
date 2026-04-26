"""
Gemini Chat - 主对话页面
功能：
- 左侧多对话管理（创建/切换/重命名/删除）
- 模型动态选择
- 多模态输入（图片/文件/PDF）
- 流式输出 + token 用量显示
- 复制 / 重新生成
- Prompt 模板库
- URL 自动抓取
- 导出对话（MD / JSON）
- 访问密码保护
- Markdown 增强（代码高亮、LaTeX、Mermaid）
"""
import streamlit as st

from core.config import (
    APP_NAME, APP_ICON, APP_DESCRIPTION, estimate_cost,
)
from core.auth import require_auth
from core.gemini import (
    get_client, fetch_available_models, files_to_parts,
    stream_chat, auto_title_for,
)
from core import db
from core.url_fetcher import augment_prompt_with_urls
from core.export import export_markdown, export_json
from core.templates import get_template_names, get_template_prompt
from core.markdown_render import render_enhanced_markdown


# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title=APP_NAME,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 自定义 CSS（暗色支持、移动端、紧凑布局）
# ============================================================
st.markdown("""
<style>
/* 紧凑侧边栏 */
section[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem;
}
/* 对话列表项 */
.conv-item {
    padding: 6px 10px;
    border-radius: 8px;
    margin-bottom: 2px;
    cursor: pointer;
    font-size: 0.92em;
    transition: background 0.15s;
}
.conv-item:hover { background: rgba(125, 125, 125, 0.12); }
.conv-active {
    background: rgba(66, 133, 244, 0.18);
    border-left: 3px solid #4285F4;
}
/* 助手消息小工具行 */
.msg-toolbar {
    display: flex;
    gap: 6px;
    margin-top: -10px;
    margin-bottom: 8px;
    opacity: 0.55;
    font-size: 0.78em;
}
.msg-toolbar:hover { opacity: 1; }
/* 移动端 */
@media (max-width: 720px) {
    .block-container { padding: 1rem 0.5rem; }
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# 鉴权
# ============================================================
require_auth()

# 触发 client 初始化（如缺 key 会 stop）
get_client()

# ============================================================
# 会话状态初始化
# ============================================================
def init_state():
    if "current_conv_id" not in st.session_state:
        # 没有当前对话，看数据库里有没有
        convs = db.list_conversations(limit=1)
        if convs:
            st.session_state.current_conv_id = convs[0]["id"]
        else:
            st.session_state.current_conv_id = None
    if "regenerate_msg_id" not in st.session_state:
        st.session_state.regenerate_msg_id = None
    if "pending_input" not in st.session_state:
        st.session_state.pending_input = None
    if "auto_fetch_url" not in st.session_state:
        st.session_state.auto_fetch_url = False


init_state()


# ============================================================
# 工具函数
# ============================================================
def ensure_current_conv(model_id: str = "", system_prompt: str = "") -> int:
    """确保有一个当前对话，如果没有就创建"""
    if st.session_state.current_conv_id is None:
        cid = db.create_conversation(
            title="新对话",
            model_id=model_id,
            system_prompt=system_prompt,
        )
        st.session_state.current_conv_id = cid
    return st.session_state.current_conv_id


def switch_to_conv(conv_id: int | None):
    st.session_state.current_conv_id = conv_id
    st.session_state.regenerate_msg_id = None
    st.session_state.pending_input = None
    st.rerun()


# ============================================================
# 侧边栏
# ============================================================
with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_NAME}")
    st.caption(APP_DESCRIPTION)

    # ----- 新对话按钮 -----
    if st.button("➕ 新对话", use_container_width=True, type="primary"):
        switch_to_conv(None)

    st.divider()

    # ----- 对话列表 -----
    st.markdown("**📂 历史对话**")
    convs = db.list_conversations(limit=50)
    if not convs:
        st.caption("还没有对话，发送一条消息开始吧。")
    else:
        cur_id = st.session_state.current_conv_id
        for c in convs:
            is_active = c["id"] == cur_id
            col_a, col_b = st.columns([5, 1])
            with col_a:
                label = c["title"][:24] + ("…" if len(c["title"]) > 24 else "")
                if st.button(
                    f"{'▶ ' if is_active else '  '}{label}",
                    key=f"conv_{c['id']}",
                    use_container_width=True,
                    help=f"{c['msg_count']} 条消息",
                ):
                    if not is_active:
                        switch_to_conv(c["id"])
            with col_b:
                if st.button("🗑️", key=f"del_{c['id']}", help="删除"):
                    db.delete_conversation(c["id"])
                    if is_active:
                        st.session_state.current_conv_id = None
                    st.rerun()

    st.divider()

    # ----- 模型 & 参数 -----
    st.markdown("**⚙️ 模型设置**")

    col_a, col_b = st.columns([4, 1])
    with col_b:
        if st.button("🔄", help="刷新模型列表"):
            fetch_available_models.clear()
            st.rerun()

    available_models = fetch_available_models()

    # 当前对话用的模型，没有就用第一个
    current_conv = (
        db.get_conversation(st.session_state.current_conv_id)
        if st.session_state.current_conv_id else None
    )
    default_model_id = (
        current_conv["model_id"] if current_conv and current_conv["model_id"]
        in available_models.values()
        else list(available_models.values())[0]
    )
    default_idx = list(available_models.values()).index(default_model_id) \
        if default_model_id in available_models.values() else 0

    model_display_name = st.selectbox(
        "模型",
        options=list(available_models.keys()),
        index=default_idx,
    )
    model_id = available_models[model_display_name]
    st.caption(f"`{model_id}`")

    # ----- Prompt 模板 -----
    st.markdown("**🎭 Prompt 模板**")
    template_names = get_template_names()
    selected_template = st.selectbox(
        "角色",
        options=template_names,
        index=0,
        label_visibility="collapsed",
    )
    template_prompt = get_template_prompt(selected_template)

    # 当前对话已存的 system_prompt 优先；否则用模板
    saved_sp = current_conv["system_prompt"] if current_conv else ""
    default_sp = saved_sp if saved_sp else template_prompt

    system_prompt = st.text_area(
        "System Prompt",
        value=default_sp,
        height=120,
        help="角色指令，可以手动改",
    )

    # ----- 参数 -----
    with st.expander("🎛️ 高级参数"):
        temperature = st.slider("Temperature", 0.0, 2.0, 1.0, 0.1)
        max_tokens = st.number_input("Max Output Tokens", 256, 65536, 8192, 256)
        st.session_state.auto_fetch_url = st.checkbox(
            "自动抓取消息中的 URL",
            value=st.session_state.auto_fetch_url,
            help="检测到 https://... 时自动获取网页内容作为上下文",
        )

    st.divider()

    # ----- Token 用量 -----
    if st.session_state.current_conv_id:
        in_tok, out_tok, cost = db.get_total_token_usage(
            st.session_state.current_conv_id
        )
        if in_tok or out_tok:
            st.markdown("**📊 当前对话用量**")
            col_x, col_y = st.columns(2)
            col_x.metric("Input Tokens", f"{in_tok:,}")
            col_y.metric("Output Tokens", f"{out_tok:,}")
            st.caption(f"💰 估算成本：**${cost:.4f}**")
            st.divider()

    # ----- 导出 -----
    if st.session_state.current_conv_id and current_conv:
        st.markdown("**📤 导出对话**")
        msgs_for_export = db.get_messages(st.session_state.current_conv_id)
        if msgs_for_export:
            md_content = export_markdown(current_conv, msgs_for_export)
            json_content = export_json(current_conv, msgs_for_export)
            safe_title = "".join(
                c if c.isalnum() or c in "._- " else "_"
                for c in (current_conv["title"] or "chat")
            )[:40]

            col_e1, col_e2 = st.columns(2)
            col_e1.download_button(
                "📝 Markdown",
                md_content,
                file_name=f"{safe_title}.md",
                mime="text/markdown",
                use_container_width=True,
            )
            col_e2.download_button(
                "📦 JSON",
                json_content,
                file_name=f"{safe_title}.json",
                mime="application/json",
                use_container_width=True,
            )

    st.divider()

    # ----- 状态 -----
    backend_label = (
        "☁️ Supabase（云端持久化）"
        if db.BACKEND == "supabase"
        else "💾 SQLite（本地，重启会丢）"
    )
    st.caption(f"存储：{backend_label}")

    # ----- 关于 -----
    with st.expander("ℹ️ 关于"):
        st.markdown(
            f"- 多对话持久化（{db.BACKEND}）\n"
            "- 多模型动态加载\n"
            "- 多模态输入（图片/PDF/音视频）\n"
            "- URL 自动抓取\n"
            "- 流式输出 + token 统计\n"
            "- Markdown / LaTeX / Mermaid 增强\n"
            "- 导出 MD / JSON"
        )


# ============================================================
# 主区域 - 标题
# ============================================================
if current_conv:
    title_col, edit_col = st.columns([10, 1])
    with title_col:
        st.markdown(f"### {current_conv['title']}")
    with edit_col:
        if st.button("✏️", help="重命名对话"):
            st.session_state[f"editing_title_{current_conv['id']}"] = True

    edit_key = f"editing_title_{current_conv['id']}"
    if st.session_state.get(edit_key):
        new_title = st.text_input(
            "新标题", value=current_conv["title"], key=f"new_title_input_{current_conv['id']}"
        )
        c1, c2 = st.columns([1, 1])
        if c1.button("✅ 保存", use_container_width=True):
            db.rename_conversation(current_conv["id"], new_title or "未命名")
            st.session_state[edit_key] = False
            st.rerun()
        if c2.button("取消", use_container_width=True):
            st.session_state[edit_key] = False
            st.rerun()
else:
    st.markdown(f"### {APP_ICON} 开始新对话")
    st.caption(f"当前模型：**{model_display_name}**")

# ============================================================
# 文件上传
# ============================================================
uploaded_files = st.file_uploader(
    "📎 上传图片或文件（可选）",
    type=[
        "png", "jpg", "jpeg", "webp", "gif", "heic", "heif",
        "pdf", "txt", "md", "csv", "json", "xml", "html",
        "py", "js", "ts", "java", "cpp", "c", "go", "rs", "rb", "php",
        "css", "sql", "sh", "yaml", "yml", "toml",
        "mp3", "wav", "m4a", "flac", "ogg", "aac",
        "mp4", "mov", "avi", "mkv", "webm", "mpeg",
    ],
    accept_multiple_files=True,
    label_visibility="collapsed",
    help="图片直接 inline；其他大文件走 File API",
)

# ============================================================
# 渲染历史消息
# ============================================================
def render_message(msg: dict, idx: int, total: int):
    """渲染单条消息，包含工具栏"""
    role = msg["role"]
    meta = msg.get("meta") or {}

    with st.chat_message(role):
        # 用户消息：先显示附件
        if role == "user":
            for img_bytes in meta.get("images", []):
                if isinstance(img_bytes, (bytes, bytearray)):
                    st.image(img_bytes, width=320)
            for fname in meta.get("file_names", []):
                st.caption(f"📎 `{fname}`")
            for url in meta.get("fetched_urls", []):
                st.caption(f"🔗 已抓取：{url}")

        # 内容（增强 markdown）
        render_enhanced_markdown(msg["content"])

        # 助手消息底部工具栏
        if role == "assistant":
            cols = st.columns([1, 1, 1, 7])
            # 复制
            with cols[0]:
                st.button(
                    "📋",
                    key=f"copy_{msg['id']}",
                    help="复制内容到剪贴板（点击后从下方文本框复制）",
                    on_click=lambda mid=msg["id"]: st.session_state.update(
                        {f"show_copy_{mid}": True}
                    ),
                )
            # 重新生成（只对最后一条助手消息）
            with cols[1]:
                is_last_assistant = (idx == total - 1)
                if is_last_assistant:
                    if st.button("🔄", key=f"regen_{msg['id']}", help="重新生成"):
                        st.session_state.regenerate_msg_id = msg["id"]
                        st.rerun()
            # token 信息
            in_tok = meta.get("input_tokens", 0)
            out_tok = meta.get("output_tokens", 0)
            if in_tok or out_tok:
                with cols[3]:
                    cost = meta.get("cost", 0.0)
                    st.caption(
                        f"📊 in={in_tok:,} · out={out_tok:,} · ${cost:.4f}"
                    )

            # 复制弹出文本框
            if st.session_state.get(f"show_copy_{msg['id']}"):
                st.text_area(
                    "复制以下内容",
                    value=msg["content"],
                    height=120,
                    key=f"copy_area_{msg['id']}",
                )


# 加载并渲染当前对话
if st.session_state.current_conv_id:
    messages = db.get_messages(st.session_state.current_conv_id)
else:
    messages = []

for i, m in enumerate(messages):
    render_message(m, i, len(messages))


# ============================================================
# 处理重新生成
# ============================================================
if st.session_state.regenerate_msg_id is not None:
    target_id = st.session_state.regenerate_msg_id
    st.session_state.regenerate_msg_id = None

    # 找到要重新生成的助手消息，删掉它
    target_msg = next((m for m in messages if m["id"] == target_id), None)
    if target_msg and target_msg["role"] == "assistant":
        db.delete_message(target_id)
        # 重新加载
        messages = db.get_messages(st.session_state.current_conv_id)
        st.session_state.pending_input = "__regenerate__"
        st.rerun()

# ============================================================
# 用户输入
# ============================================================
prompt = st.chat_input("输入你的问题…")

# 是重新生成？
is_regenerate = (st.session_state.pending_input == "__regenerate__")
if is_regenerate:
    st.session_state.pending_input = None
    prompt = None  # 不要新消息，直接用历史

# ============================================================
# 处理发送
# ============================================================
if prompt or is_regenerate:
    # 1) 确保有当前对话
    conv_id = ensure_current_conv(model_id=model_id, system_prompt=system_prompt)
    # 同步对话的模型和 system prompt 设置
    db.update_conversation_settings(
        conv_id, model_id=model_id, system_prompt=system_prompt
    )

    # 2) 处理用户消息（重新生成时跳过）
    if prompt:
        # URL 自动抓取
        fetched_urls = []
        final_prompt = prompt
        if st.session_state.auto_fetch_url:
            with st.spinner("抓取 URL 内容…"):
                final_prompt, fetched_urls = augment_prompt_with_urls(prompt)

        # 处理上传文件
        with st.spinner("处理上传文件…" if uploaded_files else ""):
            file_parts, image_previews, file_names = files_to_parts(
                uploaded_files
            )

        # 写入用户消息
        user_meta = {
            "file_names": file_names,
            "fetched_urls": fetched_urls,
            # images 用 bytes 存数据库占空间大，只在 UI session 中保留
        }
        # 注意：图片 bytes 不入库，因为可能很大；文件名入库即可
        user_msg_id = db.add_message(
            conv_id, "user", prompt, meta=user_meta
        )

        # 立即渲染用户消息（带原始图片预览）
        with st.chat_message("user"):
            for img in image_previews:
                st.image(img, width=320)
            for fname in file_names:
                st.caption(f"📎 `{fname}`")
            for url in fetched_urls:
                st.caption(f"🔗 已抓取：{url}")
            st.markdown(prompt)

        # 把 user_parts 临时塞入 session 以构造 contents
        # （重新进入页面时，多模态 parts 会丢失，但文本对话历史还在）
        if "in_memory_parts" not in st.session_state:
            st.session_state.in_memory_parts = {}
        st.session_state.in_memory_parts[user_msg_id] = (
            [final_prompt] + file_parts
        )

    # 3) 构造 contents（结合数据库历史 + 内存中的 parts）
    from google.genai import types as _gt
    contents = []
    cur_messages = db.get_messages(conv_id)
    for m in cur_messages:
        role = "user" if m["role"] == "user" else "model"
        # 当前轮的 user 用 in_memory_parts，老消息只用文本
        in_mem = st.session_state.get("in_memory_parts", {}).get(m["id"])
        raw_parts = in_mem if in_mem else [m["content"]]
        # 把所有字符串包装成 Part.from_text，对象（Part / 上传文件）保持原样
        normalized_parts = []
        for p in raw_parts:
            if isinstance(p, str):
                if p.strip():
                    normalized_parts.append(_gt.Part.from_text(text=p))
            else:
                normalized_parts.append(p)
        if not normalized_parts:
            continue
        contents.append(
            _gt.Content(role=role, parts=normalized_parts)
        )

    # 4) 调用 Gemini，流式输出
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        usage = None

        for text, is_final, u in stream_chat(
            model_id=model_id,
            contents=contents,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if text:
                full_response += text
                placeholder.markdown(full_response + "▌")
            if is_final and u:
                usage = u

        # 流结束后，用增强 markdown 替换最后渲染
        placeholder.empty()
        with placeholder.container():
            render_enhanced_markdown(full_response)

    # 5) 写入助手消息
    assistant_meta = {}
    if usage:
        in_tok = usage["input_tokens"]
        out_tok = usage["output_tokens"]
        cost = estimate_cost(model_id, in_tok, out_tok)
        assistant_meta = {
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "total_tokens": usage["total_tokens"],
            "cost": cost,
        }

    db.add_message(conv_id, "assistant", full_response, meta=assistant_meta)

    # 6) 第一次对话后自动命名
    if current_conv is None or current_conv.get("title") == "新对话":
        first_user_msg = next(
            (m["content"] for m in cur_messages if m["role"] == "user"),
            None,
        )
        if first_user_msg:
            new_title = auto_title_for(first_user_msg, model_id)
            if new_title:
                db.rename_conversation(conv_id, new_title)

    st.rerun()
