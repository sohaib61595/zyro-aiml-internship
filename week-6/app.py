"""
ZYROO Platform - Main Application Entrypoint
Delegates execution to the UI Studio located in ui/app.py
"""
import os
import sys
import runpy

_base_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.join(_base_dir, "src")
_ui_dir = os.path.join(_base_dir, "ui")

for d in [_src_dir, _ui_dir, _base_dir]:
    if d not in sys.path:
        sys.path.insert(0, d)

app_path = os.path.join(_ui_dir, "app.py")
runpy.run_path(app_path, run_name="__main__")
