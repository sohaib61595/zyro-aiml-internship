"""
ZYROO Platform - Main Application Entrypoint
Supports running via:
  1. streamlit run app.py
  2. python app.py (automatically launches the Streamlit server & opens browser)
"""
import os
import sys

_base_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.join(_base_dir, "src")
_ui_dir = os.path.join(_base_dir, "ui")

for d in [_src_dir, _ui_dir, _base_dir]:
    if d not in sys.path:
        sys.path.insert(0, d)

from streamlit.runtime.scriptrunner import get_script_run_ctx

ui_app_file = os.path.join(_ui_dir, "app.py")

if get_script_run_ctx() is None:
    # Invoked directly with python.exe app.py -> Start Streamlit CLI runner
    from streamlit.web import cli as stcli
    sys.argv = ["streamlit", "run", ui_app_file, "--server.port", "8501"]
    sys.exit(stcli.main())
else:
    # Executed within an active Streamlit runtime context
    import runpy
    runpy.run_path(ui_app_file, run_name="__main__")
