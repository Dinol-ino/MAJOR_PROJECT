from app.services.response_parser import unsupported_section_mentions as f

EV = [{"act": "IPC", "section": "420", "text": "Cheating. See also section 415."},
      {"act": "IPC", "section": "Section 379", "text": "Theft."}]


def test_supported_sections_pass():
    assert f("Section 420 and section 415 apply; s. 379 too.", EV) == []


def test_invented_section_flagged_once():
    assert f("Section 999 applies. Also section 999 and Section 420.", EV) == ["999"]


def test_no_evidence_is_not_this_checks_job():
    assert f("Section 999", []) == []
