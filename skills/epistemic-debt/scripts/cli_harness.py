#!/usr/bin/env python3
"""Shared subprocess harness for the three scripts' CLI tests.

Deliberately NOT named `test_*.py`, so `unittest discover -p "test_*.py"`
never collects it as a test module, and deliberately not an import from
`test_score.py` — that would make one test module a de-facto library whose
own tests run as a side effect of importing it, and would add a new
inter-script edge of the kind CLAUDE.md forbids.

Each test module inserts its own directory on `sys.path` before importing
this (the same pattern used for the `score`/`grasp`/`recovery` imports), so
it resolves under both invocation styles: direct
(`python3 test_score.py`) and discovery
(`python3 -m unittest discover -s skills/epistemic-debt/scripts -p "test_*.py"`).
"""
from __future__ import annotations

import subprocess
import sys


class CliHarness:
    """Mixin for `unittest.TestCase` subclasses exercising a script's CLI.

    Subclasses set `SCRIPT` (a `pathlib.Path` to the script under test) and
    inherit `_run` plus the shared malformed-stdin contract assertion.
    """

    SCRIPT = None  # each test module points this at its script

    def _run(self, stdin_text: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self.SCRIPT)],
            input=stdin_text,
            capture_output=True,
            text=True,
            # Most callers here feed deliberately malformed stdin and assert
            # on exit 1 — a non-zero exit is the expected outcome, not a
            # reason to raise.
            check=False,
        )

    def assert_malformed_stdin_contract(self, payloads) -> None:
        """All three CLIs share one failure contract: every malformed payload
        exits 1 with at least one legible line on stderr and **never** a
        traceback — the skill reads that stderr, and a stack trace buries the
        sentence saying what was wrong with the input."""
        for stdin_text in payloads:
            with self.subTest(stdin_text=stdin_text):
                proc = self._run(stdin_text)
                self.assertEqual(proc.returncode, 1)
                self.assertNotIn("Traceback", proc.stderr)
                self.assertTrue(proc.stderr.strip())
