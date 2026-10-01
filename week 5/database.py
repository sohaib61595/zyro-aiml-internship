"""
ZYROO INTERNSHIP PROGRAM - WEEK 5
Module: SQLite Database Repository & Workflow Persistence Layer
Focus: Workflow automation, validation, review and auditability

Responsibilities:
- Manages connection pool, WAL mode, foreign keys, and transactions.
- Schema initialization for 'documents' and 'audit_log' tables.
- Implements CRUD operations, multi-field search, state filtering, and batch retrievals.
- Provides atomic status updates and audit record logging.
- Aggregates comprehensive workflow metrics and operational analytics.
"""

import os
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("workflow_database")

DEFAULT_DB_FILE = "workflow_repository.db"


def get_default_db_path() -> str:
    """Returns the default absolute path for the Week 5 SQLite database."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, DEFAULT_DB_FILE)


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Creates and returns a connection to the SQLite database.
    Configures row_factory for dict-like access and enables WAL mode.
    """
    path = db_path or get_default_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """
    Initializes the SQLite schema with:
    1. 'documents' table - stores document lifecycle states, validations, and metadata.
    2. 'audit_log' table - records every state transition, automated decision, and human review action.
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            # 1. Documents Table
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
                    confidence REAL,
                    extracted_json TEXT DEFAULT '{}',
                    validation_json TEXT DEFAULT '{}',
                    review_reason TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    processing_time_ms REAL DEFAULT 0.0,
                    updated_at TEXT NOT NULL
                );
            """)

            # 2. Audit Log Table (Requirement 5)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    previous_status TEXT NOT NULL,
                    new_status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    reason TEXT DEFAULT '',
                    performed_by TEXT DEFAULT 'System',
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
            """)

            # Performance & Query Optimization Indexes
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_docs_hash ON documents(file_hash);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_status ON documents(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_type ON documents(document_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_upload_date ON documents(upload_date);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_company ON documents(company);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_inv_no ON documents(invoice_number);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_doc_id ON audit_log(document_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);")
    except sqlite3.Error as e:
        logger.error(f"Failed to initialize SQLite database: {e}")
        raise RuntimeError(f"Database initialization error: {e}")
    finally:
        conn.close()


# ==============================================================================
# DOCUMENT REPOSITORY CRUD OPERATIONS
# ==============================================================================

def insert_document(doc_data: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """
    Inserts a newly uploaded or ingested document into the SQLite repository.
    Returns the auto-generated primary key integer ID.
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
            validation_json,
            review_reason,
            notes,
            processing_time_ms,
            updated_at
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
            :validation_json,
            :review_reason,
            :notes,
            :processing_time_ms,
            :updated_at
        );
    """
    
    # Handle confidence: store None if missing, never invent an artificial number
    conf_val = doc_data.get("confidence")
    if conf_val is not None:
        try:
            conf_val = float(conf_val)
        except (ValueError, TypeError):
            conf_val = None

    params = {
        "original_filename": str(doc_data.get("original_filename", "unnamed_document")),
        "stored_filename": str(doc_data.get("stored_filename", "")),
        "document_type": str(doc_data.get("document_type", "Other")),
        "upload_date": str(doc_data.get("upload_date", now_iso)),
        "company": str(doc_data.get("company", "Not Found")),
        "invoice_number": str(doc_data.get("invoice_number", "Not Found")),
        "total_amount": str(doc_data.get("total_amount", "Not Found")),
        "file_path": str(doc_data.get("file_path", "")),
        "text_preview": str(doc_data.get("text_preview", ""))[:1500],
        "file_hash": str(doc_data.get("file_hash", "")),
        "status": str(doc_data.get("status", "New")),
        "file_size": int(doc_data.get("file_size", 0)),
        "mime_type": str(doc_data.get("mime_type", "application/octet-stream")),
        "confidence": conf_val,
        "extracted_json": str(doc_data.get("extracted_json", "{}")),
        "validation_json": str(doc_data.get("validation_json", "{}")),
        "review_reason": str(doc_data.get("review_reason", "")),
        "notes": str(doc_data.get("notes", "")),
        "processing_time_ms": float(doc_data.get("processing_time_ms", 0.0)),
        "updated_at": str(doc_data.get("updated_at", now_iso))
    }

    try:
        with conn:
            cursor = conn.execute(query, params)
            doc_id = cursor.lastrowid
            return doc_id
    except sqlite3.IntegrityError as ie:
        logger.warning(f"Integrity error (hash duplicate) on document insertion: {ie}")
        raise
    except sqlite3.Error as e:
        logger.error(f"Error inserting document: {e}")
        raise RuntimeError(f"Database insertion failed: {e}")
    finally:
        conn.close()


def update_document_status(
    doc_id: int,
    new_status: str,
    review_reason: str = "",
    reviewer_notes: Optional[str] = None,
    db_path: Optional[str] = None
) -> bool:
    """
    Updates the state of a document and its associated review reason / notes.
    """
    conn = get_db_connection(db_path)
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    query = """
        UPDATE documents
        SET status = :status,
            review_reason = :review_reason,
            notes = COALESCE(:notes, notes),
            updated_at = :updated_at
        WHERE id = :id;
    """
    params = {
        "id": doc_id,
        "status": new_status,
        "review_reason": review_reason,
        "notes": reviewer_notes,
        "updated_at": now_iso
    }
    
    try:
        with conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount > 0
    finally:
        conn.close()


def update_document_processing_result(
    doc_id: int,
    status: str,
    document_type: str,
    company: str,
    invoice_number: str,
    total_amount: str,
    confidence: Optional[float],
    extracted_json: str,
    validation_json: str,
    review_reason: str,
    processing_time_ms: float = 0.0,
    text_preview: str = "",
    db_path: Optional[str] = None
) -> bool:
    """
    Updates document metadata, classifications, extractions, validations, and final status
    after automated pipeline processing finishes.
    """
    conn = get_db_connection(db_path)
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    query = """
        UPDATE documents
        SET status = :status,
            document_type = :document_type,
            company = :company,
            invoice_number = :invoice_number,
            total_amount = :total_amount,
            confidence = :confidence,
            extracted_json = :extracted_json,
            validation_json = :validation_json,
            review_reason = :review_reason,
            processing_time_ms = :processing_time_ms,
            text_preview = CASE WHEN :text_preview != '' THEN :text_preview ELSE text_preview END,
            updated_at = :updated_at
        WHERE id = :id;
    """
    params = {
        "id": doc_id,
        "status": status,
        "document_type": document_type,
        "company": company,
        "invoice_number": invoice_number,
        "total_amount": total_amount,
        "confidence": confidence,
        "extracted_json": extracted_json,
        "validation_json": validation_json,
        "review_reason": review_reason,
        "processing_time_ms": processing_time_ms,
        "text_preview": text_preview[:1500] if text_preview else "",
        "updated_at": now_iso
    }

    try:
        with conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount > 0
    finally:
        conn.close()


def update_document_fields(
    doc_id: int,
    fields: Dict[str, Any],
    db_path: Optional[str] = None
) -> bool:
    """
    Allows human reviewer to edit/correct extracted metadata fields (company, invoice_number, total_amount, notes).
    """
    conn = get_db_connection(db_path)
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    set_clauses = ["updated_at = :updated_at"]
    params: Dict[str, Any] = {"id": doc_id, "updated_at": now_iso}

    for col in ["company", "invoice_number", "total_amount", "notes", "validation_json", "review_reason"]:
        if col in fields:
            set_clauses.append(f"{col} = :{col}")
            params[col] = fields[col]

    query = f"UPDATE documents SET {', '.join(set_clauses)} WHERE id = :id;"

    try:
        with conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount > 0
    finally:
        conn.close()


def get_document_by_id(doc_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetches a single document record by primary key ID."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_document_by_hash(file_hash: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetches document by SHA-256 hash for duplicate prevention."""
    if not file_hash:
        return None
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute("SELECT * FROM documents WHERE file_hash = ?", (file_hash,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_documents_by_ids(doc_ids: List[int], db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches a list of documents matching specified IDs for batch processing."""
    if not doc_ids:
        return []
    conn = get_db_connection(db_path)
    try:
        placeholders = ",".join("?" for _ in doc_ids)
        cursor = conn.execute(f"SELECT * FROM documents WHERE id IN ({placeholders}) ORDER BY id ASC", doc_ids)
        return [dict(row) for row in cursor.fetchall()]
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
    Multi-field search and filtering across documents with dynamic parameterized query construction.
    Supports joining latest audit action and timestamp.
    """
    conn = get_db_connection(db_path)
    conditions = []
    params: Dict[str, Any] = {}

    if search_query and search_query.strip():
        q = f"%{search_query.strip()}%"
        conditions.append("""
            (
                d.original_filename LIKE :sq
                OR d.company LIKE :sq
                OR d.invoice_number LIKE :sq
                OR d.document_type LIKE :sq
                OR d.text_preview LIKE :sq
                OR d.review_reason LIKE :sq
            )
        """)
        params["sq"] = q

    if document_type and document_type not in ["All", "Any", ""]:
        conditions.append("d.document_type = :dt")
        params["dt"] = document_type

    if status and status not in ["All", "Any", ""]:
        conditions.append("d.status = :st")
        params["st"] = status

    if start_date:
        conditions.append("date(d.upload_date) >= date(:s_date)")
        params["s_date"] = start_date

    if end_date:
        conditions.append("date(d.upload_date) <= date(:e_date)")
        params["e_date"] = end_date

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    sort_map = {
        "newest": "d.upload_date DESC",
        "oldest": "d.upload_date ASC",
        "filename_asc": "d.original_filename ASC",
        "filename_desc": "d.original_filename DESC",
        "status": "d.status ASC, d.upload_date DESC",
        "confidence_asc": "d.confidence ASC NULLS FIRST",
        "confidence_desc": "d.confidence DESC NULLS LAST"
    }
    order_clause = sort_map.get(sort_by, "d.upload_date DESC")

    query = f"""
        SELECT 
            d.*,
            (SELECT action FROM audit_log a WHERE a.document_id = d.id ORDER BY a.id DESC LIMIT 1) AS latest_action,
            (SELECT timestamp FROM audit_log a WHERE a.document_id = d.id ORDER BY a.id DESC LIMIT 1) AS latest_action_time
        FROM documents d
        {where_clause}
        ORDER BY {order_clause}
        LIMIT :limit OFFSET :offset;
    """
    params["limit"] = limit
    params["offset"] = offset

    try:
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def delete_document(doc_id: int, db_path: Optional[str] = None) -> bool:
    """Deletes a document and cascades to its audit log."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


# ==============================================================================
# AUDIT LOG PERSISTENCE (Requirement 5)
# ==============================================================================

def insert_audit_event(
    document_id: int,
    action: str,
    previous_status: str,
    new_status: str,
    reason: str = "",
    performed_by: str = "System",
    db_path: Optional[str] = None
) -> int:
    """
    Records an atomic audit log entry for any document workflow event.
    """
    conn = get_db_connection(db_path)
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    query = """
        INSERT INTO audit_log (
            document_id,
            action,
            previous_status,
            new_status,
            timestamp,
            reason,
            performed_by
        ) VALUES (
            :document_id,
            :action,
            :previous_status,
            :new_status,
            :timestamp,
            :reason,
            :performed_by
        );
    """
    params = {
        "document_id": document_id,
        "action": action,
        "previous_status": previous_status,
        "new_status": new_status,
        "timestamp": now_iso,
        "reason": reason,
        "performed_by": performed_by
    }

    try:
        with conn:
            cursor = conn.execute(query, params)
            return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"Failed to record audit event for doc #{document_id}: {e}")
        return -1
    finally:
        conn.close()


def get_audit_log_for_document(document_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns chronological audit history for a specific document."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute(
            "SELECT * FROM audit_log WHERE document_id = ? ORDER BY id ASC",
            (document_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_recent_audit_logs(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns most recent audit events across all documents with document details."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.execute("""
            SELECT 
                a.*,
                d.original_filename,
                d.document_type
            FROM audit_log a
            LEFT JOIN documents d ON a.document_id = d.id
            ORDER BY a.id DESC
            LIMIT ?;
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# ==============================================================================
# WORKFLOW METRICS & ANALYTICS (Requirement 9)
# ==============================================================================

def get_workflow_metrics(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculates comprehensive operational metrics for the Workflow Dashboard:
    - Total documents
    - Processed documents
    - Documents needing review
    - Approved documents
    - Rejected documents
    - Completed documents
    - Failed documents
    - Counts by document type
    - Average and max processing time
    """
    conn = get_db_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM documents;").fetchone()[0]

        # Status counts
        status_rows = conn.execute("""
            SELECT status, COUNT(*) as count 
            FROM documents 
            GROUP BY status;
        """).fetchall()
        status_counts = {row["status"]: row["count"] for row in status_rows}

        # Type counts
        type_rows = conn.execute("""
            SELECT document_type, COUNT(*) as count 
            FROM documents 
            GROUP BY document_type;
        """).fetchall()
        type_counts = {row["document_type"]: row["count"] for row in type_rows}

        # Processing time metrics
        time_stats = conn.execute("""
            SELECT 
                AVG(processing_time_ms) as avg_time,
                MIN(processing_time_ms) as min_time,
                MAX(processing_time_ms) as max_time
            FROM documents
            WHERE processing_time_ms > 0;
        """).fetchone()

        avg_time = round(time_stats["avg_time"], 1) if time_stats and time_stats["avg_time"] else 0.0
        min_time = round(time_stats["min_time"], 1) if time_stats and time_stats["min_time"] else 0.0
        max_time = round(time_stats["max_time"], 1) if time_stats and time_stats["max_time"] else 0.0

        # Confidence statistics
        conf_stats = conn.execute("""
            SELECT 
                AVG(confidence) as avg_conf,
                COUNT(CASE WHEN confidence < 0.75 THEN 1 END) as low_conf_count
            FROM documents
            WHERE confidence IS NOT NULL;
        """).fetchone()

        avg_conf = round(conf_stats["avg_conf"], 3) if conf_stats and conf_stats["avg_conf"] else None
        low_conf_count = conf_stats["low_conf_count"] if conf_stats else 0

        return {
            "total_documents": total,
            "new_count": status_counts.get("New", 0),
            "processing_count": status_counts.get("Processing", 0),
            "needs_review_count": status_counts.get("Needs Review", 0),
            "approved_count": status_counts.get("Approved", 0),
            "rejected_count": status_counts.get("Rejected", 0),
            "completed_count": status_counts.get("Completed", 0),
            "failed_count": status_counts.get("Failed", 0),
            "status_distribution": status_counts,
            "type_distribution": type_counts,
            "avg_processing_time_ms": avg_time,
            "min_processing_time_ms": min_time,
            "max_processing_time_ms": max_time,
            "avg_confidence": avg_conf,
            "low_confidence_count": low_conf_count
        }
    finally:
        conn.close()
