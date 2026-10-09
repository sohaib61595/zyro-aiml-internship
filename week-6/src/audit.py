"""
ZYROO INTERNSHIP PROGRAM - WEEK 6
Module: Immutable Audit Trail & Lifecycle Event Logger
Focus: Enterprise integration, security, optimization, and deployment readiness
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import database

# Standard Audit Actions
ACTION_UPLOAD = "UPLOAD"
ACTION_PROCESS_START = "PROCESS_START"
ACTION_OCR_PERFORMED = "OCR_PERFORMED"
ACTION_CLASSIFIED = "CLASSIFIED"
ACTION_EXTRACTED = "EXTRACTED"
ACTION_VALIDATION_FAILED = "VALIDATION_FAILED"
ACTION_ANOMALY_DETECTED = "ANOMALY_DETECTED"
ACTION_AUTO_DECISION = "AUTO_DECISION"
ACTION_ROUTE_REVIEW = "ROUTE_TO_REVIEW"
ACTION_APPROVE = "APPROVE"
ACTION_REJECT = "REJECT"
ACTION_FIELD_EDIT = "FIELD_EDIT"
ACTION_BATCH_PROCESS = "BATCH_PROCESS"
ACTION_RAG_INDEXED = "RAG_INDEXED"
ACTION_MANUAL_STATUS_CHANGE = "MANUAL_STATUS_CHANGE"
ACTION_COMPLETE = "COMPLETE"


def log_event(
    document_id: int,
    action: str,
    previous_status: str,
    new_status: str,
    reason: str = "",
    performed_by: str = "System",
    db_path: Optional[str] = None
) -> int:
    """Records an immutable audit trail entry for a document."""
    return database.insert_audit_event(
        document_id=document_id,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        reason=reason,
        performed_by=performed_by,
        db_path=db_path
    )


def get_document_history(document_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves full audit timeline for a specific document in chronological order."""
    return database.get_audit_log_for_document(document_id, db_path=db_path)


def get_system_audit_trail(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves the most recent workflow actions across all documents."""
    return database.get_recent_audit_logs(limit=limit, db_path=db_path)


def format_audit_badge_color(action: str) -> str:
    """Returns CSS color indicator for given action."""
    action_colors = {
        ACTION_UPLOAD: "#3b82f6",          # blue
        ACTION_PROCESS_START: "#6366f1",   # indigo
        ACTION_OCR_PERFORMED: "#0ea5e9",   # light blue
        ACTION_CLASSIFIED: "#8b5cf6",      # purple
        ACTION_EXTRACTED: "#a855f7",       # violet
        ACTION_VALIDATION_FAILED: "#f59e0b",# amber
        ACTION_ANOMALY_DETECTED: "#ef4444",# red
        ACTION_AUTO_DECISION: "#8b5cf6",   # purple
        ACTION_ROUTE_REVIEW: "#f59e0b",    # amber
        ACTION_APPROVE: "#10b981",         # green
        ACTION_REJECT: "#ef4444",          # red
        ACTION_FIELD_EDIT: "#06b6d4",      # cyan
        ACTION_RAG_INDEXED: "#14b8a6",     # teal
        ACTION_COMPLETE: "#059669",        # dark green
        ACTION_BATCH_PROCESS: "#ec4899"    # pink
    }
    return action_colors.get(action, "#6b7280")
