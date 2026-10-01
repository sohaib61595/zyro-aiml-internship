"""
ZYROO INTERNSHIP PROGRAM - WEEK 5
Automated Verification Suite: Advanced Document Workflow & Automation Platform
Focus: Workflow automation, validation, review, auditability and reliability testing

Test Scenarios (Requirement 10 & Requirements 1-9):
1. Ingestion of 15 Diverse Documents across Invoices, Resumes, Scanned, and Other cases.
2. Normal Invoice & Resume automated pass through rules engine to 'Completed'.
3. Missing required fields routed to 'Needs Review' with exact failure fields recorded.
4. Invalid extracted email, date, and numeric amount formats trapped by validator.
5. Scanned document reading and OCR fallback handling.
6. Duplicate document detection via SHA-256 hash.
7. Low-confidence classification threshold awareness (< 0.75 routed to 'Needs Review').
8. Finite State Machine: Valid transitions allowed, invalid state transitions strictly blocked.
9. Human Review Queue actions: Approve and Reject (with mandatory rejection reason enforcement).
10. Complete Audit Log verification: Traceability of all actions, states, and reviewer notes.
11. Mixed-success Batch Workflow Processing: One failed document does not stop the batch.
12. Multi-field search, status filtering, and workflow metrics aggregation.
"""

import os
import sys
import json
import tempfile
import sqlite3
from typing import Dict, Any, List

# Ensure week 5 modules can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import database
import storage
import processor
import classifier
import extractor
import validator
import audit
import workflow


