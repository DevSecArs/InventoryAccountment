"""Публикация резервных копий только после успешного завершения pg_dump."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("fail_dump", [False, True])
def test_backup_publication(tmp_path: Path, fail_dump: bool) -> None:
    binaries = tmp_path / "bin"
    binaries.mkdir()
    commands = {
        "psql": "printf 'example_revision\\n'\n",
        "date": "printf '20260101T000000Z\\n'\n",
        "pg_restore": "exit 0\n",
        "pg_dump": (
            "if [ \"$1\" = --version ]; then echo 'pg_dump (PostgreSQL) 16.4'; exit 0; fi\n"
            'for arg in "$@"; do case "$arg" in --file=*) file=${arg#--file=};; esac; done\n'
            "printf 'example dump' > \"$file\"\n"
            f"exit {1 if fail_dump else 0}\n"
        ),
    }
    for name, body in commands.items():
        command = binaries / name
        command.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        command.chmod(0o700)
    directory = tmp_path / "backup directory"
    environment = os.environ | {
        "PATH": f"{binaries}{os.pathsep}{os.environ['PATH']}",
        "PGDATABASE": "example_test",
    }
    for _ in range(2):
        result = subprocess.run(
            ["sh", str(ROOT / "scripts/backup_restore.sh"), "backup", str(directory)],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert (result.returncode != 0) == fail_dump, result.stderr
    assert not list(directory.glob(".backup-*"))
    backups = list(directory.glob("*.dump"))
    assert len(backups) == (0 if fail_dump else 2)
    for backup in backups:
        assert backup.read_text() == "example dump"
        assert Path(str(backup) + ".metadata").exists()
