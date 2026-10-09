"""
ZYROO INTERNSHIP PROGRAM - WEEK 6
Module: Intelligent Anomaly & Inconsistency Detection Engine
Focus: Financial arithmetic verification, duplicate identification, and security risk flags
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

import config
import database
import validator

logger = logging.getLogger("anomaly_engine")


def parse_numeric(val: Any) -> Optional[float]:
    """Helper to extract float value from raw currency strings."""
    if not val:
        return None
    s = str(val).strip()
    clean = re.sub(r"(?i)\b(USD|PKR|EUR|GBP|Rs\.?|\$|€|£|AUD|CAD)\b", "", s)
    clean = clean.replace(",", "").strip()
    m = re.search(r"[-+]?\d*\.?\d+", clean)
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            return None
    return None


def detect_anomalies(
    document_type: str,
    extracted_flat_values: Dict[str, Any],
    validation_result: Dict[str, Any],
    confidence: Optional[float],
    text: str,
    current_doc_id: Optional[int] = None,
    current_file_hash: Optional[str] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates multi-point anomaly criteria:
    1. Financial arithmetic consistency: Subtotal + Tax == Total Amount.
    2. Repeated identifier check: Duplicate invoice numbers across distinct files.
    3. High-value policy audit: Amounts exceeding defined risk limits ($10,000).
    4. Model uncertainty: Confidence below documented threshold (0.75).
    5. Sparse text or corrupted document anomalies.
    """
    anomalies: List[Dict[str, Any]] = []
    requires_human_review = False

    # 1. Financial Arithmetic Consistency Check (Invoices)
    if document_type == "Invoice":
        subtotal_raw = extracted_flat_values.get("subtotal")
        tax_raw = extracted_flat_values.get("tax")
        total_raw = extracted_flat_values.get("total_amount")

        subtotal_num = parse_numeric(subtotal_raw)
        tax_num = parse_numeric(tax_raw)
        total_num = parse_numeric(total_raw)

        if subtotal_num is not None and tax_num is not None and total_num is not None:
            expected_total = subtotal_num + tax_num
            discrepancy = abs(expected_total - total_num)
            if discrepancy > config.ARITHMETIC_TOLERANCE:
                anomalies.append({
                    "code": "ANOMALY_ARITHMETIC_MISMATCH",
                    "severity": "HIGH",
                    "message": (
                        f"Financial arithmetic calculation mismatch: "
                        f"Subtotal ({subtotal_num:,.2f}) + Tax ({tax_num:,.2f}) = {expected_total:,.2f}, "
                        f"but parsed Total is {total_num:,.2f} (Discrepancy: {discrepancy:,.2f})."
                    ),
                    "subtotal": subtotal_num,
                    "tax": tax_num,
                    "expected_total": expected_total,
                    "actual_total": total_num,
                    "discrepancy": round(discrepancy, 2)
                })
                requires_human_review = True

        # 2. Repeated Invoice Identifier Check in DB
        inv_no = extracted_flat_values.get("invoice_number", "").strip()
        if inv_no and inv_no.lower() not in ["not found", "n/a", "none"]:
            try:
                conn = database.get_db_connection(db_path)
                query = "SELECT id, original_filename, file_hash FROM documents WHERE invoice_number = ?"
                params = [inv_no]
                if current_doc_id:
                    query += " AND id != ?"
                    params.append(current_doc_id)
                if current_file_hash:
                    query += " AND file_hash != ?"
                    params.append(current_file_hash)
                    
                rows = conn.execute(query, params).fetchall()
                conn.close()

                if rows:
                    dup_ids = [str(r["id"]) for r in rows]
                    anomalies.append({
                        "code": "ANOMALY_REPEATED_IDENTIFIER",
                        "severity": "HIGH",
                        "message": f"Duplicate invoice identifier '{inv_no}' already exists in database record(s): #{', #'.join(dup_ids)}.",
                        "matched_ids": dup_ids
                    })
                    requires_human_review = True
            except Exception as e:
                logger.warning(f"Repeated identifier database check failed: {e}")

        # 3. High-Value Financial Transaction Check
        parsed_amount = validation_result.get("parsed_amount")
        if parsed_amount is not None and parsed_amount >= config.HIGH_VALUE_INVOICE_THRESHOLD:
            anomalies.append({
                "code": "ANOMALY_HIGH_VALUE_THRESHOLD",
                "severity": "MEDIUM",
                "message": (
                    f"High-value financial transaction: Invoice amount (${parsed_amount:,.2f}) "
                    f"exceeds operational audit threshold (${config.HIGH_VALUE_INVOICE_THRESHOLD:,.2f})."
                ),
                "amount": parsed_amount,
                "threshold": config.HIGH_VALUE_INVOICE_THRESHOLD
            })
            requires_human_review = True

    # 4. Model Confidence Anomaly
    if confidence is not None:
        if confidence < config.CLASSIFIER_CONFIDENCE_THRESHOLD:
            conf_pct = round(confidence * 100, 1)
            thresh_pct = int(config.CLASSIFIER_CONFIDENCE_THRESHOLD * 100)
            anomalies.append({
                "code": "ANOMALY_LOW_CONFIDENCE",
                "severity": "MEDIUM",
                "message": f"Low model classification confidence ({conf_pct}% < {thresh_pct}%). Ambiguous document category.",
                "confidence": confidence
            })
            requires_human_review = True

    # 5. Text Sparsity / Truncation Anomaly
    text_len = len(text.strip()) if text else 0
    if text_len < config.MIN_TEXT_LENGTH_FOR_EXTRACTION:
        anomalies.append({
            "code": "ANOMALY_SPARSE_TEXT",
            "severity": "HIGH",
            "message": f"Extracted text is critically sparse ({text_len} chars). Possible scan without OCR or damaged document.",
            "text_length": text_len
        })
        requires_human_review = True

    # Compute highest severity
    severities = [a["severity"] for a in anomalies]
    highest_severity = "NONE"
    if "HIGH" in severities:
        highest_severity = "HIGH"
    elif "MEDIUM" in severities:
        highest_severity = "MEDIUM"
    elif "LOW" in severities:
        highest_severity = "LOW"

    return {
        "has_anomalies": len(anomalies) > 0,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "requires_human_review": requires_human_review,
        "highest_severity": highest_severity
    }
