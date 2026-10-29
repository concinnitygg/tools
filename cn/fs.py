"""Directory links that work the same on every platform.

A run's cwd links the checkout's content in rather than copying it, and a
snapshot links `vendor/`. On Windows a directory link is a junction, which
needs no privilege to create.
"""

import os
import stat
from pathlib import Path

_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def is_link(path):
    path = Path(path)
    if path.is_symlink():
        return True
    if os.name != "nt":
        return False
    try:
        return bool(os.lstat(path).st_file_attributes & _REPARSE)
    except OSError:
        return False


def link_dir(source, link):
    """Point `link` at directory `source`, replacing an existing link."""
    source, link = Path(source).resolve(), Path(link)
    if is_link(link):
        unlink(link)
    elif link.exists():
        raise FileExistsError(f"{link} exists and is not a link")
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        import _winapi  # noqa: PLC0415 - Windows only

        _winapi.CreateJunction(str(source), str(link))
    else:
        os.symlink(source, link, target_is_directory=True)


def unlink(link):
    link = Path(link)
    if os.name == "nt" and not link.is_symlink():
        os.rmdir(link)
    else:
        os.unlink(link)
