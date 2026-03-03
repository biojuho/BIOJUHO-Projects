# -*- coding: utf-8 -*-
import os
import shutil
import time
from pathlib import Path

src = Path("D:/AI 프로젝트")
dst = Path("I:/내 드라이브/AI-Projects-Backup")

EXCLUDE_DIRS = {
    "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".git", ".agent", ".agents", "artifacts", "cache", "chroma_db",
    "test-results", "output", "data", "ignition", "typechain-types", "coverage",
    ".hardhat", ".nyc_output", "htmlcov",
}
EXCLUDE_EXTS = {".pyc", ".log", ".db", ".sqlite", ".tmp", ".class"}
EXCLUDE_FILES = {
    ".env", "credentials.json", "token.json", "serviceAccountKey.json",
    "canva_url.txt", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "sync_log.txt",
}

copied = 0
skipped = 0
errors = 0


def copy_filtered(source: Path, dest: Path):
    global copied, skipped, errors
    dest.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.is_dir():
            if item.name in EXCLUDE_DIRS or item.name.startswith("."):
                skipped += 1
                continue
            copy_filtered(item, dest / item.name)
        else:
            if item.name in EXCLUDE_FILES or item.suffix in EXCLUDE_EXTS:
                skipped += 1
                continue
            try:
                target = dest / item.name
                # 변경된 파일만 복사 (mtime 비교)
                if target.exists():
                    src_mtime = item.stat().st_mtime
                    dst_mtime = target.stat().st_mtime
                    if abs(src_mtime - dst_mtime) < 1:
                        skipped += 1
                        continue
                shutil.copy2(item, target)
                copied += 1
            except Exception as e:
                print(f"  [SKIP] {item.name}: {e}")
                errors += 1


if __name__ == "__main__":
    print("=" * 45)
    print("  AI 프로젝트 -> Google Drive 동기화")
    print("=" * 45)
    print(f"소스: {src}")
    print(f"대상: {dst}")
    print()

    start = time.time()
    copy_filtered(src, dst)
    elapsed = round(time.time() - start, 1)

    file_count = sum(1 for _ in dst.rglob("*") if _.is_file())
    total_bytes = sum(f.stat().st_size for f in dst.rglob("*") if f.is_file())
    total_mb = round(total_bytes / 1024 / 1024, 1)

    print()
    print("=" * 45)
    print(f"  완료!")
    print(f"  복사됨  : {copied}개")
    print(f"  건너뜀  : {skipped}개")
    print(f"  오류    : {errors}개")
    print(f"  총 파일 : {file_count}개 / {total_mb} MB")
    print(f"  소요    : {elapsed}초")
    print("=" * 45)
