"""Single-instance guard, launch, and force-kill-then-verify.

A hung GPU command buffer is uninterruptible, so a leaked client is not
recoverable: every launch is guarded by "nothing of this name is running", and
every exit path force-kills and then checks the process actually died.

Lookup matches the executable name exactly rather than the command line, which
would also match this tool whenever the repository path contains the binary's
name. `cn mcp` is a stdio bridge an editor session leaves running for hours, so
it is never counted as a client and never killed.
"""

import platform
import subprocess
import time
from pathlib import Path

from . import verdict

WINDOWS = platform.system() == "Windows"

# Subcommands that run no render loop, so an instance of one is not a client.
NON_CLIENT_SUBCOMMANDS = frozenset({"mcp"})


def binary_name(binary):
    """The process name a launched `binary` shows up under."""
    return Path(binary).stem


def is_client(command_line):
    """False for a command line whose subcommand opens no window."""
    args = command_line.split()
    return not (len(args) >= 2 and args[1] in NON_CLIENT_SUBCOMMANDS)


def _windows_processes(name):
    """(pid, command line) for every `name`.exe. tasklist cannot report args."""
    out = _capture(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Get-CimInstance Win32_Process -Filter \"Name='{name}.exe'\""
            " | ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }",
        ]
    )
    found = []
    for line in out.splitlines():
        pid, _, command_line = line.partition("\t")
        if pid.strip().isdigit():
            found.append((int(pid), command_line))
    return found


def running(binary):
    """PIDs of every running client of `binary`."""
    name = binary_name(binary)
    if WINDOWS:
        return [pid for pid, cmd in _windows_processes(name) if is_client(cmd)]
    out = _capture(["pgrep", "-x", name])
    pids = [int(p) for p in out.split() if p.isdigit()]
    return [p for p in pids if is_client(_capture(["ps", "-p", str(p), "-o", "args="]))]


def force_kill(binary, budget=10.0):
    """Kill every client of this name, then verify they are gone.

    Returns True when nothing survives. False means wedged, which is the one
    condition a run must never paper over.
    """
    for pid in running(binary):
        if WINDOWS:
            _capture(["taskkill", "/F", "/T", "/PID", str(pid)])
        else:
            _capture(["kill", "-9", str(pid)])
    deadline = time.monotonic() + budget
    while time.monotonic() < deadline:
        if not running(binary):
            return True
        time.sleep(0.25)
    return not running(binary)


def require_free(binary):
    """Refuse to start while another client of `binary` runs."""
    pids = running(binary)
    if pids:
        raise verdict.AlreadyRunning(
            f"{binary_name(binary)} already running (pid {', '.join(map(str, pids))});"
            " only one client may run at a time"
        )


def require_executable(binary):
    path = Path(binary)
    if not path.is_file():
        raise verdict.Precondition(f"binary not found: {path}")
    return path


def launch(binary, args, cwd, log_path):
    """Start one client with both streams going to `log_path`.

    Returns `(process, log handle)`; the caller closes the handle.
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("wb")
    process = subprocess.Popen(
        [str(binary), *args],
        cwd=str(cwd),
        stdout=handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )
    return process, handle


def _capture(argv):
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout or ""
