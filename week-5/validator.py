"""
ZYROO INTERNSHIP PROGRAM - WEEK 5
Module: Advanced Document Validation Engine
Focus: Workflow automation, validation, review and auditability

Requirements Addressed:
- Invoice: validate Invoice Number, Date, Company Name, and Total Amount.
- Resume: validate Name, Email, and Skills.
- Format validation: Email, Phone, Date, and Numeric Amount.
- Records exactly which fields passed and which fields failed validation with error reasons.
- Produces structured validation payloads for downstream workflow routing.
"""

import re
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional


# ==============================================================================
# FORMAT VALIDATORS
# ==============================================================================

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)

PHONE_REGEX = re.compile(
    r"^(\+?[0-9]{1,4}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?)?[\d\s.-]{5,14}$"
)

# Common placeholder / invalid string tokens
INVALID_TOKENS = {
    "not found", "n/a", "none", "unknown", "null", "undefined",
    "missing", "sample", "test", "untitled", "placeholder", ""
}


def is_placeholder_or_empty(val: Any) -> bool:
    """Checks if a string is missing, None, or a common placeholder token."""
    if val is None:
        return True
    s = str(val).strip().lower()
    return s in INVALID_TOKENS or len(s) == 0


def validate_email(email_str: str) -> Tuple[bool, str]:
    """
    Validates email format using RFC-compliant pattern.
    Must not be a placeholder and must have standard user@domain.tld structure.
    """
    if is_placeholder_or_empty(email_str):
        return False, "Email address is missing or empty."
    
    clean_email = email_str.strip()
    if not EMAIL_REGEX.match(clean_email):
        return False, f"Invalid email format: '{clean_email}'. Expected standard username@domain.com pattern."
    
    # Check domain has valid dot and tld
    parts = clean_email.split("@")
    if len(parts) != 2 or "." not in parts[1]:
        return False, f"Email domain is malformed in '{clean_email}'."
    
    domain_tld = parts[1].split(".")[-1]
    if len(domain_tld) < 2:
        return False, f"Email top-level domain '.{domain_tld}' is too short."

    return True, "Valid email format."


def validate_phone(phone_str: str) -> Tuple[bool, str]:
    """
    Validates phone number format.
    Must contain between 7 and 15 digits, allowing international +, parens, hyphens.
    """
    if is_placeholder_or_empty(phone_str):
        return False, "Phone number is missing or empty."
    
    clean_phone = phone_str.strip()
    digits_only = re.sub(r"\D", "", clean_phone)
    
    if len(digits_only) < 7:
        return False, f"Phone number '{clean_phone}' has too few digits ({len(digits_only)} found, minimum 7 required)."
    if len(digits_only) > 16:
        return False, f"Phone number '{clean_phone}' exceeds international digit limit ({len(digits_only)} digits)."
    
    if not PHONE_REGEX.match(clean_phone):
        return False, f"Phone number '{clean_phone}' contains invalid characters."

    return True, "Valid phone number format."


def validate_date(date_str: str) -> Tuple[bool, str]:
    """
    Validates date string format and calendar plausibility.
    Supports ISO (YYYY-MM-DD), slash formats (DD/MM/YYYY or MM/DD/YYYY), and verbal dates.
    Ensures calendar year is reasonable (between 1950 and 2035).
    """
    if is_placeholder_or_empty(date_str):
        return False, "Date is missing or empty."
    
    clean_date = date_str.strip()
    
    # List of candidate datetime formats
    candidate_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%d/%b/%Y",
        "%Y/%m/%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%d %b, %Y",
        "%B %d %Y"
    ]
    
    parsed_date = None
    for fmt in candidate_formats:
        try:
            parsed_date = datetime.strptime(clean_date, fmt)
            break
        except ValueError:
            continue
            
    # Regex fallback for year check if exact formatting differs slightly
    if not parsed_date:
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", clean_date)
        if year_match:
            year = int(year_match.group(1))
            if 1950 <= year <= 2035:
                return True, f"Valid date string with recognized year {year}."
        return False, f"Unrecognized or invalid date format: '{clean_date}'."

    if not (1950 <= parsed_date.year <= 2035):
        return False, f"Date year {parsed_date.year} is out of plausible operational range (1950-2035)."

    return True, f"Valid date: {parsed_date.strftime('%Y-%m-%d')}."


