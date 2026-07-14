from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.ingestion.types import PageIndexDocument
from app.platform.models import Chunk, Document, DocumentVersion, Upload


class IngestionRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_page_index(
        self,
        page_index: PageIndexDocument,
        workspace_id: uuid.UUID,
        corpus_type: str,
        storage_path: str,
        file_size_bytes: int,
    ) -> int:
        document_id = uuid.UUID(page_index.document_id)
        version_id = uuid.UUID(page_index.document_version)

        document = self.session.get(Document, document_id)
        if document is None:
            document = Document(
                id=document_id,
                workspace_id=workspace_id,
                corpus_type=corpus_type,
                title=page_index.source_filename,
                source_filename=page_index.source_filename,
                mime_type=page_index.mime_type,
                status="active",
            )
            self.session.add(document)

        version = self.session.get(DocumentVersion, version_id)
        if version is None:
            version = DocumentVersion(
                id=version_id,
                document_id=document_id,
                version_number=1,
                content_hash=page_index.content_hash,
                embedding_model="pending",
                embedding_dimensions=0,
                ingestion_status="parsed",
            )
            self.session.add(version)

        upload = Upload(
            document_id=document_id,
            session_id=None,
            storage_path=storage_path,
            original_filename=page_index.source_filename,
            file_size_bytes=file_size_bytes,
        )
        self.session.add(upload)
        self.session.flush()

        for chunk in page_index.chunks:
            chunk_id = uuid.UUID(chunk.chunk_id)
            if self.session.get(Chunk, chunk_id) is not None:
                continue

            self.session.add(
                Chunk(
                    id=chunk_id,
                    document_version_id=version_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    heading_path=chunk.heading_path,
                    section_label=chunk.section_label,
                    parent_chunk_id=(
                        uuid.UUID(chunk.parent_id) if chunk.parent_id else None
                    ),
                    text=chunk.text,
                    content_hash=chunk.content_hash,
                    metadata_json=chunk.metadata,
                )
            )

        self.session.commit()
        return len(page_index.chunks)