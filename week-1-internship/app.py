"""
ZYROO INTERNSHIP PROGRAM - WEEK 1
AI Document Intelligence & Workflow Platform (MVP)
Task 01: Build a Simple Document Intelligence MVP

Flow: Upload -> Read Text (PyMuPDF / OCR) -> Identify Type -> Extract Information -> Show Result
"""

import os
import io
import re
import json
import shutil
from typing import Tuple, Dict, Any, List, Optional
try:
    import streamlit as st
except ImportError:
    st = None
from PIL import Image

# Machine Learning for Document Classification
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

# Optional PyMuPDF (fitz)
try:
    import fitz
except ImportError:
    fitz = None

# Optional OCR (pytesseract)
try:
    import pytesseract
    # Autodetect common Windows Tesseract executable paths
    tesseract_candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    if not shutil.which("tesseract"):
        for cand in tesseract_candidates:
            if os.path.exists(cand):
                pytesseract.pytesseract.tesseract_cmd = cand
                break
except ImportError:
    pytesseract = None


# ==============================================================================
# 1. TEXT EXTRACTION (PyMuPDF + OCR Engine)
# ==============================================================================

def is_tesseract_available() -> bool:
    """Check if pytesseract and Tesseract OCR engine are installed and working."""
    if pytesseract is None:
        return False
    try:
        tesseract_candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        ]
        if not shutil.which("tesseract"):
            for cand in tesseract_candidates:
                if os.path.exists(cand):
                    pytesseract.pytesseract.tesseract_cmd = cand
                    break
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False



def extract_text_from_pdf_fallback(pdf_bytes: bytes) -> str:
    """Fallback text extractor if PyMuPDF wheel is still compiling or unavailable."""
    try:
        # Simple stream decoding for uncompressed text in standard PDFs
        raw = pdf_bytes.decode("latin1", errors="ignore")
        # Extract text within BT ... ET blocks
        matches = re.findall(r"BT\s*(.*?)\s*ET", raw, re.DOTALL)
        if matches:
            extracted_lines = []
            for block in matches:
                # Capture text inside ( ... ) Tj
                tj_matches = re.findall(r"\((.*?)\)\s*Tj", block)
                if tj_matches:
                    extracted_lines.extend(tj_matches)
            if extracted_lines:
                return "\n".join(extracted_lines)
    except Exception:
        pass
    return ""


def extract_document_text(file_bytes: bytes, filename: str) -> Tuple[str, Dict[str, Any]]:
    """
    Extracts text from PDF (using PyMuPDF) or Image (using OCR / fallback).
    """
    ext = os.path.splitext(filename)[1].lower()

    # --- PDF Processing ---
    if ext == ".pdf":
        if fitz is not None:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            num_pages = len(doc)
            page_texts = [doc[p].get_text("text").strip() for p in range(num_pages) if doc[p].get_text("text").strip()]
            combined_text = "\n\n".join(page_texts).strip()

            if len(combined_text) >= 20:
                return combined_text, {
                    "method": "PyMuPDF (Native Text)",
                    "pages": num_pages,
                    "word_count": len(combined_text.split()),
                    "ocr_used": False
                }

            # If PDF contains scanned pages with minimal native text, attempt OCR
            if is_tesseract_available():
                ocr_texts = []
                for p in range(num_pages):
                    pix = doc[p].get_pixmap(dpi=200)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    try:
                        t = pytesseract.image_to_string(img).strip()
                        if t:
                            ocr_texts.append(t)
                    except Exception:
                        pass
                if ocr_texts:
                    return "\n\n".join(ocr_texts), {
                        "method": "PyMuPDF + Tesseract OCR",
                        "pages": num_pages,
                        "word_count": len("\n\n".join(ocr_texts).split()),
                        "ocr_used": True
                    }

        # Fallback pure-python parser
        fallback_text = extract_text_from_pdf_fallback(file_bytes)
        if fallback_text:
            return fallback_text, {
                "method": "PDF Stream Parser (Native)",
                "pages": 1,
                "word_count": len(fallback_text.split()),
                "ocr_used": False
            }

        return "[Notice: No selectable text could be extracted from this PDF.]", {
            "method": "Extraction Failed",
            "pages": 0,
            "word_count": 0,
            "ocr_used": False
        }

    # --- Image Processing (PNG, JPG, JPEG) ---
    elif ext in [".png", ".jpg", ".jpeg"]:
        img = Image.open(io.BytesIO(file_bytes))
        w, h = img.size

        if is_tesseract_available():
            try:
                ocr_text = pytesseract.image_to_string(img).strip()
                if ocr_text:
                    return ocr_text, {
                        "method": "Tesseract OCR",
                        "dimensions": f"{w}x{h}",
                        "word_count": len(ocr_text.split()),
                        "ocr_used": True
                    }
            except Exception as e:
                return f"[OCR Error: {e}]", {"method": "OCR Error", "ocr_used": True}

        # If OCR binary is not installed on system, inform gracefully
        return f"[Notice: Image '{filename}' uploaded ({w}x{h}px). Install Tesseract-OCR binary to enable OCR for scanned images.]", {
            "method": "OCR Unavailable",
            "dimensions": f"{w}x{h}",
            "word_count": 0,
            "ocr_used": False
        }

    else:
        raise ValueError(f"Unsupported file format '{ext}'. Allowed: PDF, PNG, JPG, JPEG.")


