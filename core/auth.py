"""
访问密码保护，支持"记住登录"
原理：登录后给 URL 加上 token=hash(password) 参数，之后从这个 URL 进来自动登录。
用户把带 token 的 URL 存为书签后，再也不用重输密码。
"""
import hashlib
import streamlit as st
from core.config import get_access_password


def _make_token(password: str) -> str:
    """生成不可逆 token（hash 后取前 24 位），避免密码明文出现在 URL"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()[:24]


def require_auth():
    """
    放在 app.py 开头。
    - 没配置 ACCESS_PASSWORD：放行（开发模式）
    - 配置了密码：第一次需要输入，之后通过 URL token 自动登录
    """
    password = get_access_password()
    if not password:
        return  # 没设密码，放行

    expected_token = _make_token(password)

    # 1) 已经在本次 session 中登录
    if st.session_state.get("authenticated"):
        # 确保 URL 上有 token，方便用户收藏
        if st.query_params.get("token") != expected_token:
            st.query_params["token"] = expected_token
        return

    # 2) URL 里带了正确 token，自动登录
    url_token = st.query_params.get("token")
    if url_token == expected_token:
        st.session_state.authenticated = True
        return

    # 3) 显示登录界面
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
            remember = st.checkbox(
                "记住登录（下次刷新不用再输）",
                value=True,
                help="会在 URL 后加一个 token 参数，把当前页面收藏为书签即可永久免登录",
            )
            submit = st.form_submit_button("登录", use_container_width=True)
            if submit:
                if input_pwd == password:
                    st.session_state.authenticated = True
                    if remember:
                        st.query_params["token"] = expected_token
                    st.rerun()
                else:
                    st.error("密码错误")

        st.caption(
            "💡 勾选「记住登录」后，把浏览器地址栏的 URL 收藏为书签，"
            "以后从书签进入就不用再输密码了。"
        )
    st.stop()


def logout():
    """登出：清除 session 和 URL token"""
    st.session_state.authenticated = False
    if "token" in st.query_params:
        del st.query_params["token"]
