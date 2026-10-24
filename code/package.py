"""Create code.zip (runnable solution, prompts, configuration, README, evaluation/) next to the repo root.

  python3 code/package.py
Excludes dataset/, caches, bytecode, .env and any nested archives.
"""
import zipfile
from pathlib import Path

CODE = Path(__file__).resolve().parent
OUT = CODE.parent / "code.zip"
SKIP_DIRS = {".cache", "__pycache__", "dataset", ".git"}
SKIP_SUFFIX = {".pyc", ".zip", ".env"}


def main():
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(CODE.rglob("*")):
            rel = p.relative_to(CODE)
            if p.is_dir() or SKIP_DIRS & set(rel.parts) or p.suffix in SKIP_SUFFIX:
                continue
            z.write(p, rel.as_posix())
    print("wrote", OUT)


if __name__ == "__main__":
    main()
