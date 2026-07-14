from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str
    ocr_used: bool = False


@dataclass(frozen=True)
class ParsedDocument:
    filename: str
    mime_type: str
    pages: list[ParsedPage]
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text.strip())


@dataclass(frozen=True)
class PageIndexChunk:
    chunk_id: str
    parent_id: str | None
    chunk_index: int
    text: str
    page_number: int | None
    heading_path: str
    section_label: str
    content_hash: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class PageIndexDocument:
    document_id: str
    document_version: str
    source_filename: str
    mime_type: str
    content_hash: str
    chunks: list[PageIndexChunk]
