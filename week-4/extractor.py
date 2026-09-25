"""
ZYROO INTERNSHIP PROGRAM - WEEK 4
Module: Field Extraction & Processing Status Evaluation Engine
Tasks: Task 6 (Extracted Fields), Task 7 (Processing Status Determination)

Capabilities:
- Invoice extraction: Company, Invoice Number, Total Amount, Date.
- Resume extraction: Candidate Name, Email, Phone, Skills.
- Other document extraction: Title, Subject, Dates.
- Missing field resilience: Never throws unhandled exceptions; sets explicit 'Not Found'.
- Task 7 Status Evaluator: Computes 'Processed', 'Needs Review', or 'Failed'.
"""

import re
from typing import Dict, Any, List, Optional, Tuple

POPULAR_SKILLS = [
    # Programming Languages
    "Python", "JavaScript", "TypeScript", "SQL", "C++", "Java", "C#", "Go", "Rust", "Dart", "Scala", "PHP", "Bash",
    # Frameworks & Libraries
    "Django", "FastAPI", "Flask", "React", "Next.js", "Node.js", "Vue.js", "Angular", "Express", "Spring Boot", "Flutter",
    # AI / ML & Data Science
    "Machine Learning", "Deep Learning", "NLP", "Computer Vision", "PyTorch", "TensorFlow", "Scikit-Learn",
    "Pandas", "NumPy", "OpenCV", "HuggingFace", "LangChain", "Data Analysis", "Statistics", "Power BI", "Tableau",
    # Databases & Storage
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "Snowflake", "Cassandra", "Elasticsearch",
    # Cloud, DevOps & Infrastructure
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "CI/CD", "Git", "Linux", "Jenkins", "Ansible",
    # General Competencies
    "Agile", "Scrum", "Jira", "API Testing", "Selenium", "Communication", "Leadership", "Project Management"
]

COMPANY_LEGAL_SUFFIXES = [
    r"\bLLC\b", r"\bPvt\s+Ltd\b", r"\bLtd\b", r"\bInc\.?\b", r"\bCorp(?:oration)?\b",
    r"\bSolutions\b", r"\bTechnologies\b", r"\bEnterprises\b", r"\bServices\b",
    r"\bLogistics\b", r"\bStudios\b", r"\bSystems\b", r"\bConsultancy\b",
    r"\bConsulting\b", r"\bDepot\b", r"\bAgency\b", r"\bWorks\b"
]


# ==============================================================================
# 1. INVOICE FIELD EXTRACTION
# ==============================================================================

