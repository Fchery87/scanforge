from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_dedicated_worker_compose_is_single_concurrency_and_secret_minimal():
    content = (ROOT / "infra/worker/docker-compose.beta.yml").read_text()
    assert "WORKER_CONCURRENCY: \"1\"" in content
    assert "APP_ENV: private-beta" in content
    assert "DATABASE_URL" not in content
    assert "R2_ACCESS_KEY_ID" not in content
    assert "R2_SECRET_ACCESS_KEY" not in content
    assert "WORKER_CREDENTIAL_PEPPER" not in content


def test_worker_config_template_excludes_api_only_secrets():
    content = (ROOT / "infra/worker/.env.example").read_text()
    assert "DATABASE_URL" not in content
    assert "R2_ACCESS_KEY_ID" not in content
    assert "R2_SECRET_ACCESS_KEY" not in content
    assert "WORKER_CREDENTIAL_PEPPER" not in content
