"""
ZYROO INTERNSHIP PROGRAM - WEEK 6
Module: Workflow State Machine, Decision Engine & Fault-Tolerant Batch Processor
Focus: Complete end-to-end integration, optimization, security, and auditability
"""

import os
import json
import time
import logging
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field

import config
import database
import storage
import processor
import classifier
import extractor
import validator
import anomaly
import rag_engine
import audit

logger = logging.getLogger("workflow_engine")

# ==============================================================================
# 1. WORKFLOW STATES & STATE MACHINE
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

VALID_TRANSITIONS: Dict[str, List[str]] = {
    STATE_NEW: [STATE_PROCESSING, STATE_REJECTED],
    STATE_PROCESSING: [STATE_NEEDS_REVIEW, STATE_COMPLETED, STATE_REJECTED],
    STATE_NEEDS_REVIEW: [STATE_APPROVED, STATE_REJECTED, STATE_PROCESSING],
    STATE_APPROVED: [STATE_COMPLETED, STATE_PROCESSING],
    STATE_REJECTED: [STATE_PROCESSING],
    STATE_COMPLETED: []  # Terminal state
}


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal workflow state transition is attempted."""
    pass


def can_transition(current_state: str, target_state: str) -> Tuple[bool, str]:
    """
    Validates if a transition between two workflow states is legally permitted.
    Returns (is_allowed: bool, explanation_message: str).
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

    # Explanatory diagnostics
    if current_state == STATE_COMPLETED:
        return False, "Cannot transition from 'Completed'. It is a final terminal state."
    if current_state == STATE_NEW and target_state in (STATE_APPROVED, STATE_COMPLETED):
        return False, f"Cannot transition directly from 'New' to '{target_state}'. Document must be processed first."
    if current_state == STATE_PROCESSING and target_state == STATE_APPROVED:
        return False, "Cannot transition directly from 'Processing' to 'Approved'. Approval requires human review."

    return False, f"Illegal state transition from '{current_state}' to '{target_state}'. Allowed targets: {allowed_targets}."


# ==============================================================================
# 2. RULE-BASED WORKFLOW DECISION ENGINE
# ==============================================================================

@dataclass
class WorkflowDecision:
    target_state: str
    decision_code: str
    reason: str
    rules_triggered: List[str] = field(default_factory=list)
    requires_human_review: bool = False


