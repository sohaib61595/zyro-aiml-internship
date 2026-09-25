"""
ZYROO INTERNSHIP PROGRAM - WEEK 4
Module: SQLite Document Repository Layer
Tasks: Task 2 (SQLite Document Repository), Task 4 (Multi-Field Search), Task 5 (Filters & Sorting)

Architecture:
- Cleanly separated from Streamlit UI.
- Direct SQLite connection handling with context managers.
- Parameterized SQL queries to prevent SQL injection and optimize search performance.
- Supports CRUD operations: Insert, Get, Search/Filter, Update Status, Delete.
- Tracks statistics for document management dashboard.
"""

import os
import sqlite3
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("document_repository")

# Default database name in week-4 directory
DEFAULT_DB_FILE = "document_repository.db"


def get_default_db_path() -> str:
    """Returns the default absolute path for the SQLite database."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, DEFAULT_DB_FILE)


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Creates and returns a connection to the SQLite database.
    Configures row_factory for dict-like access.
    """
    path = db_path or get_default_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high concurrency & foreign keys
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """
    Initializes the SQLite schema with the required 'documents' table and indexes.
    
    Fields:
      - id: Primary Key (Auto-increment)
      - original_filename: Original user upload filename
      - stored_filename: Sanitized unique filename on disk
      - document_type: Classified category ('Invoice', 'Resume', 'Other')
      - upload_date: ISO 8601 formatted timestamp ('YYYY-MM-DD HH:MM:SS')
      - company: Extracted company name or candidate name
      - invoice_number: Extracted invoice identifier or reference ID
      - total_amount: Extracted amount or key numeric metric
      - file_path: Storage file path relative or absolute
      - text_preview: First 400-500 characters of clean extracted text
      - file_hash: SHA-256 hex digest of file contents (UNIQUE)
      - status: Document status ('Processed', 'Needs Review', 'Failed')
      - file_size: Size in bytes
      - mime_type: MIME type (e.g. application/pdf, image/png)
      - confidence: Model classification confidence score (0.0 - 1.0)
      - extracted_json: Complete JSON serialization of entity extraction results
      - notes: Optional user/reviewer notes
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    upload_date TEXT NOT NULL,
                    company TEXT DEFAULT 'Not Found',
                    invoice_number TEXT DEFAULT 'Not Found',
                    total_amount TEXT DEFAULT 'Not Found',
                    file_path TEXT NOT NULL,
                    text_preview TEXT DEFAULT '',
                    file_hash TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    mime_type TEXT DEFAULT 'application/octet-stream',
                    confidence REAL DEFAULT 0.0,
                    extracted_json TEXT DEFAULT '{}',
                    notes TEXT DEFAULT ''
                );
            """)

            # Task 4 & Task 5 Optimization: Composite and single-column indexes
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_docs_hash ON documents(file_hash);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_type ON documents(document_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_status ON documents(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_upload_date ON documents(upload_date);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_company ON documents(company);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_inv_no ON documents(invoice_number);")
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize SQLite database: {e}")
        raise RuntimeError(f"Database initialization error: {e}")
    finally:
        conn.close()


def insert_document(doc_data: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """
    Inserts a newly processed document into the SQLite database.
    
    Args:
        doc_data: Dictionary containing all metadata and extracted fields.
        db_path: Optional custom path to SQLite database.
        
    Returns:
        The integer primary key (ID) of the inserted document.
        
    Raises:
        sqlite3.IntegrityError: If a file with the same file_hash already exists.
        RuntimeError: For other unexpected database failures.
    """
    conn = get_db_connection(db_path)
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    query = """
        INSERT INTO documents (
            original_filename,
            stored_filename,
            document_type,
            upload_date,
            company,
            invoice_number,
            total_amount,
            file_path,
            text_preview,
            file_hash,
            status,
            file_size,
            mime_type,
            confidence,
            extracted_json,
            notes
        ) VALUES (
            :original_filename,
            :stored_filename,
            :document_type,
            :upload_date,
            :company,
            :invoice_number,
            :total_amount,
            :file_path,
            :text_preview,
            :file_hash,
            :status,
            :file_size,
            :mime_type,
            :confidence,
            :extracted_json,
            :notes
        );
    """
    params = {
        "original_filename": str(doc_data.get("original_filename", "unnamed_document")),
        "stored_filename": str(doc_data.get("stored_filename", "")),
        "document_type": str(doc_data.get("document_type", "Other")),
        "upload_date": str(doc_data.get("upload_date", now_iso)),
        "company": str(doc_data.get("company", "Not Found")),
        "invoice_number": str(doc_data.get("invoice_number", "Not Found")),
        "total_amount": str(doc_data.get("total_amount", "Not Found")),
        "file_path": str(doc_data.get("file_path", "")),
        "text_preview": str(doc_data.get("text_preview", ""))[:1000],
        "file_hash": str(doc_data.get("file_hash", "")),
        "status": str(doc_data.get("status", "Needs Review")),
        "file_size": int(doc_data.get("file_size", 0)),
        "mime_type": str(doc_data.get("mime_type", "application/octet-stream")),
        "confidence": float(doc_data.get("confidence", 0.0)),
        "extracted_json": str(doc_data.get("extracted_json", "{}")),
        "notes": str(doc_data.get("notes", ""))
    }

    try:
        with conn:
            cursor = conn.execute(query, params)
            doc_id = cursor.lastrowid
            return doc_id
    except sqlite3.IntegrityError as ie:
        logger.warning(f"Integrity error inserting document (hash conflict): {ie}")
        raise
    except sqlite3.Error as e:
        logger.error(f"Error inserting document: {e}")
        raise RuntimeError(f"Database insertion failed: {e}")
    finally:
        conn.close()


def get_document_by_id(doc_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetches a single document record by ID."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_document_by_hash(file_hash: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Task 3: Duplicate Detection lookup.
    Checks whether a file with the given SHA-256 hash already exists in the database.
    """
    if not file_hash:
        return None
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute("SELECT * FROM documents WHERE file_hash = ?", (file_hash,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def search_documents(
    search_query: Optional[str] = None,
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_by: str = "newest",
    limit: int = 100,
    offset: int = 0,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Task 4 & Task 5: Multi-Field Search, Filtering, and Sorting via direct SQLite queries.
    
    Search targets:
      - original_filename
      - stored_filename
      - company
      - invoice_number
      - document_type
      - text_preview
      
    Filters:
      - document_type (e.g. 'Invoice', 'Resume', 'Other')
      - status (e.g. 'Processed', 'Needs Review', 'Failed')
      - date range (upload_date between start_date and end_date)
      
    Sorting:
      - 'newest': ORDER BY upload_date DESC, id DESC
      - 'oldest': ORDER BY upload_date ASC, id ASC
      - 'filename': ORDER BY original_filename ASC
      - 'company': ORDER BY company ASC
    """
    conn = get_db_connection(db_path)
    clauses: List[str] = []
    params: List[Any] = []

    # 1. Multi-field search (Task 4)
    if search_query and search_query.strip():
        term = f"%{search_query.strip()}%"
        clauses.append("""
            (
                original_filename LIKE ? OR
                stored_filename LIKE ? OR
                company LIKE ? OR
                invoice_number LIKE ? OR
                document_type LIKE ? OR
                text_preview LIKE ? OR
                extracted_json LIKE ?
            )
        """)
        params.extend([term, term, term, term, term, term, term])

    # 2. Filter by document type
    if document_type and document_type.strip().lower() not in ["all", "any", ""]:
        clauses.append("document_type = ?")
        params.append(document_type.strip())

    # 3. Filter by status
    if status and status.strip().lower() not in ["all", "any", ""]:
        clauses.append("status = ?")
        params.append(status.strip())

    # 4. Filter by upload date range
    if start_date and start_date.strip():
        clauses.append("upload_date >= ?")
        params.append(f"{start_date.strip()} 00:00:00")

    if end_date and end_date.strip():
        clauses.append("upload_date <= ?")
        params.append(f"{end_date.strip()} 23:59:59")

    where_clause = " WHERE " + " AND ".join(clauses) if clauses else ""

    # 5. Sorting
    sort_order_sql = {
        "newest": "upload_date DESC, id DESC",
        "oldest": "upload_date ASC, id ASC",
        "filename": "original_filename ASC",
        "company": "company ASC",
        "type": "document_type ASC, upload_date DESC"
    }.get(sort_by.lower(), "upload_date DESC, id DESC")

    query = f"""
        SELECT * FROM documents
        {where_clause}
        ORDER BY {sort_order_sql}
        LIMIT ? OFFSET ?;
    """
    params.extend([limit, offset])

    try:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logger.error(f"Error querying documents: {e}")
        return []
    finally:
        conn.close()


def update_document_status(
    doc_id: int,
    status: str,
    notes: Optional[str] = None,
    db_path: Optional[str] = None
) -> bool:
    """Updates the processing status and optional notes of a document."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            if notes is not None:
                conn.execute(
                    "UPDATE documents SET status = ?, notes = ? WHERE id = ?",
                    (status, notes, doc_id)
                )
            else:
                conn.execute(
                    "UPDATE documents SET status = ? WHERE id = ?",
                    (status, doc_id)
                )
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating status for doc {doc_id}: {e}")
        return False
    finally:
        conn.close()


def update_document_fields(
    doc_id: int,
    company: Optional[str] = None,
    invoice_number: Optional[str] = None,
    total_amount: Optional[str] = None,
    db_path: Optional[str] = None
) -> bool:
    """Allows manual editing/correction of extracted fields in repository."""
    conn = get_db_connection(db_path)
    updates = []
    params = []
    if company is not None:
        updates.append("company = ?")
        params.append(company)
    if invoice_number is not None:
        updates.append("invoice_number = ?")
        params.append(invoice_number)
    if total_amount is not None:
        updates.append("total_amount = ?")
        params.append(total_amount)

    if not updates:
        return True

    params.append(doc_id)
    query = f"UPDATE documents SET {', '.join(updates)} WHERE id = ?"
    try:
        with conn:
            conn.execute(query, params)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating fields for doc {doc_id}: {e}")
        return False
    finally:
        conn.close()


def delete_document(
    doc_id: int,
    delete_file_from_disk: bool = True,
    db_path: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Deletes a document from the database and optionally removes the physical file from disk.
    
    Returns:
        (success: bool, message: str)
    """
    doc = get_document_by_id(doc_id, db_path)
    if not doc:
        return False, f"Document with ID {doc_id} not found."

    file_path = doc.get("file_path", "")
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

        # Remove physical file safely if requested
        if delete_file_from_disk and file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as oe:
                logger.warning(f"Record removed from DB, but could not delete physical file: {oe}")
                return True, f"Document record deleted, but physical file could not be removed: {oe}"

        return True, f"Document #{doc_id} successfully deleted."
    except sqlite3.Error as e:
        logger.error(f"Failed to delete document {doc_id}: {e}")
        return False, f"Database error while deleting document: {e}"
    finally:
        conn.close()


def get_repository_stats(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Aggregates repository metrics for the dashboard:
      - Total documents count
      - Count by document_type ('Invoice', 'Resume', 'Other')
      - Count by status ('Processed', 'Needs Review', 'Failed')
      - Total storage used (bytes)
    """
    conn = get_db_connection(db_path)
    stats: Dict[str, Any] = {
        "total_documents": 0,
        "types": {"Invoice": 0, "Resume": 0, "Other": 0},
        "statuses": {"Processed": 0, "Needs Review": 0, "Failed": 0},
        "total_bytes": 0
    }
    try:
        # Total count & bytes
        row = conn.execute("SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM documents").fetchone()
        if row:
            stats["total_documents"] = row[0]
            stats["total_bytes"] = row[1]

        # Counts by type
        rows_type = conn.execute("SELECT document_type, COUNT(*) FROM documents GROUP BY document_type").fetchall()
        for r in rows_type:
            doc_type = r[0]
            cnt = r[1]
            stats["types"][doc_type] = cnt

        # Counts by status
        rows_status = conn.execute("SELECT status, COUNT(*) FROM documents GROUP BY status").fetchall()
        for r in rows_status:
            st_val = r[0]
            cnt = r[1]
            stats["statuses"][st_val] = cnt

        return stats
    except sqlite3.Error as e:
        logger.error(f"Error fetching stats: {e}")
        return stats
    finally:
        conn.close()
