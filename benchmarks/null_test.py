#!/usr/bin/env python3
"""Null-test and Signal-to-Distortion Ratio (SDR) verifier for VocalPro audio quality gates (N2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf


def null_test_and_sdr(ref_path: str | Path, cand_path: str | Path) -> dict[str, float]:
    """Compare candidate audio against golden reference audio (Spec Section 14.1)."""
    a, sr_a = sf.read(str(ref_path), always_2d=True, dtype="float64")
    b, sr_b = sf.read(str(cand_path), always_2d=True, dtype="float64")
    assert sr_a == sr_b, f"Sample rate mismatch: {sr_a} vs {sr_b}"
    assert a.shape == b.shape, f"Shape mismatch: {a.shape} vs {b.shape}"
    diff = a - b
    rms_diff_db = float(20.0 * np.log10(np.sqrt(np.mean(diff**2)) + 1e-12))
    sig_pow = float(np.sum(a**2))
    err_pow = float(np.sum(diff**2) + 1e-12)
    sdr_db = float(10.0 * np.log10(sig_pow / err_pow))
    max_abs_diff = float(np.max(np.abs(diff)))
    passed = (rms_diff_db < -60.0) or (sdr_db >= 60.0)
    return {
        "rms_diff_db": round(rms_diff_db, 2),
        "sdr_db": round(sdr_db, 2),
        "max_abs_diff": max_abs_diff,
        "passed": passed,
    }


if __name__ == "__main__":
    if len(sys.argv) == 3:
        res = null_test_and_sdr(sys.argv[1], sys.argv[2])
        print(json.dumps(res, indent=2))
        sys.exit(0 if res["passed"] else 1)
    print("Usage: null_test.py <ref.wav> <cand.wav>")
    sys.exit(1)
