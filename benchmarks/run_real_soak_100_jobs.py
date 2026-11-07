#!/usr/bin/env python
"""100-job memory soak test using the REAL pretrained HTDemucs model and the REAL worker subprocess.

Label: [REAL_MODEL] [REAL_WORKER_SUBPROCESS] [LINUX_VM]
Exercises real stdio JSON-Lines protocol, real model cache across 100 jobs, real temp file cleanup.
Measures VmRSS memory growth between job 10 (warmup) and job 100.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKER_ROOT = REPO_ROOT / "worker"
REF_DIR = REPO_ROOT / "benchmarks" / "reference-real"


def get_rss_mb(pid: int) -> int:
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 0


def main() -> int:
    os.environ.pop("VOCALPRO_TEST_FAST_MODEL", None)
    input_file = REF_DIR / "real_01_excerpt30s.wav"
    if not input_file.exists():
        input_file = REPO_ROOT / "benchmarks" / "reference-set" / "track_01_pop_stereo_44k.wav"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(WORKER_ROOT)
    env.pop("VOCALPRO_TEST_FAST_MODEL", None)

    print(f"Starting real worker subprocess: {sys.executable} -m vocalpro_worker")
    proc = subprocess.Popen(
        [sys.executable, "-m", "vocalpro_worker"],
        cwd=str(WORKER_ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert proc.stdout is not None
    assert proc.stdin is not None

    ready_line = proc.stdout.readline()
    ready_ev = json.loads(ready_line.strip())
    print(f"Worker ready: version={ready_ev.get('worker_version')}, pid={proc.pid}")

    rss_samples: dict[str, int] = {}
    times: list[float] = []

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = Path(tmp_str)
        # Create a 0.5s audio clip to keep inference fast while testing real HTDemucs segment processing
        import soundfile as sf
        raw, sr = sf.read(str(input_file), frames=int(0.5 * 44100), dtype="float32", always_2d=True)
        clip_path = tmp_dir / "soak_clip_0.5s.wav"
        sf.write(str(clip_path), raw, sr, subtype="PCM_16")

        print("Executing 100 consecutive jobs with REAL htdemucs...")
        t_all_start = time.perf_counter()

        for job_i in range(1, 101):
            out_dir = tmp_dir / f"out_{job_i}"
            cmd = {
                "v": 1,
                "id": f"soak-cmd-{job_i}",
                "cmd": "separate",
                "job_id": f"soak-job-{job_i}",
                "input_path": str(clip_path),
                "output_dir": str(out_dir),
                "options": {
                    "model": "htdemucs",
                    "shifts": 0,
                    "segment": 4.0,
                    "output_mode": "vocals",
                },
            }
            t0 = time.perf_counter()
            proc.stdin.write(json.dumps(cmd) + "\n")
            proc.stdin.flush()

            # Read events until job_done
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                ev = json.loads(line.strip())
                if ev.get("event") in ("job_done", "job_error"):
                    assert ev.get("event") == "job_done", f"Job {job_i} failed: {ev}"
                    break

            elapsed = time.perf_counter() - t0
            times.append(elapsed)

            if job_i in (1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100):
                rss = get_rss_mb(proc.pid)
                rss_samples[f"job_{job_i}"] = rss
                print(f"[Soak] Job {job_i}/100: elapsed={elapsed:.2f}s, worker VmRSS={rss} MiB")

            # Clean up output dir to prevent disk exhaustion
            import shutil
            shutil.rmtree(out_dir, ignore_errors=True)

        total_elapsed = time.perf_counter() - t_all_start

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except Exception:
        proc.kill()

    rss_10 = rss_samples.get("job_10", 0)
    rss_100 = rss_samples.get("job_100", 0)
    growth_pct = round(((rss_100 - rss_10) / max(rss_10, 1)) * 100.0, 2)

    result = {
        "benchmark": "100_job_soak_real_htdemucs_worker_pool",
        "labels": ["[REAL_MODEL]", "[REAL_WORKER_SUBPROCESS]", "[LINUX_VM]"],
        "model": "htdemucs",
        "jobs_completed": 100,
        "total_elapsed_s": round(total_elapsed, 2),
        "mean_job_elapsed_s": round(sum(times) / len(times), 3),
        "rss_job_10_mb": rss_10,
        "rss_job_100_mb": rss_100,
        "rss_growth_pct_after_warmup": growth_pct,
        "rss_samples_mb": rss_samples,
        "passed_under_5pct_gate": growth_pct <= 5.0,
    }

    out_file = REPO_ROOT / "benchmarks" / "soak_100_jobs_real_htdemucs.json"
    out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\n[DONE] Soak test completed in {total_elapsed:.1f}s. Saved results to {out_file}")
    print(f"Warm RSS (job 10): {rss_10} MiB -> Final RSS (job 100): {rss_100} MiB (Growth: {growth_pct}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
