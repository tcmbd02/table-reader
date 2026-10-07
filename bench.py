"""Speed/accuracy check for the reading step (not part of the app).

    python bench.py run   out.json --format compact|full  FILE [FILE ...]   read page 1 of each file, record timings
    python bench.py compare a.json b.json                                    speed table + cells that differ

Prints only counts and times, never cell contents (the forms hold personal data). The readings themselves are saved in
out.json: keep that file out of shared folders.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import ocr
import pages


def cells_of(record: dict):
    for r, row in enumerate(record["rows"]):
        for col, cell in row["cells"].items():
            yield (r, col), cell


def run(out: Path, fmt: str, files: list[Path]) -> None:
    ocr.OUTPUT_FORMAT = fmt
    results = []
    for f in files:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                image = pages.render_pages(f, Path(tmp))[0]
                t = time.monotonic()
                rec = ocr.read_image(image)
                wall = time.monotonic() - t
            except ocr.OcrError as exc:
                print(f"{f.name[:28]:28} FAILED [{exc.code}]")
                results.append({"file": f.name, "error": exc.code})
                continue
        cells = [c for _, c in cells_of(rec)]
        entry = {"file": f.name, "seconds": round(wall, 1), "timing": rec["timing"], "rows": len(rec["rows"]),
                 "cells": len(cells), "values": sum(c["value"] is not None for c in cells),
                 "flagged": sum(c["needs_review"] for c in cells), "turn": rec["rotated_clockwise"], "record": rec}
        results.append(entry)
        print(f"{f.name[:28]:28} {entry['seconds']:6.1f}s looks={rec['timing']['looks']} "
              f"tokens={rec['timing']['output_tokens']} rows={entry['rows']} values={entry['values']} "
              f"flagged={entry['flagged']}")
        out.write_text(json.dumps({"format": fmt, "results": results}, ensure_ascii=False), encoding="utf-8")
    ok = [r for r in results if "seconds" in r]
    if ok:
        print(f"TOTAL {sum(r['seconds'] for r in ok):.0f}s over {len(ok)} files, "
              f"{sum(sum(r['timing']['output_tokens']) for r in ok)} output tokens")


def compare(a_path: Path, b_path: Path) -> None:
    a, b = (json.loads(p.read_text(encoding="utf-8")) for p in (a_path, b_path))
    print(f"A = {a['format']}   B = {b['format']}")
    tot = {"sa": 0, "sb": 0, "same": 0, "diff": 0, "a_only_flag": 0, "b_only_flag": 0, "shape": 0}
    for ra, rb in zip(a["results"], b["results"]):
        if "seconds" not in ra or "seconds" not in rb:
            print(f"{ra['file'][:28]:28} skipped (a failure in one run)")
            continue
        tot["sa"] += ra["seconds"]
        tot["sb"] += rb["seconds"]
        ca, cb = dict(cells_of(ra["record"])), dict(cells_of(rb["record"]))
        same = diff = fa = fb = 0
        for key in ca.keys() & cb.keys():
            x, y = ca[key], cb[key]
            if x["needs_review"] and not y["needs_review"]:
                fa += 1
            elif y["needs_review"] and not x["needs_review"]:
                fb += 1
            elif not x["needs_review"] and x["value"] != y["value"]:
                diff += 1
            else:
                same += 1
        shape = len(ca.keys() ^ cb.keys())
        print(f"{ra['file'][:28]:28} A {ra['seconds']:5.1f}s  B {rb['seconds']:5.1f}s  "
              f"rows {ra['rows']}/{rb['rows']}  agree={same} values-differ={diff} flagged-only-in-A={fa} "
              f"flagged-only-in-B={fb} cells-in-one-only={shape}")
        for k, v in (("same", same), ("diff", diff), ("a_only_flag", fa), ("b_only_flag", fb), ("shape", shape)):
            tot[k] += v
    print(f"TOTAL time A {tot['sa']:.0f}s  B {tot['sb']:.0f}s   agree={tot['same']} values-differ={tot['diff']} "
          f"flagged-only-in-A={tot['a_only_flag']} flagged-only-in-B={tot['b_only_flag']} "
          f"cells-in-one-only={tot['shape']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("out", type=Path)
    r.add_argument("--format", choices=["compact", "full"], required=True)
    r.add_argument("files", nargs="+", type=Path)
    c = sub.add_parser("compare")
    c.add_argument("a", type=Path)
    c.add_argument("b", type=Path)
    args = ap.parse_args()
    if args.cmd == "run":
        run(args.out, args.format, args.files)
    else:
        compare(args.a, args.b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
