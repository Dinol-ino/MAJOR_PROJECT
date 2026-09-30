"""
Canonical storage for original vault documents.

Layering (each layer is derived from the one above; none can destroy the one above):

    original file (this module)  ->  DocumentMemory row  ->  DocumentPage text
        ->  chunks  ->  Chroma / BM25 indexes  ->  retrieval cache  ->  conversation context

Lifecycle rules enforced here:
  * A file is written atomically (temp file + fsync + rename) BEFORE its database row is
    committed, so a row never points at a missing file after a crash.
  * Nothing in this module runs as a side effect of cache eviction, re-indexing, a model
    switch or a restart. Files are removed only by ``delete_document`` / ``delete_vault``,
    which the API calls solely on an explicit user delete.
  * Identifiers are validated, and resolved paths must stay inside the storage root, so a
    crafted vault/document id cannot read or write elsewhere on the disk.
"""
import hashlib
import logging
import os
import re
import shutil
import tempfile
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,80}$")


class DocumentStoreError(Exception):
    pass


class DocumentStore:
    def __init__(self, root: Optional[str] = None):
        self._root_override = root

    @property
    def root(self) -> str:
        return os.path.abspath(self._root_override or settings.VAULT_FILES_DIR)

    @staticmethod
    def _check(identifier: str, what: str) -> str:
        if not identifier or not _SAFE_ID.match(identifier):
            raise DocumentStoreError(f"Invalid {what} identifier.")
        return identifier

    def _resolve(self, relative_path: str) -> str:
        full = os.path.abspath(os.path.join(self.root, relative_path))
        if os.path.commonpath([self.root, full]) != self.root:
            raise DocumentStoreError("Path escapes the document store.")
        return full

    def relative_path(self, vault_id: str, doc_id: str, extension: str = "pdf") -> str:
        self._check(vault_id, "vault")
        self._check(doc_id, "document")
        return f"{vault_id}/{doc_id}.{extension.lstrip('.')}"

    def save(self, vault_id: str, doc_id: str, content: bytes, extension: str = "pdf") -> str:
        """Durably writes the original bytes and returns the store-relative path."""
        rel = self.relative_path(vault_id, doc_id, extension)
        target = self._resolve(rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(target), prefix=".incoming-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, target)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return rel

    def exists(self, relative_path: Optional[str]) -> bool:
        if not relative_path:
            return False
        try:
            return os.path.isfile(self._resolve(relative_path))
        except DocumentStoreError:
            return False

    def path(self, relative_path: str) -> str:
        return self._resolve(relative_path)

    def read(self, relative_path: str) -> bytes:
        with open(self._resolve(relative_path), "rb") as fh:
            return fh.read()

    def sha256(self, relative_path: str) -> str:
        h = hashlib.sha256()
        with open(self._resolve(relative_path), "rb") as fh:
            for block in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()

    def delete_document(self, relative_path: Optional[str]) -> bool:
        """Explicit user/admin deletion of one original. Returns True if a file was removed."""
        if not relative_path:
            return False
        try:
            os.unlink(self._resolve(relative_path))
            return True
        except FileNotFoundError:
            return False
        except DocumentStoreError:
            logger.warning("Refused to delete a path outside the document store.")
            return False

    def delete_vault(self, vault_id: str) -> None:
        """Explicit hard delete of every original in a vault."""
        self._check(vault_id, "vault")
        shutil.rmtree(self._resolve(vault_id), ignore_errors=True)


document_store = DocumentStore()
