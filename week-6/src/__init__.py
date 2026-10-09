"""
ZYROO Document Intelligence & Workflow Platform - Core Engine Package
"""
import sys
import os

# Automatically ensure src directory is in sys.path for direct imports
_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
