"""
ZYROO INTERNSHIP PROGRAM - WEEK 3
Module: Information Extraction & Missing-Field Resilience Engine
Steps 7 & 8: Improve Information Extraction & Handle Missing Fields

Target Fields:
- Invoice: Invoice Number, Date, Company Name, Total Amount
- Resume: Name, Email, Phone, Skills
- Other: Generic entity extraction / summary

Resilience Principles:
1. Always return 'Not Found' when a field cannot be located.
2. Never crash or throw unhandled exceptions on incomplete documents.
3. Provide an audit dictionary tracking found vs missing fields with completeness scores.
4. Normalize currencies, dates, and clean strings.
"""

import re
from typing import Dict, Any, List, Optional


# ==============================================================================
# TAXONOMY & KEYWORDS
# ==============================================================================

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
        # Explicit label matches: Invoice Number: INV-1024, Bill #: 9812, etc.
        r"(?i)\b(?:invoice\s*(?:no|number|#|id)|inv[\s#:\.\-]+|bill\s*(?:no|number|#|id)|invoice\s*ref)\s*[:\-#]?\s*([A-Z0-9\-_/]{3,25})",
        # Prefixed invoice code in text: INV-2026-0814 or FL-90421 or VNG-7712
        r"\b(INV-[A-Z0-9\-_]+)\b",
        r"\b([A-Z]{2,5}-[0-9]{3,8}(?:-[0-9]{2,4})?)\b",
        # OCR typo fallbacks (e.g. Wonca Numbar, Invoce No)
        r"(?i)\b(?:wonca|invoic|inv|bill)[a-z\s]*num[a-z]*\s*[:\-#]?\s*([A-Z0-9\-_/]{3,25})",
        # Bare #12345
        r"(?i)^#\s*([0-9]{4,12})$"
    ]
    
    for pat in patterns:
        matches = re.finditer(pat, text, re.MULTILINE)
        for m in matches:
            val = m.group(1).strip()
            # Filter false positives
            if val.lower() not in ["date", "total", "amount", "tax", "due", "usd", "pkr", "eur", "invoice", "number", "details"]:
                if len(val) >= 3:
                    return {"value": val, "status": "FOUND", "confidence": 0.95}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_invoice_date(text: str) -> Dict[str, Any]:
    """Extracts invoice/bill date supporting standard international and named month formats."""
    patterns = [
        # Labeled date: Date: 12-Jan-2026, Invoice Date: 04/02/2026
        r"(?i)\b(?:invoice\s*date|issue\s*date|statement\s*date|dated|date\s*of\s*issue|date)\s*[:\-]?\s*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2})",
        r"(?i)\b(?:invoice\s*date|issue\s*date|statement\s*date|dated|date)\s*[:\-]?\s*([0-9]{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*,?\s+[0-9]{2,4})",
        r"(?i)\b(?:invoice\s*date|issue\s*date|statement\s*date|dated|date)\s*[:\-]?\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+[0-9]{1,2},?\s+[0-9]{2,4})",
        # OCR typo date pattern
        r"(?i)\b(?:one|dute|date)\s*[:\-]?\s*([0-9]{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*-[0-9]{2,4})",
        # Bare date patterns
        r"\b([0-9]{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*-[0-9]{2,4})\b",
        r"\b([0-9]{4}-[0-9]{2}-[0-9]{2})\b",
        r"\b([0-9]{1,2}\/[0-9]{1,2}\/[0-9]{4})\b"
    ]

    for pat in patterns:
        m = re.search(pat, text)
        if m:
            val = m.group(1).strip()
            return {"value": val, "status": "FOUND", "confidence": 0.92}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_company_name(text: str) -> Dict[str, Any]:
    """Extracts vendor or issuing company name from header or explicit tags."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # 1. Look for explicit keyword labels with strict colon/dash: Sold By:, Billed By:, From:, Vendor Name:, Company Name:
    labeled_pat = r"(?i)\b(?:company(?:\s*name)?|vendor(?:\s*name)?|sold\s*by|billed\s*by|from)\s*[:\-]\s*([A-Za-z0-9\s&,\.\-]{3,45})"
    m = re.search(labeled_pat, text)
    if m:
        candidate = m.group(1).splitlines()[0].strip()
        candidate = re.sub(r"[,:\-]+$", "", candidate).strip()
        if candidate.lower() not in ["invoice", "tax invoice", "commercial invoice", "information", "details"]:
            return {"value": candidate, "status": "FOUND", "confidence": 0.90}

    # 2. Look for business entities with legal suffixes in header (top 10 lines)
    for line in lines[:10]:
        for suffix in COMPANY_LEGAL_SUFFIXES:
            if re.search(suffix, line, re.IGNORECASE):
                # Clean prefix titles if present
                clean_name = re.sub(r"(?i)^(?:commercial\s+invoice\s*-\s*|tax\s+invoice\s*-\s*|invoice\s*-\s*)", "", line).strip()
                if 3 <= len(clean_name) <= 60 and not any(bad in clean_name.lower() for bad in ["information", "details", "to:", "billed to"]):
                    return {"value": clean_name, "status": "FOUND", "confidence": 0.88}

    # 3. Heuristic fallback: check first 5 lines for candidate business name
    for line in lines[:5]:
        line_clean = line.strip()
        line_lower = line_clean.lower()
        if any(bad in line_lower for bad in ["tax invoice", "commercial invoice", "invoice", "date", "#", "http", "billed to", "bill to", "customer", "vendor information", "client details"]):
            continue
        if 4 <= len(line_clean) <= 45:
            return {"value": line_clean, "status": "FOUND", "confidence": 0.70}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_total_amount(text: str) -> Dict[str, Any]:
    """Extracts grand total amount with currency normalization."""
    # Find currency context if available
    curr_match = re.search(r"\b(PKR|USD|EUR|GBP|INR|Rs\.?|\$|€|£)\b", text, re.IGNORECASE)
    doc_currency = curr_match.group(1).upper() if curr_match else ""

    # Primary total patterns
    total_patterns = [
        # Explicit label: Total Amount: $8,389.38 or Total Amount Due: PKR 228,260
        r"(?i)\b(?:grand\s*total|total\s*amount(?:\s*due|\s*payable)?|balance\s*due|total\s*balance|total\s*charges)\s*[:\-]?\s*((?:PKR|USD|EUR|GBP|INR|Rs\.?|\$|€|£)?\s*[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)",
        # Generic total label
        r"(?i)\btotal\s*[:\-]\s*((?:PKR|USD|EUR|GBP|INR|Rs\.?|\$|€|£)?\s*[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)"
    ]

    for pat in total_patterns:
        matches = re.finditer(pat, text)
        for m in matches:
            val = m.group(1).strip()
            if re.search(r"[0-9]", val):
                if not re.search(r"(?i)(?:PKR|USD|EUR|GBP|INR|Rs|\$|€|£)", val) and doc_currency:
                    val = f"{doc_currency} {val}"
                return {"value": val, "status": "FOUND", "confidence": 0.94}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_invoice_fields(text: str) -> Dict[str, Any]:
    """Extracts all 4 standard invoice fields with audit metadata."""
    inv_num = extract_invoice_number(text)
    inv_date = extract_invoice_date(text)
    company = extract_company_name(text)
    total_amt = extract_total_amount(text)

    fields = {
        "invoice_number": inv_num,
        "date": inv_date,
        "company_name": company,
        "total_amount": total_amt
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
    # 1. Labeled pattern with strict delimiter: Name: Muhammad Usman or Candidate Name: Sarah Chen
    m = re.search(r"(?im)^\s*(?:candidate\s*name|full\s*name|name)\s*[:\-]\s*([A-Za-z\s\.]{2,35})$", text)
    if m:
        name = m.group(1).strip()
        if name.lower() not in ["resume", "curriculum vitae", "summary", "profile", "name"]:
            return {"value": name, "status": "FOUND", "confidence": 0.94}

    # 2. Header analysis: First 1-5 lines in resume
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
    """Extracts RFC-compliant email address."""
    pat = r"\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b"
    m = re.search(pat, text)
    if m:
        email = m.group(1).strip()
        return {"value": email, "status": "FOUND", "confidence": 0.98}
    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_candidate_phone(text: str) -> Dict[str, Any]:
    """Extracts phone number supporting international, US, and Pakistani cell formats."""
    patterns = [
        # Explicit label: Phone: +92 300 1234567, Tel: (415) 890-3412
        r"(?i)(?:phone|mobile|tel|cell|contact)[:\s]*(\+?[0-9\s\(\)\-\.]{9,22})",
        # Pakistani cell format: +92 300 1234567 or 0300-1234567 or 0333 4455667
        r"\b((?:\+?92[-.\s]?)?0?3[0-9]{2}[-.\s]?[0-9]{7})\b",
        # US/North American: (415) 890-3412 or 415-890-3412
        r"\b(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b",
        # International with country code
        r"\b(\+[1-9]\d{0,2}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4})\b"
    ]

    for pat in patterns:
        m = re.search(pat, text)
        if m:
            phone = m.group(1).strip()
            # Clean trailing punctuation
            phone = re.sub(r"[,;\s]+$", "", phone)
            if len(re.sub(r"\D", "", phone)) >= 7:
                return {"value": phone, "status": "FOUND", "confidence": 0.91}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_candidate_skills(text: str) -> Dict[str, Any]:
    """Extracts technical and business skills using word-boundary matching."""
    text_lower = text.lower()
    matched_skills = set()

    for skill in POPULAR_SKILLS:
        # Exact word-boundary match to avoid partial matches
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
    """Provides general document metadata for unclassified/other business documents."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    doc_title = lines[0] if lines else "Not Found"
    
    # Try to extract dates or subject lines
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


# ==============================================================================
# 4. UNIFIED EXTRACTION ROUTER
# ==============================================================================

def extract_document_information(text: str, document_type: str) -> Dict[str, Any]:
    """
    Unified extraction router. Dispatches to Invoice, Resume, or Other extraction engines.
    Always guarantees graceful error handling without raising exceptions.
    """
    try:
        if document_type == "Invoice":
            return extract_invoice_fields(text)
        elif document_type == "Resume":
            return extract_resume_fields(text)
        else:
            return extract_other_document_fields(text)
    except Exception as e:
        # Fallback safe error response
        return {
            "document_type": document_type,
            "error": str(e),
            "fields": {},
            "flat_values": {},
            "missing_fields": ["Extraction Exception Encountered"],
            "missing_count": 1,
            "total_fields": 0,
            "completeness_score": "0.0%"
        }
