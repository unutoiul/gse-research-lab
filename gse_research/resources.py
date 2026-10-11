"""How many worker processes a study may use on this machine right now.

Each study process holds the candles, the level engine state and cached 1H/4H
inputs (up to about 0.8 GB). The research PC is also someone's desktop, so the
count follows the memory actually available, not just the CPU count.
"""

from __future__ import annotations

import ctypes
import os

PER_WORKER_GB = 0.8
RESERVE_GB = 1.5
MAX_WORKERS = 16


def available_memory_gb() -> float | None:
    """Physical memory available now (free + reclaimable cache), or None if unknown."""
    try:
        if os.name == "nt":
            class Status(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            status = Status()
            status.dwLength = ctypes.sizeof(Status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return status.ullAvailPhys / 2**30
            return None
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2**30
    except (AttributeError, OSError, ValueError):
        return None


def default_workers(per_worker_gb: float = PER_WORKER_GB, reserve_gb: float = RESERVE_GB,
                    available_gb: float | None = None, cpus: int | None = None) -> int:
    """min(CPUs - 2, 16, (available memory - reserve) / per-worker memory), at least 1."""
    cpus = cpus or os.cpu_count() or 2
    by_cpu = max(1, min(MAX_WORKERS, cpus - 2))
    available_gb = available_memory_gb() if available_gb is None else available_gb
    if available_gb is None:
        return by_cpu
    return max(1, min(by_cpu, int((available_gb - reserve_gb) / per_worker_gb)))