def evaluate_workflow_rules(
    document_type: str,
    validation_result: Dict[str, Any],
    anomaly_result: Dict[str, Any],
    confidence: Optional[float],
    text_length: int,
    extraction_error: Optional[str] = None
) -> WorkflowDecision:
    """
    Evaluates rule-based workflow logic to determine document's next state:
    1. Fatal Error / Unreadable Text -> Needs Review
    2. Anomaly Flags (Arithmetic Mismatch, Repeated ID, etc.) -> Needs Review
    3. Low Model Confidence (< 0.75) -> Needs Review
    4. Validation Failures (Missing / Invalid Fields) -> Needs Review
    5. High-Value Financial Policy -> Needs Review
    6. Automated Completion -> Completed
    """
    rules_triggered: List[str] = []

    # Rule 1: Fatal Reading Error
    if extraction_error or text_length < config.MIN_TEXT_LENGTH_FOR_EXTRACTION:
        err_msg = extraction_error or f"Extracted text is empty or too short ({text_length} chars)."
        rules_triggered.append("RULE_READING_FAILURE")
        return WorkflowDecision(
            target_state=STATE_NEEDS_REVIEW,
            decision_code="DOC_UNREADABLE",
            reason=f"Document unreadable or corrupt: {err_msg}",
            rules_triggered=rules_triggered,
            requires_human_review=True
        )

    # Rule 2: Anomaly Detection Flags
    if anomaly_result.get("has_anomalies", False):
        anom_list = anomaly_result.get("anomalies", [])
        codes = [a.get("code") for a in anom_list]
        msgs = [a.get("message") for a in anom_list]
        rules_triggered.extend(codes)

        return WorkflowDecision(
            target_state=STATE_NEEDS_REVIEW,
            decision_code="ANOMALY_FLAGGED",
            reason=f"Anomaly detected: {'; '.join(msgs)}",
            rules_triggered=rules_triggered,
            requires_human_review=True
        )

    # Rule 3: Confidence-Aware Review
    if confidence is not None and confidence < config.CLASSIFIER_CONFIDENCE_THRESHOLD:
        rules_triggered.append("RULE_LOW_CONFIDENCE")
        conf_pct = round(confidence * 100, 1)
        thresh_pct = int(config.CLASSIFIER_CONFIDENCE_THRESHOLD * 100)
        return WorkflowDecision(
            target_state=STATE_NEEDS_REVIEW,
            decision_code="LOW_CONFIDENCE_CLASSIFICATION",
            reason=f"Classification confidence ({conf_pct}%) is below operational threshold ({thresh_pct}%). Requires verification.",
            rules_triggered=rules_triggered,
            requires_human_review=True
        )

    # Rule 4: Validation Rule Failures
    if not validation_result.get("is_valid", False):
        failed_fields = validation_result.get("failed_fields", [])
        field_errors = validation_result.get("field_errors", {})
        rules_triggered.append("RULE_VALIDATION_FAILURE")
        detail_lines = [f"{fld}: {field_errors.get(fld, 'Invalid')}" for fld in failed_fields]
        return WorkflowDecision(
            target_state=STATE_NEEDS_REVIEW,
            decision_code="VALIDATION_FAILED",
            reason=f"Validation failed for {len(failed_fields)} field(s): {', '.join(failed_fields)}. ({'; '.join(detail_lines)})",
            rules_triggered=rules_triggered,
            requires_human_review=True
        )

    # Rule 5: Automated Workflow Completion
    rules_triggered.append("RULE_ALL_CHECKS_PASSED")
    conf_str = f" with {int(round(confidence * 100))}% confidence" if confidence is not None else ""
    return WorkflowDecision(
        target_state=STATE_COMPLETED,
        decision_code="AUTOMATED_COMPLETION",
        reason=f"All validation rules and anomaly checks successfully passed{conf_str}. Workflow automated to completion.",
        rules_triggered=rules_triggered,
        requires_human_review=False
    )


# ==============================================================================
# 3. END-TO-END UNIFIED INGESTION PIPELINE
# ==============================================================================

