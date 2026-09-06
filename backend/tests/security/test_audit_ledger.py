import unittest
from app.memory.audit_memory import audit_memory
from app.security.audit_ledger import audit_ledger, CryptographicAuditLedger
from app.db.engine import get_sync_session
from app.db.models import AuditEvent


class TestCryptographicAuditLedger(unittest.TestCase):

    def test_clean_chain_verification_passes(self):
        # Append two valid events
        ev1 = audit_memory.append_event(
            action="test_security_event_1",
            layer="layer1_input_guard",
            injection_score=0.1,
            validation_pass_fail="pass"
        )
        ev2 = audit_memory.append_event(
            action="test_security_event_2",
            layer="layer2_trusted_context",
            injection_score=0.2,
            validation_pass_fail="pass"
        )

        report = audit_ledger.verify_chain(start_id=ev1["id"])
        self.assertTrue(report["valid"])
        self.assertIsNone(report["broken_event_id"])
        self.assertGreaterEqual(report["total_events"], 2)

    def test_tampered_event_detected(self):
        # Append an event
        event_info = audit_memory.append_event(
            action="test_tamper_target",
            layer="layer3_output_guard",
            injection_score=0.0,
            validation_pass_fail="pass"
        )
        event_id = event_info["id"]

        try:
            # Simulate unauthorized direct database alteration of historical row
            with get_sync_session() as session:
                tampered_row = session.query(AuditEvent).filter(AuditEvent.id == event_id).first()
                if tampered_row:
                    tampered_row.action = "TAMPERED_ACTION_PAYLOAD"
                    session.commit()

            # Run verification and confirm tamper detection
            report = audit_ledger.verify_chain(start_id=event_id)
            self.assertFalse(report["valid"])
            self.assertEqual(report["broken_event_id"], event_id)
            self.assertIn("tampering", report["error_details"].lower())
        finally:
            # Clean up the tampered test row to keep shared database valid
            with get_sync_session() as session:
                row = session.query(AuditEvent).filter(AuditEvent.id == event_id).first()
                if row:
                    session.delete(row)
                    session.commit()


if __name__ == "__main__":
    unittest.main()