# ==============================================================================
# 2. DOCUMENT CLASSIFICATION (Rule-based + TF-IDF Machine Learning)
# ==============================================================================

INVOICE_KEYWORDS = [
    "invoice", "bill to", "billed to", "invoice number", "inv#", "inv no",
    "subtotal", "total amount", "amount due", "balance due", "tax", "gst",
    "unit price", "quantity", "qty", "due date", "pkr", "usd"
]

RESUME_KEYWORDS = [
    "resume", "curriculum vitae", "cv", "education", "experience", "work experience",
    "skills", "technical skills", "projects", "certifications", "bachelor",
    "master", "university", "gpa", "internship", "employment", "summary"
]

_TRAINING_CORPUS = [
    ("Tax Invoice Invoice Number INV-1002 Date 02/09/2026 Bill To Total Amount Due Subtotal PKR USD", "Invoice"),
    ("Commercial Invoice Quantity Unit Price Total Tax VAT Amount Due Bank Details Payment Terms", "Invoice"),
    ("Billing Statement Invoice #98765 Due Date Description Charges Balance Total Amount Payable", "Invoice"),
    ("Sales Receipt Invoice No 4523 Client Customer Subtotal Discount Grand Total Paid", "Invoice"),
    ("John Doe Resume Professional Summary Education Bachelor of Science Experience Software Engineer Skills Python SQL", "Resume"),
    ("Curriculum Vitae Work Experience Full Stack Developer Skills React Node Django Education University Certifications", "Resume"),
    ("Resume Summary Employment History Project Lead Education Masters Computer Science Technical Skills Machine Learning", "Resume"),
    ("Software Engineer CV Skills Java C++ Git Docker Experience Data Analyst University Degree Projects", "Resume"),
    ("General document meeting notes agenda summary discussion action items announcement", "Other")
]

# Train lightweight TF-IDF classifier for instant ML cross-validation
_texts, _labels = zip(*_TRAINING_CORPUS)
_ml_pipeline = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), lowercase=True)),
    ("clf", LogisticRegression(C=1.0, max_iter=200))
])
_ml_pipeline.fit(_texts, _labels)


