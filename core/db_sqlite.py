"""
SQLite 对话存储
表结构：
- conversations: 对话列表
- messages: 每条消息
"""
import sqlite3
import json
import time
from pathlib import Path
from typing import Any
import streamlit as st

# ============================================================
# 数据库路径
# ============================================================
# Streamlit Cloud 上 /tmp 是可写的。本地用 ./data/
DB_DIR = Path.home() / ".gemini_chat"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "chat.db"


# ============================================================
# 连接（每个线程一个连接）
# ============================================================
@st.cache_resource
def get_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn


def _init_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL DEFAULT '新对话',
        model_id TEXT,
        system_prompt TEXT,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        meta TEXT,
        created_at REAL NOT NULL,
        FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_messages_conv
        ON messages(conversation_id);
    CREATE INDEX IF NOT EXISTS idx_conv_updated
        ON conversations(updated_at DESC);
    """)
    conn.commit()


# ============================================================
# 对话级操作
# ============================================================
def create_conversation(
    title: str = "新对话",
    model_id: str = "",
    system_prompt: str = "",
) -> int:
    conn = get_conn()
    now = time.time()
    cur = conn.execute(
        """INSERT INTO conversations
           (title, model_id, system_prompt, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        (title, model_id, system_prompt, now, now),
    )
    conn.commit()
    return cur.lastrowid


def list_conversations(limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT id, title, model_id, updated_at,
                  (SELECT COUNT(*) FROM messages WHERE conversation_id=conversations.id) AS msg_count
           FROM conversations
           ORDER BY updated_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(conv_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM conversations WHERE id=?", (conv_id,)
    ).fetchone()
    return dict(row) if row else None


def rename_conversation(conv_id: int, title: str):
    conn = get_conn()
    conn.execute(
        "UPDATE conversations SET title=?, updated_at=? WHERE id=?",
        (title, time.time(), conv_id),
    )
    conn.commit()


def update_conversation_settings(
    conv_id: int, model_id: str = None, system_prompt: str = None
):
    conn = get_conn()
    fields, values = [], []
    if model_id is not None:
        fields.append("model_id=?")
        values.append(model_id)
    if system_prompt is not None:
        fields.append("system_prompt=?")
        values.append(system_prompt)
    if not fields:
        return
    fields.append("updated_at=?")
    values.append(time.time())
    values.append(conv_id)
    conn.execute(
        f"UPDATE conversations SET {', '.join(fields)} WHERE id=?", values
    )
    conn.commit()


def delete_conversation(conv_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM messages WHERE conversation_id=?", (conv_id,))
    conn.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
    conn.commit()


def touch_conversation(conv_id: int):
    """更新最后修改时间，让对话冒到列表顶部"""
    conn = get_conn()
    conn.execute(
        "UPDATE conversations SET updated_at=? WHERE id=?",
        (time.time(), conv_id),
    )
    conn.commit()


# ============================================================
# 消息级操作
# ============================================================
def add_message(
    conv_id: int,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> int:
    """meta 用 JSON 存：附件文件名、token 用量等"""
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO messages
           (conversation_id, role, content, meta, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (conv_id, role, content, json.dumps(meta or {}), time.time()),
    )
    conn.commit()
    touch_conversation(conv_id)
    return cur.lastrowid


def get_messages(conv_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT id, role, content, meta, created_at
           FROM messages WHERE conversation_id=?
           ORDER BY id ASC""",
        (conv_id,),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["meta"] = json.loads(d["meta"]) if d["meta"] else {}
        except json.JSONDecodeError:
            d["meta"] = {}
        result.append(d)
    return result


def delete_message(msg_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM messages WHERE id=?", (msg_id,))
    conn.commit()


def delete_messages_after(conv_id: int, msg_id: int):
    """删除某消息之后的所有消息（用于"重新生成"）"""
    conn = get_conn()
    conn.execute(
        "DELETE FROM messages WHERE conversation_id=? AND id>=?",
        (conv_id, msg_id),
    )
    conn.commit()


def get_total_token_usage(conv_id: int) -> tuple[int, int, float]:
    """返回 (input_tokens, output_tokens, total_cost_usd)"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT meta FROM messages WHERE conversation_id=? AND role='assistant'",
        (conv_id,),
    ).fetchall()
    in_total, out_total, cost_total = 0, 0, 0.0
    for r in rows:
        try:
            meta = json.loads(r["meta"]) if r["meta"] else {}
            in_total += meta.get("input_tokens", 0)
            out_total += meta.get("output_tokens", 0)
            cost_total += meta.get("cost", 0.0)
        except json.JSONDecodeError:
            pass
    return in_total, out_total, cost_total