def extract_invoice_number(text: str) -> Dict[str, Any]:
    """Extracts invoice identifier using multiple regex heuristics and OCR fallbacks."""
    patterns = [
        r"(?i)\b(?:invoice\s*(?:no|number|#|id)|inv[\s#:\.\-]+|bill\s*(?:no|number|#|id)|invoice\s*ref)\s*[:\-#]?\s*([A-Z0-9\-_/]{3,25})",
        r"\b(INV-[A-Z0-9\-_]+)\b",
        r"\b([A-Z]{2,5}-[0-9]{3,8}(?:-[0-9]{2,4})?)\b",
        r"(?i)\b(?:wonca|invoic|inv|bill)[a-z\s]*num[a-z]*\s*[:\-#]?\s*([A-Z0-9\-_/]{3,25})",
        r"(?i)^#\s*([0-9]{4,12})$"
    ]
    
    for pat in patterns:
        matches = re.finditer(pat, text, re.MULTILINE)
        for m in matches:
            val = m.group(1).strip()
            if val.lower() not in ["date", "total", "amount", "tax", "due", "usd", "pkr", "eur", "invoice", "number", "details"]:
                if len(val) >= 3:
                    return {"value": val, "status": "FOUND", "confidence": 0.95}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_invoice_date(text: str) -> Dict[str, Any]:
    """Extracts invoice billing date supporting ISO, US, and UK date formats."""
    patterns = [
        # Explicit label: Date: 2026-09-15 or Invoice Date: 15/09/2026
        r"(?i)(?:invoice\s*date|billing\s*date|issue\s*date|date)\s*[:\-]?\s*([0-9]{1,4}[-/.][0-9]{1,2}[-/.][0-9]{1,4})",
        r"(?i)(?:invoice\s*date|date)\s*[:\-]?\s*([A-Za-z]{3,9}\s+[0-9]{1,2},?\s+[0-9]{4})",
        r"(?i)(?:invoice\s*date|date)\s*[:\-]?\s*([0-9]{1,2}\s+[A-Za-z]{3,9},?\s+[0-9]{4})",
        # Generic ISO Date: 2026-08-14
        r"\b(20[2-3][0-9]-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01]))\b",
        # Slash date: 15/09/2026
        r"\b((?:0[1-9]|[12][0-9]|3[01])/(?:0[1-9]|1[0-2])/20[2-3][0-9])\b"
    ]

    for pat in patterns:
        m = re.search(pat, text)
        if m:
            raw_date = m.group(1).strip()
            return {"value": raw_date, "status": "FOUND", "confidence": 0.92}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_company_name(text: str) -> Dict[str, Any]:
    """Extracts company/vendor name from header or company suffix patterns."""
    # Pattern 1: Billed from / From: Company Name
    from_m = re.search(r"(?im)^\s*(?:from|vendor|billed\s+from|seller|provider)\s*[:\-]\s*([A-Za-z0-9\s&.,'-]{3,45})$", text)
    if from_m:
        val = from_m.group(1).strip()
        if val.lower() not in ["invoice", "tax invoice", "bill to", "details"]:
            return {"value": val, "status": "FOUND", "confidence": 0.93}

    # Pattern 2: Search for registered company suffixes (LLC, Inc, Pvt Ltd, Technologies, Solutions)
    for suffix in COMPANY_LEGAL_SUFFIXES:
        match = re.search(rf"\b([A-Z][A-Za-z0-9&'\s]{{2,35}}\s+{suffix})", text)
        if match:
            candidate = match.group(1).strip()
            # Clean leading newlines or labels
            candidate = re.sub(r"(?i)^(?:from|to|bill\s+to|vendor)\s*[:\-]?\s*", "", candidate).strip()
            if len(candidate.splitlines()) == 1 and len(candidate) <= 50:
                return {"value": candidate, "status": "FOUND", "confidence": 0.88}

    # Pattern 3: Top 3 lines header fallback
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:3]:
        line_clean = re.sub(r"(?i)^(?:tax\s+invoice|invoice|receipt|commercial\s+invoice)\s*", "", line).strip()
        if line_clean and len(line_clean) >= 4 and len(line_clean) <= 40:
            if not any(token in line_clean.lower() for token in ["invoice", "bill to", "due", "date", "page", "phone", "email", "@"]):
                return {"value": line_clean, "status": "FOUND", "confidence": 0.75}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_total_amount(text: str) -> Dict[str, Any]:
    """Extracts grand total amount supporting multiple international and Pakistani currencies."""
    patterns = [
        # Explicit label: Total: $1,250.00 or Grand Total: PKR 150,000 or Total Due: 450.00 EUR
        r"(?i)(?:grand\s*total|total\s*amount|total\s*due|balance\s*due|amount\s*due|net\s*payable|total)\s*[:\-]?\s*([A-Z]{3}|\$|€|£|Rs\.?)?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)\s*([A-Z]{3})?",
        # Pakistani Rupee: PKR 25,000 or Rs. 15,500
        r"(?i)\b(?:PKR|Rs\.?)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)",
        # Dollar/Euro amount: $1,450.00
        r"(\$|€|£)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)"
    ]

    for pat in patterns:
        matches = list(re.finditer(pat, text))
        if matches:
            # Pick the last match since totals usually appear at bottom of invoices
            last_match = matches[-1]
            groups = [g for g in last_match.groups() if g is not None]
            
            # Format combined currency + numeric amount
            raw_str = last_match.group(0).strip()
            # Clean label prefixes if captured
            clean_str = re.sub(r"(?i)^(?:grand\s*total|total\s*amount|total\s*due|balance\s*due|amount\s*due|net\s*payable|total)\s*[:\-]?\s*", "", raw_str).strip()
            
            # Sanity check: must contain at least one digit
            if re.search(r"\d", clean_str):
                return {"value": clean_str, "status": "FOUND", "confidence": 0.94}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_invoice_fields(text: str) -> Dict[str, Any]:
    """Extracts all 4 standard invoice fields with audit metadata."""
    inv_no = extract_invoice_number(text)
    inv_date = extract_invoice_date(text)
    company = extract_company_name(text)
    total = extract_total_amount(text)

    fields = {
        "invoice_number": inv_no,
        "date": inv_date,
        "company": company,
        "total_amount": total
    }

    missing = [k for k, v in fields.items() if v["status"] == "NOT_FOUND"]
    found_count = len(fields) - len(missing)
    completeness = round((found_count / len(fields)) * 100, 1)

    return {
        "document_type": "Invoice",
        "fields": fields,
        "flat_values": {k: v["value"] for k, v in fields.items()},
        "missing_fields": missing,
        "missing_count": len(missing),
        "total_fields": len(fields),
        "completeness_score": f"{completeness}%"
    }