def classify_document(text: str) -> Dict[str, Any]:
    """
    Step 3: Classify document as Invoice, Resume, or Other using rules & TF-IDF model.
    """
    text_lower = text.lower()
    
    matched_inv = [kw for kw in INVOICE_KEYWORDS if kw in text_lower]
    matched_res = [kw for kw in RESUME_KEYWORDS if kw in text_lower]

    inv_score = sum(text_lower.count(kw) for kw in matched_inv)
    res_score = sum(text_lower.count(kw) for kw in matched_res)

    if any(k in text_lower for k in ["invoice", "inv-", "inv #", "bill to", "amount due"]):
        inv_score += 4
    if any(k in text_lower for k in ["resume", "curriculum vitae", "skills", "education"]):
        res_score += 4

    total = inv_score + res_score
    if total < 2:
        rule_type, conf = "Other", 0.40
    elif inv_score > res_score:
        rule_type, conf = "Invoice", min(0.99, 0.55 + (inv_score / (total + 2)) * 0.45)
    elif res_score > inv_score:
        rule_type, conf = "Resume", min(0.99, 0.55 + (res_score / (total + 2)) * 0.45)
    else:
        rule_type, conf = "Other", 0.50

    # ML fallback/validation
    try:
        ml_pred = _ml_pipeline.predict([text])[0]
    except Exception:
        ml_pred = rule_type

    final_type = rule_type if rule_type != "Other" else ml_pred

    return {
        "document_type": final_type,
        "confidence": round(conf, 2),
        "matched_keywords": (matched_inv if final_type == "Invoice" else matched_res)[:6],
        "scores": {"Invoice": inv_score, "Resume": res_score},
        "ml_model_prediction": ml_pred
    }


# ==============================================================================
# 3. FIELD INFORMATION EXTRACTION (Regex & Heuristics)
# ==============================================================================

POPULAR_SKILLS = [
    "Python", "SQL", "C++", "JavaScript", "Java", "TypeScript", "React", "Next.js",
    "Node.js", "Django", "FastAPI", "Flask", "Machine Learning", "Deep Learning",
    "NLP", "PyTorch", "TensorFlow", "Scikit-Learn", "Pandas", "NumPy", "OpenCV",
    "Git", "Docker", "AWS", "Azure", "Linux", "Data Analysis", "Communication"
]

def extract_invoice_fields(text: str) -> Dict[str, str]:
    """Extracts: Invoice Number, Date, Company Name, Total Amount."""
    fields = {
        "invoice_number": "Not found",
        "date": "Not found",
        "company_name": "Not found",
        "total_amount": "Not found"
    }

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # 1. Invoice Number
    inv_patterns = [
        r"(?i)(?:invoice\s*(?:no|number|#)|inv[\s#:\.\-]+|bill\s*(?:no|#))[:\s#]*([A-Z0-9\-_/]{3,20})",
        r"(?i)\b(INV-[A-Z0-9\-_]+)\b",
        r"(?i)invoice\s*id[:\s#]*([A-Z0-9\-_/]{3,20})",
        r"(?i)^#\s*([0-9]{3,15})$"
    ]
    for pattern in inv_patterns:
        m = re.search(pattern, text, re.MULTILINE)
        if m:
            val = m.group(1).strip()
            if val.lower() not in ["date", "total", "amount", "pkr", "usd", "invoice"]:
                fields["invoice_number"] = val
                break

    # 2. Date
    date_patterns = [
        r"(?i)(?:date|dated|invoice\s*date)[:\s]*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2})",
        r"(?i)(?:date|dated|invoice\s*date)[:\s]*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+[0-9]{1,2},?\s+[0-9]{2,4})",
        r"\b([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{4})\b",
        r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+[0-9]{1,2},?\s+[0-9]{4})\b",
        r"\b([0-9]{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*,?\s+[0-9]{4})\b",
    ]
    for pattern in date_patterns:
        m = re.search(pattern, text)
        if m:
            fields["date"] = m.group(1).strip()
            break

    # 3. Total Amount
    # Case A: Standard inline total (e.g. Total: $1,234.56)
    m = re.search(r"(?i)(?:grand\s*total|total\s*amount|balance\s*due|amount\s*due|total)[:\s]*([A-Z]{3}|\$|€|£|PKR)?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2}))", text)
    if m and m.group(2):
        curr = m.group(1) or ""
        if not curr:
            curr_match = re.search(r"\b(PKR|USD|EUR|GBP|INR|Rs\.?|\$)\b", text, re.IGNORECASE)
            if curr_match:
                curr = curr_match.group(1).upper()
        fields["total_amount"] = f"{curr} {m.group(2)}".strip()
    else:
        # Case B: Column/Transposed layout where currency amounts precede summary labels
        for i, line in enumerate(lines):
            if line.lower().strip() in ["total:", "total", "balance due:", "balance due"]:
                candidates = []
                for prev in lines[max(0, i - 6):i]:
                    amt_m = re.search(r"([$€£PKRUSD\s]*[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2}))", prev)
                    if amt_m:
                        candidates.append(amt_m.group(1).strip())
                if candidates:
                    fields["total_amount"] = candidates[-1]
                    break

    # 4. Company Name
    m = re.search(r"(?i)(?:company(?:\s*name)?|from|vendor|billed\s*by)[:\s]*([A-Za-z0-9\s&,\.\-]{3,35})", text)
    if m and m.group(1).strip().lower() not in ["invoice", "tax invoice"]:
        fields["company_name"] = m.group(1).strip().splitlines()[0].strip()
    else:
        # Check top lines of the document
        for line in lines[:5]:
            line_clean = line.strip()
            line_lower = line_clean.lower()
            if any(k in line_lower for k in ["invoice", "commercial", "date", "#", "bill to", "ship to"]):
                continue
            if 2 <= len(line_clean) <= 40:
                fields["company_name"] = line_clean
                break

    return fields




