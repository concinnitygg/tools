"""Parse the frame report `cn bench` prints when its run ends.

The report is text for a person, so this reads only the parts a comparison
needs: the header, the phase table and the peak memory line.
"""

import re

_HEADER = re.compile(
    r"^frame report: (\d+) measured frame\(s\), (\d+) warm-up frame\(s\) dropped, budget ([\d.]+) ms"
)
_NOTHING = re.compile(r"^frame report: no frames past the")
_HIDDEN = re.compile(r"^frame report: the window was hidden, so (\d+) frame")
_INCOMPLETE = "NOTE: the run ended before its last phase did"
_TABLE = re.compile(r"^phase\s+frames\s+p50 ms")
_MEMORY = re.compile(
    r"^peak GPU memory (\d+) MiB, mean blocked-on-GPU ([\d.]+) ms, "
    r"mean (\d+) draw call\(s\) over (\d+) object\(s\)"
)

# The phase table's numeric columns, in order.
COLUMNS = ("frames", "p50_ms", "p95_ms", "p99_ms", "max_ms", "over_budget_pct", "cpu_ms", "gpu_ms")

# The row that covers the whole run.
OVERALL = "all"


def _row(line):
    """One phase row, or None for a line that is not one."""
    parts = line.split()
    if len(parts) < len(COLUMNS) + 1:
        return None
    values = parts[-len(COLUMNS):]
    values[COLUMNS.index("over_budget_pct")] = values[COLUMNS.index("over_budget_pct")].rstrip("%")
    try:
        numbers = [float(v) for v in values]
    except ValueError:
        return None
    row = {"name": " ".join(parts[: -len(COLUMNS)])}
    row.update(zip(COLUMNS, numbers))
    row["frames"] = int(row["frames"])
    return row


def parse(text):
    """The report in `text` (a whole run log), or None when it printed none."""
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if _HEADER.match(line) or _NOTHING.match(line)),
        None,
    )
    if start is None:
        return None
    report = {
        "measured": 0,
        "warmup_dropped": 0,
        "budget_ms": None,
        "completed": True,
        "hidden_frames": 0,
        "phases": [],
        "vram_peak_mib": None,
        "draw_calls": None,
    }
    header = _HEADER.match(lines[start])
    if header:
        report["measured"] = int(header.group(1))
        report["warmup_dropped"] = int(header.group(2))
        report["budget_ms"] = float(header.group(3))
    in_table = False
    for line in lines[start + 1:]:
        stripped = line.strip()
        if _INCOMPLETE in stripped:
            report["completed"] = False
        elif _TABLE.match(stripped):
            in_table = True
        elif in_table:
            row = _row(stripped) if stripped else None
            if row is None:
                in_table = False
            else:
                report["phases"].append(row)
        if (found := _MEMORY.match(stripped)) is not None:
            report["vram_peak_mib"] = int(found.group(1))
            report["draw_calls"] = int(found.group(3))
        if (found := _HIDDEN.match(stripped)) is not None:
            report["hidden_frames"] = int(found.group(1))
    return report


def phase(report, name=OVERALL):
    """The row named `name`, or None."""
    return next((p for p in report["phases"] if p["name"] == name), None)


def problem(report):
    """Why `report` measures nothing comparable, or None when it does.

    A world that never gets past the warm-up prints that it has nothing to
    measure and exits 0, and one whose window was hidden partway left frames
    out, so neither compares with another run.
    """
    if report is None:
        return "the run printed no frame report"
    if report["measured"] == 0:
        return "the report measured no frames"
    if report["hidden_frames"]:
        return f"the window was hidden for {report['hidden_frames']} measured frame(s)"
    return None
