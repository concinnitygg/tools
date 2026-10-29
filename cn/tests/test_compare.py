import subprocess
import tempfile
import unittest
from pathlib import Path

from cn import image, repo, snapshot, verdict
from cn.commands import ab, diff


def _png(path, rows, width=4):
    """A gray image whose rows take the given levels."""
    pixels = b"".join(bytes([level] * width * 3) for level in rows)
    image.write_png(path, width, len(rows), 3, pixels)


class ImageTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.png"
            _png(path, [0, 128, 255])
            self.assertEqual(image.read_png(path)[:3], (4, 3, 3))
            self.assertEqual(image.read_png(path)[3][12:15], bytes([128] * 3))

    def test_identical_images_score_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.png", Path(tmp) / "b.png"
            _png(a, [10, 20])
            _png(b, [10, 20])
            self.assertEqual(image.score(a, b, 0), {"rmse": 0.0, "changed": 0, "max": 0})

    def test_noise_is_not_a_change_and_skipped_rows_do_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.png", Path(tmp) / "b.png"
            _png(a, [0, 10, 10])
            _png(b, [200, 12, 30])
            whole = image.score(a, b, 0)
            self.assertEqual((whole["changed"], whole["max"]), (8, 200))
            below = image.score(a, b, 1)
            self.assertEqual((below["changed"], below["max"]), (4, 20))

    def test_different_sizes_do_not_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.png", Path(tmp) / "b.png"
            _png(a, [0])
            _png(b, [0, 0])
            self.assertIsNone(image.score(a, b))
            self.assertEqual(image.describe(None), "sizes differ")


class DiffPairsTests(unittest.TestCase):
    def test_directories_pair_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            for d in (a, b):
                d.mkdir()
                _png(d / "same.png", [0])
            _png(a / "only.png", [0])
            self.assertEqual([name for name, _, _ in diff.pairs(a, b)], ["same.png"])
            with self.assertRaises(verdict.Precondition):
                diff.pairs(a, a / "same.png")


class AbMathTests(unittest.TestCase):
    def _report(self, p50, p99=20.0, cpu=2.0, gpu=5.0):
        row = {"name": "all", "p50_ms": p50, "p99_ms": p99, "cpu_ms": cpu, "gpu_ms": gpu}
        return {"phases": [row]}

    def test_perf_takes_each_metric_median_and_skips_missing_reports(self):
        medians = ab.perf([self._report(10.0), None, self._report(14.0), self._report(11.0)])
        self.assertEqual(medians["p50_ms"], 11.0)
        self.assertIsNone(ab.perf([None]))

    def test_change_is_a_percentage_of_the_base(self):
        base = {"p50_ms": 10.0, "p99_ms": 0.0, "cpu_ms": 2.0, "gpu_ms": 4.0}
        after = {"p50_ms": 9.0, "p99_ms": 1.0, "cpu_ms": 2.0, "gpu_ms": 5.0}
        changes = ab.change(base, after)
        self.assertAlmostEqual(changes["p50_ms"][2], -10.0)
        self.assertIsNone(changes["p99_ms"][2])
        self.assertAlmostEqual(changes["gpu_ms"][2], 25.0)
        self.assertIn("n/a", ab.format_change("w", changes)[1])


class SnapshotTests(unittest.TestCase):
    def test_reconcile_writes_only_what_differs_and_removes_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dest = Path(tmp) / "src", Path(tmp) / "dest"
            (src / "d").mkdir(parents=True)
            (src / "a.txt").write_text("a")
            (src / "d" / "b.txt").write_text("b")
            sources = {"a.txt": src / "a.txt", "d/b.txt": src / "d" / "b.txt"}
            self.assertEqual(snapshot.reconcile(sources, dest), 2)
            self.assertEqual(snapshot.reconcile(sources, dest), 0)
            (dest / "stale" / "x").parent.mkdir()
            (dest / "stale" / "x").write_text("x")
            (dest / snapshot.STAMP).write_text("t")
            (src / "a.txt").write_text("changed")
            self.assertEqual(snapshot.reconcile({"a.txt": src / "a.txt"}, dest), 1)
            self.assertEqual((dest / "a.txt").read_text(), "changed")
            self.assertFalse((dest / "d").exists())
            self.assertFalse((dest / "stale").exists())
            self.assertTrue((dest / snapshot.STAMP).exists())

    def test_tracked_files_skip_ignored_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkout = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            (checkout / ".gitignore").write_text("/tmp/\n")
            (checkout / "tmp").mkdir()
            (checkout / "tmp" / "x").write_text("x")
            (checkout / "kept.rs").write_text("")
            self.assertEqual(snapshot.tracked_files(checkout), [".gitignore", "kept.rs"])

    def test_names_are_checked(self):
        with self.assertRaises(verdict.Precondition):
            snapshot.path(Path("/r"), "../escape")
        with self.assertRaises(verdict.Precondition):
            snapshot.existing(Path("/nonexistent-checkout"), "never-taken")


class RepoTests(unittest.TestCase):
    def test_finds_the_checkout_from_inside_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "crates" / "concinnity-engine" / "src").mkdir(parents=True)
            (root / "Cargo.toml").write_text("")
            self.assertEqual(repo.find_root(root / "crates" / "concinnity-engine" / "src"), root)
            self.assertIsNone(repo.find_root(root.parent))


if __name__ == "__main__":
    unittest.main()