def extract_resume_fields(text: str) -> Dict[str, Any]:
    """Extracts: Name, Email, Phone, Skills."""
    fields = {
        "name": "Not found",
        "email": "Not found",
        "phone": "Not found",
        "skills": []
    }

    # Email
    m_email = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", text)
    if m_email:
        fields["email"] = m_email.group(1).strip()

    # Phone
    m_phone = re.search(r"((?:\+?92[-.\s]?)?0?3[0-9]{2}[-.\s]?[0-9]{7}|\+?[1-9]\d{0,2}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}|\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", text)
    if m_phone:
        fields["phone"] = m_phone.group(1).strip()

    # Candidate Name
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    m_name = re.search(r"(?i)(?:name|candidate\s*name)[:\s]*([A-Z][a-zA-Z\s\.]{2,30})", text)
    if m_name:
        fields["name"] = m_name.group(1).strip()
    elif lines:
        for line in lines[:3]:
            if not any(k in line.lower() for k in ["resume", "cv", "email", "@", "curriculum", "phone", "+"]):
                fields["name"] = line
                break

    # Skills
    detected_skills = set()
    text_lower = text.lower()
    for skill in POPULAR_SKILLS:
        if re.search(r"\b" + re.escape(skill.lower()) + r"\b", text_lower):
            detected_skills.add(skill)

    fields["skills"] = sorted(list(detected_skills))
    return fields


def extract_information(text: str, doc_type: str) -> Dict[str, Any]:
    if doc_type == "Invoice":
        return extract_invoice_fields(text)
    elif doc_type == "Resume":
        return extract_resume_fields(text)
    else:
        return {"notice": "Document type is 'Other'. Standard entity templates apply to Invoices and Resumes."}


# ==============================================================================
# 4. STREAMLIT APPLICATION INTERFACE
# ==============================================================================

