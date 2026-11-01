#!/usr/bin/env python3
import ast
import subprocess
import sys
import unittest
from pathlib import Path

project = Path(__file__).resolve().parents[1]
failures = []
for path in sorted(project.rglob("*.py")):
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as error:
        failures.append(str(error))
for path in sorted(project.rglob("*.sh")):
    result = subprocess.run(["bash", "-n", path.as_posix()], text=True, capture_output=True)
    if result.returncode:
        failures.append(result.stderr)
if failures:
    print("\n".join(failures), file=sys.stderr)
    raise SystemExit(1)
print("Python AST and Bash syntax checks: OK", flush=True)
suite = unittest.TestSuite()
for directory in sorted({path.parent for path in (project / "tests").rglob("test_*.py")}):
    suite.addTests(unittest.defaultTestLoader.discover(str(directory), pattern="test_*.py", top_level_dir=str(directory)))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
