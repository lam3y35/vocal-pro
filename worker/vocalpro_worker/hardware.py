"""Hardware auto-detection, device tier classification, and adaptive runtime optimization for VocalPro v3."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from typing import Any, Optional

import torch


@dataclass
class HardwareProfile:
    """Comprehensive snapshot of the host hardware and recommended optimization parameters."""

    os_name: str
    os_arch: str
    cpu_model: str
    physical_cores: int
    logical_cores: int
    simd_features: list[str]
    total_ram_mb: int
    available_ram_mb: int
    disk_free_gb: float
    cuda_available: bool
    mps_available: bool
    gpu_name: Optional[str]
    vram_mb: Optional[int]
    fp16_supported: bool
    device_tier: str
    tier_label: str
    recommended_device: str
    recommended_max_concurrent_jobs: int
    recommended_threads_per_job: int
    recommended_segment_s: float
    recommended_overlap: float
    recommended_shifts: int
    recommended_preset: str
    recommended_fp16: bool
    recommended_parallel_dsp: bool
    recommended_safe_mode: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _detect_cpu_model_and_simd() -> tuple[str, int, list[str]]:
    logical = os.cpu_count() or 4
    physical = max(1, logical // 2)
    cpu_model = platform.processor() or platform.machine() or "Generic CPU"
    simd: list[str] = []

    try:
        if Path("/proc/cpuinfo").exists():
            text = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="ignore")
            phys_ids = set()
            for line in text.splitlines():
                if line.startswith("model name") and ":" in line:
                    cpu_model = line.split(":", 1)[1].strip()
                elif line.startswith("cpu cores") and ":" in line:
                    try:
                        physical = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                elif line.startswith("flags") and ":" in line and not simd:
                    flags = set(line.split(":", 1)[1].strip().split())
                    for flag_name, label in [
                        ("avx512f", "AVX-512"),
                        ("avx2", "AVX2"),
                        ("avx", "AVX"),
                        ("fma", "FMA"),
                        ("sse4_2", "SSE4.2"),
                        ("neon", "NEON"),
                        ("asimd", "NEON"),
                    ]:
                        if flag_name in flags and label not in simd:
                            simd.append(label)
                elif line.startswith("processor") and ":" in line:
                    phys_ids.add(line.split(":", 1)[1].strip())
    except Exception:
        pass

    if not simd:
        arch = platform.machine().lower()
        if "arm" in arch or "aarch64" in arch:
            simd.append("NEON")
        elif "x86_64" in arch or "amd64" in arch:
            simd.append("AVX2")

    return cpu_model, max(1, min(physical, logical)), simd


from pathlib import Path


def _detect_memory_mb() -> tuple[int, int]:
    """Return (total_ram_mb, available_ram_mb) across Linux, Windows, and macOS."""
    try:
        if Path("/proc/meminfo").exists():
            mem_total_kb = 0
            mem_avail_kb = 0
            for line in Path("/proc/meminfo").read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("MemTotal:"):
                    mem_total_kb = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    mem_avail_kb = int(line.split()[1])
            if mem_total_kb > 0:
                total_mb = mem_total_kb // 1024
                avail_mb = (mem_avail_kb // 1024) if mem_avail_kb > 0 else int(total_mb * 0.7)
                return total_mb, avail_mb
    except Exception:
        pass

    if platform.system().lower() == "windows":
        try:
            proc = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json)",
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                import json

                data = json.loads(proc.stdout.strip())
                total_mb = int(data.get("TotalVisibleMemorySize", 8388608)) // 1024
                avail_mb = int(data.get("FreePhysicalMemory", 4194304)) // 1024
                return total_mb, avail_mb
        except Exception:
            pass

    return 8192, 6144


def detect_hardware_profile(target_dir: Optional[Path] = None) -> HardwareProfile:
    """Inspect CPU, RAM, Disk, and GPU hardware and compute an optimized device configuration."""
    cpu_model, physical_cores, simd_features = _detect_cpu_model_and_simd()
    logical_cores = os.cpu_count() or 4
    total_ram_mb, available_ram_mb = _detect_memory_mb()

    check_path = target_dir if (target_dir and target_dir.exists()) else Path.cwd()
    try:
        usage = shutil.disk_usage(str(check_path))
        disk_free_gb = round(usage.free / (1024.0**3), 2)
    except Exception:
        disk_free_gb = 50.0

    cuda_available = bool(torch.cuda.is_available())
    mps_available = bool(
         hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    )
    gpu_name: Optional[str] = None
    vram_mb: Optional[int] = None
    fp16_supported = False

    if cuda_available:
        try:
            gpu_name = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            vram_mb = int(props.total_memory // (1024 * 1024))
            fp16_supported = bool(props.major >= 6)
        except Exception:
            gpu_name = "NVIDIA CUDA GPU"
            vram_mb = 6144
            fp16_supported = True
    elif mps_available:
        gpu_name = "Apple Silicon Unified GPU (MPS)"
        vram_mb = int(total_ram_mb * 0.75)
        fp16_supported = True

    # Classify device tier and compute optimal defaults
    if cuda_available and (vram_mb or 0) >= 11500:
        device_tier = "ultra_gpu"
        tier_label = "Ultra Studio GPU (12GB+ VRAM)"
        rec_device = "cuda"
        rec_jobs = 3 if total_ram_mb >= 16000 else 2
        rec_threads = max(2, logical_cores // rec_jobs)
        rec_segment = 7.8
        rec_overlap = 0.25
        rec_shifts = 2
        rec_preset = "ultra"
        rec_fp16 = True
        rec_parallel_dsp = True
        rec_safe = False
    elif cuda_available and (vram_mb or 0) >= 5800:
        device_tier = "high_gpu"
        tier_label = "High-Performance GPU (6-11GB VRAM)"
        rec_device = "cuda"
        rec_jobs = 2 if total_ram_mb >= 12000 else 1
        rec_threads = max(2, logical_cores // rec_jobs)
        rec_segment = 7.8
        rec_overlap = 0.25
        rec_shifts = 1
        rec_preset = "high"
        rec_fp16 = True
        rec_parallel_dsp = True
        rec_safe = False
    elif cuda_available or mps_available:
        device_tier = "entry_gpu"
        tier_label = "Accelerated GPU / Apple Silicon"
        rec_device = "cuda" if cuda_available else "cpu"
        rec_jobs = 1
        rec_threads = max(2, logical_cores // 2)
        rec_segment = 5.0
        rec_overlap = 0.25
        rec_shifts = 1
        rec_preset = "balanced"
        rec_fp16 = fp16_supported
        rec_parallel_dsp = True
        rec_safe = False
    elif logical_cores >= 8 and total_ram_mb >= 14000:
        device_tier = "workstation_cpu"
        tier_label = f"Multi-Core Workstation CPU ({logical_cores} Threads)"
        rec_device = "cpu"
        rec_jobs = 2 if logical_cores >= 8 else 1
        rec_threads = max(2, logical_cores // rec_jobs)
        rec_segment = 7.0
        rec_overlap = 0.25
        rec_shifts = 1
        rec_preset = "balanced"
        rec_fp16 = False
        rec_parallel_dsp = True
        rec_safe = False
    elif logical_cores >= 4 and total_ram_mb >= 6000:
        device_tier = "standard_cpu"
        tier_label = f"Standard Desktop/Laptop CPU ({logical_cores} Threads)"
        rec_device = "cpu"
        rec_jobs = 1
        rec_threads = max(2, logical_cores)
        rec_segment = 6.0
        rec_overlap = 0.25
        rec_shifts = 1
        rec_preset = "balanced"
        rec_fp16 = False
        rec_parallel_dsp = True
        rec_safe = False
    else:
        device_tier = "low_resource"
        tier_label = "Low-Resource / Compact Device (Safe Mode Optimized)"
        rec_device = "cpu"
        rec_jobs = 1
        rec_threads = max(1, logical_cores)
        rec_segment = 4.0
        rec_overlap = 0.15
        rec_shifts = 0
        rec_preset = "fast"
        rec_fp16 = False
        rec_parallel_dsp = False
        rec_safe = True

    return HardwareProfile(
        os_name=platform.system(),
        os_arch=platform.machine(),
        cpu_model=cpu_model,
        physical_cores=physical_cores,
        logical_cores=logical_cores,
        simd_features=simd_features,
        total_ram_mb=total_ram_mb,
        available_ram_mb=available_ram_mb,
        disk_free_gb=disk_free_gb,
        cuda_available=cuda_available,
        mps_available=mps_available,
        gpu_name=gpu_name,
        vram_mb=vram_mb,
        fp16_supported=fp16_supported,
        device_tier=device_tier,
        tier_label=tier_label,
        recommended_device=rec_device,
        recommended_max_concurrent_jobs=rec_jobs,
        recommended_threads_per_job=rec_threads,
        recommended_segment_s=rec_segment,
        recommended_overlap=rec_overlap,
        recommended_shifts=rec_shifts,
        recommended_preset=rec_preset,
        recommended_fp16=rec_fp16,
        recommended_parallel_dsp=rec_parallel_dsp,
        recommended_safe_mode=rec_safe,
    )


def apply_runtime_hardware_tuning(
    opts: dict[str, Any],
    profile: Optional[HardwareProfile] = None,
) -> HardwareProfile:
    """Configure PyTorch threads, matmul precision, and cuDNN flags for the current process."""
    prof = profile or detect_hardware_profile()

    max_threads = int(opts.get("max_threads") or 0)
    if max_threads <= 0:
        max_threads = prof.recommended_threads_per_job

    try:
        torch.set_num_threads(max(1, max_threads))
    except Exception:
        pass

    if hasattr(torch, "set_float32_matmul_precision"):
        try:
            torch.set_float32_matmul_precision("high")
        except Exception:
            pass

    if prof.cuda_available and hasattr(torch.backends, "cudnn"):
        try:
            torch.backends.cudnn.benchmark = True
        except Exception:
            pass

    return prof
