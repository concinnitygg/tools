import tempfile
import unittest
from pathlib import Path

from cn import common, launch, logscan, proc, verdict


def _launch(out, **kw):
    return launch.Launch(binary=Path("cn"), world=Path("/w/showcase.jsonl"), out=Path(out), **kw)


class ArgvTests(unittest.TestCase):
    def test_a_bare_launch_benches_the_world_into_its_out_dir(self):
        self.assertEqual(
            launch.argv(_launch("/o")),
            ["bench", "-f", "/w/showcase.jsonl", "--screenshots-dir", "/o", "--no-hud"],
        )

    def test_every_option_maps_to_its_flag(self):
        args = launch.argv(
            _launch(
                "/o",
                stop_at=4.5,
                shots=[(4.0, "a.png"), (6.25, "b.png")],
                graphics_api="vulkan",
                graphics_quality="ultra",
                validation=False,
                flags=["--hide-pass", "ssao"],
            )
        )
        self.assertEqual(
            args[6:],
            [
                "--stop-at", "4.5",
                "--screenshot-at", "4:a.png",
                "--screenshot-at", "6.25:b.png",
                "--graphics-api", "vulkan",
                "--graphics-quality", "ultra",
                "--no-graphics-validation",
                "--hide-pass", "ssao",
            ],
        )

    def test_the_hud_shows_only_when_asked(self):
        self.assertIn("--hud", launch.argv(_launch("/o", hud=True)))
        self.assertNotIn("--no-hud", launch.argv(_launch("/o", hud=True)))

    def test_validation_on_is_the_positive_switch(self):
        self.assertIn("--graphics-validation", launch.argv(_launch("/o", validation=True)))


class PrepareCwdTests(unittest.TestCase):
    def test_links_content_and_drops_persisted_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, cwd = Path(tmp) / "repo", Path(tmp) / "cwd"
            (repo / "assets").mkdir(parents=True)
            settings = cwd / launch.SETTINGS
            settings.parent.mkdir(parents=True)
            settings.write_text("upscaling=on")
            (cwd / ".concinnity" / "shader-cache").write_text("kept")
            launch.prepare_cwd(repo, cwd)
            self.assertTrue((cwd / "assets").is_symlink())
            self.assertFalse((cwd / "worlds").exists())
            self.assertFalse(settings.exists())
            self.assertTrue((cwd / ".concinnity" / "shader-cache").exists())
            launch.prepare_cwd(repo, cwd)
            self.assertTrue((cwd / "assets").is_symlink())


class ProblemTests(unittest.TestCase):
    def _finished(self, out, log, exit_code=0, shots=()):
        return launch.Outcome(_launch(out, shots=list(shots)), exit_code, 1.0, log)

    def test_a_clean_run_has_none(self):
        with tempfile.TemporaryDirectory() as out:
            (Path(out) / "s.png").write_bytes(b"")
            outcome = self._finished(out, "concinnity_device::metal ready\n", shots=[(4.0, "s.png")])
            self.assertEqual(launch.problems(outcome), [])

    def test_failures_are_found(self):
        log = (
            "concinnity_device::vulkan up\n"
            "[Vulkan] VUID-x object 0x1a bad\n"
            "[Vulkan] VUID-x object 0x2b bad\n"
            "thread 'main' panicked at src/x.rs:1:1\n"
        )
        with tempfile.TemporaryDirectory() as out:
            found = launch.problems(self._finished(out, log, exit_code=101, shots=[(4.0, "s.png")]))
        texts = [text for _, text in found]
        self.assertIn("exited with 101", texts)
        self.assertTrue(any(t.startswith("panic:") for t in texts))
        self.assertTrue(any(t.startswith("validation x2:") for t in texts))
        self.assertIn("no screenshot s.png", texts)
        self.assertTrue(all(code == verdict.FAIL for code, _ in found))

    def test_an_unmeasured_run_is_inconclusive_only_when_asked(self):
        with tempfile.TemporaryDirectory() as out:
            outcome = self._finished(out, "no report\n")
            self.assertEqual(launch.problems(outcome), [])
            self.assertEqual(launch.problems(outcome, measured=True)[0][0], verdict.INCONCLUSIVE)


class LogscanTests(unittest.TestCase):
    def test_backend_and_layer_proof(self):
        log = "concinnity_device::vulkan init\nvulkan validation layer: enabled\n"
        self.assertEqual(logscan.detect_backend(log), logscan.VULKAN)
        self.assertTrue(logscan.layer_loaded(log, logscan.VULKAN))
        self.assertIsNone(logscan.layer_loaded(log, logscan.UNKNOWN))

    def test_known_exit_noise_is_not_a_finding(self):
        log = "[Vulkan] vkCmdBlitImage on a presented image\n"
        self.assertEqual(logscan.findings(log, logscan.VULKAN), [])

    def test_collapse_groups_by_shape(self):
        ranked = logscan.collapse(["[Vulkan] bad 0x1", "[Vulkan] bad 0x2", "[Vulkan] other"])
        self.assertEqual(ranked[0], (2, "bad ADDR"))


class ProcTests(unittest.TestCase):
    def test_the_mcp_bridge_is_not_a_client(self):
        self.assertFalse(proc.is_client("/bin/concinnity mcp --debug-port 8777"))
        self.assertTrue(proc.is_client("/bin/concinnity bench -f w.jsonl"))


class CommonTests(unittest.TestCase):
    def test_flags_after_the_separator_pass_through(self):
        self.assertEqual(
            common.split_passthrough(["capture", "w.jsonl", "--", "--hide-pass", "ssao"]),
            (["capture", "w.jsonl"], ["--hide-pass", "ssao"]),
        )
        self.assertEqual(common.split_passthrough(["bench", "w"]), (["bench", "w"], []))

    def test_worlds_must_exist_and_have_distinct_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a" / "w.jsonl", Path(tmp) / "b" / "w.jsonl"
            for p in (a, b):
                p.parent.mkdir()
                p.write_text("")
            self.assertEqual(common.worlds([a]), [a.resolve()])
            with self.assertRaises(verdict.Precondition):
                common.worlds([a, b])
            with self.assertRaises(verdict.Precondition):
                common.worlds([Path(tmp) / "missing.jsonl"])


if __name__ == "__main__":
    unittest.main()
