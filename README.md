# Concinnity tools

Scripts for building and testing the engine.

## Files

| Path           | What it is                                                                           |
| -------------- | ------------------------------------------------------------------------------------ |
| `cn.py`        | Entry point for the test tools below.                                                |
| `cn/`          | Their package: the guarded launch, log and report reading, image scoring, snapshots. |
| `cn/commands/` | One module per command.                                                              |
| `cn/tests/`    | Unit tests: `python3 -m unittest discover -s cn/tests -t .`                          |

## Test tools

| Command                   | What it does                                                                                                                                                        |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `capture WORLD...`        | Saves the frame `--at` seconds in (default 4) and fails on a nonzero exit, a panic, an engine assertion, any validation message, or a missing screenshot.           |
| `bench WORLD...`          | Runs each benchmark with validation off; prints each run's whole-run row and saves the parsed reports to `bench.json`. A run that measured nothing is INCONCLUSIVE. |
| `snapshot NAME`           | Copies the files git would track to `tmp/cn/snapshots/NAME`. Take one before changing code.                                                                      |
| `ab WORLD... --base NAME` | Builds the snapshot and the checkout, alternates benchmark runs between them, and reports the image score of their frames and the change in median frame costs.     |
| `diff A B`                | Scores two PNGs, or the same-named PNGs of two directories, leaving out the stat HUD's rows.                                                                        |

Commands that run worlds build `target/debug/concinnity` first unless `--bin`
names a binary, and take `--api` and `--quality`. Any other `cn` launch flag
follows a `--`:

```
python3 cn.py capture worlds/showcase.jsonl
python3 cn.py capture worlds/showcase.jsonl --api vulkan -- --hide-pass ssao
python3 cn.py bench examples/planet/planet.jsonl --stop-at 30
python3 cn.py snapshot before
python3 cn.py ab worlds/showcase.jsonl worlds/outside.jsonl --base before
python3 cn.py diff tmp/cn/ab/base tmp/cn/ab/after
```

Exit codes: `0` pass, `1` fail, `4` inconclusive, `90` a client was already
running, `91` precondition failed, `98` hard timeout, `99` the client survived
SIGKILL.
