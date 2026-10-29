"""Copies of the checkout taken before a change, to build the A/B baseline from.

A snapshot holds the files git would track (tracked plus untracked files that
are not ignored), so uncommitted work is part of it. Taking one again rewrites
only the files that differ, which keeps cargo's view of what changed exact.
"""

import filecmp
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from . import fs, repo, verdict

STAMP = ".snapshot"
NAME = re.compile(r"^[A-Za-z0-9._-]+$")

# Ignored directories a snapshot's build needs, linked from the checkout.
SHARED = ("vendor",)


def path(checkout, name):
    if not NAME.match(name) or name in (".", ".."):
        raise verdict.Precondition(f"not a snapshot name: {name!r} (letters, digits, '.', '_', '-')")
    return repo.scratch(checkout, "snapshots", name)


def tracked_files(checkout):
    """Checkout-relative paths of the files git would track."""
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=str(checkout),
        capture_output=True,
        check=True,
    ).stdout
    names = sorted({n for n in out.decode().split("\0") if n})
    return [n for n in names if (Path(checkout) / n).is_file()]


def reconcile(sources, dest):
    """Make `dest` hold exactly `sources` (relative name to source path),
    writing only the files that differ. Returns how many it wrote.

    Links in `dest` are left alone, since they are the shared directories.
    """
    dest = Path(dest)
    written = 0
    for name, source in sources.items():
        target = dest / name
        if target.is_file() and filecmp.cmp(source, target, shallow=False):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        shutil.copymode(source, target)
        written += 1
    for dirpath, _, filenames in os.walk(dest, topdown=False):
        here = Path(dirpath)
        for name in filenames:
            rel = (here / name).relative_to(dest).as_posix()
            if rel not in sources and rel != STAMP:
                (here / name).unlink()
        if here != dest and not fs.is_link(here) and not any(here.iterdir()):
            here.rmdir()
    return written


def take(checkout, name):
    """Snapshot the checkout as `name`. Returns the snapshot's path."""
    dest = path(checkout, name)
    files = tracked_files(checkout)
    written = reconcile({f: Path(checkout) / f for f in files}, dest)
    for shared in SHARED:
        if (Path(checkout) / shared).is_dir():
            fs.link_dir(Path(checkout) / shared, dest / shared)
    (dest / STAMP).write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
    verdict.say(f"snapshot {name}: {len(files)} files, {written} written, in {dest}")
    return dest


def existing(checkout, name):
    """The path of snapshot `name`, which must have been taken."""
    dest = path(checkout, name)
    if not (dest / STAMP).is_file():
        raise verdict.Precondition(f"no snapshot {name!r}; take one before changing code")
    taken = (dest / STAMP).read_text().strip()
    verdict.say(f"base: snapshot {name}, taken {taken}")
    return dest
