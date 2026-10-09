"""
ZYROO INTERNSHIP PROGRAM - WEEK 6
Module: Multi-Category Entity Extraction Engine
Focus: Enterprise integration, security, optimization, and deployment readiness
"""

import re
from typing import Dict, Any, List, Optional

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
    r"\bConsulting\b", r"\bDepot\b", r"\bAgency\b", r"\bWorks\b", r"\bSupply\b"
]


# ==============================================================================
# INVOICE FIELD EXTRACTION
# ==============================================================================

def extract_invoice_number(text: str) -> Dict[str, Any]:
    """Extracts invoice identifier using multiple regex heuristics."""
    patterns = [
        r"(?i)\b(?:invoice\s*(?:no|number|#|id)|inv[\s#:\.\-]+|bill\s*(?:no|number|#|id)|invoice\s*ref)\s*[:\-#]?\s*([A-Z0-9\-_/]{3,30})",
        r"\b(INV-[A-Z0-9\-_]+)\b",
        r"\b([A-Z]{2,5}-[0-9]{3,8}(?:-[0-9]{2,4})?)\b",
        r"(?i)\b(?:wonca|invoic|inv|bill)[a-z\s]*num[a-z]*\s*[:\-#]?\s*([A-Z0-9\-_/]{3,30})",
        r"(?i)^#\s*([0-9]{4,12})$"
    ]
    
    for pat in patterns:
        matches = re.finditer(pat, text, re.MULTILINE)
        for m in matches:
            val = m.group(1).strip()
            if val.lower() not in ["date", "total", "amount", "tax", "due", "usd", "pkr", "eur", "invoice", "number", "details", "subtotal"]:
                if len(val) >= 3:
                    return {"value": val, "status": "FOUND", "confidence": 0.95}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_invoice_date(text: str) -> Dict[str, Any]:
    """Extracts invoice billing date supporting ISO, slash, hyphenated, and verbal date formats."""
    patterns = [
        r"(?i)(?:invoice\s*date|billing\s*date|issue\s*date|date)\s*[:\-]?\s*([0-9]{1,2}[-\s/]+[A-Za-z]{3,9}[-,\s/]+[0-9]{4})",
        r"(?i)(?:invoice\s*date|billing\s*date|issue\s*date|date)\s*[:\-]?\s*([0-9]{1,4}[-/.][0-9]{1,2}[-/.][0-9]{1,4})",
        r"(?i)(?:invoice\s*date|date)\s*[:\-]?\s*([A-Za-z]{3,9}\s+[0-9]{1,2},?\s+[0-9]{4})",
        r"(?i)(?:invoice\s*date|date)\s*[:\-]?\s*([0-9]{1,2}\s+[A-Za-z]{3,9},?\s+[0-9]{4})",
        r"\b([0-9]{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*-[0-9]{4})\b",
        r"\b(20[2-3][0-9]-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01]))\b",
        r"\b((?:0[1-9]|[12][0-9]|3[01])/(?:0[1-9]|1[0-2])/20[2-3][0-9])\b"
    ]

    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw_date = m.group(1).strip()
            return {"value": raw_date, "status": "FOUND", "confidence": 0.92}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_company_name(text: str) -> Dict[str, Any]:
    """Extracts company or vendor name from headers and legal suffix patterns."""
    from_m = re.search(r"(?im)^\s*(?:from|vendor|billed\s+from|seller|provider)\s*[:\-]\s*([A-Za-z0-9\s&.,'-]{3,45})$", text)
    if from_m:
        val = from_m.group(1).strip()
        if val.lower() not in ["invoice", "tax invoice", "bill to", "details"]:
            return {"value": val, "status": "FOUND", "confidence": 0.93}

    for suffix in COMPANY_LEGAL_SUFFIXES:
        match = re.search(rf"\b([A-Z][A-Za-z0-9&'\s]{{2,35}}\s+{suffix})", text)
        if match:
            candidate = match.group(1).strip()
            candidate = re.sub(r"(?i)^(?:from|to|bill\s+to|vendor)\s*[:\-]?\s*", "", candidate).strip()
            if len(candidate.splitlines()) == 1 and len(candidate) <= 50:
                return {"value": candidate, "status": "FOUND", "confidence": 0.88}

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:3]:
        line_clean = re.sub(r"(?i)^(?:tax\s+invoice|invoice|receipt|commercial\s+invoice)\s*", "", line).strip()
        if line_clean and 4 <= len(line_clean) <= 40:
            if not any(token in line_clean.lower() for token in ["invoice", "bill to", "due", "date", "page", "phone", "email", "@"]):
                return {"value": line_clean, "status": "FOUND", "confidence": 0.75}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_subtotal(text: str) -> Dict[str, Any]:
    """Extracts financial subtotal."""
    patterns = [
        r"(?i)\b(?:subtotal|sub-total|sub\s*total|net\s*amount)\s*[:\-]?\s*([A-Za-z]{3}|\$|€|£|Rs\.?)?\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            curr = m.group(1) or ""
            val = m.group(2) or ""
            full = f"{curr} {val}".strip()
            return {"value": full, "status": "FOUND", "confidence": 0.90}
    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_tax(text: str) -> Dict[str, Any]:
    """Extracts tax / VAT amount."""
    patterns = [
        r"(?i)\b(?:tax|vat|gst|sales\s*tax)(?:\s*\([0-9.]+%\))?\s*[:\-]?\s*([A-Za-z]{3}|\$|€|£|Rs\.?)?\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            curr = m.group(1) or ""
            val = m.group(2) or ""
            full = f"{curr} {val}".strip()
            return {"value": full, "status": "FOUND", "confidence": 0.88}
    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_total_amount(text: str) -> Dict[str, Any]:
    """Extracts total amount supporting PKR, USD, EUR, GBP currencies."""
    patterns = [
        r"(?i)(?:grand\s*total|total\s*amount|total\s*due|balance\s*due|amount\s*due|net\s*payable|total)\s*[:\-]?\s*([A-Za-z]{3}|\$|€|£|Rs\.?)?\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)[ \t]*(USD|PKR|EUR|GBP|AUD|CAD)?",
        r"(?i)\b(?:PKR|Rs\.?)\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)",
        r"(\$|€|£)\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)"
    ]

    for pat in patterns:
        matches = list(re.finditer(pat, text))
        if matches:
            last_match = matches[-1]
            groups = last_match.groups()
            prefix_curr = groups[0] or ""
            amount_num = groups[1] if len(groups) > 1 and groups[1] else ""
            suffix_curr = groups[2] if len(groups) > 2 and groups[2] else ""
            
            if not amount_num and prefix_curr and re.search(r"\d", prefix_curr):
                amount_num = prefix_curr
                prefix_curr = ""

            clean_str = f"{prefix_curr} {amount_num} {suffix_curr}".strip()
            if re.search(r"\d", clean_str):
                return {"value": clean_str, "status": "FOUND", "confidence": 0.94}

    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_invoice_fields(text: str) -> Dict[str, Any]:
    """Extracts complete invoice entity fields including financial components."""
    inv_no = extract_invoice_number(text)
    inv_date = extract_invoice_date(text)
    company = extract_company_name(text)
    subtotal = extract_subtotal(text)
    tax = extract_tax(text)
    total = extract_total_amount(text)

    fields = {
        "invoice_number": inv_no,
        "date": inv_date,
        "company": company,
        "subtotal": subtotal,
        "tax": tax,
        "total_amount": total
    }
    missing = [k for k, v in fields.items() if v["status"] == "NOT_FOUND" and k in ["invoice_number", "date", "company", "total_amount"]]
    completeness = round(((4 - len(missing)) / 4) * 100, 1)

    return {
        "document_type": "Invoice",
        "fields": fields,
        "flat_values": {k: v["value"] for k, v in fields.items()},
        "missing_fields": missing,
        "completeness_score": f"{completeness}%"
    }


# ==============================================================================
# RESUME / CV FIELD EXTRACTION
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
    """Extracts candidate email address."""
    pat = r"\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b"
    m = re.search(pat, text)
    if m:
        email = m.group(1).strip()
        return {"value": email, "status": "FOUND", "confidence": 0.98}
    return {"value": "Not Found", "status": "NOT_FOUND", "confidence": 0.0}


def extract_candidate_phone(text: str) -> Dict[str, Any]:
    """Extracts candidate phone number."""
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
    """Extracts technical and business skills using word boundary matching."""
    text_lower = text.lower()
    matched_skills = set()

    for skill in POPULAR_SKILLS:
        pattern = rf"\b{re.escape(skill.lower())}\b"
        if re.search(pattern, text_lower):
            matched_skills.add(skill)

    if matched_skills:
        sorted_skills = sorted(list(matched_skills))
        skills_str = ", ".join(sorted_skills)
        return {
            "value": skills_str,
            "skills_list": sorted_skills,
            "count": len(sorted_skills),
            "status": "FOUND",
            "confidence": 0.95
        }

    return {"value": "Not Found", "skills_list": [], "count": 0, "status": "NOT_FOUND", "confidence": 0.0}


def extract_resume_fields(text: str) -> Dict[str, Any]:
    """Extracts standard resume entities."""
    name = extract_candidate_name(text)
    email = extract_candidate_email(text)
    phone = extract_candidate_phone(text)
    skills = extract_candidate_skills(text)

    fields = {
        "name": name,
        "email": email,
        "phone": phone,
        "skills": skills
    }
    missing = [k for k, v in fields.items() if v["status"] == "NOT_FOUND" and k in ["name", "email", "skills"]]
    completeness = round(((3 - len(missing)) / 3) * 100, 1)

    return {
        "document_type": "Resume",
        "fields": fields,
        "flat_values": {k: v["value"] for k, v in fields.items()},
        "missing_fields": missing,
        "completeness_score": f"{completeness}%"
    }


# ==============================================================================
# CONTRACT & OTHER DOCUMENT EXTRACTION
# ==============================================================================

def extract_contract_fields(text: str) -> Dict[str, Any]:
    """Extracts contract terms, parties, and effective dates."""
    title_m = re.search(r"(?im)^\s*([A-Za-z\s]{4,40}(?:AGREEMENT|CONTRACT|MEMORANDUM))\s*$", text)
    title = title_m.group(1).strip() if title_m else "Service Agreement"

    date_m = re.search(r"(?i)(?:effective\s*date|dated|date)\s*[:\-]?\s*([0-9]{1,4}[-/.][0-9]{1,2}[-/.][0-9]{1,4}|[A-Za-z]{3,9}\s+[0-9]{1,2},?\s+[0-9]{4})", text)
    eff_date = date_m.group(1).strip() if date_m else "Not Found"

    gov_m = re.search(r"(?i)(?:governed\s*by\s*the\s*laws\s*of|jurisdiction\s*of)\s*([A-Za-z\s,]{3,30})", text)
    gov_law = gov_m.group(1).strip() if gov_m else "Not Specified"

    fields = {
        "contract_title": {"value": title, "status": "FOUND" if title else "NOT_FOUND", "confidence": 0.85},
        "effective_date": {"value": eff_date, "status": "FOUND" if eff_date != "Not Found" else "NOT_FOUND", "confidence": 0.88},
        "governing_law": {"value": gov_law, "status": "FOUND" if gov_law != "Not Specified" else "NOT_FOUND", "confidence": 0.80}
    }

    return {
        "document_type": "Contract",
        "fields": fields,
        "flat_values": {k: v["value"] for k, v in fields.items()},
        "missing_fields": [k for k, v in fields.items() if v["status"] == "NOT_FOUND"],
        "completeness_score": "90%"
    }


def extract_other_fields(text: str) -> Dict[str, Any]:
    """Extracts general document entities."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    doc_title = lines[0][:60] if lines else "General Document"
    
    date_m = re.search(r"\b(20[2-3][0-9]-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01]))\b", text)
    found_date = date_m.group(1) if date_m else "Not Found"

    subj_m = re.search(r"(?im)^\s*(?:subject|re|regarding|topic)\s*[:\-]\s*([^\n]{3,80})", text)
    subject = subj_m.group(1).strip() if subj_m else "General Correspondence"

    fields = {
        "document_title": {"value": doc_title, "status": "FOUND", "confidence": 0.70},
        "date": {"value": found_date, "status": "FOUND" if found_date != "Not Found" else "NOT_FOUND", "confidence": 0.80},
        "subject": {"value": subject, "status": "FOUND", "confidence": 0.75}
    }

    return {
        "document_type": "Other",
        "fields": fields,
        "flat_values": {k: v["value"] for k, v in fields.items()},
        "missing_fields": [],
        "completeness_score": "100%"
    }


def extract_document_information(text: str, document_type: str) -> Dict[str, Any]:
    """Unified routing dispatcher for category extraction."""
    if document_type == "Invoice":
        return extract_invoice_fields(text)
    elif document_type == "Resume":
        return extract_resume_fields(text)
    elif document_type == "Contract":
        return extract_contract_fields(text)
    else:
        return extract_other_fields(text)
