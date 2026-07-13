import sqlite3
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

class AuditLogger:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    action TEXT NOT NULL,
                    layer TEXT,
                    hash TEXT NOT NULL,
                    prev_hash TEXT NOT NULL
                )
            """)
            conn.commit()

    def get_latest_hash(self) -> str:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT hash FROM audit_logs ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return row[0]
            # Genesis hash (64 zeros)
            return "0000000000000000000000000000000000000000000000000000000000000000"

    def log(self, action: str, layer: Optional[str] = None) -> Dict[str, Any]:
        """
        Logs an action, computes hash chaining, and inserts it.
        """
        ts = datetime.utcnow().isoformat() + "Z"
        prev_hash = self.get_latest_hash()
        
        # Calculate cryptographic SHA-256 hash of this record chained with the previous hash
        layer_str = str(layer) if layer else "null"
        hash_input = f"{ts}|{action}|{layer_str}|{prev_hash}"
        current_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        with sqlite3.connect(self.db_path) as conn:
            # Use parameterized query strictly to avoid SQL injection
            conn.execute(
                "INSERT INTO audit_logs (ts, action, layer, hash, prev_hash) VALUES (?, ?, ?, ?, ?)",
                (ts, action, layer, current_hash, prev_hash)
            )
            conn.commit()

        return {
            "ts": ts,
            "action": action,
            "layer": layer,
            "hash": current_hash,
            "prev_hash": prev_hash
        }

    def fetch_all(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT ts, action, layer, hash, prev_hash FROM audit_logs ORDER BY id ASC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def verify_chain(self) -> bool:
        """
        Verifies the cryptographic integrity of the entire audit log chain.
        Returns:
            bool: True if the chain is unbroken and valid, False otherwise.
        """
        rows = self.fetch_all()
        expected_prev_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        
        for row in rows:
            if row["prev_hash"] != expected_prev_hash:
                return False
                
            layer_str = str(row["layer"]) if row["layer"] else "null"
            hash_input = f"{row['ts']}|{row['action']}|{layer_str}|{row['prev_hash']}"
            computed_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
            
            if row["hash"] != computed_hash:
                return False
                
            expected_prev_hash = row["hash"]
            
        return True
