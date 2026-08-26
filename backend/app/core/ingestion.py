import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select

from ..db import async_session_factory
from ..models import KnowledgeDocument


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "ingestion"
UPLOADS_DIR = DATA_DIR / "uploads"
STATE_FILE = DATA_DIR / "state.json"


class IngestionService:
    """Document ingestion: upload PDFs, extract text, build parent-child chunks."""

    def __init__(self) -> None:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self.chunks: dict[str, list[dict[str, Any]]] = {}
        self._load_state()

    def _load_state(self) -> None:
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                self.chunks = data.get("chunks", {})
            except (OSError, json.JSONDecodeError):
                pass

    def _save_state(self) -> None:
        STATE_FILE.write_text(
            json.dumps({"chunks": self.chunks}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def classify_model(filename: str) -> str:
        name = filename.lower().replace("_", " ").replace("-", " ")
        for model in ("旗舰版", "标准版", "基础版", "通用"):
            if model in name:
                return model
        return "通用"

    async def create_document(self, filename: str, data: bytes, title: str = "") -> dict:
        digest = hashlib.sha256(data).hexdigest()
        async with async_session_factory() as db:
            existing = await db.scalar(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.content_hash == digest,
                    KnowledgeDocument.status != "deleted",
                )
            )
            if existing:
                return {"document_id": existing.id, "status": "ready", "duplicate": True}

        document_id = str(uuid.uuid4())
        storage = UPLOADS_DIR / f"{document_id}.pdf"
        storage.write_bytes(data)
        model = self.classify_model(filename)

        async with async_session_factory() as db:
            doc = KnowledgeDocument(
                id=document_id,
                filename=filename,
                title=title or filename,
                product_model=model,
                content_hash=digest,
                status="pending",
            )
            db.add(doc)
            await db.commit()

        return {"document_id": document_id, "status": "pending", "duplicate": False}

    async def process_document(self, document_id: str) -> None:
        async with async_session_factory() as db:
            doc = await db.get(KnowledgeDocument, document_id)
            if not doc:
                return
            doc.status = "parsing"
            await db.commit()

        try:
            storage = UPLOADS_DIR / f"{document_id}.pdf"
            text, page_count, parser = self._parse_pdf(storage)
            chunks = self._build_chunks(text, document_id, doc.product_model)

            async with async_session_factory() as db:
                doc = await db.get(KnowledgeDocument, document_id)
                doc.status = "ready"
                doc.page_count = page_count
                doc.chunk_count = len(chunks)
                doc.error = None
                doc.updated_at = _utcnow()
                await db.commit()

            self.chunks[document_id] = chunks
            self._save_state()

        except Exception as exc:
            async with async_session_factory() as db:
                doc = await db.get(KnowledgeDocument, document_id)
                if doc:
                    doc.status = "failed"
                    doc.error = str(exc)[:500]
                    doc.updated_at = _utcnow()
                    await db.commit()

    @staticmethod
    def _parse_pdf(pdf_path: Path) -> tuple[str, int, str]:
        """Extract text from PDF. Tries pdfplumber, then PyPDF2, then raw fallback."""
        try:
            import pdfplumber
            pages_text: list[str] = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    pages_text.append(page.extract_text() or "")
            return "\n\n".join(pages_text), len(pages_text), "pdfplumber"
        except ImportError:
            pass

        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(pdf_path))
            pages_text = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages_text), len(pages_text), "pypdf2"
        except ImportError:
            pass

        # Last-resort: read raw bytes and strip non-text
        raw = pdf_path.read_bytes()
        text = re.sub(rb"[^\x20-\x7e\xe4-\xef\x80-\xbf\xa1-\xfe\n]", b"", raw)
        return text.decode("utf-8", errors="ignore"), 1, "raw-fallback"

    @staticmethod
    def _split_children(content: str, size: int = 500, overlap: int = 80) -> list[str]:
        content = content.strip()
        if not content:
            return []
        parts: list[str] = []
        start = 0
        while start < len(content):
            end = min(start + size, len(content))
            if end < len(content):
                boundary = max(
                    content.rfind(marker, start, end)
                    for marker in ("\n", "。", "！", "？", "；")
                )
                if boundary > start + 200:
                    end = boundary + 1
            part = content[start:end].strip()
            if len(part) >= 20:
                parts.append(part)
            if end >= len(content):
                break
            start = max(end - overlap, start + 1)
        return parts

    @staticmethod
    def _build_chunks(text: str, document_id: str, model: str) -> list[dict[str, Any]]:
        """Build parent-child chunks: full sections as parents, sub-split as children."""
        sections: list[dict[str, Any]] = []
        current_lines: list[str] = []
        current_heading = "概述"

        for line in text.splitlines():
            heading_match = re.match(r"^(#{1,4})\s+(.+)$", line)
            numeric_match = re.match(r"^(\d+(?:\.\d+)*)\s+(.+)$", line) if len(line) < 80 else None
            if heading_match or numeric_match:
                if current_lines:
                    sections.append({
                        "title": current_heading,
                        "content": "\n".join(current_lines).strip(),
                    })
                current_lines = []
                if heading_match:
                    current_heading = heading_match.group(2).strip()
                else:
                    current_heading = f"{numeric_match.group(1)} {numeric_match.group(2).strip()}"
                continue
            current_lines.append(line)
        if current_lines:
            sections.append({"title": current_heading, "content": "\n".join(current_lines).strip()})

        chunks: list[dict[str, Any]] = []
        for idx, section in enumerate(sections):
            if not section["content"]:
                continue
            parent_id = f"{document_id}:parent:{idx}"
            common = {
                "document_id": document_id,
                "model": model,
                "chapter": section["title"],
                "section_path": f"{model} > {section['title']}",
            }
            chunks.append({
                "chunk_id": parent_id,
                "parent_id": None,
                "chunk_role": "parent",
                "content": section["content"],
                **common,
            })
            for child_idx, child_content in enumerate(IngestionService._split_children(section["content"])):
                child_id = f"{parent_id}:child:{child_idx}"
                chunks.append({
                    "chunk_id": child_id,
                    "parent_id": parent_id,
                    "chunk_role": "child",
                    "content": child_content,
                    **common,
                })
        return chunks

    async def list_documents(self) -> list[dict]:
        async with async_session_factory() as db:
            rows = await db.scalars(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.status != "deleted")
                .order_by(desc(KnowledgeDocument.updated_at))
            )
            return [
                {
                    "document_id": r.id,
                    "filename": r.filename,
                    "title": r.title,
                    "product_model": r.product_model,
                    "page_count": r.page_count,
                    "chunk_count": r.chunk_count,
                    "status": r.status,
                    "error": r.error,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
                for r in list(rows)
            ]

    async def get_document(self, document_id: str) -> dict | None:
        async with async_session_factory() as db:
            r = await db.get(KnowledgeDocument, document_id)
            if not r or r.status == "deleted":
                return None
            return {
                "document_id": r.id,
                "filename": r.filename,
                "title": r.title,
                "product_model": r.product_model,
                "page_count": r.page_count,
                "chunk_count": r.chunk_count,
                "status": r.status,
                "error": r.error,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }

    async def delete_document(self, document_id: str) -> bool:
        async with async_session_factory() as db:
            r = await db.get(KnowledgeDocument, document_id)
            if not r:
                return False
            r.status = "deleted"
            await db.commit()
        self.chunks.pop(document_id, None)
        self._save_state()
        return True

    async def reindex_document(self, document_id: str) -> bool:
        async with async_session_factory() as db:
            r = await db.get(KnowledgeDocument, document_id)
            if not r or r.status == "deleted":
                return False
            r.status = "pending"
            await db.commit()
        await self.process_document(document_id)
        return True

    def ready_chunks(self) -> list[dict[str, Any]]:
        """Return all child chunks from ready documents for RAG indexing."""
        return [
            chunk for chunks in self.chunks.values() for chunk in chunks
            if chunk.get("chunk_role") == "child"
        ]

    def document_chunks(self, document_id: str) -> list[dict[str, Any]]:
        return self.chunks.get(document_id, [])


ingestion_service = IngestionService()
