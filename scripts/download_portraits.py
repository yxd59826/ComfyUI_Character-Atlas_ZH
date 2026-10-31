"""Download the public Chinese portrait catalogue and its referenced images.

Existing files are kept, so interrupted downloads can be resumed safely.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "library"
BASE = "https://raw.githubusercontent.com/anhao/ai-pose-gallery-zh/main/"
USER_AGENT = "ComfyUI-Character-Atlas-ZH/1.0"


def download(relative: str, timeout: int = 60) -> str:
    destination = LIBRARY / relative
    if destination.is_file() and destination.stat().st_size:
        return "cached"
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(BASE + relative, headers={"User-Agent": USER_AGENT})
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, temporary.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        os.replace(temporary, destination)
        return "downloaded"
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()
    download("data/portrait-zh.json")
    try:
        download("data/portrait-meta-zh.json")
    except Exception as exc:
        print(f"Optional metadata: {exc}")
    if args.metadata_only:
        print("Portrait metadata ready.")
        return
    rows = json.loads((LIBRARY / "data" / "portrait-zh.json").read_text(encoding="utf-8-sig"))
    paths = sorted({row[key] for row in rows for key in ("原图", "缩略图", "全身图") if row.get(key)})
    print(f"Portrait assets: {len(paths)} files; existing files are skipped.", flush=True)
    counts = {"downloaded": 0, "cached": 0}
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(download, path): path for path in paths}
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            path = futures[future]
            try:
                counts[future.result()] += 1
            except Exception as exc:
                failures.append((path, str(exc)))
            if index % 100 == 0 or index == len(paths):
                print(f"{index}/{len(paths)}; failed={len(failures)}", flush=True)
    (LIBRARY / "download-failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Done: {counts}; failed={len(failures)}", flush=True)
    if failures:
        raise SystemExit("Some downloads failed; run this command again to resume.")


if __name__ == "__main__":
    main()
