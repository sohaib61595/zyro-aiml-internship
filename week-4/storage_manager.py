"""
ZYROO INTERNSHIP PROGRAM - WEEK 4
Module: Structured File Storage & Duplicate Detection Engine
Tasks: Task 1 (Structured File Storage), Task 3 (Duplicate Detection), Task 8 (File Validation)

Design:
- Organizes documents into category subdirectories:
    storage/
    ├── invoices/
    ├── resumes/
    └── other/
- Generates safe, collision-resistant filenames preserving original extensions.
- Calculates SHA-256 hashes to guarantee data integrity and duplicate prevention.
- Validates uploads against unsupported file types and oversized payloads.
"""

import os
import re
import hashlib
import unicodedata
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
import db_repository

# Supported file extensions and size limit (Task 8)
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB Limit

# Base storage path inside week-4 directory
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
    Task 3: Computes cryptographic SHA-256 hash of document binary content.
    Returns 64-character hexadecimal digest.
    """
    return hashlib.sha256(file_bytes).hexdigest()


def sanitize_filename(filename: str) -> str:
    """
    Generates a secure, sanitized base filename:
    - Removes path traversal patterns
    - Normalizes unicode characters
    - Replaces whitespace and illegal characters with underscores
    """
    # Extract only the base name (prevent directory traversal)
    base = os.path.basename(filename).strip()
    
    # Normalize unicode
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    
    # Split name and extension
    name, ext = os.path.splitext(base)
    ext = ext.lower().strip()
    
    # Replace illegal/unsafe characters with underscore
    safe_name = re.sub(r"[^\w\-_.]", "_", name)
    safe_name = re.sub(r"_{2,}", "_", safe_name).strip("._")
    
    if not safe_name:
        safe_name = "document"
        
    return f"{safe_name}{ext}"


def generate_safe_stored_filename(original_filename: str, file_hash: str) -> str:
    """
    Task 1: Generates collision-proof, deterministic stored filename.
    Format: YYYYMMDD_HHMMSS_<hash_prefix8>_<sanitized_name>.<ext>
    """
    sanitized = sanitize_filename(original_filename)
    name, ext = os.path.splitext(sanitized)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    hash_prefix = file_hash[:8]
    return f"{timestamp}_{hash_prefix}_{name}{ext}"


def validate_uploaded_file(filename: str, file_bytes: bytes) -> Tuple[bool, str]:
    """
    Task 8: Enforces security and stability constraints on uploaded files.
    - Validates file extension against whitelist.
    - Enforces maximum file size limit.
    - Checks for non-empty payload.
    """
    if not filename or not isinstance(filename, str):
        return False, "Invalid filename provided."

    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type '{ext}'. Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}."

    size = len(file_bytes)
    if size == 0:
        return False, "Uploaded file is empty (0 bytes)."

    if size > MAX_UPLOAD_SIZE_BYTES:
        max_mb = MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
        curr_mb = round(size / (1024 * 1024), 2)
        return False, f"File exceeds maximum allowed upload size of {max_mb:.0f} MB (Uploaded: {curr_mb} MB)."

    return True, "Valid"


def check_for_duplicate(file_hash: str, db_path: Optional[str] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Task 3: Queries SQLite database to detect if this exact file (by SHA-256) already exists.
    Returns (True, existing_record) if found, else (False, None).
    """
    existing_doc = db_repository.get_document_by_hash(file_hash, db_path=db_path)
    if existing_doc:
        return True, existing_doc
    return False, None


def save_document_file(
    file_bytes: bytes,
    original_filename: str,
    document_type: str,
    file_hash: str
) -> Tuple[str, str]:
    """
    Task 1: Writes the binary document safely to the categorized directory.
    
    Returns:
        (stored_filename, absolute_file_path)
    """
    ensure_storage_structure()
    target_dir = get_storage_folder(document_type)
    stored_filename = generate_safe_stored_filename(original_filename, file_hash)
    stored_path = os.path.join(target_dir, stored_filename)

    with open(stored_path, "wb") as f:
        f.write(file_bytes)

    return stored_filename, stored_path
