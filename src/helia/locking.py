"""Conservative local-process lock reclamation, serialized against other claimants."""

import json
import os
import socket
import sys
from pathlib import Path


def process_dead(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 87  # nonexistent PID; access denied is not dead
        kernel.CloseHandle(handle)
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


def acquire_lock(path: Path) -> None:
    guard = path.with_name(path.name + ".guard")
    try:
        guard.mkdir()
    except FileExistsError:
        raise RuntimeError(f"Lock acquisition in progress or interrupted: {guard}") from None
    try:
        if path.exists():
            try:
                owner = json.loads(path.read_text())
                dead = (isinstance(owner, dict)
                        and owner.get("host") == socket.gethostname()
                        and isinstance(owner.get("pid"), int)
                        and process_dead(owner["pid"]))
            except (ValueError, OSError):
                dead = False
            if not dead:
                raise RuntimeError(f"Run is locked; owner not verified dead: {path}")
            path.unlink()
        with path.open("x", encoding="utf-8") as stream:
            json.dump({"schema_version": 2, "host": socket.gethostname(), "pid": os.getpid()}, stream)
    finally:
        guard.rmdir()