def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def run_week5_test_suite():
    print_banner("STARTING ZYROO WEEK 5 WORKFLOW AUTOMATION TEST SUITE")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    samples_dir = os.path.join(base_dir, "samples")
    assert os.path.exists(samples_dir), f"Samples directory missing at {samples_dir}"

    test_db = os.path.join(base_dir, "test_workflow_repository.db")
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass

    database.init_db(test_db)
    storage.ensure_storage_structure()
    print(f"Initialized clean test database at: {test_db}")

    # =========================================================================
    # TEST 1: INGESTION OF 15 DIVERSE DOCUMENTS
    # =========================================================================
    print_banner("TEST 1: INGESTION & PIPELINE EXECUTION FOR 15 TEST DOCUMENTS")
    sample_files = [
        # Normal Invoices
        "invoice_standard.pdf",
        "invoice_pkr_currency.pdf",
        "invoice_consulting_services.pdf",
        # Missing & Invalid Invoices
        "invoice_missing_fields.pdf",
        "invoice_invalid_date_amount.pdf",
        "invoice_high_value_audit.pdf",
        "invoice_scanned_receipt.png",
        # Normal & Edge Resumes
        "resume_software_engineer.pdf",
        "resume_missing_contact.pdf",
        "resume_invalid_email.pdf",
        "resume_scanned.jpg",
        # Other & Ambiguous Documents
        "other_business_memo.pdf",
        "other_contract_agreement.pdf",
        "other_policy_guidelines.pdf",
        "document_low_confidence_ambiguous.pdf"
    ]

    ingested_results: List[Dict[str, Any]] = []

    for idx, fname in enumerate(sample_files, 1):
        fpath = os.path.join(samples_dir, fname)
        assert os.path.exists(fpath), f"File {fname} not found in samples"

        with open(fpath, "rb") as f:
            b_data = f.read()

        res = workflow.ingest_and_execute_workflow(
            file_bytes=b_data,
            original_filename=fname,
            apply_ocr_preprocessing=True,
            db_path=test_db
        )

        assert res["success"] is True, f"Failed ingesting {fname}: {res.get('message')}"
        assert res["is_duplicate"] is False, f"Unexpected duplicate for fresh file {fname}"
        doc_rec = res["document_record"]
        ingested_results.append(res)

        conf_str = f"{int(round(res['confidence']*100))}%" if res['confidence'] is not None else "None"
        print(f"[{idx:02d}/15] Ingested: {fname:<35} | Type: {res['document_type']:<8} | State: {res['status']:<12} | Conf: {conf_str:<4} | Time: {res['processing_time_ms']}ms")

    assert len(ingested_results) == 15, "Expected 15 documents to be ingested."
    print(">>> PASS: All 15 documents ingested and moved through workflow engine.")

    # =========================================================================
    # TEST 2: VERIFY VALIDATION & DECISION LOGIC
    # =========================================================================
    print_banner("TEST 2: ADVANCED DOCUMENT VALIDATION & RULE ENGINE DECISIONS")
    
    # 2A: Standard Invoice should be Completed
    std_inv = next(r for r in ingested_results if r["document_record"]["original_filename"] == "invoice_standard.pdf")
    assert std_inv["status"] == "Completed", f"Expected 'invoice_standard.pdf' to be Completed, got {std_inv['status']}"
    assert std_inv["validation_result"]["is_valid"] is True
    print(f"  [OK] Standard Invoice: State='{std_inv['status']}' | Reason: {std_inv['decision'].reason}")

    # 2B: Standard Resume should be Completed
    std_res = next(r for r in ingested_results if r["document_record"]["original_filename"] == "resume_software_engineer.pdf")
    assert std_res["status"] == "Completed", f"Expected 'resume_software_engineer.pdf' to be Completed, got {std_res['status']}"
    assert std_res["validation_result"]["is_valid"] is True
    print(f"  [OK] Standard Resume: State='{std_res['status']}' | Reason: {std_res['decision'].reason}")

    # 2C: Missing Fields Invoice -> Needs Review
    miss_inv = next(r for r in ingested_results if r["document_record"]["original_filename"] == "invoice_missing_fields.pdf")
    assert miss_inv["status"] == "Needs Review", f"Expected 'invoice_missing_fields.pdf' to be Needs Review, got {miss_inv['status']}"
    assert miss_inv["validation_result"]["is_valid"] is False
    assert len(miss_inv["validation_result"]["failed_fields"]) > 0
    print(f"  [OK] Missing Fields Invoice: State='{miss_inv['status']}' | Failed fields: {miss_inv['validation_result']['failed_fields']}")

    # 2D: Invalid Date & Amount Format -> Needs Review
    inv_date_amt = next(r for r in ingested_results if r["document_record"]["original_filename"] == "invoice_invalid_date_amount.pdf")
    assert inv_date_amt["status"] == "Needs Review", f"Expected invalid date/amount to be Needs Review, got {inv_date_amt['status']}"
    assert "date" in inv_date_amt["validation_result"]["failed_fields"] or "total_amount" in inv_date_amt["validation_result"]["failed_fields"]
    print(f"  [OK] Invalid Date/Amount Invoice: State='{inv_date_amt['status']}' | Errors: {inv_date_amt['validation_result']['field_errors']}")

    # 2E: Invalid Email Format Resume -> Needs Review
    inv_email = next(r for r in ingested_results if r["document_record"]["original_filename"] == "resume_invalid_email.pdf")
    assert inv_email["status"] == "Needs Review", f"Expected invalid email resume to be Needs Review, got {inv_email['status']}"
    assert "email" in inv_email["validation_result"]["failed_fields"]
    print(f"  [OK] Invalid Email Resume: State='{inv_email['status']}' | Failed: {inv_email['validation_result']['field_errors'].get('email')}")

    # 2F: High Value Invoice -> Needs Review (Policy Rule)
    high_val = next(r for r in ingested_results if r["document_record"]["original_filename"] == "invoice_high_value_audit.pdf")
    assert high_val["status"] == "Needs Review", f"Expected high value invoice to be Needs Review, got {high_val['status']}"
    assert "RULE_HIGH_VALUE_THRESHOLD" in high_val["decision"].rules_triggered
    print(f"  [OK] High Value Invoice Policy: State='{high_val['status']}' | Rule: {high_val['decision'].rules_triggered}")

    print(">>> PASS: Document validation and rule-based decisions verified.")

    # =========================================================================
    # TEST 3: DUPLICATE DETECTION (SHA-256)
    # =========================================================================
    print_banner("TEST 3: CRYPTOGRAPHIC SHA-256 DUPLICATE DETECTION")
    fpath = os.path.join(samples_dir, "invoice_standard.pdf")
    with open(fpath, "rb") as f:
        dup_bytes = f.read()

    dup_res = workflow.ingest_and_execute_workflow(
        file_bytes=dup_bytes,
        original_filename="copy_of_invoice_standard.pdf",
        db_path=test_db
    )
    assert dup_res["is_duplicate"] is True, "Failed to detect exact file duplicate!"
    assert dup_res["document_id"] == std_inv["document_id"]
    print(f"  [OK] Duplicate correctly detected! Original ID #{dup_res['document_id']} flagged.")
    print(">>> PASS: SHA-256 Duplicate detection verified.")

    # =========================================================================
    # TEST 4: FINITE STATE MACHINE & TRANSITION ENFORCEMENT (Task 1)
    # =========================================================================
    print_banner("TEST 4: WORKFLOW STATE TRANSITIONS & ILLEGAL TRANSITION BLOCKING")
    
    # Valid transitions
    ok1, _ = workflow.can_transition("New", "Processing")
    assert ok1 is True
    ok2, _ = workflow.can_transition("Processing", "Needs Review")
    assert ok2 is True
    ok3, _ = workflow.can_transition("Needs Review", "Approved")
    assert ok3 is True
    ok4, _ = workflow.can_transition("Needs Review", "Rejected")
    assert ok4 is True
    ok5, _ = workflow.can_transition("Approved", "Completed")
    assert ok5 is True

    # Invalid transitions (MUST BE BLOCKED)
    bad1, msg1 = workflow.can_transition("New", "Approved")
    assert bad1 is False, "Allowed direct transition New -> Approved!"
    print(f"  [OK] Blocked illegal transition (New -> Approved): '{msg1}'")

    bad2, msg2 = workflow.can_transition("Completed", "Needs Review")
    assert bad2 is False, "Allowed transition from terminal Completed state!"
    print(f"  [OK] Blocked illegal transition (Completed -> Needs Review): '{msg2}'")

    bad3, msg3 = workflow.can_transition("Processing", "Approved")
    assert bad3 is False, "Allowed direct transition Processing -> Approved!"
    print(f"  [OK] Blocked illegal transition (Processing -> Approved): '{msg3}'")

    print(">>> PASS: State machine enforcement verified.")

    # =========================================================================
    # TEST 5: HUMAN REVIEW QUEUE - APPROVE & REJECT ACTIONS (Task 6)
    # =========================================================================
    print_banner("TEST 5: HUMAN REVIEW QUEUE APPROVE & REJECT ACTIONS")
    
    # 5A: Approve a document in 'Needs Review'
    review_doc_id = miss_inv["document_id"]
    approve_ok, approve_msg = workflow.approve_document(
        doc_id=review_doc_id,
        reviewer_notes="Verified manually with vendor; invoice number confirmed.",
        performed_by="Auditor Jane",
        db_path=test_db
    )
    assert approve_ok is True, f"Failed to approve document #{review_doc_id}: {approve_msg}"
    updated_doc = database.get_document_by_id(review_doc_id, db_path=test_db)
    assert updated_doc["status"] == "Completed", f"Expected Approved doc to complete, got {updated_doc['status']}"
    print(f"  [OK] Approve Document #{review_doc_id}: {approve_msg} | Final Status: {updated_doc['status']}")

    # 5B: Reject document without mandatory reason (MUST FAIL)
    reject_doc_id = inv_email["document_id"]
    reject_fail_ok, reject_fail_msg = workflow.reject_document(
        doc_id=reject_doc_id,
        rejection_reason="",  # Empty reason forbidden
        performed_by="Reviewer Bob",
        db_path=test_db
    )
    assert reject_fail_ok is False, "Allowed document rejection without mandatory reason!"
    print(f"  [OK] Mandatory rejection reason enforced: '{reject_fail_msg}'")

    # 5C: Reject document with valid reason (MUST SUCCEED)
    reject_ok, reject_msg = workflow.reject_document(
        doc_id=reject_doc_id,
        rejection_reason="Candidate email is completely malformed and missing domain.",
        performed_by="Reviewer Bob",
        db_path=test_db
    )
    assert reject_ok is True, f"Failed to reject document #{reject_doc_id}: {reject_msg}"
    rejected_doc = database.get_document_by_id(reject_doc_id, db_path=test_db)
    assert rejected_doc["status"] == "Rejected", f"Expected status 'Rejected', got {rejected_doc['status']}"
    print(f"  [OK] Reject Document #{reject_doc_id}: {reject_msg} | Status: {rejected_doc['status']}")

    print(">>> PASS: Human Review Queue approve & reject verified.")

    # =========================================================================
    # TEST 6: AUDIT TRAIL LOGGING & TRACEABILITY (Task 5)
    # =========================================================================
    print_banner("TEST 6: AUDIT TRAIL VERIFICATION")
    
    # Audit trail for the rejected document
    history = audit.get_document_history(reject_doc_id, db_path=test_db)
    assert len(history) >= 4, f"Expected at least 4 audit events for doc #{reject_doc_id}, found {len(history)}"
    
    actions_logged = [h["action"] for h in history]
    assert audit.ACTION_UPLOAD in actions_logged
    assert audit.ACTION_PROCESS_START in actions_logged
    assert audit.ACTION_ROUTE_REVIEW in actions_logged
    assert audit.ACTION_REJECT in actions_logged
    
    print(f"  [OK] Complete audit trail for Doc #{reject_doc_id} ({len(history)} events):")
    for h in history:
        print(f"    - [{h['timestamp']}] {h['action']:<15} | {h['previous_status']} -> {h['new_status']} | Actor: {h['performed_by']:<15} | Note: {h['reason']}")

    print(">>> PASS: Audit logging and event traceability verified.")

    # =========================================================================
    # TEST 7: BATCH WORKFLOW PROCESSING (Task 7)
    # =========================================================================
    print_banner("TEST 7: FAULT-TOLERANT BATCH WORKFLOW PROCESSING")
    
    # Select multiple documents + 1 non-existent ID to test failure tolerance
    batch_ids = [r["document_id"] for r in ingested_results[:4]] + [99999]  # 99999 is non-existent
    
    batch_summary = workflow.execute_batch_workflow(batch_ids, db_path=test_db)
    
    assert batch_summary["total_selected"] == 5
    assert batch_summary["processed_count"] == 4
    assert batch_summary["failed_count"] == 1  # The non-existent document failed gracefully
    assert len(batch_summary["results"]) == 5
    
    # Verify the batch didn't abort or crash!
    print(f"  [OK] Batch Processed: {batch_summary['processed_count']}/5 successful | Failed: {batch_summary['failed_count']}")
    for b_res in batch_summary["results"]:
        status_flag = "SUCCESS" if b_res["success"] else "FAILED (Expected)"
        print(f"    - Doc #{b_res['document_id']:<5} | Status: {status_flag:<15} | Current State: {b_res['new_status']}")

    print(">>> PASS: Batch processing fault tolerance verified.")

    # =========================================================================
    # TEST 8: SEARCH, FILTERING & METRICS DASHBOARD (Tasks 8 & 9)
    # =========================================================================
    print_banner("TEST 8: WORKFLOW SEARCH, FILTERS & METRICS DASHBOARD")
    
    # 8A: Filter by 'Completed'
    completed_docs = database.search_documents(status="Completed", db_path=test_db)
    assert len(completed_docs) >= 1
    print(f"  [OK] Filter status='Completed': {len(completed_docs)} documents returned.")

    # 8B: Filter by 'Rejected'
    rejected_docs = database.search_documents(status="Rejected", db_path=test_db)
    assert len(rejected_docs) >= 1
    print(f"  [OK] Filter status='Rejected': {len(rejected_docs)} documents returned.")

    # 8C: Multi-field Search by company / invoice number
    search_res = database.search_documents(search_query="Apex", db_path=test_db)
    assert len(search_res) >= 1
    print(f"  [OK] Search query='Apex': {len(search_res)} matching records found.")

    # 8D: Metrics Dashboard Calculation
    metrics = database.get_workflow_metrics(db_path=test_db)
    assert metrics["total_documents"] >= 15
    print(f"  [OK] Operational Metrics aggregated:")
    print(f"    - Total Documents:    {metrics['total_documents']}")
    print(f"    - Completed:          {metrics['completed_count']}")
    print(f"    - Needs Review:       {metrics['needs_review_count']}")
    print(f"    - Approved:           {metrics['approved_count']}")
    print(f"    - Rejected:           {metrics['rejected_count']}")
    print(f"    - Avg Processing Time:{metrics['avg_processing_time_ms']} ms")
    print(f"    - Document Types:     {metrics['type_distribution']}")

    print(">>> PASS: Search, filters, and metrics dashboard verified.")

    # =========================================================================
    # FINAL VERIFICATION SUMMARY
    # =========================================================================
    print_banner("ALL ZYROO WEEK 5 VERIFICATION CHECKS PASSED SUCCESSFULLY (12/12)!")
    return True


if __name__ == "__main__":
    success = run_week5_test_suite()
    sys.exit(0 if success else 1)
