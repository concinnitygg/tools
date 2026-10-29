"""ab: compare the checkout against a snapshot taken before a change.

Builds the snapshot and the checkout, then runs each world's benchmark on both
sides in turn (base, after, base, after, ...) so drift in machine state lands
on both alike. Every run also saves the frame drawn `--at` seconds in. The
result is the image score of the two sides' first frames and the median of
each side's whole-run frame costs, written to `ab.json`.
"""

import json
import statistics

from .. import common, image, launch, report, repo, snapshot, verdict

NAME = "ab"

BASE = "base"
AFTER = "after"
SIDES = (BASE, AFTER)

# The whole-run figures compared, from the report's phase table.
METRICS = ("p50_ms", "p99_ms", "cpu_ms", "gpu_ms")

DEFAULT_AT = 4.0
DEFAULT_REPEATS = 2


def add_parser(sub):
    parser = sub.add_parser(NAME, help="compare the checkout against a snapshot", description=__doc__)
    common.add_launch(parser)
    common.add_binary(parser)
    parser.add_argument("--base", required=True, help="the snapshot to compare against")
    parser.add_argument("--at", type=float, default=DEFAULT_AT, help="seconds into the run to capture")
    parser.add_argument("--stop-at", type=float, help="cut each run this many seconds in")
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS, help="runs per side and world")
    parser.set_defaults(run=run)


def shot_name(world, repeat):
    return f"{world.stem}-{repeat}.png"


def launch_for(world, binary, out, opts, repeat):
    return launch.Launch(
        binary=binary,
        world=world,
        out=out,
        stop_at=opts.stop_at,
        shots=[(opts.at, shot_name(world, repeat))],
        graphics_api=opts.api,
        graphics_quality=opts.quality,
        validation=False,
        flags=opts.flags,
        log_name=f"{world.stem}-{repeat}.log",
        timeout=opts.timeout,
    )


def perf(reports):
    """Each metric's median over the whole-run rows of `reports`, or None
    when none has one."""
    rows = [row for r in reports if r and (row := report.phase(r)) is not None]
    if not rows:
        return None
    return {m: statistics.median(row[m] for row in rows) for m in METRICS}


def change(base, after):
    """`{metric: (base, after, percent change)}`; the percentage is None
    from a zero base."""
    out = {}
    for m in METRICS:
        b, a = base[m], after[m]
        out[m] = (b, a, None if b == 0 else (a - b) / b * 100.0)
    return out


def format_change(world, changes):
    lines = []
    for m, (b, a, pct) in changes.items():
        moved = "n/a" if pct is None else f"{pct:+.1f}%"
        lines.append(f"{world:20s} {m:8s} {b:9.2f} {a:9.2f} {moved:>8s}")
    return lines


def run(opts):
    checkout = repo.root(opts.repo)
    worlds = common.worlds(opts.worlds)
    tree = snapshot.existing(checkout, opts.base)
    out = common.out_dir(opts, checkout, NAME)
    binaries = {
        BASE: repo.build(tree, repo.scratch(checkout, "target", opts.base), out / "base-build.log"),
        AFTER: common.current_binary(opts, checkout),
    }
    cwds = {BASE: common.run_cwd(checkout, f"base-{opts.base}"), AFTER: common.run_cwd(checkout, "current")}
    codes, results = [], {}
    for world in worlds:
        reports = {side: [] for side in SIDES}
        for repeat in range(1, opts.repeats + 1):
            for side in SIDES:
                outcome = launch.run(launch_for(world, binaries[side], out / side, opts, repeat), cwds[side])
                verdict.say(f"{side}: {launch.describe(outcome)}")
                found = launch.problems(outcome, measured=True)
                codes.append(common.report_problems(f"{world.stem} {side}", found))
                reports[side].append(outcome.report)
        first = shot_name(world, 1)
        shots = [out / side / first for side in SIDES]
        score = image.score(*shots) if all(p.is_file() for p in shots) else None
        medians = {side: perf(reports[side]) for side in SIDES}
        changes = change(medians[BASE], medians[AFTER]) if all(medians.values()) else None
        results[world.stem] = {"image": score, "perf": changes, "reports": reports}

    verdict.say(f"A/B against snapshot {opts.base}, {opts.repeats} run(s) a side, medians:")
    verdict.say(f"{'world':20s} {'metric':8s} {'base':>9s} {'after':>9s} {'change':>8s}")
    for name, result in results.items():
        for line in format_change(name, result["perf"]) if result["perf"] else [f"{name:20s} no perf"]:
            verdict.say(line)
        verdict.say(f"{name:20s} image    {image.describe(result['image'])}")
    path = out / "ab.json"
    path.write_text(json.dumps(results, indent=2) + "\n")
    verdict.say(f"results: {path}; frames under {out / BASE} and {out / AFTER}")
    return verdict.worst(codes)