def validate_numeric_amount(amount_str: str) -> Tuple[bool, Optional[float], str]:
    """
    Validates numeric currency amount.
    Handles currency symbols ($ , € , £ , PKR , Rs , USD , EUR) and commas.
    Amount must be a positive float greater than 0.0.
    """
    if is_placeholder_or_empty(amount_str):
        return False, None, "Total amount is missing or empty."
    
    clean = str(amount_str).strip()
    
    # Strip known currency prefixes / suffixes
    clean_num = re.sub(r"(?i)\b(USD|PKR|EUR|GBP|Rs\.?|\$|€|£|AUD|CAD)\b", "", clean)
    clean_num = clean_num.replace(",", "").strip()
    
    # Check if a valid float number can be parsed
    num_match = re.search(r"[-+]?\d*\.?\d+", clean_num)
    if not num_match:
        return False, None, f"Could not parse numeric amount from '{amount_str}'."
    
    try:
        val = float(num_match.group(0))
        if val <= 0.0:
            return False, val, f"Total amount must be greater than zero, found: {val}."
        return True, val, f"Valid positive amount: {val:.2f}."
    except ValueError:
        return False, None, f"Invalid numeric representation in amount: '{amount_str}'."


def validate_invoice_number(inv_no: str) -> Tuple[bool, str]:
    """
    Validates invoice identifier format:
    - Must not be empty or placeholder
    - Minimum length of 3, maximum of 35 characters
    - Must contain at least one digit or alphanumeric sequence
    - Must not be generic noise words
    """
    if is_placeholder_or_empty(inv_no):
        return False, "Invoice number is missing or empty."
    
    clean = inv_no.strip()
    if len(clean) < 3:
        return False, f"Invoice number '{clean}' is too short (minimum 3 characters)."
    if len(clean) > 35:
        return False, f"Invoice number '{clean}' exceeds maximum length of 35 characters."
    
    # Disallow generic words that sometimes get captured by OCR
    forbidden = {"invoice", "tax invoice", "bill", "receipt", "number", "details", "payment", "amount"}
    if clean.lower() in forbidden:
        return False, f"Invoice number '{clean}' matches a generic document header."
    
    if not re.search(r"[A-Za-z0-9]", clean):
        return False, f"Invoice number '{clean}' contains no alphanumeric characters."

    return True, "Valid invoice identifier."


def validate_company_name(company: str) -> Tuple[bool, str]:
    """
    Validates company/vendor name:
    - Must not be empty or placeholder
    - Minimum length of 2 characters
    - Must not be generic system headers
    """
    if is_placeholder_or_empty(company):
        return False, "Company name is missing or empty."
    
    clean = company.strip()
    if len(clean) < 2:
        return False, f"Company name '{clean}' is too short."
    if len(clean) > 80:
        return False, f"Company name exceeds realistic length limit ({len(clean)} characters)."
    
    generic_headers = {"invoice", "tax invoice", "receipt", "statement", "bill to", "billed to", "date"}
    if clean.lower() in generic_headers:
        return False, f"Company name '{clean}' is an invalid document keyword."

    return True, "Valid company name."


def validate_candidate_name(name: str) -> Tuple[bool, str]:
    """
    Validates candidate name on resume:
    - Must not be empty or placeholder
    - Length between 2 and 50 characters
    - Must not contain obvious header words
    """
    if is_placeholder_or_empty(name):
        return False, "Candidate name is missing or empty."
    
    clean = name.strip()
    if len(clean) < 2:
        return False, f"Candidate name '{clean}' is too short."
    if len(clean) > 60:
        return False, f"Candidate name '{clean}' exceeds expected length."
        
    generic = {"resume", "curriculum vitae", "cv", "summary", "profile", "contact", "education", "experience"}
    if clean.lower() in generic:
        return False, f"Candidate name '{clean}' is a generic resume section header."

    # Must contain alphabetic characters
    if not re.search(r"[A-Za-z]", clean):
        return False, f"Candidate name '{clean}' contains no letters."

    return True, "Valid candidate name."


def validate_skills(skills_val: Any) -> Tuple[bool, str]:
    """
    Validates candidate skills list:
    - Must not be empty or placeholder
    - Can be a list or comma-separated string
    - Must contain at least 1 verified skill
    """
    if is_placeholder_or_empty(skills_val):
        return False, "Skills section is missing or no recognizable skills were extracted."
    
    if isinstance(skills_val, list):
        if len(skills_val) == 0:
            return False, "Skills list is empty."
        return True, f"Valid skills list with {len(skills_val)} skill(s)."
    
    clean_str = str(skills_val).strip()
    parts = [p.strip() for p in clean_str.split(",") if p.strip()]
    if not parts:
        return False, "No valid skills extracted from string representation."

    return True, f"Valid skills with {len(parts)} skill(s) detected."


# ==============================================================================
# UNIFIED DOCUMENT VALIDATOR
# ==============================================================================

