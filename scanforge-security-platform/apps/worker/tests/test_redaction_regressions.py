from app.services.scan_orchestrator import ScanOrchestrator


def test_redact_sensitive_text_removes_full_basic_auth_header():
    orchestrator = ScanOrchestrator(queue=None, r2=None)
    redacted = orchestrator._redact_sensitive_text(
        "git clone failed: Authorization: Basic ZXhhbXBsZTpzZWNyZXQ= request rejected"
    )

    assert "ZXhhbXBsZTpzZWNyZXQ=" not in redacted
    assert "Authorization: Basic [REDACTED]" in redacted


def test_redact_payload_scrubs_credential_fields_and_known_secrets():
    """R08: structured log / cleanup-receipt payloads must not carry credentials."""
    import json

    from app.security.redaction import redact_payload

    payload = {
        "scan_id": "scan-123",
        "receipt": {
            "containers_removed": ["scanforge-scanner-trivy-x1"],
            "temp_dirs": ["/tmp/scan_repo_abc123"],  # noqa: S108
            "error": (
                "clone failed: fatal: unable to access "
                "'https://x-access-token:ghp_R08TOKENVALUE@github.com/org/repo.git/'"
            ),
            "presigned_url": (
                "https://s3.example.com/bucket/scan-artifacts/o/s/scanner/out.json"
                "?X-Amz-Signature=r08signaturevalue&X-Amz-Credential=AKIAEXAMPLE%2F20260913"
            ),
            "worker_credential": "r08-worker-credential-value",
            "metadata": {"api_key": "sk-r08-not-for-scanners", "attempts": 2},
        },
    }
    redacted = redact_payload(payload, known_secrets=("r08-worker-credential-value",))
    text = json.dumps(redacted)

    assert "r08-worker-credential-value" not in text
    assert "ghp_R08TOKENVALUE" not in text
    assert "r08signaturevalue" not in text
    assert "AKIAEXAMPLE" not in text
    assert "sk-r08-not-for-scanners" not in text
    # safe receipt fields survive
    assert redacted["receipt"]["containers_removed"] == ["scanforge-scanner-trivy-x1"]
    assert redacted["receipt"]["metadata"]["attempts"] == 2
    assert redacted["receipt"]["error"].count("[REDACTED]") >= 1
    assert "[REDACTED]" in redacted["receipt"]["presigned_url"]
