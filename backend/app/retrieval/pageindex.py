from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from typing import Any

from app.ingestion.types import PageIndexChunk, PageIndexDocument, ParsedDocument


@dataclass(frozen=True)
class _SectionState:
    chapter: str
    section_label: str
    heading_path: str
    parent_id: str


class PageIndexBuilder:
    """
    Builds both the legacy Act -> Chapter -> Section map and the Stage 2
    stable PageIndex used for durable uploaded-document chunks.
    """

    _chapter_pattern = re.compile(
        r"(?i)^\s*(?:CHAPTER|CHAP\.)\s+([IVXLCDM\d\-]+)(.*)$"
    )
    _section_pattern = re.compile(
        r"(?i)^\s*(?:Section|Sec\.)\s*(\d+[A-Z]*)(.*)$"
    )
    _paragraph_split_pattern = re.compile(r"\n\s*\n+")

    def build_tree_from_text(self, text: str) -> dict[str, Any]:
        tree: dict[str, Any] = {"chapters": {}}
        current_chapter = "General"
        current_section = None
        current_section_lines: list[str] = []

        for line in text.split("\n"):
            chap_match = self._chapter_pattern.match(line)
            sec_match = self._section_pattern.match(line)

            if chap_match:
                if current_section and current_section_lines:
                    self._store_legacy_section(
                        tree,
                        current_chapter,
                        current_section,
                        current_section_lines,
                    )
                    current_section_lines = []

                chap_num = chap_match.group(1).strip()
                chap_title = self._clean_heading_title(chap_match.group(2).strip())
                current_chapter = f"Chapter {chap_num}"
                if chap_title:
                    current_chapter += f" - {chap_title}"
                current_section = None

            elif sec_match:
                if current_section and current_section_lines:
                    self._store_legacy_section(
                        tree,
                        current_chapter,
                        current_section,
                        current_section_lines,
                    )

                current_section = sec_match.group(1).strip()
                header_text = sec_match.group(2).strip()
                line_to_add = f"Section {current_section}"
                if header_text:
                    line_to_add += f" {header_text}"
                current_section_lines = [line_to_add]
            else:
                if current_section is not None:
                    current_section_lines.append(line)

        if current_section and current_section_lines:
            self._store_legacy_section(
                tree,
                current_chapter,
                current_section,
                current_section_lines,
            )

        return tree

    def extract_section_headers(self, text: str) -> list[dict[str, Any]]:
        tree = self.build_tree_from_text(text)
        chunks = []
        for _chap_name, chap_data in tree.get("chapters", {}).items():
            for sec_num, sec_text in chap_data.get("sections", {}).items():
                chunks.append({"section": sec_num, "text": sec_text})
        return chunks

    def build_page_index(
        self,
        parsed_document: ParsedDocument,
        workspace_id: str,
        corpus_type: str,
        content_hash: str,
    ) -> PageIndexDocument:
        document_id = self._stable_uuid(
            "document",
            workspace_id,
            corpus_type,
            parsed_document.filename,
            content_hash,
        )
        document_version = self._stable_uuid("version", document_id, content_hash)
        chunks: list[PageIndexChunk] = []

        current_chapter = "General"
        current_section = _SectionState(
            chapter=current_chapter,
            section_label="General",
            heading_path=current_chapter,
            parent_id=self._stable_uuid("section", document_version, current_chapter),
        )
        pending_lines: list[str] = []
        pending_page_number: int | None = None

        for page in parsed_document.pages:
            for line in page.text.splitlines():
                chap_match = self._chapter_pattern.match(line)
                sec_match = self._section_pattern.match(line)

                if chap_match:
                    chunks.extend(
                        self._flush_section_chunks(
                            pending_lines,
                            pending_page_number,
                            current_section,
                            document_id,
                            document_version,
                            len(chunks),
                            parsed_document,
                            corpus_type,
                            page.ocr_used,
                        )
                    )
                    pending_lines = []
                    pending_page_number = None

                    chap_num = chap_match.group(1).strip()
                    chap_title = self._clean_heading_title(chap_match.group(2).strip())
                    current_chapter = f"Chapter {chap_num}"
                    if chap_title:
                        current_chapter += f" - {chap_title}"
                    current_section = _SectionState(
                        chapter=current_chapter,
                        section_label="General",
                        heading_path=current_chapter,
                        parent_id=self._stable_uuid(
                            "section",
                            document_version,
                            current_chapter,
                        ),
                    )
                    continue

                if sec_match:
                    chunks.extend(
                        self._flush_section_chunks(
                            pending_lines,
                            pending_page_number,
                            current_section,
                            document_id,
                            document_version,
                            len(chunks),
                            parsed_document,
                            corpus_type,
                            page.ocr_used,
                        )
                    )
                    pending_lines = []
                    pending_page_number = None

                    section_number = sec_match.group(1).strip()
                    header_text = sec_match.group(2).strip()
                    section_label = f"Section {section_number}"
                    if header_text:
                        section_label += f" {header_text}"
                    heading_path = f"{current_chapter} > {section_label}"
                    current_section = _SectionState(
                        chapter=current_chapter,
                        section_label=section_number,
                        heading_path=heading_path,
                        parent_id=self._stable_uuid(
                            "section",
                            document_version,
                            heading_path,
                        ),
                    )
                    pending_lines.append(section_label)
                    pending_page_number = pending_page_number or page.page_number
                    continue

                if line.strip():
                    pending_lines.append(line)
                    pending_page_number = pending_page_number or page.page_number

            if pending_lines:
                chunks.extend(
                    self._flush_section_chunks(
                        pending_lines,
                        pending_page_number,
                        current_section,
                        document_id,
                        document_version,
                        len(chunks),
                        parsed_document,
                        corpus_type,
                        page.ocr_used,
                    )
                )
                pending_lines = []
                pending_page_number = None

        chunks.extend(
            self._flush_section_chunks(
                pending_lines,
                pending_page_number,
                current_section,
                document_id,
                document_version,
                len(chunks),
                parsed_document,
                corpus_type,
                any(page.ocr_used for page in parsed_document.pages),
            )
        )

        if not chunks and parsed_document.text.strip():
            chunks = self._fallback_chunks(
                parsed_document,
                document_id,
                document_version,
                corpus_type,
                current_section,
            )

        return PageIndexDocument(
            document_id=document_id,
            document_version=document_version,
            source_filename=parsed_document.filename,
            mime_type=parsed_document.mime_type,
            content_hash=content_hash,
            chunks=chunks,
        )

    def _flush_section_chunks(
        self,
        lines: list[str],
        page_number: int | None,
        section: _SectionState,
        document_id: str,
        document_version: str,
        start_index: int,
        parsed_document: ParsedDocument,
        corpus_type: str,
        ocr_used: bool,
    ) -> list[PageIndexChunk]:
        text = "\n".join(lines).strip()
        if not text:
            return []

        paragraphs = [
            paragraph.strip()
            for paragraph in self._paragraph_split_pattern.split(text)
            if paragraph.strip()
        ]
        if not paragraphs:
            paragraphs = [text]

        chunks: list[PageIndexChunk] = []
        for offset, paragraph in enumerate(paragraphs):
            chunk_index = start_index + offset
            chunk_hash = hashlib.sha256(paragraph.encode("utf-8")).hexdigest()
            chunk_id = self._stable_uuid(
                "chunk",
                document_version,
                str(chunk_index),
                chunk_hash,
            )
            chunks.append(
                PageIndexChunk(
                    chunk_id=chunk_id,
                    parent_id=section.parent_id,
                    chunk_index=chunk_index,
                    text=paragraph,
                    page_number=page_number,
                    heading_path=section.heading_path,
                    section_label=section.section_label,
                    content_hash=chunk_hash,
                    metadata={
                        "document_id": document_id,
                        "document_version": document_version,
                        "corpus_type": corpus_type,
                        "source_filename": parsed_document.filename,
                        "mime_type": parsed_document.mime_type,
                        "hierarchy_level": "chunk",
                        "chapter": section.chapter,
                        "ocr_used": str(ocr_used).lower(),
                    },
                )
            )
        return chunks

    def _fallback_chunks(
        self,
        parsed_document: ParsedDocument,
        document_id: str,
        document_version: str,
        corpus_type: str,
        section: _SectionState,
    ) -> list[PageIndexChunk]:
        return self._flush_section_chunks(
            [parsed_document.text],
            parsed_document.pages[0].page_number if parsed_document.pages else None,
            section,
            document_id,
            document_version,
            0,
            parsed_document,
            corpus_type,
            any(page.ocr_used for page in parsed_document.pages),
        )

    @staticmethod
    def _store_legacy_section(
        tree: dict[str, Any],
        chapter: str,
        section: str,
        lines: list[str],
    ) -> None:
        if chapter not in tree["chapters"]:
            tree["chapters"][chapter] = {"sections": {}}
        tree["chapters"][chapter]["sections"][section] = "\n".join(lines).strip()

    @staticmethod
    def _clean_heading_title(title: str) -> str:
        return re.sub(r"^[\s\-:\u2013\u2014]+", "", title).strip()

    @staticmethod
    def _stable_uuid(*parts: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, ":".join(parts)))
