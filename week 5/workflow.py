"""
ZYROO INTERNSHIP PROGRAM - WEEK 5
Module: Workflow State Machine & Rule-Based Decision Engine
Focus: Workflow automation, validation, review and auditability

Requirements Addressed:
- Task 1: Workflow State Management (New, Processing, Needs Review, Approved, Rejected, Completed)
  - Strict validation of allowed transitions; blocks invalid state changes.
- Task 3: Rule-Based Workflow Engine
  - Decoupled from Streamlit UI code.
  - Transparent rule evaluation: document type, validation results, missing fields, model confidence.
  - Produces deterministic decisions and audit-ready justifications.
- Task 4: Confidence-Aware Review
  - Documented threshold for uncertain classifications (0.75).
  - Routes low-confidence documents to Needs Review.
  - Never fabricates confidence values.
- Task 6: Human Review Queue Actions
  - Approve & Reject actions with mandatory rejection reason enforcement.
- Task 7: Batch Workflow Processing
  - Fault-tolerant multi-document processing.
  - Individual document failures do not crash or abort the batch.
"""

import os
import json
import time
import logging
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field

import database
import storage
import processor
import classifier
import extractor
import validator
import audit

logger = logging.getLogger("workflow_engine")

# ==============================================================================
# 1. WORKFLOW STATES & STATE MACHINE (Task 1)
# ==============================================================================

STATE_NEW = "New"
STATE_PROCESSING = "Processing"
STATE_NEEDS_REVIEW = "Needs Review"
STATE_APPROVED = "Approved"
STATE_REJECTED = "Rejected"
STATE_COMPLETED = "Completed"

ALL_STATES = [
    STATE_NEW,
    STATE_PROCESSING,
    STATE_NEEDS_REVIEW,
    STATE_APPROVED,
    STATE_REJECTED,
    STATE_COMPLETED
]

