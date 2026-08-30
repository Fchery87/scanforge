from pathlib import Path


def test_runtime_dockerfiles_are_digest_pinned_and_non_root():
    root = Path(__file__).resolve().parents[3]
    for relative in ("apps/api/Dockerfile", "apps/worker/Dockerfile", "apps/worker/Dockerfile.scanners"):
        content = (root / relative).read_text()
        first_from = next(line for line in content.splitlines() if line.startswith("FROM "))
        assert "@sha256:" in first_from
        assert "REPLACE_WITH" not in first_from
        assert "USER " in content


def test_worker_compose_does_not_mount_docker_socket_or_database():
    content = (Path(__file__).resolve().parents[3] / "infra/worker/docker-compose.beta.yml").read_text()
    assert "docker.sock" not in content
    assert "DATABASE_URL" not in content
    assert "R2_ACCESS_KEY_ID" not in content
    assert "R2_SECRET_ACCESS_KEY" not in content
