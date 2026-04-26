# Gemini Chat

一个用 Streamlit + Gemini API 搭建的私人 AI 对话工具，体验对标 Gemini Pro 网页版。

## ✨ 当前功能

- 💬 **多对话管理**：左侧栏切换/重命名/删除多个对话
- ☁️ **云端持久化**：通过 Supabase 永久保存对话历史（也支持本地 SQLite）
- 🤖 **动态模型列表**：自动拉取最新 Gemini 模型
- 🖼️ **多模态输入**：图片、PDF、音视频、代码文件
- 🌊 **流式输出**：边生成边显示
- 📊 **Token 用量 + 成本估算**
- 🔄 **重新生成 / 复制按钮**
- 🎭 **12 个 Prompt 模板**：写作、翻译、代码审查、苏格拉底等
- 🔗 **URL 自动抓取**
- 📤 **导出对话**：Markdown / JSON
- 🔒 **访问密码保护**
- 🎨 **Markdown 增强**：代码高亮、LaTeX、Mermaid

## 🚀 快速部署（全部在云端）

需要 3 个免费账号：GitHub、Google AI Studio、Supabase。

### Step 1: 拿 Gemini API Key

1. 打开 [Google AI Studio](https://aistudio.google.com/apikey)
2. Create API key → Create in new project
3. 复制保存（`AIzaSy...` 开头）

### Step 2: 创建 Supabase 项目

1. 打开 [supabase.com](https://supabase.com) → 用 GitHub 登录
2. New project → 项目名随意（比如 `gemini-chat`）→ 设密码 → 选离你最近的 Region → Create
3. 等 1-2 分钟项目创建完成
4. 左侧 **SQL Editor** → **New query** → 把 `supabase_init.sql` 内容粘贴 → Run
5. 左侧 **Project Settings** → **API**：
   - 复制 **Project URL**（类似 `https://xxx.supabase.co`）
   - 复制 **service_role secret**（注意不是 anon public key）

### Step 3: 推到 GitHub

把项目所有文件推到 GitHub 仓库（除了 `.streamlit/secrets.toml`）。

### Step 4: 部署到 Streamlit Cloud

1. [share.streamlit.io](https://share.streamlit.io/) → Continue with GitHub
2. Create app → Deploy from GitHub
3. 选你的仓库，Main file 填 `app.py`
4. **Advanced settings → Secrets** 粘贴：

```toml
GEMINI_API_KEY = "AIzaSy..."
ACCESS_PASSWORD = "你的访问密码"
SUPABASE_URL = "https://xxx.supabase.co"
SUPABASE_KEY = "你的 service_role secret"
```

5. Deploy → 等 2-3 分钟 → 完成

## 🛠️ 项目结构

```
gemini-chat/
├── app.py                    # 主程序
├── supabase_init.sql        # Supabase 建表 SQL
├── core/
│   ├── auth.py              # 访问密码
│   ├── config.py            # 配置 + 价格
│   ├── db.py                # 数据库路由（自动选 Supabase 或 SQLite）
│   ├── db_sqlite.py         # SQLite 实现
│   ├── db_supabase.py       # Supabase 实现
│   ├── export.py            # 导出 MD / JSON
│   ├── gemini.py            # Gemini API 封装
│   ├── markdown_render.py   # Mermaid + LaTeX 渲染
│   ├── templates.py         # Prompt 模板加载
│   └── url_fetcher.py       # URL 抓取
├── prompts/templates.json
├── .streamlit/config.toml
├── requirements.txt
└── README.md
```

## 💻 本地开发

```bash
git clone <你的仓库>
cd gemini-chat
pip install -r requirements.txt

mkdir -p .streamlit
cat > .streamlit/secrets.toml << EOF2
GEMINI_API_KEY = "你的key"
# 本地用 SQLite 就不用配 Supabase 了
EOF2

streamlit run app.py
```

不配 Supabase 时自动用本地 SQLite，对话存在 `~/.gemini_chat/chat.db`。

## 📋 后续迭代计划

**第二批：智能能力**
- Google 联网搜索（Grounding）
- 代码执行
- Function Calling（网页抓取/维基/日程）
- 长对话自动总结
- 多模型对比 Tab

**第三批：多模态生成**
- 图片生成 (Nano Banana 2)
- Veo 视频生成
- 语音输入 / TTS
- RAG 知识库（基于 Supabase pgvector）
