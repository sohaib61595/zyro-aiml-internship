"""
ZYROO INTERNSHIP PROGRAM - WEEK 6
Module: SQLite Database Repository, RAG Persistence & Workflow Metrics
Focus: Enterprise integration, security, optimization, and deployment readiness
"""

import os
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import config

logger = logging.getLogger("workflow_database")


def get_default_db_path() -> str:
    """Returns the default absolute path for the SQLite database."""
    return config.DEFAULT_DB_PATH


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Creates and returns a connection to the SQLite database.
    Configures row_factory for dict-like access and enables WAL mode and foreign keys.
    """
    path = db_path or get_default_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """
    Initializes the relational SQLite schema:
    1. 'documents' table - stores metadata, status, extraction, validation, anomalies & timing
    2. 'audit_log' table - immutable chronological trail of actions and state transitions
    3. 'rag_chunks' table - semantic document chunks with exact provenance for RAG
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
                    anomaly_json TEXT DEFAULT '{}',
                    review_reason TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    processing_time_ms REAL DEFAULT 0.0,
                    stage_timings_json TEXT DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
            """)

            # 2. Audit Log Table
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

            # 3. RAG Chunks Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    page_number INTEGER DEFAULT 1,
                    chunk_text TEXT NOT NULL,
                    token_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
            """)

            # Performance Indexes
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_docs_hash ON documents(file_hash);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_status ON documents(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_type ON documents(document_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_doc_id ON audit_log(document_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON rag_chunks(document_id);")

        logger.info("Database schema initialized successfully.")
    finally:
        conn.close()


def insert_document(doc_data: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """Inserts a new document record and returns the new integer ID."""
    now_iso = datetime.now().isoformat()
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.execute("""
                INSERT INTO documents (
                    original_filename, stored_filename, document_type, upload_date,
                    company, invoice_number, total_amount, file_path, text_preview,
                    file_hash, status, file_size, mime_type, confidence,
                    extracted_json, validation_json, anomaly_json, review_reason,
                    notes, processing_time_ms, stage_timings_json, updated_at
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?
                );
            """, (
                doc_data.get("original_filename", "unnamed"),
                doc_data.get("stored_filename", "pending"),
                doc_data.get("document_type", "Unknown"),
                doc_data.get("upload_date", now_iso),
                doc_data.get("company", "Not Found"),
                doc_data.get("invoice_number", "Not Found"),
                doc_data.get("total_amount", "Not Found"),
                doc_data.get("file_path", "pending"),
                doc_data.get("text_preview", ""),
                doc_data["file_hash"],
                doc_data.get("status", "New"),
                doc_data.get("file_size", 0),
                doc_data.get("mime_type", "application/octet-stream"),
                doc_data.get("confidence"),
                doc_data.get("extracted_json", "{}"),
                doc_data.get("validation_json", "{}"),
                doc_data.get("anomaly_json", "{}"),
                doc_data.get("review_reason", ""),
                doc_data.get("notes", ""),
                doc_data.get("processing_time_ms", 0.0),
                doc_data.get("stage_timings_json", "{}"),
                now_iso
            ))
            return cursor.lastrowid
    finally:
        conn.close()


def get_document_by_id(doc_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves document record by primary key."""
    conn = get_db_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_document_by_hash(file_hash: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves document record by exact SHA-256 hash."""
    conn = get_db_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM documents WHERE file_hash = ?", (file_hash,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_documents(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all documents ordered by ID descending."""
    conn = get_db_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM documents ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def search_documents(
    query: Optional[str] = None,
    status_filter: Optional[str] = None,
    type_filter: Optional[str] = None,
    anomaly_only: bool = False,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Multi-parameter filtered document search."""
    conn = get_db_connection(db_path)
    try:
        clauses = []
        params = []

        if query:
            q_like = f"%{query}%"
            clauses.append("""
                (original_filename LIKE ? OR company LIKE ? OR invoice_number LIKE ? 
                 OR text_preview LIKE ? OR review_reason LIKE ?)
            """)
            params.extend([q_like, q_like, q_like, q_like, q_like])

        if status_filter and status_filter != "All":
            clauses.append("status = ?")
            params.append(status_filter)

        if type_filter and type_filter != "All":
            clauses.append("document_type = ?")
            params.append(type_filter)

        if anomaly_only:
            clauses.append("(anomaly_json != '{}' AND anomaly_json IS NOT NULL)")

        where_stmt = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM documents {where_stmt} ORDER BY id DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_document_status(
    doc_id: int,
    new_status: str,
    reason: str = "",
    db_path: Optional[str] = None
) -> None:
    """Updates status and timestamp atomically."""
    conn = get_db_connection(db_path)
    try:
        now_iso = datetime.now().isoformat()
        with conn:
            conn.execute("""
                UPDATE documents 
                SET status = ?, review_reason = ?, updated_at = ?
                WHERE id = ?
            """, (new_status, reason, now_iso, doc_id))
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
    anomaly_json: str,
    review_reason: str,
    processing_time_ms: float,
    stage_timings_json: str,
    text_preview: str,
    db_path: Optional[str] = None
) -> None:
    """Updates complete extraction, validation, and anomaly intelligence results."""
    conn = get_db_connection(db_path)
    try:
        now_iso = datetime.now().isoformat()
        with conn:
            conn.execute("""
                UPDATE documents
                SET status = ?,
                    document_type = ?,
                    company = ?,
                    invoice_number = ?,
                    total_amount = ?,
                    confidence = ?,
                    extracted_json = ?,
                    validation_json = ?,
                    anomaly_json = ?,
                    review_reason = ?,
                    processing_time_ms = ?,
                    stage_timings_json = ?,
                    text_preview = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                status, document_type, company, invoice_number, total_amount,
                confidence, extracted_json, validation_json, anomaly_json,
                review_reason, processing_time_ms, stage_timings_json,
                text_preview, now_iso, doc_id
            ))
    finally:
        conn.close()


def update_document_fields(
    doc_id: int,
    fields: Dict[str, Any],
    db_path: Optional[str] = None
) -> None:
    """Updates extracted fields after manual human review edit."""
    conn = get_db_connection(db_path)
    try:
        now_iso = datetime.now().isoformat()
        with conn:
            conn.execute("""
                UPDATE documents
                SET company = ?,
                    invoice_number = ?,
                    total_amount = ?,
                    extracted_json = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                fields.get("company", "Not Found"),
                fields.get("invoice_number", "Not Found"),
                fields.get("total_amount", "Not Found"),
                fields.get("extracted_json", "{}"),
                now_iso,
                doc_id
            ))
    finally:
        conn.close()


# ------------------------------------------------------------------------------
# RAG Persistence
# ------------------------------------------------------------------------------

def insert_rag_chunks(chunks: List[Dict[str, Any]], db_path: Optional[str] = None) -> int:
    """Inserts a batch of document chunks into rag_chunks table."""
    if not chunks:
        return 0
    now_iso = datetime.now().isoformat()
    conn = get_db_connection(db_path)
    try:
        with conn:
            # Delete existing chunks for this document first if replacing
            doc_id = chunks[0]["document_id"]
            conn.execute("DELETE FROM rag_chunks WHERE document_id = ?", (doc_id,))
            
            rows = [
                (
                    c["document_id"],
                    c["chunk_index"],
                    c.get("page_number", 1),
                    c["chunk_text"],
                    c.get("token_count", len(c["chunk_text"].split())),
                    now_iso
                )
                for c in chunks
            ]
            conn.executemany("""
                INSERT INTO rag_chunks (
                    document_id, chunk_index, page_number, chunk_text, token_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?);
            """, rows)
            return len(rows)
    finally:
        conn.close()


def get_all_rag_chunks(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all indexed RAG chunks with document metadata."""
    conn = get_db_connection(db_path)
    try:
        sql = """
            SELECT c.*, d.original_filename, d.document_type
            FROM rag_chunks c
            JOIN documents d ON c.document_id = d.id
            ORDER BY c.document_id ASC, c.chunk_index ASC
        """
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_rag_chunks_for_document(doc_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves chunks belonging to a single document."""
    conn = get_db_connection(db_path)
    try:
        rows = conn.execute("""
            SELECT * FROM rag_chunks WHERE document_id = ? ORDER BY chunk_index ASC
        """, (doc_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ------------------------------------------------------------------------------
# Audit Log & Workflow Analytics
# ------------------------------------------------------------------------------

def insert_audit_event(
    document_id: int,
    action: str,
    previous_status: str,
    new_status: str,
    reason: str = "",
    performed_by: str = "System",
    db_path: Optional[str] = None
) -> int:
    """Inserts an immutable audit event record."""
    now_iso = datetime.now().isoformat()
    conn = get_db_connection(db_path)
    try:
        with conn:
            cursor = conn.execute("""
                INSERT INTO audit_log (
                    document_id, action, previous_status, new_status,
                    timestamp, reason, performed_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                document_id, action, previous_status, new_status,
                now_iso, reason, performed_by
            ))
            return cursor.lastrowid
    finally:
        conn.close()


def get_audit_logs_for_document(doc_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves chronological audit trail for a specific document."""
    conn = get_db_connection(db_path)
    try:
        rows = conn.execute("""
            SELECT * FROM audit_log WHERE document_id = ? ORDER BY id ASC
        """, (doc_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_audit_log_for_document(doc_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Alias for get_audit_logs_for_document."""
    return get_audit_logs_for_document(doc_id, db_path=db_path)


def get_recent_audit_logs(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves recent audit events across the platform."""
    conn = get_db_connection(db_path)
    try:
        sql = f"""
            SELECT a.*, d.original_filename, d.document_type
            FROM audit_log a
            LEFT JOIN documents d ON a.document_id = d.id
            ORDER BY a.id DESC LIMIT {limit}
        """
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_workflow_metrics(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Aggregates platform KPIs, stage latencies, anomaly rates and statuses."""
    conn = get_db_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

        # By status
        status_rows = conn.execute("SELECT status, COUNT(*) FROM documents GROUP BY status").fetchall()
        by_status = {r[0]: r[1] for r in status_rows}

        # By type
        type_rows = conn.execute("SELECT document_type, COUNT(*) FROM documents GROUP BY document_type").fetchall()
        by_type = {r[0]: r[1] for r in type_rows}

        # Anomaly count
        anomaly_count = conn.execute("""
            SELECT COUNT(*) FROM documents 
            WHERE anomaly_json != '{}' AND anomaly_json IS NOT NULL AND anomaly_json != '{"has_anomalies": false, "anomalies": []}'
        """).fetchone()[0]

        # Processing times
        time_row = conn.execute("""
            SELECT AVG(processing_time_ms), MIN(processing_time_ms), MAX(processing_time_ms)
            FROM documents WHERE processing_time_ms > 0
        """).fetchone()

        avg_ms = round(time_row[0] or 0.0, 2)
        min_ms = round(time_row[1] or 0.0, 2)
        max_ms = round(time_row[2] or 0.0, 2)

        # Total RAG chunks
        chunks_count = conn.execute("SELECT COUNT(*) FROM rag_chunks").fetchone()[0]

        return {
            "total_documents": total,
            "by_status": by_status,
            "by_type": by_type,
            "approved_count": by_status.get("Approved", 0),
            "completed_count": by_status.get("Completed", 0),
            "needs_review_count": by_status.get("Needs Review", 0),
            "rejected_count": by_status.get("Rejected", 0),
            "processing_count": by_status.get("Processing", 0),
            "new_count": by_status.get("New", 0),
            "anomaly_count": anomaly_count,
            "avg_processing_time_ms": avg_ms,
            "min_processing_time_ms": min_ms,
            "max_processing_time_ms": max_ms,
            "total_rag_chunks": chunks_count
        }
    finally:
        conn.close()
