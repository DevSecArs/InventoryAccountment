"""Исходники отчётов входят в образ, локальные зависимости и секреты — нет."""

import tarfile
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
from pathlib import Path

from pytest import MonkeyPatch

spec = spec_from_file_location(
    "build_test_image", Path(__file__).resolve().parents[2] / "scripts" / "build_test_image.py"
)
assert spec is not None and spec.loader is not None
build_test_image = module_from_spec(spec)
spec.loader.exec_module(build_test_image)


def test_context_preserves_report_sources_and_excludes_local_files(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    frontend = tmp_path / "frontend"
    source = frontend / "src" / "features" / "reports" / "ReportsPage.tsx"
    source.parent.mkdir(parents=True)
    source.write_text("export {};", encoding="utf-8")
    modules = frontend / "node_modules"
    modules.mkdir()
    (modules / "local-only.txt").write_text("dependency", encoding="utf-8")
    (frontend / ".env.local").write_text("TEST_ONLY=not-a-secret", encoding="utf-8")
    monkeypatch.setattr(build_test_image, "ROOT", tmp_path)
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        build_test_image.add_source(archive, frontend)
    buffer.seek(0)
    with tarfile.open(fileobj=buffer) as archive:
        assert archive.getnames() == ["frontend/src/features/reports/ReportsPage.tsx"]