def main():
    if st is None:
        print("Streamlit is not yet installed. Please run: pip install -r requirements.txt")
        return

    st.set_page_config(
        page_title="AI Document Intelligence MVP | Zyroo Week 1",
        page_icon="📄",
        layout="wide"
    )

    # Custom Styling
    st.markdown("""
    <style>
        .main-title {
            font-size: 2.1rem;
            font-weight: 800;
            color: #1E3A8A;
            margin-bottom: 0.2rem;
        }
        .sub-title {
            color: #4B5563;
            font-size: 1rem;
            margin-bottom: 1.5rem;
        }
        .card {
            background-color: #FFFFFF;
            border-radius: 10px;
            padding: 1.1rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border: 1px solid #E5E7EB;
            margin-bottom: 0.8rem;
        }
        .metric-label {
            font-size: 0.82rem;
            color: #6B7280;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 600;
        }
        .metric-value {
            font-size: 1.25rem;
            font-weight: 700;
            color: #111827;
            margin-top: 4px;
        }
        .badge-invoice {
            background-color: #DBEAFE;
            color: #1E40AF;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.9rem;
        }
        .badge-resume {
            background-color: #D1FAE5;
            color: #065F46;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.9rem;
        }
        .badge-other {
            background-color: #F3F4F6;
            color: #374151;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.9rem;
        }
        .skill-chip {
            background-color: #EEF2FF;
            color: #4338CA;
            padding: 3px 10px;
            border-radius: 14px;
            font-size: 0.85rem;
            font-weight: 600;
            display: inline-block;
            margin: 3px;
            border: 1px solid #C7D2FE;
        }
    </style>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:

        st.markdown("### 🏢 Zyroo Internship")
        st.markdown("**AI/ML Internship • Week 1**  \n**Task 01**: AI Document Intelligence MVP")
        st.divider()

        st.markdown("### ⚡ Quick Test Samples")
        samples_dir = os.path.join(os.path.dirname(__file__), "samples")
        samples = []
        if os.path.exists(samples_dir):
            samples = [f for f in os.listdir(samples_dir) if f.endswith((".pdf", ".png", ".jpg"))]

        selected_sample = st.selectbox("Select a pre-built sample document:", ["None"] + samples) if samples else None

        st.divider()
        st.markdown("### ⚙️ OCR Engine Status")
        if is_tesseract_available():
            st.success("Tesseract OCR: Active ✅")
        else:
            st.info("Tesseract OCR: Not installed (PyMuPDF active for native PDFs) ℹ️")

    # Header
    st.markdown('<div class="main-title">📄 AI Document Intelligence MVP</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Upload &rarr; Read Text &rarr; Identify Type &rarr; Extract Fields &rarr; Show Result</div>', unsafe_allow_html=True)

    # Upload Section
    c_up, c_meta = st.columns([2, 1])
    with c_up:
        uploaded_file = st.file_uploader(
            "Upload a document (PDF, PNG, JPG, JPEG):",
            type=["pdf", "png", "jpg", "jpeg"]
        )

    file_bytes = None
    filename = None
    file_type = None

    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        filename = uploaded_file.name
        file_type = uploaded_file.type or filename.split(".")[-1].upper()
    elif selected_sample and selected_sample != "None":
        s_path = os.path.join(samples_dir, selected_sample)
        with open(s_path, "rb") as f:
            file_bytes = f.read()
        filename = selected_sample
        file_type = filename.split(".")[-1].upper()
        st.info(f"Loaded sample: **{filename}**")

    with c_meta:
        st.markdown("### 📋 Upload Info")
        if filename:
            st.write(f"**Filename:** `{filename}`")
            st.write(f"**Type:** `{file_type}`")
            st.write(f"**Size:** `{len(file_bytes)/1024:.1f} KB`")
        else:
            st.caption("Upload a file or choose a sample from the sidebar.")

    if file_bytes is None:
        st.divider()
        st.info("👋 Upload an invoice or resume to begin extraction.")
        st.stop()

    st.divider()

    # Pipeline Processing
    with st.spinner("Processing document intelligence..."):
        try:
            # 1. Read Text
            raw_text, extract_meta = extract_document_text(file_bytes, filename)

            # 2. Identify Type
            classification = classify_document(raw_text)
            doc_type = classification["document_type"]
            confidence = classification["confidence"]

            # 3. Extract Simple Information
            fields = extract_information(raw_text, doc_type)

        except Exception as e:
            st.error(f"Error processing document: {e}")
            st.stop()

    # Results Display
    st.markdown("## 📊 Document Intelligence Results")

    # Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        if doc_type == "Invoice":
            b_html = '<span class="badge-invoice">INVOICE</span>'
        elif doc_type == "Resume":
            b_html = '<span class="badge-resume">RESUME</span>'
        else:
            b_html = '<span class="badge-other">OTHER</span>'
        st.markdown(f'<div class="metric-label">Document Type</div><div>{b_html}</div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-label">Confidence</div><div class="metric-value">{int(confidence*100)}%</div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-label">Method</div><div class="metric-value" style="font-size:1rem;">{extract_meta.get("method", "Standard")}</div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="metric-label">Word Count</div><div class="metric-value">{extract_meta.get("word_count", len(raw_text.split()))} words</div>', unsafe_allow_html=True)

    st.write("")

    # Split View: Extracted Entities & Raw Text / Preview
    col_fields, col_preview = st.columns([1.2, 1])

    with col_fields:
        st.markdown("### 🎯 Extracted Fields")
        if doc_type == "Invoice":
            ic1, ic2 = st.columns(2)
            with ic1:
                st.markdown(f"""
                <div class="card">
                    <div class="metric-label">Invoice Number</div>
                    <div class="metric-value" style="color:#2563EB;">{fields.get('invoice_number', 'Not found')}</div>
                </div>
                <div class="card">
                    <div class="metric-label">Company Name</div>
                    <div class="metric-value">{fields.get('company_name', 'Not found')}</div>
                </div>
                """, unsafe_allow_html=True)
            with ic2:
                st.markdown(f"""
                <div class="card">
                    <div class="metric-label">Invoice Date</div>
                    <div class="metric-value">{fields.get('date', 'Not found')}</div>
                </div>
                <div class="card">
                    <div class="metric-label">Total Amount</div>
                    <div class="metric-value" style="color:#059669;">{fields.get('total_amount', 'Not found')}</div>
                </div>
                """, unsafe_allow_html=True)

        elif doc_type == "Resume":
            st.markdown(f"""
            <div class="card">
                <div class="metric-label">Candidate Name</div>
                <div class="metric-value" style="color:#1E40AF;">{fields.get('name', 'Not found')}</div>
            </div>
            """, unsafe_allow_html=True)

            rc1, rc2 = st.columns(2)
            with rc1:
                st.markdown(f"""
                <div class="card">
                    <div class="metric-label">Email</div>
                    <div class="metric-value" style="font-size:1.05rem;">{fields.get('email', 'Not found')}</div>
                </div>
                """, unsafe_allow_html=True)
            with rc2:
                st.markdown(f"""
                <div class="card">
                    <div class="metric-label">Phone</div>
                    <div class="metric-value" style="font-size:1.05rem;">{fields.get('phone', 'Not found')}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown('<div class="card"><div class="metric-label" style="margin-bottom:8px;">Skills</div>', unsafe_allow_html=True)
            skills = fields.get("skills", [])
            if skills:
                chips = "".join([f'<span class="skill-chip">{s}</span>' for s in skills])
                st.markdown(chips, unsafe_allow_html=True)
            else:
                st.write("No predefined skills detected.")
            st.markdown('</div>', unsafe_allow_html=True)

        else:
            st.warning("Document classified as 'Other'. Specific key fields are supported for Invoices and Resumes.")

        # Download JSON
        result_json = {
            "filename": filename,
            "document_type": doc_type,
            "confidence": confidence,
            "extracted_fields": fields,
            "metadata": extract_meta
        }
        st.write("")
        st.download_button(
            "📥 Download Result as JSON",
            data=json.dumps(result_json, indent=2),
            file_name=f"result_{filename}.json",
            mime="application/json",
            use_container_width=True
        )

    with col_preview:
        st.markdown("### 📜 Extracted Text & Preview")
        tab_raw, tab_view = st.tabs(["Extracted Text", "Document Preview"])
        with tab_raw:
            st.text_area("Raw Text Output", raw_text, height=360)
        with tab_view:
            ext = os.path.splitext(filename)[1].lower()
            if ext in [".png", ".jpg", ".jpeg"]:
                st.image(Image.open(io.BytesIO(file_bytes)), caption=filename, use_container_width=True)
            elif ext == ".pdf" and fitz is not None:
                try:
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    if len(doc) > 0:
                        pix = doc[0].get_pixmap(dpi=150)
                        st.image(Image.open(io.BytesIO(pix.tobytes("png"))), caption=f"{filename} (Page 1)", use_container_width=True)
                except Exception:
                    st.caption("PDF preview unavailable.")
            else:
                st.caption("Preview not available for this document.")


if __name__ == "__main__":
    main()