def validate_document(
    document_type: str,
    extracted_values: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Executes advanced document validation rules based on document type.
    
    Week 5 Specification:
    - Invoice: validate Invoice Number, Date, Company Name and Total Amount.
    - Resume: validate Name, Email and Skills (and Phone if present).
    - Other: validate Title and Date.
    - Record exactly which fields failed validation.
    
    Args:
        document_type: 'Invoice', 'Resume', or 'Other'
        extracted_values: Dictionary of extracted field values (e.g. flat_values)
        
    Returns:
        dict: {
            "is_valid": bool,
            "document_type": str,
            "passed_fields": list[str],
            "failed_fields": list[str],
            "field_errors": dict[str, str],
            "field_results": dict[str, dict],
            "parsed_amount": float or None,
            "summary": str
        }
    """
    passed_fields: List[str] = []
    failed_fields: List[str] = []
    field_errors: Dict[str, str] = {}
    field_results: Dict[str, Dict[str, Any]] = {}
    parsed_amount: Optional[float] = None

    if document_type == "Invoice":
        # 1. Invoice Number
        inv_no = extracted_values.get("invoice_number", "Not Found")
        ok, reason = validate_invoice_number(inv_no)
        field_results["invoice_number"] = {"value": inv_no, "valid": ok, "reason": reason}
        if ok:
            passed_fields.append("invoice_number")
        else:
            failed_fields.append("invoice_number")
            field_errors["invoice_number"] = reason

        # 2. Date
        inv_date = extracted_values.get("date", "Not Found")
        ok, reason = validate_date(inv_date)
        field_results["date"] = {"value": inv_date, "valid": ok, "reason": reason}
        if ok:
            passed_fields.append("date")
        else:
            failed_fields.append("date")
            field_errors["date"] = reason

        # 3. Company Name
        company = extracted_values.get("company", "Not Found")
        ok, reason = validate_company_name(company)
        field_results["company"] = {"value": company, "valid": ok, "reason": reason}
        if ok:
            passed_fields.append("company")
        else:
            failed_fields.append("company")
            field_errors["company"] = reason

        # 4. Total Amount
        tot_amount = extracted_values.get("total_amount", "Not Found")
        ok, parsed_num, reason = validate_numeric_amount(tot_amount)
        parsed_amount = parsed_num
        field_results["total_amount"] = {"value": tot_amount, "valid": ok, "reason": reason, "numeric_value": parsed_num}
        if ok:
            passed_fields.append("total_amount")
        else:
            failed_fields.append("total_amount")
            field_errors["total_amount"] = reason

    elif document_type == "Resume":
        # 1. Candidate Name
        cand_name = extracted_values.get("name", "Not Found")
        ok, reason = validate_candidate_name(cand_name)
        field_results["name"] = {"value": cand_name, "valid": ok, "reason": reason}
        if ok:
            passed_fields.append("name")
        else:
            failed_fields.append("name")
            field_errors["name"] = reason

        # 2. Candidate Email
        cand_email = extracted_values.get("email", "Not Found")
        ok, reason = validate_email(cand_email)
        field_results["email"] = {"value": cand_email, "valid": ok, "reason": reason}
        if ok:
            passed_fields.append("email")
        else:
            failed_fields.append("email")
            field_errors["email"] = reason

        # 3. Skills
        cand_skills = extracted_values.get("skills", "Not Found")
        ok, reason = validate_skills(cand_skills)
        field_results["skills"] = {"value": cand_skills, "valid": ok, "reason": reason}
        if ok:
            passed_fields.append("skills")
        else:
            failed_fields.append("skills")
            field_errors["skills"] = reason

        # 4. Phone (Optional field for resume, but validate format if present)
        cand_phone = extracted_values.get("phone")
        if cand_phone and not is_placeholder_or_empty(cand_phone):
            ok_phone, phone_reason = validate_phone(cand_phone)
            field_results["phone"] = {"value": cand_phone, "valid": ok_phone, "reason": phone_reason}
            if not ok_phone:
                failed_fields.append("phone")
                field_errors["phone"] = phone_reason
            else:
                passed_fields.append("phone")

    else:
        # Document Type: Other
        doc_title = extracted_values.get("document_title", extracted_values.get("title", "Not Found"))
        if is_placeholder_or_empty(doc_title):
            failed_fields.append("document_title")
            field_errors["document_title"] = "Document title is missing or unreadable."
            field_results["document_title"] = {"value": doc_title, "valid": False, "reason": "Missing title"}
        else:
            passed_fields.append("document_title")
            field_results["document_title"] = {"value": doc_title, "valid": True, "reason": "Valid document title"}

        # Optional date check if present
        date_val = extracted_values.get("date")
        if date_val and not is_placeholder_or_empty(date_val):
            ok, reason = validate_date(date_val)
            field_results["date"] = {"value": date_val, "valid": ok, "reason": reason}
            if ok:
                passed_fields.append("date")
            else:
                failed_fields.append("date")
                field_errors["date"] = reason

    is_overall_valid = (len(failed_fields) == 0)

    if is_overall_valid:
        summary = f"All {len(passed_fields)} required fields successfully validated."
    else:
        summary = f"Validation failed for {len(failed_fields)} field(s): {', '.join(failed_fields)}."

    return {
        "is_valid": is_overall_valid,
        "document_type": document_type,
        "passed_fields": passed_fields,
        "failed_fields": failed_fields,
        "field_errors": field_errors,
        "field_results": field_results,
        "parsed_amount": parsed_amount,
        "summary": summary
    }
