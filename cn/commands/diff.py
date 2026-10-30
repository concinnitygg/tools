"""diff: score PNG captures against each other.

Takes two files, or two directories whose same-named PNGs are paired. Prints
the RMSE (0..1), the pixels that changed by more than noise, and the largest
channel difference. Launches made by these tools hide the stats HUD unless
given `--hud`, so their captures carry no stat chips to leave out.
"""

from pathlib import Path

from .. import image, verdict

NAME = "diff"


def add_parser(sub):
    parser = sub.add_parser(NAME, help="score PNG captures against each other", description=__doc__)
    parser.add_argument("a", type=Path)
    parser.add_argument("b", type=Path)
    parser.add_argument(
        "--skip-rows",
        type=int,
        default=0,
        help="rows at the top left out, for captures that show the stat HUD (default %(default)s)",
    )
    parser.set_defaults(run=run)


def pairs(a, b):
    """`(name, a file, b file)` for what `a` and `b` have in common."""
    if a.is_file() and b.is_file():
        return [(a.name, a, b)]
    if a.is_dir() and b.is_dir():
        names = sorted({p.name for p in a.glob("*.png")} & {p.name for p in b.glob("*.png")})
        return [(name, a / name, b / name) for name in names]
    raise verdict.Precondition("compare two PNG files or two directories")


def run(opts):
    found = pairs(opts.a, opts.b)
    if not found:
        raise verdict.Precondition("no PNG name in common")
    for name, a, b in found:
        verdict.say(f"{name:28s} {image.describe(image.score(a, b, opts.skip_rows))}")
