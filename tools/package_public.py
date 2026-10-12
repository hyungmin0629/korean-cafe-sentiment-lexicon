"""Package an allowlist of authored public files, excluding raw reviews."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ("src", "lexicon", "configs", "schemas", "examples", "docs", "tests", "tools")
FILES = ("README.md", "LICENSE", "CHANGELOG.md", ".gitignore", "pyproject.toml", "run.py", "requirements-crawl.txt")


def main():
    candidates = [ROOT / name for name in FILES]
    for directory in DIRECTORIES:
        candidates.extend(path for path in (ROOT / directory).rglob("*") if path.is_file()
                          and "__pycache__" not in path.parts
                          and not any(part.endswith(".egg-info") for part in path.parts)
                          and path.suffix not in (".pyc", ".pyo"))
    paths = sorted(set(candidates))
    if any(not path.is_file() for path in paths):
        raise ValueError("Missing required public file")
    destination = ROOT / "outputs_private/cafe-sentiment-lexicon-v0.1.0.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = []
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            relative = path.relative_to(ROOT).as_posix()
            assert not relative.startswith(("data_private/", "outputs_private/"))
            archive.write(path, relative)
            manifest.append({"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (destination.parent / "public_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"archive": str(destination), "files": len(paths)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
