"""Exit codes, the tagged log line, and the one verdict line a command ends with."""

import sys

PASS = 0
FAIL = 1
INCONCLUSIVE = 4
ALREADY_RUNNING = 90
PRECONDITION = 91
STALL = 98
WEDGED = 99

MEANING = {
    PASS: "PASS",
    FAIL: "FAIL",
    INCONCLUSIVE: "INCONCLUSIVE (the run did not measure what it claims to)",
    ALREADY_RUNNING: "ABORT (a client is already running; runs never stack)",
    PRECONDITION: "ABORT (precondition failed)",
    STALL: "STALL (hard timeout)",
    WEDGED: "DANGER (client survived SIGKILL)",
}


def say(message):
    print(f"[cn.py] {message}", flush=True)


def verdict(code, detail=""):
    """Print the single line a caller can grep for, and return the code."""
    text = MEANING.get(code, f"FAIL (rc={code})")
    say(f"VERDICT: {text}{': ' + detail if detail else ''}")
    if code == WEDGED:
        say("The client is wedged in an uninterruptible GPU wait. Do not launch")
        say("another run until it is cleared; a reboot may be needed.")
    return code


def worst(codes):
    """The code a set of results ends with: any failure outranks a pass."""
    codes = [c for c in codes if c != PASS]
    return max(codes) if codes else PASS


class ToolError(Exception):
    """A failure carrying the exit code it should end with."""

    code = FAIL

    def __init__(self, message, code=None):
        super().__init__(message)
        if code is not None:
            self.code = code


class Precondition(ToolError):
    code = PRECONDITION


class AlreadyRunning(ToolError):
    code = ALREADY_RUNNING


class Stall(ToolError):
    code = STALL


def main(fn):
    """Run a command body, turning any ToolError into its verdict line.

    An unexpected exception is a tool bug, not a finding, so it prints its
    traceback and exits FAIL rather than reading as a clean result.
    """
    try:
        code = fn()
    except ToolError as e:
        return verdict(e.code, str(e))
    except KeyboardInterrupt:
        return verdict(STALL, "interrupted")
    except Exception:  # noqa: BLE001 - a tool bug must not read as a finding
        import traceback

        traceback.print_exc()
        return verdict(FAIL, "the tool raised an unexpected exception (see traceback)")
    return verdict(PASS if code is None else code)


def run(fn):
    sys.exit(main(fn))
