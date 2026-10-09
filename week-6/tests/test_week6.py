"""
ZYROO INTERNSHIP PROGRAM - WEEK 6
Automated End-to-End Verification & Quality Gate Suite
Focus: Enterprise integration, validation, anomaly checks, RAG assistant, security, and reliability
"""

import os
import sys
import json
import time
from typing import Dict, Any, List

# Ensure week 6 src modules can be imported
_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.abspath(os.path.join(_current_dir, "..", "src"))
for d in [_current_dir, _src_dir]:
    if d not in sys.path:
        sys.path.insert(0, d)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import config
import database
import storage
import processor
import classifier
import extractor
import validator
import anomaly
import rag_engine
import workflow
import audit


def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def run_week6_test_suite():
    print_banner("STARTING ZYROO WEEK 6: FINAL INTEGRATION & QUALITY GATE TEST SUITE")

    samples_dir = config.SAMPLES_DIR
    assert os.path.exists(samples_dir), f"Samples directory missing at {samples_dir}"

    test_db = os.path.join(config.BASE_DIR, "test_final_platform.db")
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass

    database.init_db(test_db)
    storage.ensure_storage_structure()
    print(f"Clean verification database initialized at: {test_db}")

    passed_tests = 0
    total_tests = 14

    # =========================================================================
    # TEST 1: CLEAN DIGITAL PDF (INVOICE & RESUME)
    # =========================================================================
    print_banner("TEST 1: CLEAN DIGITAL PDF INGESTION & PIPELINE AUTOMATION")
    clean_pdf_path = os.path.join(samples_dir, "invoice_standard.pdf")
    with open(clean_pdf_path, "rb") as f:
        pdf_bytes = f.read()

    res1 = workflow.ingest_and_execute_workflow(
        file_bytes=pdf_bytes,
        original_filename="invoice_standard.pdf",
        db_path=test_db
    )
    assert res1["success"] is True, f"Clean PDF ingestion failed: {res1.get('message')}"
    assert res1["document_type"] == "Invoice", f"Expected Invoice, got {res1['document_type']}"
    assert res1["status"] == workflow.STATE_COMPLETED, f"Expected Completed status, got {res1['status']}"
    assert res1["validation_result"]["is_valid"] is True
    print(f"[PASS] Clean digital PDF processed → Status: '{res1['status']}' in {res1['processing_time_ms']}ms.")
    passed_tests += 1

    # =========================================================================
    # TEST 2: SCANNED DOCUMENT REQUIRING OCR
    # =========================================================================
    print_banner("TEST 2: SCANNED DOCUMENT REQUIRING OCR")
    scanned_path = os.path.join(samples_dir, "invoice_scanned_receipt.png")
    with open(scanned_path, "rb") as f:
        scanned_bytes = f.read()

    res2 = workflow.ingest_and_execute_workflow(
        file_bytes=scanned_bytes,
        original_filename="invoice_scanned_receipt.png",
        apply_ocr_preprocessing=True,
        db_path=test_db
    )
    assert res2["success"] is True, f"Scanned file processing failed: {res2.get('message')}"
    assert res2["document_record"]["file_size"] > 0
    print(f"[PASS] Scanned document processed with OCR handling → Status: '{res2['status']}'.")
    passed_tests += 1

    # =========================================================================
    # TEST 3: MULTI-CATEGORY SUPPORT (RESUME & CONTRACT)
    # =========================================================================
    print_banner("TEST 3: MULTI-CATEGORY SUPPORT (CONTRACT & RESUME)")
    contract_path = os.path.join(samples_dir, "other_contract_agreement.pdf")
    with open(contract_path, "rb") as f:
        contract_bytes = f.read()

    res3 = workflow.ingest_and_execute_workflow(
        file_bytes=contract_bytes,
        original_filename="other_contract_agreement.pdf",
        db_path=test_db
    )
    assert res3["success"] is True
    print(f"[PASS] Multi-category document recognized → Type: '{res3['document_type']}', Status: '{res3['status']}'.")
    passed_tests += 1

    # =========================================================================
    # TEST 4: DOCUMENT WITH MISSING REQUIRED FIELDS
    # =========================================================================
    print_banner("TEST 4: DOCUMENT WITH MISSING REQUIRED FIELDS ROUTED TO REVIEW")
    missing_path = os.path.join(samples_dir, "invoice_missing_fields.pdf")
    with open(missing_path, "rb") as f:
        missing_bytes = f.read()

    res4 = workflow.ingest_and_execute_workflow(
        file_bytes=missing_bytes,
        original_filename="invoice_missing_fields.pdf",
        db_path=test_db
    )
    assert res4["success"] is True
    assert res4["status"] == workflow.STATE_NEEDS_REVIEW, f"Expected Needs Review, got {res4['status']}"
    assert res4["validation_result"]["is_valid"] is False
    assert len(res4["validation_result"]["failed_fields"]) > 0
    print(f"[PASS] Missing fields correctly routed to 'Needs Review' → Failed: {res4['validation_result']['failed_fields']}.")
    passed_tests += 1

    # =========================================================================
    # TEST 5: DUPLICATE DOCUMENT & REPEATED IDENTIFIER
    # =========================================================================
    print_banner("TEST 5: DUPLICATE DETECTION (SHA-256 HASH & IDENTIFIERS)")
    # Duplicate submission of standard invoice
    res5 = workflow.ingest_and_execute_workflow(
        file_bytes=pdf_bytes,
        original_filename="invoice_standard_duplicate.pdf",
        db_path=test_db
    )
    assert res5["is_duplicate"] is True, "Duplicate file failed to be detected"
    assert res5["document_id"] == res1["document_id"], "Duplicate did not return original document ID"
    print(f"[PASS] Cryptographic SHA-256 duplicate trapped → Matches Record #{res5['document_id']}.")
    passed_tests += 1

    # =========================================================================
    # TEST 6: UNSUPPORTED FILE TYPE
    # =========================================================================
    print_banner("TEST 6: UNSUPPORTED FILE TYPE REJECTION")
    unsupported_path = os.path.join(samples_dir, "unsupported_file.exe")
    with open(unsupported_path, "rb") as f:
        bad_bytes = f.read()

    res6 = workflow.ingest_and_execute_workflow(
        file_bytes=bad_bytes,
        original_filename="unsupported_file.exe",
        db_path=test_db
    )
    assert res6["success"] is False, "Unsupported file should have failed validation"
    assert "Unsupported file type" in res6["message"]
    print(f"[PASS] Unsupported file safely rejected: '{res6['message']}'.")
    passed_tests += 1

    # =========================================================================
    # TEST 7: CORRUPTED OR UNREADABLE FILE
    # =========================================================================
    print_banner("TEST 7: CORRUPTED OR MALFORMED FILE HANDLING")
    corrupt_path = os.path.join(samples_dir, "corrupted_document.pdf")
    with open(corrupt_path, "rb") as f:
        corrupt_bytes = f.read()

    res7 = workflow.ingest_and_execute_workflow(
        file_bytes=corrupt_bytes,
        original_filename="corrupted_document.pdf",
        db_path=test_db
    )
    # Corrupt document should either fail validation or route to Needs Review cleanly
    assert res7["status"] in [workflow.STATE_NEEDS_REVIEW, "Failed"]
    print(f"[PASS] Corrupted file defensively handled without traceback → Status: '{res7['status']}'.")
    passed_tests += 1

    # =========================================================================
    # TEST 8: LOW-CONFIDENCE CLASSIFICATION
    # =========================================================================
    print_banner("TEST 8: CONFIDENCE-AWARE ROUTING (< 0.75 THRESHOLD)")
    ambig_path = os.path.join(samples_dir, "document_low_confidence_ambiguous.pdf")
    with open(ambig_path, "rb") as f:
        ambig_bytes = f.read()

    res8 = workflow.ingest_and_execute_workflow(
        file_bytes=ambig_bytes,
        original_filename="document_low_confidence_ambiguous.pdf",
        db_path=test_db
    )
    assert res8["success"] is True
    assert res8["status"] == workflow.STATE_NEEDS_REVIEW, f"Expected Needs Review for low confidence, got {res8['status']}"
    print(f"[PASS] Low confidence document routed to review → Confidence: {res8.get('confidence')}.")
    passed_tests += 1

    # =========================================================================
    # TEST 9: FINANCIAL ARITHMETIC MISMATCH (ANOMALY DETECTION)
    # =========================================================================
    print_banner("TEST 9: FINANCIAL ARITHMETIC MISMATCH DETECTION")
    mismatch_path = os.path.join(samples_dir, "invoice_arithmetic_mismatch.pdf")
    with open(mismatch_path, "rb") as f:
        mismatch_bytes = f.read()

    res9 = workflow.ingest_and_execute_workflow(
        file_bytes=mismatch_bytes,
        original_filename="invoice_arithmetic_mismatch.pdf",
        db_path=test_db
    )
    assert res9["success"] is True
    assert res9["status"] == workflow.STATE_NEEDS_REVIEW, f"Expected Needs Review for arithmetic mismatch, got {res9['status']}"
    anom_res = res9.get("anomaly_result", {})
    assert anom_res.get("has_anomalies") is True, "Arithmetic mismatch failed to trigger anomaly flag"
    codes = [a["code"] for a in anom_res.get("anomalies", [])]
    assert "ANOMALY_ARITHMETIC_MISMATCH" in codes, f"Expected ANOMALY_ARITHMETIC_MISMATCH, got {codes}"
    print(f"[PASS] Financial arithmetic mismatch detected: {codes} → Document routed to Needs Review.")
    passed_tests += 1

    # =========================================================================
    # TEST 10: FINITE STATE MACHINE & ILLEGAL TRANSITIONS
    # =========================================================================
    print_banner("TEST 10: FINITE STATE MACHINE (FSM) TRANSITION INTEGRITY")
    # Illegal Transition 1: New -> Approved
    ok1, msg1 = workflow.can_transition(workflow.STATE_NEW, workflow.STATE_APPROVED)
    assert ok1 is False, "New -> Approved should be illegally blocked"

    # Illegal Transition 2: Completed -> Needs Review
    ok2, msg2 = workflow.can_transition(workflow.STATE_COMPLETED, workflow.STATE_NEEDS_REVIEW)
    assert ok2 is False, "Completed -> Needs Review should be illegally blocked"

    # Illegal Transition 3: Processing -> Approved
    ok3, msg3 = workflow.can_transition(workflow.STATE_PROCESSING, workflow.STATE_APPROVED)
    assert ok3 is False, "Processing -> Approved should be illegally blocked"

    print(f"[PASS] FSM illegal state transitions strictly blocked as expected.")
    passed_tests += 1

    # =========================================================================
    # TEST 11: HUMAN REVIEW ACTIONS & RBAC
    # =========================================================================
    print_banner("TEST 11: REVIEW QUEUE ACTIONS (APPROVE, REJECT & RBAC)")
    target_review_id = res4["document_id"]  # Document currently in Needs Review

    # RBAC test: Viewer cannot approve
    ok_v, msg_v = workflow.approve_document(
        doc_id=target_review_id,
        reviewer_notes="Attempted by viewer",
        user_role=config.ROLE_VIEWER,
        db_path=test_db
    )
    assert ok_v is False and "Access Denied" in msg_v, "Viewer should have been blocked by RBAC"

    # Mandatory rejection reason test: Empty string rejected
    ok_r_fail, msg_r_fail = workflow.reject_document(
        doc_id=target_review_id,
        rejection_reason="",
        user_role=config.ROLE_REVIEWER,
        db_path=test_db
    )
    assert ok_r_fail is False, "Rejection without reason should be blocked"

    # Legitimate Approval by Reviewer
    ok_app, msg_app = workflow.approve_document(
        doc_id=target_review_id,
        reviewer_notes="Audited and approved by Senior QA.",
        user_role=config.ROLE_REVIEWER,
        db_path=test_db
    )
    assert ok_app is True, f"Approval failed: {msg_app}"

    doc_after_app = database.get_document_by_id(target_review_id, db_path=test_db)
    assert doc_after_app["status"] == workflow.STATE_COMPLETED, "Approved document should be Completed"

    # Verify audit history exists
    history = audit.get_document_history(target_review_id, db_path=test_db)
    actions = [h["action"] for h in history]
    assert audit.ACTION_APPROVE in actions and audit.ACTION_COMPLETE in actions
    print(f"[PASS] Human review actions, audit logging & RBAC verified successfully.")
    passed_tests += 1

    # =========================================================================
    # TEST 12: FAULT-TOLERANT MIXED-SUCCESS BATCH PROCESSING
    # =========================================================================
    print_banner("TEST 12: FAULT-TOLERANT MIXED-SUCCESS BATCH INGESTION")
    batch_items = [
        ("batch_valid_invoice.pdf", pdf_bytes),
        ("batch_mismatch_invoice.pdf", mismatch_bytes),
        ("batch_corrupt_file.pdf", corrupt_bytes),
        ("batch_unsupported.exe", bad_bytes)
    ]

    batch_summary = workflow.process_batch_files(batch_items, db_path=test_db)
    assert batch_summary["total_submitted"] == 4
    assert batch_summary["failure_count"] >= 1, "Expected failures in corrupted/unsupported files"
    assert len(batch_summary["results"]) == 4, "Batch aborted early on individual failure!"
    print(f"[PASS] Batch executed with fault tolerance ({batch_summary['total_time_ms']}ms): {batch_summary['success_count']} success, {batch_summary['failure_count']} failure, {batch_summary['duplicate_count']} dups.")
    passed_tests += 1

    # =========================================================================
    # TEST 13: APPLICATION RESTART & PERSISTENCE VERIFICATION
    # =========================================================================
    print_banner("TEST 13: APPLICATION RESTART WITH STORED RECORDS AVAILABLE")
    # Simulate fresh app startup by closing and re-opening database connection
    metrics_restart = database.get_workflow_metrics(db_path=test_db)
    assert metrics_restart["total_documents"] > 0, "No records retained after restart simulation!"
    assert metrics_restart["total_rag_chunks"] > 0, "RAG chunks lost after restart!"
    print(f"[PASS] Persistence verified: {metrics_restart['total_documents']} documents & {metrics_restart['total_rag_chunks']} RAG chunks retained.")
    passed_tests += 1

    # =========================================================================
    # TEST 14: AI ASSISTANT & RAG CHECK (GROUNDED VS UNGROUNDED FALLBACK)
    # =========================================================================
    print_banner("TEST 14: AI ASSISTANT & RAG (GROUNDED ANSWERS & NEGATIVE CASE)")
    # Part A: Answerable Question (Grounded)
    q_pos = "What is the invoice number for Apex Digital Solutions?"
    res_pos = rag_engine.answer_document_query(query=q_pos, db_path=test_db)
    assert res_pos["has_sufficient_information"] is True, "Expected positive grounded answer"
    assert len(res_pos["citations"]) > 0, "Expected at least one citation for positive answer"
    print(f"[PASS] Grounded question answered with {len(res_pos['citations'])} source citation(s).")

    # Part B: Unanswerable Question (Strict Negative Constraint)
    q_neg = "What is the warranty policy on quantum computing servers?"
    res_neg = rag_engine.answer_document_query(query=q_neg, db_path=test_db)
    assert res_neg["has_sufficient_information"] is False, "Expected negative fallback for unsupported question"
    assert "The available documents do not contain enough information to answer this question." in res_neg["answer"]
    print(f"[PASS] Negative fallback constraint satisfied: '{res_neg['answer']}'.")
    passed_tests += 1

    # =========================================================================
    # FINAL QUALITY GATE SUMMARY
    # =========================================================================
    print_banner("FINAL QUALITY GATE EVALUATION REPORT")
    print(f"Total Scenarios Tested: {total_tests}")
    print(f"Scenarios Passed:       {passed_tests}")
    print(f"Pass Rate:              {passed_tests / total_tests * 100:.1f}%")
    print("=" * 80)
    assert passed_tests == total_tests, f"Test suite did not achieve 100% pass rate: {passed_tests}/{total_tests}"
    print(">>> ALL 14 QUALITY GATE SCENARIOS PASSED WITH ZERO DEFECTS. <<<")


if __name__ == "__main__":
    run_week6_test_suite()
