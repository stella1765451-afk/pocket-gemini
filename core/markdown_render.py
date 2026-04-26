"""
增强的 Markdown 渲染：
- 自动检测并渲染 Mermaid 图表
- LaTeX 数学公式（Streamlit 原生支持 $...$ 和 $$...$$）
- 代码高亮（Streamlit 自带）
"""
import re
import streamlit as st


MERMAID_BLOCK_RE = re.compile(
    r"```mermaid\s*\n(.*?)```", re.DOTALL
)


def render_mermaid(code: str, height: int = 400):
    """用 Mermaid CDN 渲染图表"""
    html = f"""
    <div class="mermaid" style="background: white; padding: 12px; border-radius: 8px;">
{code}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>
        mermaid.initialize({{startOnLoad: true, theme: 'default'}});
    </script>
    """
    st.components.v1.html(html, height=height, scrolling=True)


def render_enhanced_markdown(text: str):
    """
    渲染 Markdown，遇到 mermaid 代码块特殊处理。
    其他部分（LaTeX、代码高亮）由 Streamlit 原生 markdown 处理。
    """
    if not text:
        return

    # 找出所有 mermaid 块及其位置
    last_end = 0
    for match in MERMAID_BLOCK_RE.finditer(text):
        # 渲染前面的普通 markdown
        before = text[last_end:match.start()]
        if before.strip():
            st.markdown(before)
        # 渲染 mermaid
        mermaid_code = match.group(1).strip()
        if mermaid_code:
            render_mermaid(mermaid_code)
        last_end = match.end()

    # 剩余部分（如果没有 mermaid 块，rest 就是整个 text）
    rest = text[last_end:]
    if rest.strip():
        st.markdown(rest)
