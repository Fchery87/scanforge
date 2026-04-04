from app.services.scan_orchestrator import ScanOrchestrator


def test_redact_sensitive_text_removes_full_basic_auth_header():
    orchestrator = ScanOrchestrator(queue=None, r2=None)
    redacted = orchestrator._redact_sensitive_text(
        "git clone failed: Authorization: Basic ZXhhbXBsZTpzZWNyZXQ= request rejected"
    )

    assert "ZXhhbXBsZTpzZWNyZXQ=" not in redacted
    assert "Authorization: Basic [REDACTED]" in redacted