# ==============================================================================
# 2. RESUME FIELD EXTRACTION
# ==============================================================================

def extract_candidate_name(text: str) -> Dict[str, Any]:
    """Extracts candidate name using labeled patterns and header heuristics."""
    m = re.search(r"(?im)^\s*(?:candidate\s*name|full\s*name|name)\s*[:\-]\s*([A-Za-z\s\.]{2,35})$", text)
    if m:
        name = m.group(1).strip()
        if name.lower() not in ["resume", "curriculum vitae", "summary", "profile", "name"]:
            return {"value": name, "status": "FOUND", "confidence": 0.94}

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:5]:
        line_clean = re.sub(r"(?i)^(?:curriculum\s+vitae\s*-\s*|resume\s*-\s*|cv\s*-\s*)", "", line).strip()
        line_lower = line_clean.lower()
        if any(bad in line_lower for bad in ["curriculum vitae", "resume", "email", "phone", "@", "+", "http", "objective", "summary", "profile", "candidate"]):
            continue
        words = line_clean.split()
        if 1 <= len(words) <= 4 and 2 <= len(line_clean) <= 35:
            if words[0][0].isupper():
                return {"value": line_clean, "status": "FOUND", "confidence": 0.85}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_candidate_email(text: str) -> Dict[str, Any]:
    """Extracts email address."""
    pat = r"\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b"
    m = re.search(pat, text)
    if m:
        email = m.group(1).strip()
        return {"value": email, "status": "FOUND", "confidence": 0.98}
    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_candidate_phone(text: str) -> Dict[str, Any]:
    """Extracts phone number."""
    patterns = [
        r"(?i)(?:phone|mobile|tel|cell|contact)[:\s]*(\+?[0-9\s\(\)\-\.]{9,22})",
        r"\b((?:\+?92[-.\s]?)?0?3[0-9]{2}[-.\s]?[0-9]{7})\b",
        r"\b(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b",
        r"\b(\+[1-9]\d{0,2}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4})\b"
    ]

    for pat in patterns:
        m = re.search(pat, text)
        if m:
            phone = m.group(1).strip()
            phone = re.sub(r"[,;\s]+$", "", phone)
            if len(re.sub(r"\D", "", phone)) >= 7:
                return {"value": phone, "status": "FOUND", "confidence": 0.91}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_candidate_skills(text: str) -> Dict[str, Any]:
    """Extracts technical and business skills using word-boundary matching."""
    text_lower = text.lower()
    matched_skills = set()

    for skill in POPULAR_SKILLS:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            matched_skills.add(skill)

    skills_list = sorted(list(matched_skills))
    if skills_list:
        return {
            "value": ", ".join(skills_list),
            "status": "FOUND",
            "skills_list": skills_list,
            "count": len(skills_list),
            "confidence": 0.95
        }
    return {
        "value": "Not Found",
        "status": "NOT_FOUND",
        "skills_list": [],
        "count": 0,
        "confidence": 0.0
    }


def extract_resume_fields(text: str) -> Dict[str, Any]:
    """Extracts all 4 standard resume fields with audit metadata."""
    cand_name = extract_candidate_name(text)
    cand_email = extract_candidate_email(text)
    cand_phone = extract_candidate_phone(text)
    cand_skills = extract_candidate_skills(text)

    fields = {
        "name": cand_name,
        "email": cand_email,
        "phone": cand_phone,
        "skills": cand_skills
    }

    missing = [k for k, v in fields.items() if v["status"] == "NOT_FOUND"]
    found_count = len(fields) - len(missing)
    completeness = round((found_count / len(fields)) * 100, 1)

    return {
        "document_type": "Resume",
        "fields": fields,
        "flat_values": {k: v["value"] for k, v in fields.items()},
        "missing_fields": missing,
        "missing_count": len(missing),
        "total_fields": len(fields),
        "completeness_score": f"{completeness}%"
    }


