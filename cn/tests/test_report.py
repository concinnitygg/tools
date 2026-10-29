import unittest

from cn import report

LOG = """\
INFO concinnity_runtime: starting
frame report: 300 measured frame(s), 232 warm-up frame(s) dropped, budget 16.67 ms
display: 120 Hz, variable down to 24 Hz
  NOTE: the run ended before its last phase did, so this covers part of it only

phase             frames   p50 ms   p95 ms   p99 ms   max ms  over bgt   cpu ms   gpu ms
all                  300     8.45     8.83     8.96     9.11      0.0%     1.95     5.50
city street          120     9.00     9.50     9.90    10.00     12.5%     2.00     6.00

peak GPU memory 635 MiB, mean blocked-on-GPU 6.40 ms, mean 42 draw call(s) over 17 object(s)
"""


class ParseTests(unittest.TestCase):
    def test_reads_the_header_table_and_memory(self):
        parsed = report.parse(LOG)
        self.assertEqual(parsed["measured"], 300)
        self.assertEqual(parsed["warmup_dropped"], 232)
        self.assertEqual(parsed["budget_ms"], 16.67)
        self.assertFalse(parsed["completed"])
        self.assertEqual(parsed["vram_peak_mib"], 635)
        self.assertEqual(parsed["draw_calls"], 42)
        self.assertEqual([p["name"] for p in parsed["phases"]], ["all", "city street"])

    def test_a_row_keeps_every_column(self):
        row = report.phase(report.parse(LOG), "city street")
        self.assertEqual(row["frames"], 120)
        self.assertEqual(row["over_budget_pct"], 12.5)
        self.assertEqual((row["p50_ms"], row["p99_ms"], row["cpu_ms"], row["gpu_ms"]), (9.0, 9.9, 2.0, 6.0))

    def test_a_log_without_a_report_parses_to_none(self):
        self.assertIsNone(report.parse("INFO nothing here\n"))
        self.assertEqual(report.problem(None), "the run printed no frame report")

    def test_a_run_with_nothing_past_the_warm_up_is_a_problem(self):
        parsed = report.parse("frame report: no frames past the 2.0s warm-up, so there is nothing to measure\n")
        self.assertEqual(parsed["measured"], 0)
        self.assertEqual(report.problem(parsed), "the report measured no frames")

    def test_hidden_frames_are_a_problem(self):
        parsed = report.parse(LOG + "frame report: the window was hidden, so 7 frame(s) past the warm-up (run 7) were left out\n")
        self.assertEqual(parsed["hidden_frames"], 7)
        self.assertIn("hidden", report.problem(parsed))

    def test_a_complete_measured_run_has_no_problem(self):
        parsed = report.parse(LOG.replace("  NOTE: the run ended before its last phase did, so this covers part of it only\n", ""))
        self.assertTrue(parsed["completed"])
        self.assertIsNone(report.problem(parsed))


if __name__ == "__main__":
    unittest.main()