# Strict Finite State Machine (FSM) Transition Graph
# Maps current_state -> set of valid target states
VALID_TRANSITIONS: Dict[str, List[str]] = {
    STATE_NEW: [STATE_PROCESSING, STATE_REJECTED],
    STATE_PROCESSING: [STATE_NEEDS_REVIEW, STATE_COMPLETED, STATE_REJECTED],
    STATE_NEEDS_REVIEW: [STATE_APPROVED, STATE_REJECTED, STATE_PROCESSING],
    STATE_APPROVED: [STATE_COMPLETED, STATE_PROCESSING],
    STATE_REJECTED: [STATE_PROCESSING],  # Re-processing allowed if re-submitted or appealed
    STATE_COMPLETED: []  # Terminal state
}


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal workflow state transition is attempted."""
    pass


def can_transition(current_state: str, target_state: str) -> Tuple[bool, str]:
    """
    Checks if a transition between two workflow states is legally permitted.
    
    Returns:
        (is_allowed: bool, explanation_message: str)
    """
    if current_state not in VALID_TRANSITIONS:
        return False, f"Unknown current state: '{current_state}'."

    if target_state not in ALL_STATES:
        return False, f"Unknown target state: '{target_state}'."

    if current_state == target_state:
        return False, f"Document is already in state '{current_state}'."

    allowed_targets = VALID_TRANSITIONS.get(current_state, [])
    if target_state in allowed_targets:
        return True, f"Transition '{current_state}' -> '{target_state}' is valid."

    # Helpful diagnostics for rejected transitions
    if current_state == STATE_COMPLETED:
        return False, "Cannot transition from 'Completed'. It is a final terminal state."
    if current_state == STATE_NEW and target_state in (STATE_APPROVED, STATE_COMPLETED):
        return False, f"Cannot transition directly from 'New' to '{target_state}'. Document must be processed first."
    if current_state == STATE_PROCESSING and target_state == STATE_APPROVED:
        return False, "Cannot transition directly from 'Processing' to 'Approved'. Approval requires human review."

    return False, f"Illegal state transition from '{current_state}' to '{target_state}'. Allowed targets: {allowed_targets}."


# ==============================================================================
# 2. RULE-BASED WORKFLOW ENGINE (Task 3 & Task 4)
# ==============================================================================

# Documented confidence threshold for uncertain classification (Requirement 4)
CLASSIFIER_CONFIDENCE_THRESHOLD = 0.75

# Configurable business rule: High-value invoice review threshold
HIGH_VALUE_INVOICE_THRESHOLD = 10000.0  # e.g. USD 10,000 or PKR 1,000,000


@dataclass
class WorkflowDecision:
    """Encapsulates the decision made by the rule engine."""
    target_state: str
    decision_code: str
    reason: str
    rules_triggered: List[str] = field(default_factory=list)
    requires_human_review: bool = False


def evaluate_workflow_rules(
    document_type: str,
    validation_result: Dict[str, Any],
    confidence: Optional[float],
    text_length: int,
    extraction_error: Optional[str] = None
) -> WorkflowDecision:
    """
    Evaluates rule-based workflow logic to determine the document's next state.
    
    Inputs:
    - document_type: Classified document category ('Invoice', 'Resume', 'Other')
    - validation_result: Dictionary returned by validator.validate_document()
    - confidence: Model classification confidence score (None if not provided)
    - text_length: Length of cleaned text
    - extraction_error: OCR or reading error string if any
    
    Decision Rules:
    1. FATAL_ERROR: Text reading/OCR error or 0 characters -> Rejected or Needs Review
    2. LOW_CONFIDENCE: Model confidence is available and < 0.75 -> Needs Review
    3. VALIDATION_FAILURE: Required field missing or malformed -> Needs Review
    4. HIGH_VALUE_POLICY: Invoices > $10,000 require manual signoff -> Needs Review
    5. AUTO_COMPLETE: All validations pass and high confidence -> Completed
    """
    rules_triggered: List[str] = []

    # Rule 1: Fatal Reading / Extraction Error
    if extraction_error or text_length < 20:
        err_msg = extraction_error or f"Extracted text is empty or too short ({text_length} chars)."
        rules_triggered.append("RULE_READING_FAILURE")
        return WorkflowDecision(
            target_state=STATE_NEEDS_REVIEW,
            decision_code="DOC_UNREADABLE",
            reason=f"Document could not be processed cleanly: {err_msg}",
            rules_triggered=rules_triggered,
            requires_human_review=True
        )

    # Rule 2: Confidence-Aware Review (Task 4)
    # Only applies when confidence is provided by the model; never fabricates a score.
    if confidence is not None:
        if confidence < CLASSIFIER_CONFIDENCE_THRESHOLD:
            rules_triggered.append("RULE_LOW_CONFIDENCE")
            conf_pct = round(confidence * 100, 1)
            thresh_pct = int(CLASSIFIER_CONFIDENCE_THRESHOLD * 100)
            return WorkflowDecision(
                target_state=STATE_NEEDS_REVIEW,
                decision_code="LOW_CONFIDENCE_CLASSIFICATION",
                reason=f"Classification confidence ({conf_pct}%) is below operational threshold ({thresh_pct}%). Requires verification.",
                rules_triggered=rules_triggered,
                requires_human_review=True
            )

    # Rule 3: Advanced Document Validation Rules (Task 2)
    if not validation_result.get("is_valid", False):
        failed_fields = validation_result.get("failed_fields", [])
        field_errors = validation_result.get("field_errors", {})
        rules_triggered.append("RULE_VALIDATION_FAILURE")
        
        detail_lines = [f"{fld}: {field_errors.get(fld, 'Invalid')}" for fld in failed_fields]
        details_str = "; ".join(detail_lines)

        return WorkflowDecision(
            target_state=STATE_NEEDS_REVIEW,
            decision_code="VALIDATION_FAILED",
            reason=f"Validation failed for {len(failed_fields)} field(s): {', '.join(failed_fields)}. ({details_str})",
            rules_triggered=rules_triggered,
            requires_human_review=True
        )

    # Rule 4: Business Policy Rule - High Value Invoices
    if document_type == "Invoice":
        parsed_amount = validation_result.get("parsed_amount")
        if parsed_amount is not None and parsed_amount >= HIGH_VALUE_INVOICE_THRESHOLD:
            rules_triggered.append("RULE_HIGH_VALUE_THRESHOLD")
            return WorkflowDecision(
                target_state=STATE_NEEDS_REVIEW,
                decision_code="HIGH_VALUE_AUDIT",
                reason=f"Invoice total (${parsed_amount:,.2f}) meets or exceeds high-value threshold (${HIGH_VALUE_INVOICE_THRESHOLD:,.2f}). Requires supervisor approval.",
                rules_triggered=rules_triggered,
                requires_human_review=True
            )

    # Rule 5: Automated Workflow Completion
    rules_triggered.append("RULE_ALL_CHECKS_PASSED")
    conf_str = f" with {int(round(confidence * 100))}% confidence" if confidence is not None else ""
    return WorkflowDecision(
        target_state=STATE_COMPLETED,
        decision_code="AUTOMATED_COMPLETION",
        reason=f"All validation rules successfully passed{conf_str}. Workflow automated to completion.",
        rules_triggered=rules_triggered,
        requires_human_review=False
    )


# ==============================================================================
# 3. END-TO-END INGESTION & WORKFLOW PIPELINE
# ==============================================================================

def ingest_and_execute_workflow(
    file_bytes: bytes,
    original_filename: str,
    apply_ocr_preprocessing: bool = True,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the unified Week 5 target workflow:
    Upload → Validate → Hash/Dup Check → New → Processing → Read/OCR →
    Clean → Classify → Extract → Validate → Apply Rules → Complete/Review → Audit Log
    """
    start_time = time.perf_counter()

    # Step 1: Storage validation
    is_valid_upload, val_err = storage.validate_uploaded_file(original_filename, file_bytes)
    if not is_valid_upload:
        return {
            "success": False,
            "is_duplicate": False,
            "document_id": None,
            "status": "Failed",
            "message": f"Upload Validation Failed: {val_err}",
            "error_type": "VALIDATION_ERROR"
        }

    # Step 2: Hash & duplicate check
    file_hash = storage.compute_file_hash(file_bytes)
    is_dup, existing_doc = storage.check_for_duplicate(file_hash, db_path=db_path)
    if is_dup and existing_doc:
        return {
            "success": True,
            "is_duplicate": True,
            "document_id": existing_doc.get("id"),
            "document_record": existing_doc,
            "status": existing_doc.get("status"),
            "message": f"Duplicate document detected! '{original_filename}' matches existing record #{existing_doc.get('id')} ({existing_doc.get('original_filename')}).",
            "file_hash": file_hash
        }

    # Step 3: Insert Initial Record in 'New' state
    doc_payload = {
        "original_filename": original_filename,
        "stored_filename": f"pending_{file_hash[:8]}",
        "document_type": "Unknown",
        "company": "Not Found",
        "invoice_number": "Not Found",
        "total_amount": "Not Found",
        "file_path": "pending",
        "text_preview": "",
        "file_hash": file_hash,
        "status": STATE_NEW,
        "file_size": len(file_bytes),
        "mime_type": "application/pdf" if original_filename.lower().endswith(".pdf") else "image/png",
        "confidence": None,
        "extracted_json": "{}",
        "validation_json": "{}",
        "review_reason": "Document uploaded and queued for processing.",
        "processing_time_ms": 0.0
    }

    try:
        doc_id = database.insert_document(doc_payload, db_path=db_path)
    except Exception as e:
        logger.error(f"Failed to insert new document into DB: {e}")
        return {
            "success": False,
            "is_duplicate": False,
            "document_id": None,
            "status": "Failed",
            "message": f"Database insertion failed: {str(e)}",
            "error_type": "DATABASE_ERROR"
        }

    # Record Audit: Upload
    audit.log_event(
        document_id=doc_id,
        action=audit.ACTION_UPLOAD,
        previous_status="None",
        new_status=STATE_NEW,
        reason="Document uploaded successfully.",
        performed_by="System",
        db_path=db_path
    )

    # Step 4: Transition New -> Processing
    database.update_document_status(doc_id, STATE_PROCESSING, "Extraction and classification running.", db_path=db_path)
    audit.log_event(
        document_id=doc_id,
        action=audit.ACTION_PROCESS_START,
        previous_status=STATE_NEW,
        new_status=STATE_PROCESSING,
        reason="Automated pipeline started.",
        performed_by="Workflow Engine",
        db_path=db_path
    )

    # Step 5: Read / OCR extraction
    raw_text, cleaned_text, proc_meta = processor.read_and_process_document(
        file_bytes=file_bytes,
        filename=original_filename,
        apply_ocr_preprocessing=apply_ocr_preprocessing
    )
    extraction_error = proc_meta.get("error")

    # Step 6: Classification & Confidence Scoring
    cls_result = classifier.classify_document(cleaned_text)
    document_type = cls_result.get("document_type", "Other")
    confidence = cls_result.get("confidence")  # None if model doesn't provide it

    # Step 7: Information Extraction
    extract_result = extractor.extract_document_information(cleaned_text, document_type)
    flat_values = extract_result.get("flat_values", {})

    # Step 8: Document Validation (Task 2)
    val_result = validator.validate_document(document_type, flat_values)

    # Step 9: Save physical file to category folder
    stored_filename, stored_path = storage.save_document_file(
        file_bytes=file_bytes,
        original_filename=original_filename,
        document_type=document_type,
        file_hash=file_hash
    )

    # Step 10: Apply Rule-Based Workflow Engine (Task 3)
    decision = evaluate_workflow_rules(
        document_type=document_type,
        validation_result=val_result,
        confidence=confidence,
        text_length=len(cleaned_text),
        extraction_error=extraction_error
    )

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # Map primary display columns
    if document_type == "Invoice":
        company = flat_values.get("company", "Not Found")
        invoice_no = flat_values.get("invoice_number", "Not Found")
        total_amount = flat_values.get("total_amount", "Not Found")
    elif document_type == "Resume":
        company = flat_values.get("name", "Not Found")
        invoice_no = flat_values.get("email", "Not Found")
        skills_summary = flat_values.get("skills", "Not Found")
        total_amount = f"{skills_summary[:28]}..." if len(skills_summary) > 28 else skills_summary
    else:
        company = flat_values.get("document_title", "General Document")
        invoice_no = flat_values.get("subject", "N/A")
        total_amount = flat_values.get("date", "N/A")

    preview_snippet = " ".join(cleaned_text.split())[:1200] if cleaned_text else "[No text preview available]"

    # Step 11: Update database with final decision and metadata
    database.update_document_processing_result(
        doc_id=doc_id,
        status=decision.target_state,
        document_type=document_type,
        company=company,
        invoice_number=invoice_no,
        total_amount=total_amount,
        confidence=confidence,
        extracted_json=json.dumps(extract_result),
        validation_json=json.dumps(val_result),
        review_reason=decision.reason,
        processing_time_ms=elapsed_ms,
        text_preview=preview_snippet,
        db_path=db_path
    )

    # Also update storage file path and stored filename
    conn = database.get_db_connection(db_path)
    with conn:
        conn.execute("UPDATE documents SET stored_filename = ?, file_path = ? WHERE id = ?", (stored_filename, stored_path, doc_id))
    conn.close()

    # Step 12: Record Audit Event for Decision
    action_type = audit.ACTION_ROUTE_REVIEW if decision.target_state == STATE_NEEDS_REVIEW else audit.ACTION_AUTO_DECISION
    audit.log_event(
        document_id=doc_id,
        action=action_type,
        previous_status=STATE_PROCESSING,
        new_status=decision.target_state,
        reason=f"[{decision.decision_code}] {decision.reason}",
        performed_by="Rule-Based Workflow Engine",
        db_path=db_path
    )

    doc_record = database.get_document_by_id(doc_id, db_path=db_path)

    return {
        "success": True,
        "is_duplicate": False,
        "document_id": doc_id,
        "status": decision.target_state,
        "document_type": document_type,
        "confidence": confidence,
        "decision": decision,
        "validation_result": val_result,
        "document_record": doc_record,
        "message": f"Document #{doc_id} workflow executed → '{decision.target_state}' in {elapsed_ms}ms.",
        "file_hash": file_hash,
        "processing_time_ms": elapsed_ms
    }


