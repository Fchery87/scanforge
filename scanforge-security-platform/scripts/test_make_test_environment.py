"""Exercise make's test environment without installing or running package suites."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MakeTestEnvironmentTests(unittest.TestCase):
    def run_make(self, database_url=None):
        with tempfile.TemporaryDirectory(prefix="scanforge-make-test-") as directory:
            root = Path(directory)
            shutil.copyfile(ROOT / "Makefile", root / "Makefile")
            (root / "apps/web").mkdir(parents=True)
            commands = root / "bin"
            commands.mkdir()
            recorder = commands / "record"
            recorder.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "with open(os.environ['COMMAND_LOG'], 'a') as log:\n"
                "    log.write(json.dumps({'args': sys.argv[1:], "
                "'database_url': os.environ.get('DATABASE_URL')}) + '\\n')\n"
            )
            recorder.chmod(0o755)
            (commands / "npm").symlink_to(recorder)
            log = root / "commands.jsonl"
            env = {key: value for key, value in os.environ.items()
                   if key not in {"DATABASE_URL", "MAKEFLAGS", "MFLAGS", "MAKELEVEL"}}
            env.update(PATH=f"{commands}:{env['PATH']}", COMMAND_LOG=str(log), PWD=str(root))
            if database_url is not None:
                env["DATABASE_URL"] = database_url
            result = subprocess.run(
                ["make", "test", f"API_PYTHON={recorder}", f"WORKER_PYTHON={recorder}"],
                cwd=root, env=env, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return [json.loads(line) for line in log.read_text().splitlines()]

    def test_unset_database_uses_test_only_in_memory_default(self):
        calls = self.run_make()
        self.assertEqual([call["args"] for call in calls], [
            ["-m", "pytest", "apps/api"], ["-m", "pytest", "apps/worker"],
            ["run", "test:node"], ["run", "test:vitest"],
        ])
        self.assertEqual([call["database_url"] for call in calls], [
            "sqlite+aiosqlite:///:memory:", "sqlite+aiosqlite:///:memory:", None, None,
        ])

    def test_explicit_database_override_is_preserved(self):
        url = "postgresql+asyncpg://fixture@localhost/owned_test_database"
        self.assertEqual([call["database_url"] for call in self.run_make(url)], [url] * 4)

    def test_empty_database_uses_in_memory_default(self):
        calls = self.run_make("")
        self.assertEqual([call["database_url"] for call in calls[:2]],
                         ["sqlite+aiosqlite:///:memory:"] * 2)


if __name__ == "__main__":
    unittest.main()
