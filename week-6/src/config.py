"""
ZYROO INTERNSHIP PROGRAM - WEEK 6
Module: Centralized Configuration & Environment Settings
Focus: Enterprise integration, security, optimization, and deployment readiness
"""

import os
from pathlib import Path
from typing import Set

# Base directories for Week 6
SRC_DIR = Path(__file__).resolve().parent
BASE_DIR = SRC_DIR.parent

# ------------------------------------------------------------------------------
# 1. Database & Storage Paths
# ------------------------------------------------------------------------------
DEFAULT_DB_FILE = os.getenv("ZYROO_DB_FILE", "workflow_repository.db")
DEFAULT_DB_PATH = str(BASE_DIR / DEFAULT_DB_FILE)

STORAGE_DIR = str(BASE_DIR / os.getenv("ZYROO_STORAGE_DIR", "storage"))
MODELS_DIR = str(BASE_DIR / "models")
SAMPLES_DIR = str(BASE_DIR / "samples")

# ------------------------------------------------------------------------------
# 2. Security & Input Limits
# ------------------------------------------------------------------------------
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("ZYROO_MAX_FILE_SIZE_BYTES", 25 * 1024 * 1024))  # 25 MB
ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
ALLOWED_MIME_TYPES: Set[str] = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
    "image/bmp"
}

# Role-Based Access Control (RBAC)
ROLE_ADMIN = "Admin"
ROLE_REVIEWER = "Reviewer"
ROLE_VIEWER = "Viewer"
VALID_ROLES = [ROLE_ADMIN, ROLE_REVIEWER, ROLE_VIEWER]

# Secret Token for API Authentication (Optional guardrail)
API_SECRET_KEY = os.getenv("ZYROO_API_SECRET", "zyroo-doc-intel-prod-secret-2026")

# ------------------------------------------------------------------------------
# 3. ML & Workflow Operational Thresholds
# ------------------------------------------------------------------------------
# Classification confidence threshold for automated completion (Task 4)
CLASSIFIER_CONFIDENCE_THRESHOLD = float(os.getenv("ZYROO_CONFIDENCE_THRESHOLD", "0.75"))

# High-value invoice policy threshold (routes to review)
HIGH_VALUE_INVOICE_THRESHOLD = float(os.getenv("ZYROO_HIGH_VALUE_THRESHOLD", "10000.0"))

# Financial arithmetic mismatch tolerance (cents/rounding)
ARITHMETIC_TOLERANCE = float(os.getenv("ZYROO_ARITHMETIC_TOLERANCE", "0.05"))

# Minimum character length for valid digital extraction before OCR/Review flag
MIN_TEXT_LENGTH_FOR_EXTRACTION = 20

# ------------------------------------------------------------------------------
# 4. RAG & AI Assistant Settings
# ------------------------------------------------------------------------------
RAG_CHUNK_SIZE = int(os.getenv("ZYROO_RAG_CHUNK_SIZE", "350"))
RAG_CHUNK_OVERLAP = int(os.getenv("ZYROO_RAG_CHUNK_OVERLAP", "60"))
RAG_TOP_K = int(os.getenv("ZYROO_RAG_TOP_K", "4"))
RAG_MIN_SIMILARITY_SCORE = float(os.getenv("ZYROO_RAG_MIN_SIMILARITY", "0.15"))

# Optional External LLM Integration (OpenAI, Groq, Gemini)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ------------------------------------------------------------------------------
# 5. Logging & Diagnostics
# ------------------------------------------------------------------------------
LOG_LEVEL = os.getenv("ZYROO_LOG_LEVEL", "INFO")
ENABLE_PROFILING = os.getenv("ZYROO_ENABLE_PROFILING", "true").lower() == "true"
