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
                    injection_score REAL,
                    retrieval_hits INTEGER,
                    citations_used INTEGER,
                    validation_pass_fail TEXT,
                    model_tier_used TEXT,
                    latency_ms REAL,
                    hash TEXT NOT NULL,
                    prev_hash TEXT NOT NULL
                )
            """)
            conn.commit()
            
            # Migration check for existing DB missing new columns
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(audit_logs)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            
            new_cols = {
                "injection_score": "REAL",
                "retrieval_hits": "INTEGER",
                "citations_used": "INTEGER",
                "validation_pass_fail": "TEXT",
                "model_tier_used": "TEXT",
                "latency_ms": "REAL"
            }
            for col_name, col_type in new_cols.items():
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE audit_logs ADD COLUMN {col_name} {col_type}")
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

    def log(
        self,
        action: str,
        layer: Optional[str] = None,
        injection_score: Optional[float] = None,
        retrieval_hits: Optional[int] = None,
        citations_used: Optional[int] = None,
        validation_pass_fail: Optional[str] = None,
        model_tier_used: Optional[str] = None,
        latency_ms: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Logs an action, computes cryptographic hash chaining across telemetry metrics, and inserts it.
        """
        ts = datetime.utcnow().isoformat() + "Z"
        prev_hash = self.get_latest_hash()
        
        layer_str = str(layer) if layer else "null"
        inj_str = f"{injection_score:.4f}" if injection_score is not None else "null"
        hits_str = str(retrieval_hits) if retrieval_hits is not None else "null"
        cites_str = str(citations_used) if citations_used is not None else "null"
        val_str = str(validation_pass_fail) if validation_pass_fail else "null"
        tier_str = str(model_tier_used) if model_tier_used else "null"
        lat_str = f"{latency_ms:.2f}" if latency_ms is not None else "null"

        hash_input = f"{ts}|{action}|{layer_str}|{inj_str}|{hits_str}|{cites_str}|{val_str}|{tier_str}|{lat_str}|{prev_hash}"
        current_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (
                    ts, action, layer, injection_score, retrieval_hits, 
                    citations_used, validation_pass_fail, model_tier_used, 
                    latency_ms, hash, prev_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts, action, layer, injection_score, retrieval_hits,
                    citations_used, validation_pass_fail, model_tier_used,
                    latency_ms, current_hash, prev_hash
                )
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
            cursor.execute("""
                SELECT ts, action, layer, injection_score, retrieval_hits, 
                       citations_used, validation_pass_fail, model_tier_used, 
                       latency_ms, hash, prev_hash 
                FROM audit_logs ORDER BY id ASC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def verify_chain(self) -> bool:
        """
        Verifies the cryptographic integrity of the entire audit log chain.
        """
        rows = self.fetch_all()
        expected_prev_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        
        for row in rows:
            if row["prev_hash"] != expected_prev_hash:
                return False
                
            layer_str = str(row["layer"]) if row["layer"] else "null"
            inj_str = f"{row['injection_score']:.4f}" if row.get('injection_score') is not None else "null"
            hits_str = str(row['retrieval_hits']) if row.get('retrieval_hits') is not None else "null"
            cites_str = str(row['citations_used']) if row.get('citations_used') is not None else "null"
            val_str = str(row['validation_pass_fail']) if row.get('validation_pass_fail') else "null"
            tier_str = str(row['model_tier_used']) if row.get('model_tier_used') else "null"
            lat_str = f"{row['latency_ms']:.2f}" if row.get('latency_ms') is not None else "null"

            hash_input = f"{row['ts']}|{row['action']}|{layer_str}|{inj_str}|{hits_str}|{cites_str}|{val_str}|{tier_str}|{lat_str}|{row['prev_hash']}"
            computed_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
            
            if row["hash"] != computed_hash:
                return False
                
            expected_prev_hash = row["hash"]
            
        return True

