import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.config import settings
from app.ingestion.document_parser import DocumentParser, UnsupportedDocumentError
from app.ingestion.service import IngestionService
from app.ingestion.types import ParsedDocument, ParsedPage
from app.platform.bootstrap import run_migrations
from app.platform.database import check_database_connection, get_session_factory
from app.platform.models import Chunk, Document, DocumentVersion, Upload
from app.retrieval.pageindex import PageIndexBuilder


class TestStage2Ingestion(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_txt_parser_produces_parsed_document(self):
        path = Path(self.test_dir) / "policy.txt"
        path.write_text("Section 1 Scope\nThis policy applies.", encoding="utf-8")

        parsed = DocumentParser().parse(path)

        self.assertEqual(parsed.filename, "policy.txt")
        self.assertEqual(parsed.mime_type, "text/plain")
        self.assertEqual(parsed.pages[0].page_number, 1)
        self.assertIn("Section 1", parsed.text)

    def test_parser_rejects_unsupported_file_types(self):
        path = Path(self.test_dir) / "payload.exe"
        path.write_text("not a document", encoding="utf-8")

        with self.assertRaises(UnsupportedDocumentError):
            DocumentParser().parse(path)

    def test_page_index_has_stable_chunk_identity_and_trace_metadata(self):
        parsed = ParsedDocument(
            filename="it-act.txt",
            mime_type="text/plain",
            pages=[
                ParsedPage(
                    page_number=7,
                    text=(
                        "CHAPTER I - PRELIMINARY\n"
                        "Section 1 Short title\n"
                        "This Act may be called the IT Act.\n\n"
                        "Section 2 Definitions\n"
                        "Definitions apply here."
                    ),
                )
            ],
        )
        builder = PageIndexBuilder()

        first = builder.build_page_index(
            parsed,
            workspace_id=str(settings.default_workspace_uuid),
            corpus_type="tier2_user",
            content_hash="abc123",
        )
        second = builder.build_page_index(
            parsed,
            workspace_id=str(settings.default_workspace_uuid),
            corpus_type="tier2_user",
            content_hash="abc123",
        )

        self.assertEqual(first.document_id, second.document_id)
        self.assertEqual(first.document_version, second.document_version)
        self.assertEqual(
            [chunk.chunk_id for chunk in first.chunks],
            [chunk.chunk_id for chunk in second.chunks],
        )
        self.assertEqual(first.chunks[0].page_number, 7)
        self.assertIn("Chapter I - PRELIMINARY", first.chunks[0].heading_path)
        self.assertEqual(first.chunks[0].section_label, "1")
        self.assertEqual(first.chunks[0].metadata["document_id"], first.document_id)
        self.assertEqual(
            first.chunks[0].metadata["document_version"],
            first.document_version,
        )
        self.assertEqual(first.chunks[0].metadata["corpus_type"], "tier2_user")
    def test_page_index_preserves_page_numbers_for_cross_page_sections(self):
        parsed = ParsedDocument(
            filename="multi-page.txt",
            mime_type="text/plain",
            pages=[
                ParsedPage(
                    page_number=1,
                    text="Section 5 Duties\nFirst page duty text.",
                ),
                ParsedPage(
                    page_number=2,
                    text="Second page duty text continues same section.",
                ),
            ],
        )

        page_index = PageIndexBuilder().build_page_index(
            parsed,
            workspace_id=str(settings.default_workspace_uuid),
            corpus_type="tier2_user",
            content_hash="cross-page",
        )

        self.assertEqual([chunk.page_number for chunk in page_index.chunks], [1, 2])
        self.assertTrue(
            all(chunk.section_label == "5" for chunk in page_index.chunks)
        )


    def test_ingestion_service_persists_page_index_without_session_binding(self):
        try:
            check_database_connection()
        except Exception as exc:
            self.skipTest(f"PostgreSQL is not available: {exc}")

        run_migrations()

        old_upload_root = settings.UPLOAD_ROOT
        settings.UPLOAD_ROOT = str(Path(self.test_dir) / "uploads")
        source_path = Path(self.test_dir) / "stage2-live-ingest.txt"
        source_path.write_text(
            "Section 10 Access\nPersistent upload text.",
            encoding="utf-8",
        )

        SessionLocal = get_session_factory()
        page_index = None
        try:
            with SessionLocal() as session:
                page_index = IngestionService(session).ingest_file(
                    source_path,
                    filename="stage2-live-ingest.txt",
                    workspace_id=uuid.uuid4(),
                )

                stored_upload = (
                    session.query(Upload)
                    .filter(Upload.document_id == uuid.UUID(page_index.document_id))
                    .one()
                )
                stored_chunk = (
                    session.query(Chunk)
                    .filter(
                        Chunk.document_version_id
                        == uuid.UUID(page_index.document_version)
                    )
                    .one()
                )

                self.assertIsNone(stored_upload.session_id)
                self.assertEqual(stored_chunk.page_number, 1)
                self.assertEqual(stored_chunk.section_label, "10")
                self.assertIn("source_filename", stored_chunk.metadata_json)
        finally:
            settings.UPLOAD_ROOT = old_upload_root
            if page_index is not None:
                document_id = uuid.UUID(page_index.document_id)
                version_id = uuid.UUID(page_index.document_version)
                with SessionLocal() as session:
                    self._delete_document_graph(session, document_id, version_id)
                    session.commit()

    def test_upload_route_accepts_txt_without_legacy_vector_write(self):
        try:
            check_database_connection()
        except Exception as exc:
            self.skipTest(f"PostgreSQL is not available: {exc}")

        run_migrations()

        from app.main import app

        filename = "stage2-route-upload.txt"
        old_upload_root = settings.UPLOAD_ROOT
        old_chroma_enabled = settings.CHROMA_LEGACY_ENABLED
        settings.UPLOAD_ROOT = str(Path(self.test_dir) / "route-uploads")
        settings.CHROMA_LEGACY_ENABLED = False

        SessionLocal = get_session_factory()
        try:
            client = TestClient(app)
            response = client.post(
                "/upload",
                data={"session_id": "route-test-session"},
                files={
                    "file": (
                        filename,
                        b"Section 99 Route\nUploaded route text.",
                        "text/plain",
                    )
                },
            )

            payload = response.json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["filename"], filename)
            self.assertGreaterEqual(payload["chunks_added"], 1)
        finally:
            settings.UPLOAD_ROOT = old_upload_root
            settings.CHROMA_LEGACY_ENABLED = old_chroma_enabled
            with SessionLocal() as session:
                documents = (
                    session.query(Document)
                    .filter(Document.source_filename == filename)
                    .all()
                )
                for document in documents:
                    version_ids = [
                        row.id
                        for row in session.query(DocumentVersion.id)
                        .filter(DocumentVersion.document_id == document.id)
                        .all()
                    ]
                    for version_id in version_ids:
                        session.execute(
                            delete(Chunk).where(
                                Chunk.document_version_id == version_id
                            )
                        )
                    session.execute(delete(Upload).where(Upload.document_id == document.id))
                    session.execute(
                        delete(DocumentVersion).where(
                            DocumentVersion.document_id == document.id
                        )
                    )
                    session.execute(delete(Document).where(Document.id == document.id))
                session.commit()

    @staticmethod
    def _delete_document_graph(session, document_id, version_id):
        session.execute(delete(Chunk).where(Chunk.document_version_id == version_id))
        session.execute(delete(Upload).where(Upload.document_id == document_id))
        session.execute(delete(DocumentVersion).where(DocumentVersion.id == version_id))
        session.execute(delete(Document).where(Document.id == document_id))


if __name__ == "__main__":
    unittest.main()
