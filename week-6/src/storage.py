"""
ZYROO INTERNSHIP PROGRAM - WEEK 6
Module: Secure Document Storage, SHA-256 Deduplication & Path Protection
Focus: Enterprise integration, security, optimization, and deployment readiness
"""

import os
import re
import hashlib
import unicodedata
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from datetime import datetime

import config
import database

logger = logging.getLogger("document_storage")

# Category to directory mapping
SUBDIRECTORIES = {
    "Invoice": "invoices",
    "Resume": "resumes",
    "Contract": "contracts",
    "Receipt": "invoices",
    "Other": "other"
}

# Known file signatures (magic bytes)
MAGIC_SIGNATURES = {
    ".pdf": b"%PDF",
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8",
    ".jpeg": b"\xff\xd8",
    ".tiff": (b"II*\x00", b"MM\x00*"),
    ".bmp": b"BM"
}


def ensure_storage_structure() -> None:
    """Creates the organized directory hierarchy under configured storage path."""
    os.makedirs(config.STORAGE_DIR, exist_ok=True)
    for folder in set(SUBDIRECTORIES.values()):
        target_path = os.path.join(config.STORAGE_DIR, folder)
        os.makedirs(target_path, exist_ok=True)
    quarantine_path = os.path.join(config.STORAGE_DIR, "quarantine")
    os.makedirs(quarantine_path, exist_ok=True)


def get_storage_folder(doc_type: str) -> str:
    """Returns the absolute path to the appropriate category directory."""
    folder_name = SUBDIRECTORIES.get(doc_type, "other")
    target_path = os.path.join(config.STORAGE_DIR, folder_name)
    os.makedirs(target_path, exist_ok=True)
    return target_path


def compute_file_hash(file_bytes: bytes) -> str:
    """Computes cryptographic SHA-256 hex digest of document bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def check_for_duplicate(file_hash: str, db_path: Optional[str] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Queries SQLite database to check if a document with identical hash exists.
    Returns (is_duplicate: bool, existing_document_record: Optional[Dict]).
    """
    existing = database.get_document_by_hash(file_hash, db_path=db_path)
    return (existing is not None, existing)


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes user upload filenames:
    - Strips directory traversal characters (e.g. ../, ..\\)
    - Normalizes unicode characters to ASCII
    - Replaces whitespace and dangerous symbols with underscores
    """
    base = os.path.basename(filename).strip()
    # Normalize unicode
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    name, ext = os.path.splitext(base)
    ext = ext.lower().strip()

    # Strip dangerous characters
    safe_name = re.sub(r"[^\w\-_.]", "_", name)
    safe_name = re.sub(r"_{2,}", "_", safe_name).strip("._")
    if not safe_name:
        safe_name = "document"
    return f"{safe_name}{ext}"


def is_safe_path(target_path: str, base_dir: Optional[str] = None) -> bool:
    """
    Defends against path traversal attacks:
    Ensures that resolved target_path resides strictly within base_dir.
    """
    base = Path(base_dir or config.STORAGE_DIR).resolve()
    target = Path(target_path).resolve()
    try:
        return base in target.parents or target == base
    except Exception:
        return False


def generate_safe_stored_filename(original_filename: str, file_hash: str) -> str:
    """Generates unique, timestamped, collision-proof filename."""
    sanitized = sanitize_filename(original_filename)
    name, ext = os.path.splitext(sanitized)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    hash_prefix = file_hash[:8]
    return f"{timestamp}_{hash_prefix}_{name}{ext}"


def validate_uploaded_file(filename: str, file_bytes: bytes) -> Tuple[bool, str]:
    """
    Rigorous security and integrity validation:
    1. Validates non-empty content
    2. Validates maximum file size limit
    3. Validates allowed extension
    4. Validates file header magic bytes to prevent masquerading
    """
    if not file_bytes or len(file_bytes) == 0:
        return False, "File is empty (0 bytes). Processing rejected."

    if len(file_bytes) > config.MAX_UPLOAD_SIZE_BYTES:
        size_mb = round(len(file_bytes) / (1024 * 1024), 2)
        limit_mb = round(config.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024), 2)
        return False, f"File size ({size_mb} MB) exceeds maximum allowed limit of {limit_mb} MB."

    # Validate extension
    _, ext = os.path.splitext(filename.lower().strip())
    if ext not in config.ALLOWED_EXTENSIONS:
        allowed_list = ", ".join(sorted(config.ALLOWED_EXTENSIONS))
        return False, f"Unsupported file type '{ext}'. Allowed extensions: {allowed_list}."

    # Validate file magic bytes
    if ext in MAGIC_SIGNATURES:
        expected = MAGIC_SIGNATURES[ext]
        if isinstance(expected, tuple):
            if not any(file_bytes.startswith(sig) for sig in expected):
                return False, f"Corrupted file header: Content does not match valid {ext.upper()} format."
        else:
            if not file_bytes.startswith(expected):
                return False, f"Corrupted or invalid file header: Content does not match valid {ext.upper()} format."

    return True, "File passed security and integrity validation."


def save_document_file(
    file_bytes: bytes,
    original_filename: str,
    document_type: str,
    file_hash: str
) -> Tuple[str, str]:
    """
    Persists file bytes safely to the appropriate category directory.
    Returns (stored_filename: str, absolute_stored_path: str).
    """
    ensure_storage_structure()
    target_folder = get_storage_folder(document_type)
    stored_filename = generate_safe_stored_filename(original_filename, file_hash)
    target_path = os.path.join(target_folder, stored_filename)

    # Path traversal validation guardrail
    if not is_safe_path(target_path, config.STORAGE_DIR):
        raise PermissionError(f"Security Alert: Directory traversal detected for target path '{target_path}'.")

    with open(target_path, "wb") as f:
        f.write(file_bytes)

    logger.info(f"Safely persisted {stored_filename} to {target_path}")
    return stored_filename, os.path.abspath(target_path)
