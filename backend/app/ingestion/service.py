from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.ingestion.document_parser import DocumentParser
from app.ingestion.repository import IngestionRepository
from app.ingestion.types import PageIndexDocument
from app.retrieval.pageindex import PageIndexBuilder


class IngestionService:
    def __init__(
        self,
        db_session: Session,
        parser: DocumentParser | None = None,
        page_index_builder: PageIndexBuilder | None = None,
    ):
        self.db_session = db_session
        self.parser = parser or DocumentParser()
        self.page_index_builder = page_index_builder or PageIndexBuilder()
        self.repository = IngestionRepository(db_session)

    def ingest_file(
        self,
        file_path: str | Path,
        filename: str,
        workspace_id: uuid.UUID | None = None,
        corpus_type: str = "tier2_user",
    ) -> PageIndexDocument:
        path = Path(file_path)
        active_workspace_id = workspace_id or settings.default_workspace_uuid
        file_hash = self._hash_file(path)
        stored_path = self._persist_raw_file(path, filename, file_hash)
        parsed_document = self.parser.parse(stored_path, filename=filename)

        page_index = self.page_index_builder.build_page_index(
            parsed_document=parsed_document,
            workspace_id=str(active_workspace_id),
            corpus_type=corpus_type,
            content_hash=file_hash,
        )

        self.repository.save_page_index(
            page_index=page_index,
            workspace_id=active_workspace_id,
            corpus_type=corpus_type,
            storage_path=str(stored_path),
            file_size_bytes=path.stat().st_size,
        )
        return page_index

    def _persist_raw_file(self, path: Path, filename: str, file_hash: str) -> Path:
        upload_root = Path(settings.UPLOAD_ROOT)
        upload_root.mkdir(parents=True, exist_ok=True)

        suffix = Path(filename).suffix.lower()
        target = upload_root / f"{file_hash}{suffix}"
        if not target.exists():
            shutil.copyfile(path, target)
        return target

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
