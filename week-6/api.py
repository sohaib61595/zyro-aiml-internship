"""
ZYROO Platform - Production FastAPI Backend Entrypoint
Exposes app instance from src/api.py for Uvicorn
"""
import os
import sys

_base_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.join(_base_dir, "src")
for d in [_src_dir, _base_dir]:
    if d not in sys.path:
        sys.path.insert(0, d)

from api import app
