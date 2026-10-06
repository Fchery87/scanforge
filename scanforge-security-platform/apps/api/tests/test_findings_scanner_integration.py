from app.db.models.finding import Finding
from app.services.secret_safety import sanitize_secret_mapping


def test_finding_model_exposes_detail_relationships():
    assert hasattr(Finding, "instances")
    assert hasattr(Finding, "references")
    assert hasattr(Finding, "events")


def test_api_secret_boundary_removes_canary_value_before_persistence():
    canary = "ghp_api_boundary_canary_987654321"
    finding = sanitize_secret_mapping(
        {
            "category": "secret",
            "description": canary,
            "instance": {
                "path": "config.py",
                "line_start": 7,
                "match": canary,
                "secret_value": canary,
            },
            "metadata_json": {"raw": canary, "rule_id": "github-token"},
        }
    )

    assert canary not in str(finding)
    assert finding["description"] == "A secret was detected by the scanner."
    assert finding["instance"] == {"path": "config.py", "line_start": 7}
    assert finding["metadata_json"] == {"rule_id": "github-token"}
