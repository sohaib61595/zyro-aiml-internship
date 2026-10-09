"""
ZYROO Platform - Automated Test Suite Entrypoint
Delegates execution to the Quality Gate suite located in tests/test_week6.py
"""
import os
import sys
import runpy

_base_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.join(_base_dir, "src")
_tests_dir = os.path.join(_base_dir, "tests")

for d in [_src_dir, _tests_dir, _base_dir]:
    if d not in sys.path:
        sys.path.insert(0, d)

test_path = os.path.join(_tests_dir, "test_week6.py")
runpy.run_path(test_path, run_name="__main__")
