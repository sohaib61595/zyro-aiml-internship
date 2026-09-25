"""
ZYROO INTERNSHIP PROGRAM - WEEK 4
Module: Unified Document Processing & Management Pipeline
Flow: Upload → Validate → Hash → Read/OCR → Clean → Classify → Extract → Store File → Store Metadata

Adheres strictly to Week 4 specifications:
- Validates file constraints (Task 8)
- Checks duplicate hash before writing (Task 3)
- OCR with preprocessing fallback (Week 3/4)
- Text cleaning and NFKC normalization
- Calibrated ML Classification (Invoice / Resume / Other)
- Information Extraction with resilience (Task 6)
- Structured storage categorization (Task 1)
- SQLite repository persistence (Task 2)
- Automated status evaluation (Processed / Needs Review / Failed) (Task 7)
"""

import os
import json
import logging
import mimetypes
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

import db_repository
import storage_manager
from text_cleaner import clean_extracted_text, validate_text_quality
from ocr_engine import extract_document_text
from model_trainer import classify_document
from extractor import extract_document_information, determine_processing_status

logger = logging.getLogger("document_pipeline")


def process_document_pipeline(
    file_bytes: bytes,
    original_filename: str,
    apply_ocr_preprocessing: bool = True,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the end-to-end ingestion and document intelligence pipeline.
    
    Returns:
        dict: {
            "success": bool,
            "is_duplicate": bool,
            "document_id": int or None,
            "document_record": dict,
            "message": str,
            "processing_steps": dict
        }
    """
    # ---------------------------------------------------------
    # STEP 1: VALIDATE UPLOAD (Task 8)
    # ---------------------------------------------------------
    is_valid, val_msg = storage_manager.validate_uploaded_file(original_filename, file_bytes)
    if not is_valid:
        return {
            "success": False,
            "is_duplicate": False,
            "document_id": None,
            "document_record": None,
            "message": f"Upload Validation Failed: {val_msg}",
            "error_type": "VALIDATION_ERROR"
        }

    # ---------------------------------------------------------
    # STEP 2: CALCULATE HASH & DUPLICATE DETECTION (Task 3)
    # ---------------------------------------------------------
    file_hash = storage_manager.compute_file_hash(file_bytes)
    is_dup, existing_doc = storage_manager.check_for_duplicate(file_hash, db_path=db_path)
    if is_dup and existing_doc:
        return {
            "success": True,
            "is_duplicate": True,
            "document_id": existing_doc.get("id"),
            "document_record": existing_doc,
            "message": f"Duplicate document detected! '{original_filename}' matches existing record #{existing_doc.get('id')} ({existing_doc.get('original_filename')}).",
            "file_hash": file_hash
        }

    # ---------------------------------------------------------
    # STEP 3: READ / OCR EXTRACTION (Task 8 Safe Handling)
    # ---------------------------------------------------------
    raw_text, ocr_meta = extract_document_text(
        file_bytes,
        original_filename,
        apply_ocr_preprocessing=apply_ocr_preprocessing
    )
    extraction_error = ocr_meta.get("error")

    # ---------------------------------------------------------
    # STEP 4: CLEAN & NORMALIZE TEXT
    # ---------------------------------------------------------
    cleaned_text = clean_extracted_text(raw_text)
    text_quality = validate_text_quality(cleaned_text, min_chars=20)
    text_len = len(cleaned_text.strip())

    # ---------------------------------------------------------
    # STEP 5: DOCUMENT CLASSIFICATION & CONFIDENCE SCORING
    # ---------------------------------------------------------
    cls_result = classify_document(cleaned_text)
    document_type = cls_result.get("document_type", "Other")
    confidence = cls_result.get("confidence", 0.0)

    # ---------------------------------------------------------
    # STEP 6: ENTITY EXTRACTION & AUDIT
    # ---------------------------------------------------------
    extraction_result = extract_document_information(cleaned_text, document_type)
    flat_values = extraction_result.get("flat_values", {})

    # Map extracted values to standard columns
    if document_type == "Invoice":
        company = flat_values.get("company", "Not Found")
        invoice_no = flat_values.get("invoice_number", "Not Found")
        total_amount = flat_values.get("total_amount", "Not Found")
    elif document_type == "Resume":
        company = flat_values.get("name", "Not Found")          # Candidate Name in company/name slot
        invoice_no = flat_values.get("email", "Not Found")       # Contact email in identifier slot
        total_amount = f"{flat_values.get('skills', 'Not Found')[:30]}..." if flat_values.get('skills') != "Not Found" else "Not Found"
    else:
        company = flat_values.get("document_title", "General Document")
        invoice_no = flat_values.get("subject", "N/A")
        total_amount = flat_values.get("date", {}).get("value", "N/A") if isinstance(flat_values.get("date"), dict) else "N/A"

    # ---------------------------------------------------------
    # STEP 7: EVALUATE PROCESSING STATUS (Task 7)
    # ---------------------------------------------------------
    status, status_reason = determine_processing_status(
        document_type=document_type,
        extraction_result=extraction_result,
        classification_confidence=confidence,
        text_length=text_len,
        extraction_error=extraction_error
    )

    # ---------------------------------------------------------
    # STEP 8: SAVE FILE TO ORGANIZED STORAGE (Task 1)
    # ---------------------------------------------------------
    stored_filename, stored_path = storage_manager.save_document_file(
        file_bytes=file_bytes,
        original_filename=original_filename,
        document_type=document_type,
        file_hash=file_hash
    )

    # ---------------------------------------------------------
    # STEP 9: PERSIST METADATA TO SQLITE (Task 2)
    # ---------------------------------------------------------
    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(original_filename)
    if not mime_type:
        mime_type = "application/pdf" if original_filename.lower().endswith(".pdf") else "application/octet-stream"

    # Create text preview (clean single-spaced excerpt up to 1000 chars)
    preview_snippet = " ".join(cleaned_text.split())[:1000] if cleaned_text else "[No preview available]"

    doc_record_payload = {
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "document_type": document_type,
        "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "company": company,
        "invoice_number": invoice_no,
        "total_amount": total_amount,
        "file_path": stored_path,
        "text_preview": preview_snippet,
        "file_hash": file_hash,
        "status": status,
        "file_size": len(file_bytes),
        "mime_type": mime_type,
        "confidence": confidence,
        "extracted_json": json.dumps(extraction_result),
        "notes": status_reason
    }

    try:
        doc_id = db_repository.insert_document(doc_record_payload, db_path=db_path)
        doc_record_payload["id"] = doc_id

        return {
            "success": True,
            "is_duplicate": False,
            "document_id": doc_id,
            "document_record": doc_record_payload,
            "message": f"Document #{doc_id} successfully stored in repository with status '{status}'.",
            "status": status,
            "status_reason": status_reason,
            "file_hash": file_hash,
            "processing_steps": {
                "ocr": ocr_meta,
                "text_quality": text_quality,
                "classification": cls_result,
                "extraction": extraction_result
            }
        }
    except Exception as e:
        logger.error(f"Failed to record document metadata into database: {e}")
        return {
            "success": False,
            "is_duplicate": False,
            "document_id": None,
            "document_record": None,
            "message": f"Storage completed, but database registration failed: {str(e)}",
            "error_type": "DATABASE_ERROR"
        }
