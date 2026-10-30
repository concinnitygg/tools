"""bench: run each world's benchmark and collect what its frames cost.

Runs with the validation layer off, since it costs frame time. Each run's
report is printed as `cn` wrote it and saved, parsed, to `bench.json`. A run
whose report measured nothing comparable is INCONCLUSIVE rather than a pass.
"""

import json

from .. import common, launch, report, repo, verdict

NAME = "bench"


def add_parser(sub):
    parser = sub.add_parser(NAME, help="benchmark each world", description=__doc__)
    common.add_launch(parser)
    common.add_binary(parser)
    parser.add_argument("--stop-at", type=float, help="cut each run this many seconds in")
    parser.add_argument("--repeats", type=int, default=1, help="runs per world")
    parser.set_defaults(run=run)


def launch_for(world, binary, out, opts, repeat):
    return launch.Launch(
        binary=binary,
        world=world,
        out=out,
        stop_at=opts.stop_at,
        graphics_api=opts.api,
        graphics_quality=opts.quality,
        validation=False,
        hud=opts.hud,
        flags=opts.flags,
        log_name=f"{world.stem}-{repeat}.log",
        timeout=opts.timeout,
    )


def summary(name, parsed):
    """One line for a run's whole-run row."""
    row = report.phase(parsed) if parsed else None
    if row is None:
        return f"{name}: no report"
    return (
        f"{name}: {row['frames']} frames, p50 {row['p50_ms']:.2f} ms, p99 {row['p99_ms']:.2f} ms, "
        f"cpu {row['cpu_ms']:.2f} ms, gpu {row['gpu_ms']:.2f} ms"
    )


def run(opts):
    checkout = repo.root(opts.repo)
    worlds = common.worlds(opts.worlds)
    binary = common.current_binary(opts, checkout)
    out = common.out_dir(opts, checkout, NAME)
    cwd = common.run_cwd(checkout, "current")
    results, codes = {}, []
    for world in worlds:
        runs = []
        for repeat in range(1, opts.repeats + 1):
            outcome = launch.run(launch_for(world, binary, out, opts, repeat), cwd)
            verdict.say(launch.describe(outcome))
            parsed = outcome.report
            verdict.say(f"  {summary(f'{world.stem} #{repeat}', parsed)}")
            codes.append(common.report_problems(world.stem, launch.problems(outcome, measured=True)))
            runs.append({"backend": outcome.backend, "report": parsed})
        results[world.stem] = runs
    path = out / "bench.json"
    path.write_text(json.dumps(results, indent=2) + "\n")
    verdict.say(f"reports: {path}")
    return verdict.worst(codes)
