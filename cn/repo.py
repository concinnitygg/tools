"""Where the engine checkout, its binary and this tool's scratch space are."""

import platform
import subprocess
from pathlib import Path

from . import verdict

# Everything the tools write lands under here, which the checkout ignores.
SCRATCH = Path("tmp") / "cn"

BINARY = "concinnity"
BUILD = ["cargo", "build", "--locked", "--all-features", "--bin", BINARY]


def find_root(start):
    """The engine checkout `start` is in, or None."""
    for path in (Path(start).resolve(), *Path(start).resolve().parents):
        if (path / "Cargo.toml").is_file() and (path / "crates" / "concinnity-engine").is_dir():
            return path
    return None


def root(given=None):
    found = find_root(given or Path.cwd())
    if found is None:
        raise verdict.Precondition(f"not inside an engine checkout: {given or Path.cwd()}")
    return found


def scratch(repo, *parts):
    return Path(repo).joinpath(SCRATCH, *parts)


def binary_in(target_dir):
    suffix = ".exe" if platform.system() == "Windows" else ""
    return Path(target_dir) / "debug" / f"{BINARY}{suffix}"


def build(tree, target_dir, log_path):
    """Build the debug binary of `tree` into `target_dir`, returning its path."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    verdict.say(f"building {tree} into {target_dir} (log {log_path})")
    with log_path.open("wb") as log:
        done = subprocess.run(
            [*BUILD, "--target-dir", str(target_dir)],
            cwd=str(tree),
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if done.returncode != 0:
        tail = "\n".join(log_path.read_text(errors="replace").splitlines()[-15:])
        raise verdict.ToolError(f"build of {tree} failed:\n{tail}")
    return binary_in(target_dir)
