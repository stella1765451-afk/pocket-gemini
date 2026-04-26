"""导出对话为 Markdown / JSON"""
import json
from datetime import datetime


def export_markdown(conversation: dict, messages: list[dict]) -> str:
    """生成 Markdown 格式的对话"""
    lines = []
    title = conversation.get("title") or "对话"
    model = conversation.get("model_id") or ""
    created_at = conversation.get("created_at") or 0
    created_str = (
        datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M:%S")
        if created_at else ""
    )

    lines.append(f"# {title}")
    lines.append("")
    if model:
        lines.append(f"**模型**：`{model}`")
    if created_str:
        lines.append(f"**创建时间**：{created_str}")
    if conversation.get("system_prompt"):
        lines.append(f"\n**System Prompt**：\n> {conversation['system_prompt']}")
    lines.append("\n---\n")

    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        meta = msg.get("meta") or {}

        if role == "user":
            lines.append("### 🧑 用户")
            files = meta.get("file_names", [])
            if files:
                lines.append("\n**附件**: " + ", ".join(f"`{f}`" for f in files))
        elif role == "assistant":
            lines.append("### 🤖 助手")
        else:
            lines.append(f"### {role}")

        lines.append("")
        lines.append(content)
        lines.append("\n---\n")

    return "\n".join(lines)


def export_json(conversation: dict, messages: list[dict]) -> str:
    """生成 JSON 格式（包含完整元数据）"""
    data = {
        "conversation": {
            "id": conversation.get("id"),
            "title": conversation.get("title"),
            "model_id": conversation.get("model_id"),
            "system_prompt": conversation.get("system_prompt"),
            "created_at": conversation.get("created_at"),
            "updated_at": conversation.get("updated_at"),
        },
        "messages": [
            {
                "role": m["role"],
                "content": m["content"],
                "meta": m.get("meta") or {},
                "created_at": m.get("created_at"),
            }
            for m in messages
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)
