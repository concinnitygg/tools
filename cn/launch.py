"""One guarded `cn bench` launch, and what its log says about it.

Every world is run through its benchmark, which ends by itself, so a launch is
a process that runs to completion under a hard timeout: never stacked on
another client, force-killed and verified dead on every exit path.

Each launch runs in a working directory of its own with the repository's
content directories linked in. The directory keeps its shader and pipeline
caches between launches, but never its persisted settings, which would
otherwise beat the world and the launch flags without a word in the log.
"""

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import fs, logscan, proc, report, verdict

# Repository directories a world names its files under, relative to the cwd.
LINKED = ("assets", "worlds", "examples")

# What a run persists from one launch to the next under its cwd.
SETTINGS = Path(".concinnity") / "settings"

# The first launch bakes a 4K HDRI and compiles every pipeline cold, so the cap
# is generous: the failures it guards against are hangs, not slow starts.
TIMEOUT = 900.0


@dataclass
class Launch:
    binary: Path
    world: Path
    out: Path
    stop_at: float = None
    # (seconds, file name) pairs, written under `out`.
    shots: list = field(default_factory=list)
    graphics_api: str = None
    graphics_quality: str = None
    validation: bool = None
    # Whether the stats HUD shows. Off by default: captures stay comparable and
    # frames are timed without it.
    hud: bool = False
    # Further launch flags, passed through as given.
    flags: list = field(default_factory=list)
    log_name: str = "run.log"
    timeout: float = TIMEOUT

    @property
    def log_path(self):
        return Path(self.out) / self.log_name


@dataclass
class Outcome:
    launch: Launch
    exit_code: int
    seconds: float
    log: str

    @property
    def backend(self):
        return logscan.detect_backend(self.log)

    @property
    def report(self):
        return report.parse(self.log)


def seconds_arg(seconds):
    return f"{seconds:g}"


def argv(launch):
    """The `cn` arguments `launch` runs with."""
    args = ["bench", "-f", str(launch.world), "--screenshots-dir", str(launch.out)]
    args.append("--hud" if launch.hud else "--no-hud")
    if launch.stop_at is not None:
        args += ["--stop-at", seconds_arg(launch.stop_at)]
    for seconds, name in launch.shots:
        args += ["--screenshot-at", f"{seconds_arg(seconds)}:{name}"]
    if launch.graphics_api is not None:
        args += ["--graphics-api", launch.graphics_api]
    if launch.graphics_quality is not None:
        args += ["--graphics-quality", launch.graphics_quality]
    if launch.validation is not None:
        args.append("--graphics-validation" if launch.validation else "--no-graphics-validation")
    return args + list(launch.flags)


def prepare_cwd(repo, cwd):
    """Make `cwd` ready for a launch: content linked in, no persisted settings."""
    cwd = Path(cwd)
    cwd.mkdir(parents=True, exist_ok=True)
    for name in LINKED:
        source = Path(repo) / name
        if source.is_dir():
            fs.link_dir(source, cwd / name)
    settings = cwd / SETTINGS
    if settings.is_dir():
        shutil.rmtree(settings)
    elif settings.exists():
        settings.unlink()
    return cwd


def run(launch, cwd):
    """Run `launch` to its end in `cwd`. Raises on a stall or a wedged client."""
    proc.require_executable(launch.binary)
    proc.require_free(launch.binary)
    for _, name in launch.shots:
        (Path(launch.out) / name).unlink(missing_ok=True)
    verdict.say(f"launching {launch.binary} {' '.join(argv(launch))}")
    started = time.monotonic()
    child, handle = proc.launch(launch.binary, argv(launch), cwd, launch.log_path)
    stalled = False
    try:
        child.wait(timeout=launch.timeout)
    except subprocess.TimeoutExpired:
        stalled = True
    finally:
        handle.close()
        wedged = not proc.force_kill(launch.binary)
    if wedged:
        raise verdict.ToolError("client survived SIGKILL", code=verdict.WEDGED)
    if stalled:
        raise verdict.Stall(f"run exceeded {launch.timeout:.0f}s; log: {launch.log_path}")
    log = launch.log_path.read_text(errors="replace")
    return Outcome(launch, child.returncode, time.monotonic() - started, log)


def problems(outcome, measured=False):
    """What went wrong in a finished run, worst first, as `(code, text)` pairs.

    `measured` asks that the run's frame report measured something comparable.
    """
    found = []
    log = outcome.log
    if outcome.exit_code != 0:
        found.append((verdict.FAIL, f"exited with {outcome.exit_code}"))
    for line in logscan.panics(log)[:3]:
        found.append((verdict.FAIL, f"panic: {line.strip()}"))
    for line in logscan.assertions(log)[:3]:
        found.append((verdict.FAIL, f"assertion: {line.strip()}"))
    for count, shape in logscan.collapse(logscan.findings(log, outcome.backend), limit=5):
        found.append((verdict.FAIL, f"validation x{count}: {shape}"))
    for _, name in outcome.launch.shots:
        if not (Path(outcome.launch.out) / name).is_file():
            found.append((verdict.FAIL, f"no screenshot {name}"))
    if measured and (why := report.problem(outcome.report)) is not None:
        found.append((verdict.INCONCLUSIVE, why))
    return found


def describe(outcome):
    """One line naming what ran and on what."""
    validation = logscan.layer_loaded(outcome.log, outcome.backend)
    layer = {True: "validation on", False: "validation off", None: "validation unknown"}[validation]
    return (
        f"{Path(outcome.launch.world).name}: {outcome.backend}, {layer}, "
        f"{outcome.seconds:.0f}s, log {outcome.launch.log_path}"
    )
