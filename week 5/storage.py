"""
ZYROO INTERNSHIP PROGRAM - WEEK 5
Module: File Storage & Duplicate Detection Engine
Focus: Workflow automation, validation, review and auditability

Capabilities:
- Organized hierarchical file storage by category (invoices, resumes, other).
- Cryptographic SHA-256 content hashing for guaranteed uniqueness and duplicate prevention.
- Sanitized, collision-proof filename generation preserving original extensions.
- Upload validation against file size limits and unauthorized extensions.
- Safe file writes and deletions with comprehensive error handling.
"""

import os
import re
import hashlib
import unicodedata
from typing import Dict, Any, Tuple, Optional
from datetime import datetime

import database

# File constraints
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

# Base storage path inside week 5 directory
STORAGE_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage")

SUBDIRECTORIES = {
    "Invoice": "invoices",
    "Resume": "resumes",
    "Other": "other"
}


def ensure_storage_structure() -> None:
    """Creates the organized directory hierarchy if it does not already exist."""
    os.makedirs(STORAGE_BASE_DIR, exist_ok=True)
    for folder in SUBDIRECTORIES.values():
        target_path = os.path.join(STORAGE_BASE_DIR, folder)
        os.makedirs(target_path, exist_ok=True)


def get_storage_folder(doc_type: str) -> str:
    """Returns the absolute path to the appropriate category directory."""
    folder_name = SUBDIRECTORIES.get(doc_type, "other")
    target_path = os.path.join(STORAGE_BASE_DIR, folder_name)
    os.makedirs(target_path, exist_ok=True)
    return target_path


def compute_file_hash(file_bytes: bytes) -> str:
    """
    Computes cryptographic SHA-256 hex digest of file bytes.
    Used for tamper-proofing and instant duplicate identification.
    """
    return hashlib.sha256(file_bytes).hexdigest()


def check_for_duplicate(file_hash: str, db_path: Optional[str] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Queries SQLite database to check if a document with the exact SHA-256 hash already exists.
    Returns (is_duplicate, existing_document_record).
    """
    existing = database.get_document_by_hash(file_hash, db_path=db_path)
    return (existing is not None, existing)


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes user upload filenames:
    - Strips directory traversal characters (e.g. ../)
    - Normalizes unicode characters to ASCII
    - Replaces whitespace and special symbols with underscores
    """
    base = os.path.basename(filename).strip()
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    name, ext = os.path.splitext(base)
    ext = ext.lower().strip()
    
    safe_name = re.sub(r"[^\w\-_.]", "_", name)
    safe_name = re.sub(r"_{2,}", "_", safe_name).strip("._")
    if not safe_name:
        safe_name = "document"
    return f"{safe_name}{ext}"


def generate_safe_stored_filename(original_filename: str, file_hash: str) -> str:
    """
    Generates a unique stored filename:
    Format: YYYYMMDD_HHMMSS_<hash_prefix8>_<sanitized_name>.<ext>
    """
    sanitized = sanitize_filename(original_filename)
    name, ext = os.path.splitext(sanitized)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    hash_prefix = file_hash[:8]
    return f"{timestamp}_{hash_prefix}_{name}{ext}"


def validate_uploaded_file(filename: str, file_bytes: bytes) -> Tuple[bool, str]:
    """
    Validates uploaded file against extension and size constraints.
    """
    if not filename or not filename.strip():
        return False, "File must have a valid filename."
    
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
    
    size = len(file_bytes)
    if size == 0:
        return False, "Uploaded file is completely empty (0 bytes)."
    if size > MAX_UPLOAD_SIZE_BYTES:
        mb = round(size / (1024 * 1024), 2)
        return False, f"File size ({mb} MB) exceeds maximum limit of 20 MB."

    return True, "File successfully validated."


def save_document_file(
    file_bytes: bytes,
    original_filename: str,
    document_type: str,
    file_hash: str
) -> Tuple[str, str]:
    """
    Saves document binary to the organized category folder on disk.
    
    Returns:
        (stored_filename, absolute_file_path)
    """
    ensure_storage_structure()
    target_folder = get_storage_folder(document_type)
    stored_filename = generate_safe_stored_filename(original_filename, file_hash)
    stored_path = os.path.join(target_folder, stored_filename)

    with open(stored_path, "wb") as f:
        f.write(file_bytes)

    return stored_filename, stored_path


def delete_stored_file(file_path: str) -> bool:
    """Safely removes physical file from disk if present."""
    if not file_path:
        return False
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except OSError:
        return False
