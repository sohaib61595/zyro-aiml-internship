"""
ZYROO INTERNSHIP PROGRAM - WEEK 5
Module: Workflow History & Audit Logging
Focus: Workflow automation, validation, review and auditability

Requirements Addressed:
- Task 5 (Audit Log):
  - Document ID
  - Action
  - Previous status
  - New status
  - Timestamp
  - Reason or reviewer note
  - Performed by
- Traceable chronological workflow history.
- Helper formatters for Streamlit UI display.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import database

# Standard Audit Actions
ACTION_UPLOAD = "UPLOAD"
ACTION_PROCESS_START = "PROCESS_START"
ACTION_AUTO_DECISION = "AUTO_DECISION"
ACTION_ROUTE_REVIEW = "ROUTE_TO_REVIEW"
ACTION_APPROVE = "APPROVE"
ACTION_REJECT = "REJECT"
ACTION_FIELD_EDIT = "FIELD_EDIT"
ACTION_BATCH_PROCESS = "BATCH_PROCESS"
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
    """
    Records an immutable audit trail entry for a document.
    
    Args:
        document_id: Foreign key ID of document
        action: Standard action identifier
        previous_status: Status prior to this action
        new_status: Resulting status
        reason: Explanation or reviewer justification
        performed_by: Actor ('System', 'Rule Engine', 'Human Reviewer')
        db_path: Optional custom SQLite database path
        
    Returns:
        Generated audit log entry ID
    """
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
    """
    Retrieves full audit timeline for a specific document in chronological order.
    """
    return database.get_audit_log_for_document(document_id, db_path=db_path)


def get_system_audit_trail(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves the most recent workflow actions across all documents.
    """
    return database.get_recent_audit_logs(limit=limit, db_path=db_path)


def format_audit_badge_color(action: str) -> str:
    """Returns CSS color indicator for given action."""
    action_colors = {
        ACTION_UPLOAD: "#3b82f6",          # blue
        ACTION_PROCESS_START: "#6366f1",   # indigo
        ACTION_AUTO_DECISION: "#8b5cf6",   # purple
        ACTION_ROUTE_REVIEW: "#f59e0b",    # amber
        ACTION_APPROVE: "#10b981",         # green
        ACTION_REJECT: "#ef4444",          # red
        ACTION_FIELD_EDIT: "#06b6d4",      # cyan
        ACTION_COMPLETE: "#059669",        # dark green
        ACTION_BATCH_PROCESS: "#ec4899"    # pink
    }
    return action_colors.get(action, "#6b7280")
