"""The prediction archive: manifest, verification and zip."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "archive_predictions", Path(__file__).resolve().parents[1] / "scripts/archive_predictions.py"
)
assert SPEC and SPEC.loader
arch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(arch)


def make_results(root: Path) -> Path:
    results = root / "results"
    run = results / "e2" / "lamda" / "cell" / "abc"
    run.mkdir(parents=True)
    (run / "predictions.parquet").write_bytes(b"pred")
    (run / "run.json").write_text("{}", encoding="utf-8")
    (run / "cache.tmp").write_bytes(b"not archived")
    (results / "logs").mkdir()
    (results / "logs" / "predictions.parquet").write_bytes(b"outside the experiments")
    return results


def test_collect_takes_only_named_files_of_the_experiments(tmp_path: Path) -> None:
    results = make_results(tmp_path)
    names = [p.name for p in arch.collect(results)]
    assert names == ["predictions.parquet", "run.json"]


def test_verify_reports_changed_and_missing_files(tmp_path: Path) -> None:
    results = make_results(tmp_path)
    files = arch.collect(results)
    manifest = tmp_path / "manifest.csv"
    arch.write_manifest(arch.manifest_rows(results, files), manifest)
    assert arch.verify(results, manifest) == []
    files[0].write_bytes(b"tampered")
    files[1].unlink()
    problems = arch.verify(results, manifest)
    assert len(problems) == 2
    assert any(p.startswith("changed") for p in problems)
    assert any(p.startswith("missing") for p in problems)


def test_zip_holds_the_collected_files_under_relative_paths(tmp_path: Path) -> None:
    results = make_results(tmp_path)
    out = tmp_path / "out.zip"
    arch.write_zip(results, arch.collect(results), out)
    with zipfile.ZipFile(out) as archive:
        assert sorted(archive.namelist()) == [
            "e2/lamda/cell/abc/predictions.parquet",
            "e2/lamda/cell/abc/run.json",
        ]
