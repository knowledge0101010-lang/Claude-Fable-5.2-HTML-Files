"""The regression gate: same command, before and after.

    python3 harness/regress.py --full --save-baseline   # freeze the reference
    python3 harness/regress.py                          # what changed this loop?
    python3 harness/regress.py --full                    # dense sweep

Exit code 1 on any metric that got worse, so "개선했다"는 말은 숫자로만 한다.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPORTS = ROOT / "reports"
BASELINE = REPORTS / "baseline.json"
LATEST = REPORTS / "latest.json"

METRICS = [
    # (scope, key, direction)  +1 higher is better, -1 lower is better
    ("static", "composite_mean", +1),
    ("static", "palette_perfect", +1),
    ("static", "api_perfect", +1),
    ("static", "keyboard_missing", -1),
    ("static", "reduced_motion_missing", -1),
    ("static", "external_refs", -1),
    ("static", "gallery_passed", +1),
    ("runtime", "failed", -1),
    ("runtime", "console_errors", -1),
    ("runtime", "mobile_overflow", -1),
    ("runtime", "desktop_overflow", -1),
    ("runtime", "fps_mean", +1),
]


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, **kw)


def step_originals() -> bool:
    r = run([sys.executable, "harness/manifest.py", "verify"])
    print(r.stdout.strip())
    return r.returncode == 0


def step_gallery_build() -> bool:
    r = run([sys.executable, "scripts/build_gallery.py", "--check"])
    print(r.stdout.strip())
    return r.returncode == 0


def step_schedule(full: bool, scheduler: str) -> dict:
    sys.path.insert(0, str(HERE))
    import sparse  # noqa: E402
    import spiking  # noqa: E402

    if scheduler == "spiking" and not full:
        snapshot = sparse.snapshot()
        previous = json.loads(sparse.SNAPSHOT.read_text(encoding="utf-8")) if sparse.SNAPSHOT.exists() else None
        global_event = previous is None or previous.get("harness") != sparse.harness_hash(snapshot)
        fired = spiking.step(snapshot, previous, global_event)
        stems = [n[:-5] for n in snapshot if n.endswith(".html") and n[0].isdigit()]
        p = {
            "reason": "spiking" + (" (cold start)" if global_event else ""),
            "files": snapshot,
            "studies_total": len(stems),
            "l2": fired["fired"],
            "l3": fired["fired"],
            "sparsity": round(1 - len(fired["fired"]) / max(len(stems), 1), 4),
            "runtime_targets": len(fired["fired"]) + (1 if global_event else 0),
            "gallery_l3": global_event,
            "theta_mean": fired["theta_mean"],
            "_spiking": fired,
        }
        if full:
            p["l2"] = p["l3"] = stems
        return p

    p = sparse.plan()
    if full:
        stems = sorted(n[:-5] for n in p["files"] if n.endswith(".html") and n[0].isdigit())
        p["l3"] = stems
        p["l2"] = stems
        p["sparsity"] = 0.0
        p["runtime_targets"] = len(p["l3"]) + 1
        p["reason"] = "full sweep (forced)"
    print(
        f"schedule: {p['reason']} · L2={len(p['l2'])} L3={len(p['l3'])} "
        f"skipped={p['studies_total'] - len(p['l3'])} sparsity={p['sparsity']:.0%}"
    )
    return p


def step_static(plan: dict) -> dict:
    prev = REPORTS / "static.json"
    cmd = [sys.executable, "harness/static_audit.py", str(prev)]
    if plan["reason"].startswith("incremental") and plan["l2"]:
        cmd += ["--only", ",".join(f"{s}.html" for s in plan["l2"]), "--previous", str(prev)]
    r = run(cmd)
    if r.returncode:
        print(r.stdout, r.stderr, sep="\n")
        raise SystemExit("static audit failed")
    return json.loads(prev.read_text(encoding="utf-8"))


def step_runtime(plan: dict) -> dict | None:
    targets = plan["l3"] + (["index"] if plan["gallery_l3"] else [])
    if not targets:
        p = REPORTS / "runtime.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    cmd = ["node", "harness/runtime.mjs", "--out", str(REPORTS / "runtime.json"),
           "--shots", str(REPORTS / "shots")]
    if plan["reason"].startswith("incremental") and plan["l3"]:
        cmd += ["--only", ",".join(plan["l3"])]
    r = run(cmd, timeout=1800)
    if r.returncode:
        print(r.stdout[-3000:], r.stderr[-3000:], sep="\n")
        raise SystemExit("runtime capture failed")
    return json.loads((REPORTS / "runtime.json").read_text(encoding="utf-8"))


def collect(static: dict, runtime: dict | None) -> dict:
    vals = {"static": static["summary"], "runtime": (runtime or {}).get("summary", {})}
    return {f"{scope}.{key}": vals[scope].get(key) for scope, key, _ in METRICS}


def compare(baseline: dict | None, current: dict) -> tuple[list[str], list[str], list[str]]:
    if not baseline:
        return [], [], []
    base = baseline.get("metrics", {})
    regressions, improvements, stable = [], [], []
    for scope, key, direction in METRICS:
        label = f"{scope}.{key}"
        old, new = base.get(label), current.get(label)
        if old is None or new is None:
            continue
        delta = new - old
        if direction < 0:
            delta = -delta
        if delta < -1e-9:
            regressions.append(f"{label}: {old} -> {new}")
        elif delta > 1e-9:
            improvements.append(f"{label}: {old} -> {new}")
        else:
            stable.append(label)
    return regressions, improvements, stable


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="ignore the sparse schedule")
    ap.add_argument("--no-runtime", action="store_true")
    ap.add_argument("--save-baseline", action="store_true")
    ap.add_argument("--scheduler", choices=("spiking", "sparse"), default="spiking")
    args = ap.parse_args()

    t0 = time.perf_counter()
    REPORTS.mkdir(exist_ok=True)

    originals_ok = step_originals()
    gallery_ok = step_gallery_build()
    plan = step_schedule(args.full, args.scheduler)
    static = step_static(plan)
    runtime = None if args.no_runtime else step_runtime(plan)
    metrics = collect(static, runtime)
    wall = round(time.perf_counter() - t0, 1)

    baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else None
    regressions, improvements, stable = compare(baseline, metrics)

    if plan.get("_spiking") is not None:
        import spiking  # noqa: E402

        clean = {}
        for study in static["studies"]:
            stem = study["file"][:-5]
            clean[stem] = not (
                study["palette"]["missing"]
                or study["api"]["missing"]
                or study["keyboard"]["keys"] and not study["keyboard"]["keydown"]
                or not all(study["a11y"].values())
            )
        spiking.reinforce(plan["_spiking"]["fired"], clean)

    report = {
        "builtAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "wall_seconds": wall,
        "schedule": {
            k: plan[k] for k in ("reason", "sparsity", "runtime_targets", "l3", "l2", "theta_mean") if k in plan
        },
        "originals_unchanged": originals_ok,
        "gallery_reproducible": gallery_ok,
        "metrics": metrics,
        "regressions": regressions,
        "improvements": improvements,
        "stable": stable,
        "static_summary": static["summary"],
        "runtime_summary": (runtime or {}).get("summary"),
    }
    LATEST.write_text(json.dumps(report, indent=1), encoding="utf-8")

    print(f"\n회귀 게이트 · {wall}s · 원본 불변 {'PASS' if originals_ok else 'FAIL'} · 갤러리 재현 {'PASS' if gallery_ok else 'FAIL'}")
    for line in improvements:
        print(f"  개선  {line}")
    for line in regressions:
        print(f"  회귀  {line}")
    if not baseline:
        print("  (기준선 없음)")
    elif not regressions:
        print(f"  PASS  회귀 0건 · 유지 {len(stable)}개 지표")

    if args.save_baseline:
        BASELINE.write_text(json.dumps(report, indent=1), encoding="utf-8")
        import sparse

        sparse.save(plan)
        print(f"  기준선 저장 → {BASELINE.relative_to(ROOT)}")
        return 0

    failed = (not originals_ok) or (not gallery_ok) or bool(regressions)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