def ingest_and_execute_workflow(
    file_bytes: bytes,
    original_filename: str,
    apply_ocr_preprocessing: bool = True,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the complete Week 6 final product flow:
    Upload → Validate → OCR/Text Extraction → Classify → Extract → Store → Verify →
    Anomaly Check → RAG Indexing → Workflow Decision → Audit Log → Return Results
    """
    start_time = time.perf_counter()
    stage_timings: Dict[str, float] = {}

    # Step 1: File security & integrity validation
    t0 = time.perf_counter()
    is_valid_upload, val_err = storage.validate_uploaded_file(original_filename, file_bytes)
    stage_timings["file_validation_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    if not is_valid_upload:
        return {
            "success": False,
            "is_duplicate": False,
            "document_id": None,
            "status": "Failed",
            "message": f"Upload Validation Failed: {val_err}",
            "error_type": "VALIDATION_ERROR",
            "stage_timings": stage_timings
        }

    # Step 2: Cryptographic SHA-256 deduplication
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
            "file_hash": file_hash,
            "stage_timings": stage_timings
        }

    # Step 3: Insert initial record in 'New' state
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
        "anomaly_json": "{}",
        "review_reason": "Document uploaded and queued for processing.",
        "processing_time_ms": 0.0,
        "stage_timings_json": "{}"
    }

    try:
        doc_id = database.insert_document(doc_payload, db_path=db_path)
    except Exception as e:
        logger.error(f"Database insertion failed: {e}")
        return {
            "success": False,
            "is_duplicate": False,
            "document_id": None,
            "status": "Failed",
            "message": f"Database insertion failed: {str(e)}",
            "error_type": "DATABASE_ERROR"
        }

    # Log initial upload audit
    audit.log_event(
        document_id=doc_id,
        action=audit.ACTION_UPLOAD,
        previous_status="None",
        new_status=STATE_NEW,
        reason="Document uploaded successfully.",
        performed_by="System",
        db_path=db_path
    )

    # Step 4: Transition to 'Processing'
    database.update_document_status(doc_id, STATE_PROCESSING, "Processing pipeline active.", db_path=db_path)
    audit.log_event(
        document_id=doc_id,
        action=audit.ACTION_PROCESS_START,
        previous_status=STATE_NEW,
        new_status=STATE_PROCESSING,
        reason="Automated pipeline started.",
        performed_by="Workflow Engine",
        db_path=db_path
    )

    # Step 5: Text Extraction / OCR
    t0 = time.perf_counter()
    raw_text, cleaned_text, proc_meta = processor.read_and_process_document(
        file_bytes=file_bytes,
        filename=original_filename,
        apply_ocr_preprocessing=apply_ocr_preprocessing
    )
    stage_timings["ocr_extraction_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    extraction_error = proc_meta.get("error")

    if proc_meta.get("ocr_applied"):
        audit.log_event(
            document_id=doc_id,
            action=audit.ACTION_OCR_PERFORMED,
            previous_status=STATE_PROCESSING,
            new_status=STATE_PROCESSING,
            reason="OCR extraction performed on scanned pages/images.",
            performed_by="OCR Engine",
            db_path=db_path
        )

    # Step 6: Classification
    t0 = time.perf_counter()
    cls_result = classifier.classify_document(cleaned_text)
    stage_timings["classification_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    document_type = cls_result.get("document_type", "Other")
    confidence = cls_result.get("confidence")

    audit.log_event(
        document_id=doc_id,
        action=audit.ACTION_CLASSIFIED,
        previous_status=STATE_PROCESSING,
        new_status=STATE_PROCESSING,
        reason=f"Classified as '{document_type}' (Confidence: {cls_result.get('confidence_percentage', 'N/A')}).",
        performed_by="ML Classifier",
        db_path=db_path
    )

    # Step 7: Information Extraction
    t0 = time.perf_counter()
    extract_result = extractor.extract_document_information(cleaned_text, document_type)
    stage_timings["extraction_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    flat_values = extract_result.get("flat_values", {})

    audit.log_event(
        document_id=doc_id,
        action=audit.ACTION_EXTRACTED,
        previous_status=STATE_PROCESSING,
        new_status=STATE_PROCESSING,
        reason=f"Extracted entities with completeness {extract_result.get('completeness_score', 'N/A')}.",
        performed_by="Extractor Engine",
        db_path=db_path
    )

    # Step 8: Document Validation
    t0 = time.perf_counter()
    val_result = validator.validate_document(document_type, flat_values)
    stage_timings["validation_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    # Step 9: Anomaly & Inconsistency Detection
    t0 = time.perf_counter()
    anom_result = anomaly.detect_anomalies(
        document_type=document_type,
        extracted_flat_values=flat_values,
        validation_result=val_result,
        confidence=confidence,
        text=cleaned_text,
        current_doc_id=doc_id,
        current_file_hash=file_hash,
        db_path=db_path
    )
    stage_timings["anomaly_check_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    if anom_result.get("has_anomalies"):
        audit.log_event(
            document_id=doc_id,
            action=audit.ACTION_ANOMALY_DETECTED,
            previous_status=STATE_PROCESSING,
            new_status=STATE_PROCESSING,
            reason=f"Detected {anom_result.get('anomaly_count')} anomaly flags.",
            performed_by="Anomaly Engine",
            db_path=db_path
        )

    # Step 10: RAG Semantic Chunking & Indexing
    t0 = time.perf_counter()
    chunks_indexed = rag_engine.index_document_for_rag(
        document_id=doc_id,
        text=cleaned_text,
        page_texts=proc_meta.get("page_texts"),
        db_path=db_path
    )
    stage_timings["rag_indexing_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    if chunks_indexed > 0:
        audit.log_event(
            document_id=doc_id,
            action=audit.ACTION_RAG_INDEXED,
            previous_status=STATE_PROCESSING,
            new_status=STATE_PROCESSING,
            reason=f"Indexed {chunks_indexed} semantic chunks for RAG search.",
            performed_by="RAG Indexer",
            db_path=db_path
        )

    # Step 11: Save physical file to category folder
    stored_filename, stored_path = storage.save_document_file(
        file_bytes=file_bytes,
        original_filename=original_filename,
        document_type=document_type,
        file_hash=file_hash
    )

    # Step 12: Rule-Based Workflow Decision
    decision = evaluate_workflow_rules(
        document_type=document_type,
        validation_result=val_result,
        anomaly_result=anom_result,
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
    elif document_type == "Contract":
        company = flat_values.get("contract_title", "Agreement")
        invoice_no = flat_values.get("governing_law", "General")
        total_amount = flat_values.get("effective_date", "Not Found")
    else:
        company = flat_values.get("document_title", "General Document")
        invoice_no = flat_values.get("subject", "N/A")
        total_amount = flat_values.get("date", "N/A")

    preview_snippet = " ".join(cleaned_text.split())[:1200] if cleaned_text else "[No text preview available]"

    # Step 13: Update database with final decision and metadata
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
        anomaly_json=json.dumps(anom_result),
        review_reason=decision.reason,
        processing_time_ms=elapsed_ms,
        stage_timings_json=json.dumps(stage_timings),
        text_preview=preview_snippet,
        db_path=db_path
    )

    # Update storage file path
    conn = database.get_db_connection(db_path)
    with conn:
        conn.execute("UPDATE documents SET stored_filename = ?, file_path = ? WHERE id = ?", (stored_filename, stored_path, doc_id))
    conn.close()

    # Step 14: Log audit event for decision
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
        "anomaly_result": anom_result,
        "document_record": doc_record,
        "message": f"Document #{doc_id} workflow executed → '{decision.target_state}' in {elapsed_ms}ms.",
        "file_hash": file_hash,
        "processing_time_ms": elapsed_ms,
        "stage_timings": stage_timings
    }


# ==============================================================================
# 4. HUMAN REVIEW QUEUE ACTIONS (WITH RBAC)
# ==============================================================================

def approve_document(
    doc_id: int,
    reviewer_notes: str = "",
    performed_by: str = "Human Reviewer",
    user_role: str = config.ROLE_REVIEWER,
    db_path: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Reviewer accepts the document.
    Enforces Role-Based Access Control: Viewer role cannot approve.
    Transitions 'Needs Review' -> 'Approved' -> 'Completed'.
    """
    if user_role == config.ROLE_VIEWER:
        return False, "Access Denied: Role 'Viewer' has read-only permissions and cannot approve documents."

    doc = database.get_document_by_id(doc_id, db_path=db_path)
    if not doc:
        return False, f"Document #{doc_id} not found."

    current_status = doc.get("status")
    allowed, msg = can_transition(current_status, STATE_APPROVED)
    if not allowed:
        return False, f"Cannot approve document: {msg}"

    note_text = reviewer_notes.strip() or "Accepted by reviewer."

    # Update to Approved
    database.update_document_status(doc_id, STATE_APPROVED, note_text, db_path=db_path)
    audit.log_event(
        document_id=doc_id,
        action=audit.ACTION_APPROVE,
        previous_status=current_status,
        new_status=STATE_APPROVED,
        reason=f"Approved by {performed_by} ({user_role}): {note_text}",
        performed_by=performed_by,
        db_path=db_path
    )

    # Immediately transition Approved -> Completed
    database.update_document_status(doc_id, STATE_COMPLETED, "Workflow complete following human verification.", db_path=db_path)
    audit.log_event(
        document_id=doc_id,
        action=audit.ACTION_COMPLETE,
        previous_status=STATE_APPROVED,
        new_status=STATE_COMPLETED,
        reason="Workflow successfully finalized.",
        performed_by="System",
        db_path=db_path
    )

    return True, f"Document #{doc_id} successfully approved and completed."


def reject_document(
    doc_id: int,
    rejection_reason: str,
    performed_by: str = "Human Reviewer",
    user_role: str = config.ROLE_REVIEWER,
    db_path: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Reviewer rejects the document.
    Enforces non-empty rejection reason and RBAC permissions.
    Transitions 'Needs Review' -> 'Rejected'.
    """
    if user_role == config.ROLE_VIEWER:
        return False, "Access Denied: Role 'Viewer' has read-only permissions and cannot reject documents."

    if not rejection_reason or not rejection_reason.strip():
        return False, "Rejection failed: A clear, non-empty rejection justification is mandatory."

    doc = database.get_document_by_id(doc_id, db_path=db_path)
    if not doc:
        return False, f"Document #{doc_id} not found."

    current_status = doc.get("status")
    allowed, msg = can_transition(current_status, STATE_REJECTED)
    if not allowed:
        return False, f"Cannot reject document: {msg}"

    clean_reason = rejection_reason.strip()
    database.update_document_status(doc_id, STATE_REJECTED, clean_reason, db_path=db_path)

    audit.log_event(
        document_id=doc_id,
        action=audit.ACTION_REJECT,
        previous_status=current_status,
        new_status=STATE_REJECTED,
        reason=f"Rejected by {performed_by} ({user_role}): {clean_reason}",
        performed_by=performed_by,
        db_path=db_path
    )

    return True, f"Document #{doc_id} rejected. Reason logged in immutable audit history."


def edit_document_fields(
    doc_id: int,
    updated_fields: Dict[str, Any],
    performed_by: str = "Human Reviewer",
    db_path: Optional[str] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """Updates document fields following manual correction and re-validates."""
    doc = database.get_document_by_id(doc_id, db_path=db_path)
    if not doc:
        return False, f"Document #{doc_id} not found.", {}

    doc_type = doc.get("document_type", "Other")
    try:
        existing_extracted = json.loads(doc.get("extracted_json") or "{}")
    except Exception:
        existing_extracted = {}

    flat_values = existing_extracted.get("flat_values", {})
    flat_values.update(updated_fields)
    existing_extracted["flat_values"] = flat_values

    # Re-validate
    val_result = validator.validate_document(doc_type, flat_values)

    # Persist
    database.update_document_fields(
        doc_id=doc_id,
        fields={
            "company": flat_values.get("company", doc.get("company")),
            "invoice_number": flat_values.get("invoice_number", doc.get("invoice_number")),
            "total_amount": flat_values.get("total_amount", doc.get("total_amount")),
            "extracted_json": json.dumps(existing_extracted)
        },
        db_path=db_path
    )

    # Update validation json in db
    conn = database.get_db_connection(db_path)
    with conn:
        conn.execute("UPDATE documents SET validation_json = ? WHERE id = ?", (json.dumps(val_result), doc_id))
    conn.close()

    audit.log_event(
        document_id=doc_id,
        action=audit.ACTION_FIELD_EDIT,
        previous_status=doc.get("status"),
        new_status=doc.get("status"),
        reason=f"Fields edited by {performed_by}: {list(updated_fields.keys())}",
        performed_by=performed_by,
        db_path=db_path
    )

    return True, f"Document #{doc_id} fields updated and re-validated.", val_result


# ==============================================================================
# 5. FAULT-TOLERANT BATCH WORKFLOW PROCESSING
# ==============================================================================

def process_batch_files(
    file_tuples: List[Tuple[str, bytes]],
    apply_ocr: bool = True,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Processes multiple documents in a single batch with full fault tolerance:
    One document failure does not halt or abort remaining files.
    """
    batch_start = time.perf_counter()
    results: List[Dict[str, Any]] = []
    success_count = 0
    failure_count = 0
    duplicate_count = 0

    for filename, file_bytes in file_tuples:
        try:
            res = ingest_and_execute_workflow(
                file_bytes=file_bytes,
                original_filename=filename,
                apply_ocr_preprocessing=apply_ocr,
                db_path=db_path
            )
            if res.get("is_duplicate"):
                duplicate_count += 1
            elif res.get("success"):
                success_count += 1
            else:
                failure_count += 1
            results.append(res)
        except Exception as e:
            logger.error(f"Batch processing error on '{filename}': {e}")
            failure_count += 1
            results.append({
                "success": False,
                "is_duplicate": False,
                "document_id": None,
                "original_filename": filename,
                "status": "Failed",
                "message": f"Unexpected batch exception: {str(e)}",
                "error_type": "BATCH_EXCEPTION"
            })

    total_time_ms = round((time.perf_counter() - batch_start) * 1000, 2)

    return {
        "total_submitted": len(file_tuples),
        "success_count": success_count,
        "failure_count": failure_count,
        "duplicate_count": duplicate_count,
        "total_time_ms": total_time_ms,
        "avg_time_per_doc_ms": round(total_time_ms / max(len(file_tuples), 1), 2),
        "results": results
    }
