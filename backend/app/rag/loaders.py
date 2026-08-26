# 知识库文档加载与切分：读取 data/knowledge 下的 Markdown，按标题切分并控制分块大小
import re
from pathlib import Path


# 切分第一步：将整篇 Markdown 按标题行拆成"标题+正文"的独立小节
def _split_sections(text: str) -> list[str]:
    # 按 Markdown 标题切分知识库；子标题块会带上所属一级标题，避免分块丢失商品/政策上下文
    sections: list[str] = []
    current: list[str] = []
    current_h1 = ""
    for line in text.splitlines():
        if re.match(r"^#\s+", line):
            if current:
                sections.append("\n".join(current))
            current_h1 = line
            current = [line]
        elif re.match(r"^#{2,6}\s+", line):
            # 子标题作为独立小节时，前缀一级标题保证分块后可溯源到具体商品/政策
            if current:
                sections.append("\n".join(current))
            current = [current_h1, line] if current_h1 else [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current))
    return sections


# 切分第二步：将小节进一步切成不超过 limit 字的检索分块，保证块内语义完整
def _chunk_text(text: str, limit: int = 300) -> list[str]:
    # 每个分块不超过 300 字，优先按段落和句号切分
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        while len(paragraph) > limit:
            # 超长段落按最近的句号截断，避免在句子中间断开
            boundary = paragraph.rfind("。", 0, limit)
            if boundary < 0:
                boundary = limit
            if current:
                chunks.append(current)
                current = ""
            chunks.append(paragraph[: boundary + 1])
            paragraph = paragraph[boundary + 1 :].strip()
        # 当前块拼接下一段会超限时，先收尾当前块再开新块
        if current and len(current) + len(paragraph) + 2 > limit:
            chunks.append(current)
            current = ""
        current = f"{current}\n\n{paragraph}".strip() if current else paragraph
    if current:
        chunks.append(current)
    return chunks


# 知识库加载入口：遍历目录下的 Markdown，切分后返回带来源文件的文本分块
def load_knowledge_markdown(base_dir: Path) -> list[dict]:
    # 读取 data/knowledge 下所有 md 文件，返回 text + source 分块
    chunks: list[dict] = []
    # 按文件名排序遍历，保证多次加载的块顺序稳定
    for file_path in sorted(base_dir.glob("*.md")):
        source = file_path.name
        text = file_path.read_text(encoding="utf-8")
        for section in _split_sections(text):
            for piece in _chunk_text(section):
                if piece.strip():
                    chunks.append({"text": piece.strip(), "source": source})
    return chunks
