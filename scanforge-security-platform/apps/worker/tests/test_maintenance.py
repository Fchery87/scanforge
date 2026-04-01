from pathlib import Path

from app.worker import maintenance


def test_load_env_reads_repo_env_file(monkeypatch, tmp_path: Path):
    repo_root = tmp_path / "repo"
    worker_dir = repo_root / "apps" / "worker" / "app" / "worker"
    worker_dir.mkdir(parents=True)
    env_file = repo_root / ".env"
    env_file.write_text("UPSTASH_REDIS_REST_URL=https://redis.example\n")

    loaded = {}

    def fake_load_dotenv(path, override=False):
        loaded["path"] = Path(path)
        loaded["override"] = override

    monkeypatch.setattr("dotenv.load_dotenv", fake_load_dotenv)

    maintenance._load_env(worker_dir / "maintenance.py")

    assert loaded == {
        "path": env_file,
        "override": False,
    }
