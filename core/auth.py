"""简单的访问密码保护"""
import streamlit as st
from core.config import get_access_password


def require_auth():
    """
    放在 app.py 开头。
    如果 secrets 里没配置 ACCESS_PASSWORD，就直接放行（开发模式）。
    配置了密码就要求输入。
    """
    password = get_access_password()
    if not password:
        return  # 没设密码，放行

    if st.session_state.get("authenticated"):
        return

    # 显示登录界面
    st.markdown(
        "<h1 style='text-align: center;'>🔒 Gemini Chat</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; color: gray;'>"
        "请输入访问密码以继续</p>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("auth_form"):
            input_pwd = st.text_input("访问密码", type="password")
            submit = st.form_submit_button("登录", use_container_width=True)
            if submit:
                if input_pwd == password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("密码错误")
    st.stop()
