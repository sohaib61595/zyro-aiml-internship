"""
ZYROO INTERNSHIP PROGRAM - WEEK 6
Module: Advanced Document Validation Engine
Focus: Enterprise integration, security, optimization, and deployment readiness
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
    r"^(\+?[0-9]{1,4}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?)?[\d\s.-]{5,16}$"
)

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
    """Validates email format using RFC-compliant pattern."""
    if is_placeholder_or_empty(email_str):
        return False, "Email address is missing or empty."
    
    clean_email = email_str.strip()
    if not EMAIL_REGEX.match(clean_email):
        return False, f"Invalid email format: '{clean_email}'. Expected standard username@domain.com pattern."
    
    parts = clean_email.split("@")
    if len(parts) != 2 or "." not in parts[1]:
        return False, f"Email domain is malformed in '{clean_email}'."
    
    domain_tld = parts[1].split(".")[-1]
    if len(domain_tld) < 2:
        return False, f"Email top-level domain '.{domain_tld}' is too short."

    return True, "Valid email format."


def validate_phone(phone_str: str) -> Tuple[bool, str]:
    """Validates phone number format."""
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
    """Validates date string format and calendar plausibility (1950 - 2035)."""
    if is_placeholder_or_empty(date_str):
        return False, "Date is missing or empty."
    
    clean_date = date_str.strip()
    candidate_formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
        "%d-%b-%Y", "%d-%B-%Y", "%d/%b/%Y", "%Y/%m/%d", "%B %d, %Y",
        "%b %d, %Y", "%d %B %Y", "%d %b %Y", "%d %b, %Y", "%B %d %Y"
    ]
    
    parsed_date = None
    for fmt in candidate_formats:
        try:
            parsed_date = datetime.strptime(clean_date, fmt)
            break
        except ValueError:
            continue
            
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
    """Validates numeric currency amount and parses float value."""
    if is_placeholder_or_empty(amount_str):
        return False, None, "Total amount is missing or empty."
    
    clean = str(amount_str).strip()
    clean_num = re.sub(r"(?i)\b(USD|PKR|EUR|GBP|Rs\.?|\$|€|£|AUD|CAD)\b", "", clean)
    clean_num = clean_num.replace(",", "").strip()
    
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
    """Validates invoice identifier format."""
    if is_placeholder_or_empty(inv_no):
        return False, "Invoice number is missing or empty."
    
    clean = inv_no.strip()
    if len(clean) < 3:
        return False, f"Invoice number '{clean}' is too short (minimum 3 characters)."
    if len(clean) > 35:
        return False, f"Invoice number '{clean}' exceeds maximum length of 35 characters."
    
    forbidden = {"invoice", "tax invoice", "bill", "receipt", "number", "details", "payment", "amount", "subtotal"}
    if clean.lower() in forbidden:
        return False, f"Invoice number '{clean}' matches a generic document header."
    
    if not re.search(r"[A-Za-z0-9]", clean):
        return False, f"Invoice number '{clean}' contains no alphanumeric characters."

    return True, "Valid invoice identifier."


def validate_company_name(company: str) -> Tuple[bool, str]:
    """Validates company/vendor name."""
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
    """Validates candidate name on resume."""
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

    if not re.search(r"[A-Za-z]", clean):
        return False, f"Candidate name '{clean}' contains no letters."

    return True, "Valid candidate name."


# ==============================================================================
# DOCUMENT VALIDATION DISPATCHER
# ==============================================================================

def validate_invoice(extracted: Dict[str, Any]) -> Dict[str, Any]:
    """Applies validation rules to extracted invoice fields."""
    inv_no = extracted.get("invoice_number", "")
    date_val = extracted.get("date", "")
    company = extracted.get("company", "")
    total_val = extracted.get("total_amount", "")

    passed_fields = []
    failed_fields = []
    field_errors = {}
    parsed_amount = None

    # 1. Invoice Number
    is_ok, msg = validate_invoice_number(inv_no)
    if is_ok:
        passed_fields.append("invoice_number")
    else:
        failed_fields.append("invoice_number")
        field_errors["invoice_number"] = msg

    # 2. Date
    is_ok, msg = validate_date(date_val)
    if is_ok:
        passed_fields.append("date")
    else:
        failed_fields.append("date")
        field_errors["date"] = msg

    # 3. Company Name
    is_ok, msg = validate_company_name(company)
    if is_ok:
        passed_fields.append("company")
    else:
        failed_fields.append("company")
        field_errors["company"] = msg

    # 4. Total Amount
    is_ok, parsed_amount, msg = validate_numeric_amount(total_val)
    if is_ok:
        passed_fields.append("total_amount")
    else:
        failed_fields.append("total_amount")
        field_errors["total_amount"] = msg

    is_all_valid = (len(failed_fields) == 0)

    return {
        "document_type": "Invoice",
        "is_valid": is_all_valid,
        "passed_fields": passed_fields,
        "failed_fields": failed_fields,
        "field_errors": field_errors,
        "parsed_amount": parsed_amount,
        "total_fields_checked": 4,
        "passed_count": len(passed_fields)
    }


def validate_resume(extracted: Dict[str, Any]) -> Dict[str, Any]:
    """Applies validation rules to extracted resume fields."""
    name = extracted.get("name", "")
    email = extracted.get("email", "")
    phone = extracted.get("phone", "")
    skills = extracted.get("skills", "")

    passed_fields = []
    failed_fields = []
    field_errors = {}

    # 1. Candidate Name
    is_ok, msg = validate_candidate_name(name)
    if is_ok:
        passed_fields.append("name")
    else:
        failed_fields.append("name")
        field_errors["name"] = msg

    # 2. Email Address
    is_ok, msg = validate_email(email)
    if is_ok:
        passed_fields.append("email")
    else:
        failed_fields.append("email")
        field_errors["email"] = msg

    # 3. Technical Skills
    if is_placeholder_or_empty(skills):
        failed_fields.append("skills")
        field_errors["skills"] = "No technical skills identified."
    else:
        passed_fields.append("skills")

    # 4. Phone (optional but validated if provided)
    if not is_placeholder_or_empty(phone):
        is_ok, msg = validate_phone(phone)
        if is_ok:
            passed_fields.append("phone")
        else:
            failed_fields.append("phone")
            field_errors["phone"] = msg

    is_all_valid = (len(failed_fields) == 0)

    return {
        "document_type": "Resume",
        "is_valid": is_all_valid,
        "passed_fields": passed_fields,
        "failed_fields": failed_fields,
        "field_errors": field_errors,
        "parsed_amount": None,
        "total_fields_checked": 3 + (1 if not is_placeholder_or_empty(phone) else 0),
        "passed_count": len(passed_fields)
    }


def validate_contract(extracted: Dict[str, Any]) -> Dict[str, Any]:
    """Applies validation rules to contract fields."""
    title = extracted.get("contract_title", "")
    eff_date = extracted.get("effective_date", "")

    passed_fields = []
    failed_fields = []
    field_errors = {}

    if is_placeholder_or_empty(title):
        failed_fields.append("contract_title")
        field_errors["contract_title"] = "Contract title missing."
    else:
        passed_fields.append("contract_title")

    if is_placeholder_or_empty(eff_date):
        failed_fields.append("effective_date")
        field_errors["effective_date"] = "Effective date missing."
    else:
        passed_fields.append("effective_date")

    return {
        "document_type": "Contract",
        "is_valid": (len(failed_fields) == 0),
        "passed_fields": passed_fields,
        "failed_fields": failed_fields,
        "field_errors": field_errors,
        "parsed_amount": None,
        "total_fields_checked": 2,
        "passed_count": len(passed_fields)
    }


def validate_document(document_type: str, extracted_flat_values: Dict[str, Any]) -> Dict[str, Any]:
    """Universal dispatcher for document validation."""
    if document_type == "Invoice":
        return validate_invoice(extracted_flat_values)
    elif document_type == "Resume":
        return validate_resume(extracted_flat_values)
    elif document_type == "Contract":
        return validate_contract(extracted_flat_values)
    else:
        return {
            "document_type": "Other",
            "is_valid": True,
            "passed_fields": ["document_title"],
            "failed_fields": [],
            "field_errors": {},
            "parsed_amount": None,
            "total_fields_checked": 1,
            "passed_count": 1
        }
