"""Subcommand dispatch."""

import argparse

from . import common, verdict
from .commands import ALL

DESCRIPTION = """\
Test tools for the engine, run on this machine. Every world runs through its
benchmark (`cn bench`), which ends by itself; one client runs at a time, under
a hard timeout, and is verified dead afterwards. Launch flags for `cn` follow
a `--`, e.g. `capture worlds/showcase.jsonl -- --hide-pass ssao`.
"""


def build_parser():
    parser = argparse.ArgumentParser(
        prog="cn.py",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for module in ALL:
        module.add_parser(sub)
    return parser


def parse(argv):
    own, flags = common.split_passthrough(argv)
    opts = build_parser().parse_args(own)
    opts.flags = flags
    return opts


def main(argv=None):
    import sys

    opts = parse(sys.argv[1:] if argv is None else argv)
    return verdict.main(lambda: opts.run(opts))
