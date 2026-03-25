from app.db.models.finding import Finding


def test_finding_model_exposes_detail_relationships():
    assert hasattr(Finding, "instances")
    assert hasattr(Finding, "references")
    assert hasattr(Finding, "events")
