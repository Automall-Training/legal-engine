"""Windows support of legal-watch: the browser-profile lock, the command engine's URL quoting, the engine's Python
and the Windows Task Scheduler (schtasks). Runs on every system; the lock test uses the real lock of the system."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "scripts"))
from watch import fetchers as F, library as lib, schedule  # noqa: E402
import legal_watch as cli  # noqa: E402


class Lock(unittest.TestCase):
    def test_second_holder_is_refused_until_the_first_unlocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "browser.lock"
            # why: two separate opens conflict like two processes (flock and msvcrt lock per open file / handle)
            with open(path, "a+", encoding="utf-8") as first, open(path, "a+", encoding="utf-8") as second:
                self.assertTrue(F.try_lock(first))
                self.assertFalse(F.try_lock(second))
                F.unlock(first)
                self.assertTrue(F.try_lock(second))
                F.unlock(second)

    def test_lock_in_another_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "browser.lock"
            probe = ("import sys; sys.path.insert(0, sys.argv[1]); from watch import fetchers as F; "
                     "fh = open(sys.argv[2], 'a+', encoding='utf-8'); sys.exit(0 if F.try_lock(fh) else 7)")
            args = [sys.executable, "-c", probe, str(SKILL / "scripts"), str(path)]
            with open(path, "a+", encoding="utf-8") as held:
                self.assertTrue(F.try_lock(held))
                self.assertEqual(subprocess.run(args).returncode, 7)      # busy: "already running"
                F.unlock(held)
            self.assertEqual(subprocess.run(args).returncode, 0)


class QuoteUrl(unittest.TestCase):
    URL = "https://www.legis.md/cautare/getResults?doc_id=1&lang=ro"

    def test_posix_shell_quoting(self):
        self.assertEqual(F.quote_url(self.URL, windows=False), "'" + self.URL + "'")

    def test_cmd_exe_needs_double_quotes(self):
        self.assertEqual(F.quote_url(self.URL, windows=True), '"' + self.URL + '"')
        self.assertEqual(F.quote_url('https://example.org/a"b', windows=True), '"https://example.org/a%22b"')

    def test_command_output_is_read_as_utf8(self):
        seen = {}

        def run(cmd, **kw):
            seen.update(kw, cmd=cmd)
            return mock.Mock(returncode=0, stdout="# Legea nr. 1 — ș ț\n" + "x" * 50)

        F.CommandFetcher("fetch {url}", run=run, pause_range=(0, 0)).get(self.URL)
        self.assertEqual((seen["encoding"], seen["errors"]), ("utf-8", "replace"))
        self.assertIn(F.quote_url(self.URL), seen["cmd"])


class EnginePython(unittest.TestCase):
    def test_layout_per_system(self):
        root = Path("engine")
        self.assertEqual(schedule.venv_python(root, windows=True), root / ".venv" / "Scripts" / "python.exe")
        self.assertEqual(schedule.venv_python(root, windows=False), root / ".venv" / "bin" / "python")

    def test_default_kind_per_system(self):
        self.assertEqual(schedule.default_kind("darwin"), "launchd")
        self.assertEqual(schedule.default_kind("win32"), "schtasks")
        self.assertEqual(schedule.default_kind("linux"), "cron")
        self.assertEqual(cli.parser().parse_args(["schedule", "plan"]).kind, schedule.default_kind())


class Schtasks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.profile = Path(self.tmp.name) / "legal profile"   # a space: the command must quote it
        # why: a typical Windows install (C:\\Users\\<name>\\legal-engine); this checkout may sit deeper and
        # its real path would exceed the /TR limit that test_too_long_command_is_refused checks on its own.
        short = mock.patch.object(schedule, "engine_python", return_value=Path("C:/e/.venv/Scripts/python.exe"))
        short.start()
        self.addCleanup(short.stop)
        lib_skill = mock.patch.object(schedule.lib, "SKILL", Path("C:/e/skills/legal-watch"))
        lib_skill.start()
        self.addCleanup(lib_skill.stop)

    def test_plan_prints_the_exact_create_command(self):
        out = schedule.plan(self.profile, "schtasks")
        cmd = schedule.schtasks_create(self.profile)
        self.assertEqual(out["command"], subprocess.list2cmdline(cmd))
        self.assertEqual(cmd[:10], ["schtasks", "/Create", "/TN", "legal-engine-watch", "/SC", "WEEKLY",
                                    "/D", "MON", "/ST", "09:00"])
        self.assertEqual(cmd[-1], "/F")                                   # replaces, never duplicates
        tr = cmd[cmd.index("/TR") + 1]
        self.assertEqual(tr, subprocess.list2cmdline(schedule.command(self.profile)))
        self.assertIn(f'"{self.profile}"', tr)
        self.assertTrue(tr.endswith(" run"))
        self.assertIn("legal_watch.py", tr)

    def test_too_long_command_is_refused(self):
        with self.assertRaises(lib.WatchError):
            schedule.schtasks_create(Path(self.tmp.name) / ("x" * 300))

    def test_install_and_remove_on_windows(self):
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(schedule.sys, "platform", "win32"):
            self.assertEqual(schedule.install(self.profile, "schtasks", run=run)["installed"],
                             "Task Scheduler: legal-engine-watch")
            self.assertEqual(calls[0], schedule.schtasks_create(self.profile))
            self.assertTrue((self.profile / "laws" / "runs").is_dir())
            self.assertEqual(schedule.remove("schtasks", run=run)["removed"], "Task Scheduler: legal-engine-watch")
        self.assertEqual(calls[1][:2], ["schtasks", "/Query"])
        self.assertEqual(calls[2], ["schtasks", "/Delete", "/TN", "legal-engine-watch", "/F"])

    def test_remove_without_a_task_and_failures(self):
        absent = lambda cmd, **kw: mock.Mock(returncode=1, stdout="", stderr="not found")  # noqa: E731
        with mock.patch.object(schedule.sys, "platform", "win32"):
            self.assertIsNone(schedule.remove("schtasks", run=absent)["removed"])
            with self.assertRaises(lib.WatchError):
                schedule.install(self.profile, "schtasks", run=absent)

    def test_install_only_on_windows(self):
        run = mock.Mock()
        with mock.patch.object(schedule.sys, "platform", "darwin"):
            with self.assertRaises(lib.WatchError):
                schedule.install(self.profile, "schtasks", run=run)
            with self.assertRaises(lib.WatchError):
                schedule.remove("schtasks", run=run)
        run.assert_not_called()

    def test_cron_and_claude_are_removed_by_the_user(self):
        self.assertIn("crontab", schedule.remove("cron")["how"])
        self.assertIn("/schedule", schedule.remove("claude-schedule")["how"])
        with self.assertRaises(lib.WatchError):
            schedule.install(self.profile, "cron")


if __name__ == "__main__":
    unittest.main()
