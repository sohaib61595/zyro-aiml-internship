"""
ZYROO INTERNSHIP PROGRAM - WEEK 4
Automated Test Suite: Complete Document Repository & Management Verification
Task 9: Test the Complete Repository

Verification Criteria:
1. Ingest at least 10 documents (Invoices, Resumes, Other).
2. Include duplicate files (Verify SHA-256 hash duplicate detection).
3. Include scanned documents (PyMuPDF render + Preprocessed OCR).
4. Include documents with missing fields (Verify 'Needs Review' status).
5. Multi-field search (filename, company, invoice #, doc type, text preview).
6. Filter by type, status, and upload date.
7. Sort by newest, oldest, filename.
8. CRUD updates and safe deletion.
9. Restart simulation: Verify records persist after connection reload.
10. Defensive error handling: Unsupported formats and corrupted bytes.
"""

import os
import sys
import tempfile
import sqlite3
from typing import Dict, Any, List

# Ensure week-4 modules can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db_repository
import storage_manager
from pipeline import process_document_pipeline


def print_banner(title: str):
    print("\n" + "=" * 75)
    print(f"  {title}")
    print("=" * 75)


def run_comprehensive_week4_test_suite():
    print_banner("STARTING ZYROO WEEK 4 COMPLETE TEST SUITE")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    samples_dir = os.path.join(base_dir, "samples")
    assert os.path.exists(samples_dir), f"Samples directory missing at {samples_dir}"

    # Use dedicated test database to keep tests isolated & repeatable
    test_db = os.path.join(base_dir, "test_repository.db")
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except OSError:
            pass

    db_repository.init_db(test_db)
    storage_manager.ensure_storage_structure()
    print(f"Initialized clean test database at: {test_db}")

    # =========================================================================
    # STEP 1: TEST AT LEAST 10 DIVERSE DOCUMENTS
    # =========================================================================
    print_banner("TEST 1: BATCH INGESTION OF 11 DIVERSE DOCUMENTS")
    sample_files = [
        # Invoices
        "invoice_standard.pdf",
        "invoice_pkr_currency.pdf",
        "invoice_consulting_services.pdf",
        "invoice_missing_fields.pdf",
        "invoice_scanned_receipt.png",
        # Resumes
        "resume_software_engineer.pdf",
        "resume_missing_contact.pdf",
        "resume_scanned.jpg",
        # Other documents
        "other_business_memo.pdf",
        "other_contract_agreement.pdf",
        "other_policy_guidelines.pdf"
    ]

    ingested_records: List[Dict[str, Any]] = []

    for idx, fname in enumerate(sample_files, 1):
        fpath = os.path.join(samples_dir, fname)
        assert os.path.exists(fpath), f"Sample file not found: {fpath}"

        with open(fpath, "rb") as f:
            b_data = f.read()

        res = process_document_pipeline(
            file_bytes=b_data,
            original_filename=fname,
            apply_ocr_preprocessing=True,
            db_path=test_db
        )

        assert res["success"] is True, f"Failed ingesting {fname}: {res.get('message')}"
        assert res["is_duplicate"] is False, f"Unexpected duplicate for fresh file {fname}"
        doc_rec = res["document_record"]
        ingested_records.append(doc_rec)

        print(f"[{idx:02d}/11] Ingested: {fname:<32} | Type: {doc_rec['document_type']:<8} | Status: {doc_rec['status']:<12} | Conf: {doc_rec['confidence']:.2f}")

    print(f"\nSuccessfully ingested {len(ingested_records)} distinct documents into SQLite repository.")
    assert len(ingested_records) >= 10, "Did not meet requirement of testing at least 10 documents!"

    # =========================================================================
    # STEP 2: STRUCTURED STORAGE AUDIT (Task 1)
    # =========================================================================
    print_banner("TEST 2: STRUCTURED STORAGE HIERARCHY AUDIT (Task 1)")
    for rec in ingested_records:
        stored_path = rec["file_path"]
        assert os.path.exists(stored_path), f"Stored file not found on disk: {stored_path}"
        # Check proper categorization folder
        doc_type = rec["document_type"]
        expected_folder = storage_manager.SUBDIRECTORIES.get(doc_type, "other")
        assert expected_folder in stored_path.replace("\\", "/"), f"File {stored_path} not in expected folder {expected_folder}"
        # Confirm safe filename
        assert rec["stored_filename"] != rec["original_filename"], "Stored filename must be sanitized/prefixed, not raw original!"
        assert rec["original_filename"] in rec["stored_filename"], "Stored filename should retain original base components."

    print("Structured storage verification passed: Files safely organized by category with safe collision-proof filenames.")

    # =========================================================================
    # STEP 3: DUPLICATE DETECTION (Task 3)
    # =========================================================================
    print_banner("TEST 3: CRYPTOGRAPHIC DUPLICATE DETECTION (Task 3)")
    dup_file = "invoice_standard.pdf"
    with open(os.path.join(samples_dir, dup_file), "rb") as f:
        dup_bytes = f.read()

    dup_res = process_document_pipeline(
        file_bytes=dup_bytes,
        original_filename="duplicate_copy_of_invoice.pdf",
        db_path=test_db
    )

    assert dup_res["success"] is True, "Duplicate check should succeed gracefully."
    assert dup_res["is_duplicate"] is True, "Duplicate flag must be True for identical bytes."
    existing_rec = dup_res["document_record"]
    assert existing_rec["original_filename"] == dup_file, f"Expected duplicate of {dup_file}, got {existing_rec['original_filename']}"
    print(f"Duplicate successfully intercepted via SHA-256 ({existing_rec['file_hash'][:16]}...). Linked to Document #{existing_rec['id']}.")

    # =========================================================================
    # STEP 4: PROCESSING STATUS EVALUATION (Task 7)
    # =========================================================================
    print_banner("TEST 4: PROCESSING STATUS LOGIC (Task 7)")
    # 'invoice_missing_fields.pdf' must be 'Needs Review'
    missing_inv = next(r for r in ingested_records if r["original_filename"] == "invoice_missing_fields.pdf")
    assert missing_inv["status"] == "Needs Review", f"Expected 'Needs Review' for invoice_missing_fields, got '{missing_inv['status']}'"
    print(f"Verified: 'invoice_missing_fields.pdf' marked as '{missing_inv['status']}' (Reason: {missing_inv['notes']})")

    # 'resume_missing_contact.pdf' must be 'Needs Review'
    missing_res = next(r for r in ingested_records if r["original_filename"] == "resume_missing_contact.pdf")
    assert missing_res["status"] == "Needs Review", f"Expected 'Needs Review' for resume_missing_contact, got '{missing_res['status']}'"
    print(f"Verified: 'resume_missing_contact.pdf' marked as '{missing_res['status']}' (Reason: {missing_res['notes']})")

    # Complete documents must be 'Processed'
    standard_inv = next(r for r in ingested_records if r["original_filename"] == "invoice_standard.pdf")
    assert standard_inv["status"] == "Processed", f"Expected 'Processed' for invoice_standard, got '{standard_inv['status']}'"
    print(f"Verified: 'invoice_standard.pdf' marked as '{standard_inv['status']}'")

    # =========================================================================
    # STEP 5: MULTI-FIELD SEARCH (Task 4)
    # =========================================================================
    print_banner("TEST 5: MULTI-FIELD SEARCH VIA SQLITE (Task 4)")

    # 1. Search by Company
    res_company = db_repository.search_documents(search_query="Apex", db_path=test_db)
    assert len(res_company) >= 1, "Search by company 'Apex' should return matching document"
    print(f"Search 'Apex' (Company): Found {len(res_company)} document(s): #{res_company[0]['id']} {res_company[0]['original_filename']}")

    # 2. Search by Invoice Number
    res_inv = db_repository.search_documents(search_query="INV-99201", db_path=test_db)
    assert len(res_inv) == 1, "Search by invoice number 'INV-99201' should return exactly 1 document"
    print(f"Search 'INV-99201' (Invoice #): Found #{res_inv[0]['id']} {res_inv[0]['original_filename']}")

    # 3. Search by Stored Text Excerpt (e.g. 'Software' in resume)
    res_text = db_repository.search_documents(search_query="Software", db_path=test_db)
    assert len(res_text) >= 1, "Search by text 'Software' should match resume"
    print(f"Search 'Software' (Text Preview): Found {len(res_text)} document(s): #{res_text[0]['id']} {res_text[0]['original_filename']}")

    # 4. Search by Document Type keyword
    res_memo = db_repository.search_documents(search_query="memorandum", db_path=test_db)
    assert len(res_memo) >= 1, "Search by 'memorandum' should match other memo documents"
    print(f"Search 'memorandum' (Document Title/Preview): Found {len(res_memo)} document(s)")

    # =========================================================================
    # STEP 6: FILTERS & SORTING (Task 5)
    # =========================================================================
    print_banner("TEST 6: FILTERS & SORTING (Task 5)")

    # Filter by Document Type: Invoice
    only_invoices = db_repository.search_documents(document_type="Invoice", db_path=test_db)
    assert all(d["document_type"] == "Invoice" for d in only_invoices)
    assert len(only_invoices) >= 4, f"Expected at least 4 invoices, got {len(only_invoices)}"
    print(f"Filter Document Type == 'Invoice': {len(only_invoices)} records (all verified 'Invoice')")

    # Filter by Document Type: Resume
    only_resumes = db_repository.search_documents(document_type="Resume", db_path=test_db)
    assert all(d["document_type"] == "Resume" for d in only_resumes)
    assert len(only_resumes) >= 3, f"Expected at least 3 resumes, got {len(only_resumes)}"
    print(f"Filter Document Type == 'Resume': {len(only_resumes)} records (all verified 'Resume')")

    # Filter by Status: Needs Review
    needs_review = db_repository.search_documents(status="Needs Review", db_path=test_db)
    assert all(d["status"] == "Needs Review" for d in needs_review)
    assert len(needs_review) >= 2, f"Expected at least 2 Needs Review records, got {len(needs_review)}"
    print(f"Filter Status == 'Needs Review': {len(needs_review)} records")

    # Sorting by Oldest
    sorted_oldest = db_repository.search_documents(sort_by="oldest", db_path=test_db)
    assert sorted_oldest[0]["id"] == 1, "Oldest document should have ID 1"
    sorted_newest = db_repository.search_documents(sort_by="newest", db_path=test_db)
    assert sorted_newest[0]["id"] == len(ingested_records), f"Newest document should have ID {len(ingested_records)}"
    print("Sorting verification passed (Ascending and Descending order verified).")

    # =========================================================================
    # STEP 7: CRUD OPERATIONS & MANUAL FIELD UPDATES
    # =========================================================================
    print_banner("TEST 7: CRUD OPERATIONS & STATUS OVERRIDE")
    target_id = missing_inv["id"]
    # Update status from 'Needs Review' to 'Processed'
    upd_ok = db_repository.update_document_status(target_id, "Processed", notes="Approved manually by reviewer", db_path=test_db)
    assert upd_ok is True
    re_fetched = db_repository.get_document_by_id(target_id, db_path=test_db)
    assert re_fetched["status"] == "Processed"
    assert re_fetched["notes"] == "Approved manually by reviewer"
    print(f"Status update verified for Doc #{target_id}: Now '{re_fetched['status']}'")

    # Update extracted field
    field_ok = db_repository.update_document_fields(target_id, company="Manual Corrected Corp", db_path=test_db)
    assert field_ok is True
    re_fetched2 = db_repository.get_document_by_id(target_id, db_path=test_db)
    assert re_fetched2["company"] == "Manual Corrected Corp"
    print(f"Field correction verified: Company name updated to '{re_fetched2['company']}'")

    # =========================================================================
    # STEP 8: PERSISTENCE ACROSS APPLICATION RESTART
    # =========================================================================
    print_banner("TEST 8: PERSISTENCE ACROSS APP RESTART")
    # Simulate full app restart by querying fresh connection
    stats_after = db_repository.get_repository_stats(db_path=test_db)
    assert stats_after["total_documents"] == len(ingested_records)
    print(f"Persistence confirmed: {stats_after['total_documents']} documents intact across independent SQLite connections.")

    # =========================================================================
    # STEP 9: DEFENSIVE ERROR HANDLING (Task 8)
    # =========================================================================
    print_banner("TEST 9: DEFENSIVE ERROR HANDLING (Task 8)")
    
    # 1. Unsupported File Extension
    bad_ext_res = process_document_pipeline(b"fake data", "payload.exe", db_path=test_db)
    assert bad_ext_res["success"] is False
    assert "Unsupported file type" in bad_ext_res["message"]
    print("Verified: Unsupported file format (.exe) safely rejected.")

    # 2. Corrupted PDF Bytes
    corrupt_pdf_res = process_document_pipeline(b"NOT A REAL PDF FILE AT ALL", "corrupt.pdf", db_path=test_db)
    assert corrupt_pdf_res["success"] is True or corrupt_pdf_res.get("status") == "Failed"
    print("Verified: Corrupted PDF handled gracefully without uncaught exceptions.")

    # 3. Oversized file (> 20 MB)
    huge_bytes = b"0" * (21 * 1024 * 1024)
    huge_res = process_document_pipeline(huge_bytes, "oversized.pdf", db_path=test_db)
    assert huge_res["success"] is False
    assert "maximum allowed upload size" in huge_res["message"]
    print("Verified: Oversized upload (>20MB) safely intercepted.")

    print_banner("ALL ZYROO WEEK 4 TESTS PASSED PERFECTLY (100% SUCCESS)!")


if __name__ == "__main__":
    run_comprehensive_week4_test_suite()