# ==============================================================================
# 4. HUMAN REVIEW QUEUE ACTIONS (Task 6)
# ==============================================================================

def approve_document(
    doc_id: int,
    reviewer_notes: str = "",
    performed_by: str = "Human Reviewer",
    db_path: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Task 6: Reviewer accepts the document.
    Moves document from 'Needs Review' -> 'Approved' (and then to 'Completed').
    Records audit history for the review decision.
    """
    doc = database.get_document_by_id(doc_id, db_path=db_path)
    if not doc:
        return False, f"Document #{doc_id} not found."

    current_status = doc.get("status")
    allowed, msg = can_transition(current_status, STATE_APPROVED)
    if not allowed:
        return False, f"Cannot approve document: {msg}"

    note_text = reviewer_notes.strip() or "Accepted by reviewer."
    
    # Update to Approved
    database.update_document_status(
        doc_id=doc_id,
        new_status=STATE_APPROVED,
        review_reason=f"Approved: {note_text}",
        reviewer_notes=note_text,
        db_path=db_path
    )
    audit.log_event(
        document_id=doc_id,
        action=audit.ACTION_APPROVE,
        previous_status=current_status,
        new_status=STATE_APPROVED,
        reason=note_text,
        performed_by=performed_by,
        db_path=db_path
    )

    # Immediately transition from Approved to Completed (successful workflow completion)
    database.update_document_status(
        doc_id=doc_id,
        new_status=STATE_COMPLETED,
        review_reason=f"Completed following approval: {note_text}",
        reviewer_notes=note_text,
        db_path=db_path
    )
    audit.log_event(
        document_id=doc_id,
        action=audit.ACTION_COMPLETE,
        previous_status=STATE_APPROVED,
        new_status=STATE_COMPLETED,
        reason="Workflow completed post-approval.",
        performed_by="System",
        db_path=db_path
    )

    return True, f"Document #{doc_id} approved and completed successfully."


def reject_document(
    doc_id: int,
    rejection_reason: str,
    performed_by: str = "Human Reviewer",
    db_path: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Task 6: Reviewer rejects the document.
    Enforces Requirement: 'Require a short reason when rejecting'.
    Moves document to 'Rejected' and records audit history.
    """
    clean_reason = rejection_reason.strip() if rejection_reason else ""
    if not clean_reason or len(clean_reason) < 4:
        return False, "Rejection rejected: A valid short reason is mandatory when rejecting a document (minimum 4 characters)."

    doc = database.get_document_by_id(doc_id, db_path=db_path)
    if not doc:
        return False, f"Document #{doc_id} not found."

    current_status = doc.get("status")
    allowed, msg = can_transition(current_status, STATE_REJECTED)
    if not allowed:
        return False, f"Cannot reject document: {msg}"

    database.update_document_status(
        doc_id=doc_id,
        new_status=STATE_REJECTED,
        review_reason=f"Rejected: {clean_reason}",
        reviewer_notes=clean_reason,
        db_path=db_path
    )
    audit.log_event(
        document_id=doc_id,
        action=audit.ACTION_REJECT,
        previous_status=current_status,
        new_status=STATE_REJECTED,
        reason=clean_reason,
        performed_by=performed_by,
        db_path=db_path
    )

    return True, f"Document #{doc_id} rejected. Reason recorded in audit trail."


# ==============================================================================
# 5. BATCH WORKFLOW PROCESSING (Task 7)
# ==============================================================================

def execute_batch_workflow(
    doc_ids: List[int],
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Task 7: Batch Workflow Processing
    - Selects several stored documents at once.
    - Runs the same workflow rules for every selected document.
    - Shows processed, review, completed, rejected, and failed counts.
    - CRITICAL: One failed document must not stop the entire batch!
    - Records an individual result and audit entry for every document.
    """
    results: List[Dict[str, Any]] = []
    counts = {
        "processed": 0,
        "completed": 0,
        "review": 0,
        "rejected": 0,
        "failed": 0
    }

    if not doc_ids:
        return {
            "total_selected": 0,
            "processed_count": 0,
            "review_count": 0,
            "completed_count": 0,
            "rejected_count": 0,
            "failed_count": 0,
            "results": []
        }

    docs = database.get_documents_by_ids(doc_ids, db_path=db_path)
    doc_lookup = {d["id"]: d for d in docs}

    for target_id in doc_ids:
        doc = doc_lookup.get(target_id)
        if not doc:
            # Missing document handled without crashing batch
            counts["failed"] += 1
            results.append({
                "document_id": target_id,
                "original_filename": "Unknown",
                "old_status": "Unknown",
                "new_status": "Failed",
                "success": False,
                "error": f"Document ID #{target_id} not found in database."
            })
            continue

        filename = doc.get("original_filename", "unnamed")
        old_status = doc.get("status", STATE_NEW)

        try:
            # Extract metadata and perform rule evaluation
            file_path = doc.get("file_path", "")
            raw_text = doc.get("text_preview", "")
            
            # Read from file if file exists
            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, "rb") as f:
                        file_bytes = f.read()
                    _, cleaned_text, _ = processor.read_and_process_document(file_bytes, filename)
                except Exception:
                    cleaned_text = raw_text
            else:
                cleaned_text = raw_text

            # Re-classify and re-extract
            cls_result = classifier.classify_document(cleaned_text)
            doc_type = cls_result.get("document_type", doc.get("document_type", "Other"))
            confidence = cls_result.get("confidence")

            extract_result = extractor.extract_document_information(cleaned_text, doc_type)
            flat_values = extract_result.get("flat_values", {})

            val_result = validator.validate_document(doc_type, flat_values)

            # Evaluate rules
            decision = evaluate_workflow_rules(
                document_type=doc_type,
                validation_result=val_result,
                confidence=confidence,
                text_length=len(cleaned_text)
            )

            # Check transition validity
            allowed, t_msg = can_transition(old_status, decision.target_state)
            target_state = decision.target_state if allowed else old_status
            decision_reason = decision.reason if allowed else f"Rule evaluated {decision.target_state}, but transition blocked: {t_msg}"

            if allowed:
                database.update_document_status(
                    doc_id=target_id,
                    new_status=target_state,
                    review_reason=decision_reason,
                    db_path=db_path
                )
                audit.log_event(
                    document_id=target_id,
                    action=audit.ACTION_BATCH_PROCESS,
                    previous_status=old_status,
                    new_status=target_state,
                    reason=f"Batch re-evaluation: {decision_reason}",
                    performed_by="Batch Workflow Processor",
                    db_path=db_path
                )

            counts["processed"] += 1
            if target_state == STATE_COMPLETED:
                counts["completed"] += 1
            elif target_state == STATE_NEEDS_REVIEW:
                counts["review"] += 1
            elif target_state == STATE_REJECTED:
                counts["rejected"] += 1

            results.append({
                "document_id": target_id,
                "original_filename": filename,
                "old_status": old_status,
                "new_status": target_state,
                "success": True,
                "reason": decision_reason,
                "rules_triggered": decision.rules_triggered
            })

        except Exception as e:
            # DEFENSIVE: One failed document does NOT stop the entire batch
            logger.error(f"Error batch-processing doc #{target_id}: {e}")
            counts["failed"] += 1
            results.append({
                "document_id": target_id,
                "original_filename": filename,
                "old_status": old_status,
                "new_status": "Failed",
                "success": False,
                "error": str(e)
            })

    return {
        "total_selected": len(doc_ids),
        "processed_count": counts["processed"],
        "review_count": counts["review"],
        "completed_count": counts["completed"],
        "rejected_count": counts["rejected"],
        "failed_count": counts["failed"],
        "results": results
    }
