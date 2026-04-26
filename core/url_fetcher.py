"""URL 抓取：从用户消息里提取 URL，抓取网页内容作为上下文"""
import re
import urllib.request
import urllib.error
from html.parser import HTMLParser

URL_RE = re.compile(
    r"https?://[\w\-._~:/?#\[\]@!$&'()*+,;=%]+",
    re.IGNORECASE,
)


def extract_urls(text: str) -> list[str]:
    return URL_RE.findall(text or "")


class _TextExtractor(HTMLParser):
    """简单 HTML → 纯文本提取器"""
    SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}

    def __init__(self):
        super().__init__()
        self._stack = []
        self._buf = []

    def handle_starttag(self, tag, attrs):
        self._stack.append(tag.lower())

    def handle_endtag(self, tag):
        if self._stack and self._stack[-1] == tag.lower():
            self._stack.pop()

    def handle_data(self, data):
        if any(t in self.SKIP_TAGS for t in self._stack):
            return
        text = data.strip()
        if text:
            self._buf.append(text)

    def get_text(self) -> str:
        return "\n".join(self._buf)


def fetch_url(url: str, max_chars: int = 8000, timeout: int = 10) -> tuple[bool, str]:
    """
    抓取 URL 内容并提取为纯文本。
    返回 (success, text_or_error)
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; GeminiChat/1.0; "
                    "+https://github.com/yourname/gemini-chat)"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "").lower()
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].split(";")[0].strip()
            raw = resp.read(2_000_000).decode(charset, errors="replace")

        if "html" in content_type:
            parser = _TextExtractor()
            parser.feed(raw)
            text = parser.get_text()
        else:
            text = raw

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[内容过长已截断，原文长度约 {len(text)} 字符]"

        return True, text

    except urllib.error.HTTPError as e:
        return False, f"HTTP 错误 {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, f"URL 错误: {e.reason}"
    except Exception as e:
        return False, f"抓取失败: {e}"


def augment_prompt_with_urls(text: str) -> tuple[str, list[str]]:
    """
    检测文本里的 URL，抓取内容并附加到 prompt 末尾。
    返回 (增强后的 prompt, 成功抓取的 URL 列表)
    """
    urls = extract_urls(text)
    if not urls:
        return text, []

    fetched = []
    blocks = []
    for url in urls[:3]:  # 最多抓 3 个，避免太慢
        ok, content = fetch_url(url)
        if ok:
            fetched.append(url)
            blocks.append(f"\n\n--- 来自 {url} 的网页内容 ---\n{content}\n")

    if blocks:
        return text + "\n\n[已自动抓取以下网页内容供你参考]" + "".join(blocks), fetched
    return text, []
