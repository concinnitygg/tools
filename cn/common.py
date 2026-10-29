"""Options and steps the commands share."""

from pathlib import Path

from . import launch, repo, verdict

# Launch flags a command passes through untouched follow this on the command line.
PASSTHROUGH = "--"


def split_passthrough(argv):
    """`(tool arguments, launch flags)`: everything after the first `--` goes to `cn`."""
    if PASSTHROUGH not in argv:
        return list(argv), []
    at = argv.index(PASSTHROUGH)
    return list(argv[:at]), list(argv[at + 1:])


def add_repo(parser):
    parser.add_argument("--repo", type=Path, help="engine checkout (default: the one the cwd is in)")


def add_launch(parser):
    add_repo(parser)
    parser.add_argument("worlds", nargs="+", type=Path, help="world JSONL files")
    parser.add_argument("--api", help="graphics API (default: the platform's native one)")
    parser.add_argument("--quality", help="graphics-quality preset")
    parser.add_argument("--out", type=Path, help="output directory (default: tmp/cn/<command>)")
    parser.add_argument("--timeout", type=float, default=launch.TIMEOUT, help="hard cap per launch, seconds")


def add_binary(parser):
    parser.add_argument(
        "--bin",
        type=Path,
        help="the binary to run (default: target/debug/concinnity, built first)",
    )


def worlds(paths):
    """The worlds to run, resolved, each with a distinct file stem."""
    resolved = []
    for path in paths:
        if not path.is_file():
            raise verdict.Precondition(f"no world file {path}")
        resolved.append(path.resolve())
    stems = [p.stem for p in resolved]
    if len(set(stems)) != len(stems):
        raise verdict.Precondition("two worlds share a file name; outputs are named by it")
    return resolved


def out_dir(opts, checkout, command):
    return (opts.out or repo.scratch(checkout, command)).resolve()


def run_cwd(checkout, side):
    """The working directory a side's launches share."""
    return launch.prepare_cwd(checkout, repo.scratch(checkout, "cwd", side))


def current_binary(opts, checkout):
    """The binary a command runs: the one named, or this checkout's, built now."""
    if opts.bin is not None:
        return opts.bin.resolve()
    return repo.build(checkout, checkout / "target", repo.scratch(checkout, "build.log"))


def report_problems(name, found):
    """Print a run's problems and return the code they end with."""
    for code, text in found:
        verdict.say(f"  {name}: {verdict.MEANING[code].split()[0]} {text}")
    return verdict.worst(code for code, _ in found)
