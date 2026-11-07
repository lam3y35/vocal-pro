#!/usr/bin/env python3
"""Automated Shipping Readiness & Non-Negotiables (N1..N9) Verification Suite for VocalPro v3.0.0."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def run_step(name: str, cmd: list[str], cwd: Path = ROOT_DIR) -> tuple[bool, float, str]:
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    elapsed = round(time.perf_counter() - t0, 2)
    out = (proc.stdout + "\n" + proc.stderr).strip()
    return proc.returncode == 0, elapsed, out


def main() -> int:
    print("=" * 78)
    print("VocalPro v3.0.0 — Pre-Release Shipping Readiness & N1..N9 Verification")
    print("=" * 78)

    checks: list[dict] = []

    # 1. Verify Python Worker + Golden Null-Test + Hardware Optimizer + Parallel DSP (N1, N2, N3, N5, N7)
    ok_py, dt_py, out_py = run_step(
        "Python Worker, Golden Null-Tests & Hardware Auto-Optimizer (pytest)",
        ["/home/antigravity/.venv/bin/pytest", "worker/tests", "-v"],
    )
    checks.append(
        {
            "name": "Python AI Worker, Golden DSP Null-Tests & Hardware Optimizer",
            "passed": ok_py,
            "elapsed_s": dt_py,
        }
    )
    print(f"[{'PASS' if ok_py else 'FAIL'}] Python Worker & Golden Null-Tests ({dt_py}s)")
    if not ok_py:
        print(out_py)

    # 2. Verify Rust Core + Multi-Process Worker Pool + Legacy Migration + Native Audio (N4, N6, N8, N9)
    ok_rs, dt_rs, out_rs = run_step(
        "Rust Core, Multi-Process Worker Pool, Symphonia Waveform & SQLite Migration (cargo test)",
        ["cargo", "test", "--manifest-path", "src-tauri/Cargo.toml"],
    )
    checks.append(
        {
            "name": "Rust Core, Multi-Process Worker Pool & SQLite Migration",
            "passed": ok_rs,
            "elapsed_s": dt_rs,
        }
    )
    print(f"[{'PASS' if ok_rs else 'FAIL'}] Rust Core & Multi-Process Pool Integration Tests ({dt_rs}s)")
    if not ok_rs:
        print(out_rs)

    # 3. Verify Frontend TypeScript Contracts & Production Vite Bundle (N1, N6, N8)
    ok_ui, dt_ui, out_ui = run_step(
        "React 19 + TypeScript Strict Typecheck & Production Bundle (pnpm build)",
        ["pnpm", "build"],
    )
    checks.append(
        {
            "name": "React 19 + TypeScript Strict Typecheck & Production Bundle",
            "passed": ok_ui,
            "elapsed_s": dt_ui,
        }
    )
    print(f"[{'PASS' if ok_ui else 'FAIL'}] Frontend TypeScript & Vite Production Build ({dt_ui}s)")
    if not ok_ui:
        print(out_ui)

    all_passed = all(c["passed"] for c in checks)
    report_path = ROOT_DIR / "benchmarks" / "baseline" / "shipping_verification.json"
    report_path.write_text(
        json.dumps(
            {
                "version": "3.0.0",
                "all_passed": all_passed,
                "checks": checks,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("=" * 78)
    print(f"OVERALL SHIPPING STATUS: {'READY FOR SHIPPING (ALL CHECKS PASSED)' if all_passed else 'FAILED'}")
    print("=" * 78)
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
