"""capture: one settled frame of each world, with the run's log checked.

Runs each world's benchmark until just past `--at`, saving the frame drawn
`--at` seconds in as `<world>.png`. The run fails on a nonzero exit, a panic,
an engine assertion, any validation-layer message, or a missing screenshot.
"""

from .. import common, launch, repo, verdict

NAME = "capture"

# Seconds into the run the frame is taken: past the benchmark's warm-up, with
# temporal history and exposure settled.
DEFAULT_AT = 4.0

# How long the run goes on after the shot, so the shot lands before it stops.
STOP_MARGIN = 0.5


def add_parser(sub):
    parser = sub.add_parser(NAME, help="screenshot each world and check its log", description=__doc__)
    common.add_launch(parser)
    common.add_binary(parser)
    parser.add_argument("--at", type=float, default=DEFAULT_AT, help="seconds into the run to capture")
    parser.add_argument(
        "--no-validation",
        dest="validation",
        action="store_false",
        default=None,
        help="turn the graphics validation layer off (default: the build's default)",
    )
    parser.set_defaults(run=run)


def launch_for(world, binary, out, opts):
    return launch.Launch(
        binary=binary,
        world=world,
        out=out,
        stop_at=opts.at + STOP_MARGIN,
        shots=[(opts.at, f"{world.stem}.png")],
        graphics_api=opts.api,
        graphics_quality=opts.quality,
        validation=opts.validation,
        flags=opts.flags,
        log_name=f"{world.stem}.log",
        timeout=opts.timeout,
    )


def run(opts):
    checkout = repo.root(opts.repo)
    worlds = common.worlds(opts.worlds)
    binary = common.current_binary(opts, checkout)
    out = common.out_dir(opts, checkout, NAME)
    cwd = common.run_cwd(checkout, "current")
    codes = []
    for world in worlds:
        outcome = launch.run(launch_for(world, binary, out, opts), cwd)
        verdict.say(launch.describe(outcome))
        code = common.report_problems(world.stem, launch.problems(outcome))
        if code == verdict.PASS:
            verdict.say(f"  {world.stem}: {out / (world.stem + '.png')}")
        codes.append(code)
    return verdict.worst(codes)