# ==============================================================================
# 3. GENERIC 'OTHER' FIELD EXTRACTION
# ==============================================================================

def extract_other_document_fields(text: str) -> Dict[str, Any]:
    """Extracts metadata for general / other business documents."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    doc_title = lines[0] if lines else "Not Found"
    date_info = extract_invoice_date(text)
    subj_match = re.search(r"(?i)(?:subject|regarding|re)[:\s]*([^\n]+)", text)
    subject = subj_match.group(1).strip() if subj_match else "Not Found"

    fields = {
        "document_title": {"value": doc_title, "status": "FOUND" if doc_title != "Not Found" else "NOT_FOUND", "confidence": 0.75},
        "date": date_info,
        "subject": {"value": subject, "status": "FOUND" if subject != "Not Found" else "NOT_FOUND", "confidence": 0.80}
    }

    missing = [k for k, v in fields.items() if v["status"] == "NOT_FOUND"]

    return {
        "document_type": "Other",
        "fields": fields,
        "flat_values": {k: v["value"] for k, v in fields.items()},
        "missing_fields": missing,
        "missing_count": len(missing),
        "total_fields": len(fields),
        "completeness_score": f"{round(((len(fields) - len(missing)) / len(fields)) * 100, 1)}%"
    }


def extract_document_information(text: str, document_type: str) -> Dict[str, Any]:
    """Unified extraction router."""
    try:
        if document_type == "Invoice":
            return extract_invoice_fields(text)
        elif document_type == "Resume":
            return extract_resume_fields(text)
        else:
            return extract_other_document_fields(text)
    except Exception as e:
        return {
            "document_type": document_type,
            "error": str(e),
            "fields": {},
            "flat_values": {},
            "missing_fields": ["Extraction error"],
            "missing_count": 1,
            "total_fields": 0,
            "completeness_score": "0.0%"
        }


# ==============================================================================
# 4. TASK 7: PROCESSING STATUS EVALUATOR
# ==============================================================================

def determine_processing_status(
    document_type: str,
    extraction_result: Dict[str, Any],
    classification_confidence: float = 1.0,
    text_length: int = 100,
    extraction_error: Optional[str] = None
) -> Tuple[str, str]:
    """
    Task 7: Evaluates whether a document is 'Processed', 'Needs Review', or 'Failed'.
    
    Status Logic:
    - 'Failed':
        * Extraction error or completely unreadable text (length == 0).
    - 'Needs Review':
        * Invoices missing 'invoice_number' or 'total_amount'.
        * Resumes missing 'name' or 'email'.
        * Classification confidence is marginal (< 0.65).
        * Text is suspiciously short (< 35 characters).
    - 'Processed':
        * Critical fields located successfully and classification confidence is solid.
        
    Returns:
        (status_string, explanation_reason)
    """
    if extraction_error or text_length == 0:
        return "Failed", extraction_error or "Document contains no readable text."

    missing = extraction_result.get("missing_fields", [])
    flat_values = extraction_result.get("flat_values", {})

    if document_type == "Invoice":
        critical_missing = []
        if flat_values.get("invoice_number") == "Not Found":
            critical_missing.append("Invoice Number")
        if flat_values.get("total_amount") == "Not Found":
            critical_missing.append("Total Amount")
        if flat_values.get("company") == "Not Found":
            critical_missing.append("Company/Vendor")

        if critical_missing:
            return "Needs Review", f"Missing critical invoice field(s): {', '.join(critical_missing)}."

    elif document_type == "Resume":
        critical_missing = []
        if flat_values.get("name") == "Not Found":
            critical_missing.append("Candidate Name")
        if flat_values.get("email") == "Not Found":
            critical_missing.append("Email Address")

        if critical_missing:
            return "Needs Review", f"Missing essential contact field(s): {', '.join(critical_missing)}."

    if classification_confidence < 0.65:
        return "Needs Review", f"Low classification confidence ({round(classification_confidence * 100, 1)}%)."

    if text_length < 35:
        return "Needs Review", f"Extracted text is very short ({text_length} characters)."

    return "Processed", "All critical metadata successfully extracted and validated."
