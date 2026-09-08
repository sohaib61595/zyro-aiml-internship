import os
import sys
import runpy

# Ensure week-1-internship is on sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
target_dir = os.path.join(root_dir, "week-1-internship")
if target_dir not in sys.path:
    sys.path.insert(0, target_dir)

# Execute the application in week-1-internship
target_script = os.path.join(target_dir, "app.py")
runpy.run_path(target_script, run_name="__main__")
