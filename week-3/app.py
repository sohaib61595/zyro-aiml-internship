"""
ZYROO INTERNSHIP PROGRAM - WEEK 3
AI Document Intelligence & Workflow Platform
Task 02: Improve Document Understanding

Pipeline Flow:
Upload -> Read Text / Preprocessed OCR -> Clean & Normalize Text ->
ML Classification (TF-IDF + Linear SVM) -> Field Extraction -> Missing Field Audit -> Show Results
"""

import os
import io
import json
import time
from typing import Dict, Any, Tuple
from PIL import Image

import streamlit as st
import pandas as pd

# Core Week 3 Modules
from text_cleaner import clean_extracted_text, normalize_for_classification, validate_text_quality, get_cleaning_summary
from ocr_engine import is_tesseract_available, extract_document_text, preprocess_image_for_ocr
from model_trainer import classify_document, load_dataset, evaluate_models, build_candidate_models
from extractor import extract_document_information


# ==============================================================================
# 1. STREAMLIT CONFIGURATION & CUSTOM STYLES
# ==============================================================================

st.set_page_config(
    page_title="AI Document Intelligence | Zyroo Week 3",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Global Styling */
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #1E3A8A 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #4B5563;
        font-size: 1.05rem;
        margin-bottom: 1.2rem;
    }
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 0.8rem;
    }
    .badge-found {
        background-color: #DEF7EC;
        color: #03543F;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 600;
        border: 1px solid #BCF0DA;
    }
    .badge-missing {
        background-color: #FDE8E8;
        color: #9B1C1C;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 600;
        border: 1px solid #F8B4B4;
    }
    .confidence-badge {
        display: inline-block;
        font-size: 1.15rem;
        font-weight: 700;
        padding: 0.35rem 0.9rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
    }
    .type-invoice { background-color: #E0E7FF; color: #3730A3; border: 1px solid #C7D2FE; }
    .type-resume { background-color: #D1FAE5; color: #065F46; border: 1px solid #A7F3D0; }
    .type-other { background-color: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px 6px 0 0;
        padding: 10px 18px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


def safe_render_image(img_or_path, caption=None):
    """Safely renders an image across all Streamlit versions (local & cloud)."""
    try:
        if isinstance(img_or_path, str):
            if os.path.exists(img_or_path):
                img = Image.open(img_or_path)
                try:
                    st.image(img, caption=caption, use_container_width=True)
                except TypeError:
                    st.image(img, caption=caption)
        elif img_or_path is not None:
            try:
                st.image(img_or_path, caption=caption, use_container_width=True)
            except TypeError:
                st.image(img_or_path, caption=caption)
    except Exception:
        if caption:
            st.caption(f"[{caption}]")


# ==============================================================================
# 2. SIDEBAR CONFIGURATION & APP INFO
# ==============================================================================

with st.sidebar:
    st.image("https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/Python-Dark.svg", width=42)
    st.markdown("### **Zyroo AI/ML Internship**")
    st.markdown("*Improve Document Understanding*")
    st.divider()

    st.markdown("####  Pipeline Settings")
    enable_ocr_preproc = st.toggle("Enable OCR Preprocessing", value=True, help="Applies Grayscale, Resizing, Contrast Enhancement, Denoise & Otsu Binarization to scanned files.")
    min_char_threshold = st.slider("Min Text Length Warning", min_value=10, max_value=80, value=25)

    st.divider()
    st.markdown("####  System Diagnostics")
    tess_status = is_tesseract_available()
    if tess_status:
        st.success(" Tesseract-OCR Active", icon="🔍")
    else:
        st.warning(" Tesseract-OCR Not Detected", icon="⚠️")

    st.info(" **Model Active:**\nCalibrated Linear SVM + TF-IDF (1-2 N-Grams)")
    
    st.divider()
    st.caption("Official ZYROO Program ")


# ==============================================================================
# 3. TOP BANNER
# ==============================================================================

st.markdown('<div class="main-header">AI Document Intelligence & Understanding</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Week 3 Enhanced Pipeline: Advanced Preprocessing • Scanned OCR Binarization • Calibrated ML Classification • Missing-Field Resilience</div>', unsafe_allow_html=True)

# Tabs
tab_intelligence, tab_benchmark, tab_ocr_studio, tab_batch_audit = st.tabs([
    " Document Intelligence",
    " Model Benchmark & Confusion Matrix",
    " OCR Preprocessing Studio",
    " Batch Document Audit"
])


# ==============================================================================
# TAB 1: DOCUMENT INTELLIGENCE (MAIN WORKFLOW)
# ==============================================================================

with tab_intelligence:
    samples_dir = os.path.join(os.path.dirname(__file__), "samples")
    sample_options = ["-- None (Upload your own file) --"]
    if os.path.exists(samples_dir):
        sample_options += sorted(os.listdir(samples_dir))

    col_upload, col_sample = st.columns([3, 2])
    with col_upload:
        uploaded_file = st.file_uploader(
            "Upload Document (PDF, PNG, JPG, JPEG):",
            type=["pdf", "png", "jpg", "jpeg"],
            help="Select a local invoice, resume, or document."
        )
    with col_sample:
        selected_sample = st.selectbox(
            " Quick Test Samples (Preloaded):",
            options=sample_options,
            help="Quickly evaluate sample files without needing to browse local directories."
        )

    # Resolve document bytes & filename
    doc_bytes = None
    doc_filename = None

    if uploaded_file is not None:
        doc_bytes = uploaded_file.read()
        doc_filename = uploaded_file.name
    elif selected_sample != "-- None (Upload your own file) --":
        sample_path = os.path.join(samples_dir, selected_sample)
        if os.path.exists(sample_path):
            with open(sample_path, "rb") as f:
                doc_bytes = f.read()
            doc_filename = selected_sample

    if doc_bytes and doc_filename:
        st.divider()
        with st.spinner("Processing document through extraction, cleaning, ML classification, and entity extraction..."):
            t_start = time.time()
            
            # Step 1: Text Extraction (Digital or Preprocessed OCR)
            raw_text, extract_meta = extract_document_text(
                doc_bytes, doc_filename, apply_ocr_preprocessing=enable_ocr_preproc
            )
            
            # Step 2: Text Cleaning & Quality Validation
            cleaned_text = clean_extracted_text(raw_text)
            quality_info = validate_text_quality(cleaned_text, min_chars=min_char_threshold)
            cleaning_stats = get_cleaning_summary(raw_text, cleaned_text)

            # Step 3: ML Document Classification & Confidence Scoring
            cls_result = classify_document(cleaned_text)
            doc_type = cls_result["document_type"]
            confidence = cls_result["confidence"]
            conf_percentage = cls_result["confidence_percentage"]

            # Step 4: Information Extraction & Missing-Field Audit
            extraction_result = extract_document_information(cleaned_text, doc_type)
            elapsed = round(time.time() - t_start, 3)

        # Classification Header & Badges
        col_res1, col_res2, col_res3 = st.columns([2, 1, 1])
        with col_res1:
            type_class = "type-invoice" if doc_type == "Invoice" else ("type-resume" if doc_type == "Resume" else "type-other")
            st.markdown(f"""
            <div class="confidence-badge {type_class}">
                Document Type: {doc_type} &nbsp;|&nbsp; Confidence: {conf_percentage}
            </div>
            """, unsafe_allow_html=True)
            st.caption(f" **File:** `{doc_filename}` &nbsp;•&nbsp; ⚡ **Latency:** `{elapsed}s` &nbsp;•&nbsp; 🛠️ **Method:** `{extract_meta.get('method', 'N/A')}`")

        with col_res2:
            st.metric("Completeness Score", extraction_result.get("completeness_score", "100%"))

        with col_res3:
            missing_cnt = extraction_result.get("missing_count", 0)
            st.metric("Missing Fields", f"{missing_cnt} / {extraction_result.get('total_fields', 4)}")

        # Warning for short/unclear text if detected
        if quality_info["warning"]:
            st.warning(f" {quality_info['warning']}")

        # Primary Results Layout: Entity Extraction vs Text Comparison
        left_col, right_col = st.columns([1.1, 0.9])

        with left_col:
            st.markdown("###  Structured Entity Extraction")
            st.caption("Fields automatically extracted with regex heuristics & missing-field resilience.")

            fields_data = extraction_result.get("fields", {})
            table_rows = []

            for field_name, field_dict in fields_data.items():
                val = field_dict.get("value", "Not Found")
                status = field_dict.get("status", "NOT_FOUND")
                conf = field_dict.get("confidence", 0.0)
                display_name = field_name.replace("_", " ").title()

                badge_html = f'<span class="badge-found">FOUND</span>' if status == "FOUND" else f'<span class="badge-missing">NOT FOUND</span>'
                table_rows.append({
                    "Field": display_name,
                    "Result": val,
                    "Status": badge_html,
                    "Field Conf": f"{int(round(conf * 100))}%" if status == "FOUND" else "0%"
                })

            df_display = pd.DataFrame(table_rows)
            st.write(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)

            st.write("")
            # Probability Breakdown Chart
            st.markdown("####  Classification Probability Distribution")
            prob_dict = cls_result.get("probabilities", {})
            if prob_dict:
                prob_df = pd.DataFrame(list(prob_dict.items()), columns=["Category", "Probability"])
                st.bar_chart(prob_df.set_index("Category"), color="#2563EB", height=200)

            # JSON Export
            payload = {
                "filename": doc_filename,
                "document_type": doc_type,
                "confidence": confidence,
                "confidence_percentage": conf_percentage,
                "probabilities": prob_dict,
                "extraction_metadata": extract_meta,
                "fields": extraction_result.get("flat_values", {}),
                "missing_fields": extraction_result.get("missing_fields", []),
                "completeness_score": extraction_result.get("completeness_score", "0%")
            }
            json_str = json.dumps(payload, indent=2)
            st.download_button(
                label="📥 Download JSON Payload",
                data=json_str,
                file_name=f"{os.path.splitext(doc_filename)[0]}_intelligence.json",
                mime="application/json"
            )

        with right_col:
            st.markdown("### 🔍 Text Preprocessing & Cleaning Comparison")
            tab_clean, tab_raw, tab_stats = st.tabs(["✨ Cleaned Text", "📄 Raw Stream", "📊 Cleaning Diagnostics"])

            with tab_clean:
                st.text_area("Normalized Text (Used for ML & Extraction):", cleaned_text, height=360)

            with tab_raw:
                st.text_area("Original Uncleaned Parser Stream:", raw_text, height=360)

            with tab_stats:
                st.markdown("#### Cleaning Impact:")
                st.write(f"- **Raw Characters:** `{cleaning_stats['raw_characters']}`")
                st.write(f"- **Cleaned Characters:** `{cleaning_stats['cleaned_characters']}`")
                st.write(f"- **Whitespace / Artifacts Removed:** `{cleaning_stats['characters_removed']} ({cleaning_stats['reduction_percentage']})`")
                st.write(f"- **Lines Condensed:** `{cleaning_stats['raw_lines']} -> {cleaning_stats['cleaned_lines']}`")
                st.write(f"- **OCR Preprocessing Steps:** `{extract_meta.get('preprocessing', 'None')}`")

    else:
        st.info(" Upload a document or select a preloaded test sample from the dropdown above to begin.", icon="ℹ️")


# ==============================================================================
# TAB 2: MODEL BENCHMARK & EVALUATION
# ==============================================================================

with tab_benchmark:
    st.markdown("###  Classification Models Benchmark & Evaluation")
    st.markdown("Comparing **Rule-Based Baseline**, **Logistic Regression**, **Linear SVM (Calibrated)**, and **Multinomial Naive Bayes** on the curated balanced dataset.")

    # Display Metrics Table
    base_dir = os.path.dirname(__file__)
    benchmark_data = [
        {"Model": "Rule-Based Baseline", "Accuracy": 1.0000, "Precision": 1.0000, "Recall": 1.0000, "F1-Score": 1.0000, "CV 4-Fold Mean Acc": 1.0000},
        {"Model": "Logistic Regression", "Accuracy": 1.0000, "Precision": 1.0000, "Recall": 1.0000, "F1-Score": 1.0000, "CV 4-Fold Mean Acc": 0.9167},
        {"Model": "Linear SVM (Calibrated)", "Accuracy": 1.0000, "Precision": 1.0000, "Recall": 1.0000, "F1-Score": 1.0000, "CV 4-Fold Mean Acc": 0.9722},
        {"Model": "Multinomial Naive Bayes", "Accuracy": 0.8889, "Precision": 0.9167, "Recall": 0.8889, "F1-Score": 0.8857, "CV 4-Fold Mean Acc": 0.9167}
    ]
    st.dataframe(pd.DataFrame(benchmark_data), use_container_width=True)

    col_graph1, col_graph2 = st.columns(2)
    with col_graph1:
        metrics_chart = os.path.join(base_dir, "graphs", "model_metrics_barchart.png")
        if os.path.exists(metrics_chart):
            safe_render_image(metrics_chart, caption="Model Metrics Comparison Bar Chart")

    with col_graph2:
        tfidf_chart = os.path.join(base_dir, "graphs", "tfidf_top_features.png")
        if os.path.exists(tfidf_chart):
            safe_render_image(tfidf_chart, caption="Top TF-IDF Informative Features per Class")

    st.markdown("#### 🔍 Confusion Matrices Comparison")
    cm_chart = os.path.join(base_dir, "graphs", "confusion_matrices_comparison.png")
    if os.path.exists(cm_chart):
        safe_render_image(cm_chart, caption="Side-by-Side Confusion Matrices across all evaluated models")


# ==============================================================================
# TAB 3: OCR PREPROCESSING STUDIO
# ==============================================================================

with tab_ocr_studio:
    st.markdown("###  Scanned Document OCR Preprocessing Lab")
    st.markdown("Inspect how computer vision and image processing enhancements convert low-contrast, noisy scans into high-accuracy machine-readable text.")

    col_img_in, col_img_out = st.columns(2)
    
    scanned_sample_path = os.path.join(os.path.dirname(__file__), "samples", "invoice_scanned_receipt.png")
    demo_image = Image.open(scanned_sample_path) if os.path.exists(scanned_sample_path) else None

    with col_img_in:
        st.markdown("#### Original Document")
        if demo_image:
            safe_render_image(demo_image, caption="Raw Scanned Image")
            
    with col_img_out:
        st.markdown("#### Preprocessed for Tesseract OCR")
        if demo_image:
            proc_demo, proc_steps = preprocess_image_for_ocr(
                demo_image, to_grayscale=True, scale_factor=1.5, contrast_boost=1.8, binarize=True, denoise=True
            )
            safe_render_image(proc_demo, caption=f"Preprocessed (Otsu Binarized & Upscaled): {proc_steps}")

    if demo_image and is_tesseract_available():
        st.markdown("#### ⚡ OCR Recognition Comparison")
        c1, c2 = st.columns(2)
        with c1:
            raw_ocr, _ = extract_document_text(open(scanned_sample_path, "rb").read(), "invoice_scanned_receipt.png", apply_ocr_preprocessing=False)
            st.text_area("Without Preprocessing (Raw Scan OCR):", raw_ocr, height=200)
        with c2:
            proc_ocr, _ = extract_document_text(open(scanned_sample_path, "rb").read(), "invoice_scanned_receipt.png", apply_ocr_preprocessing=True)
            st.text_area("With Preprocessing (Binarized + Denoised OCR):", proc_ocr, height=200)


# ==============================================================================
# TAB 4: BATCH DOCUMENT AUDIT
# ==============================================================================

with tab_batch_audit:
    st.markdown("### Batch Test & Missing-Field Audit")
    st.markdown("Run the complete Week 3 pipeline across all sample documents at once to evaluate classification accuracy, extraction completeness, and missing-field resilience.")

    if st.button(" Run Full Batch Audit Now", type="primary"):
        samples_dir = os.path.join(os.path.dirname(__file__), "samples")
        files = sorted(os.listdir(samples_dir))
        
        results = []
        progress_bar = st.progress(0)

        for idx, fname in enumerate(files):
            fpath = os.path.join(samples_dir, fname)
            if not os.path.isfile(fpath):
                continue
            with open(fpath, "rb") as f:
                b = f.read()

            raw_txt, meta = extract_document_text(b, fname)
            cl_txt = clean_extracted_text(raw_txt)
            cls_out = classify_document(cl_txt)
            doc_t = cls_out["document_type"]
            conf = cls_out["confidence_percentage"]

            ext_out = extract_document_information(cl_txt, doc_t)
            missing = ", ".join(ext_out.get("missing_fields", [])) or "None"
            completeness = ext_out.get("completeness_score", "100%")

            results.append({
                "Document Name": fname,
                "Predicted Type": doc_t,
                "Confidence": conf,
                "Missing Fields": missing,
                "Completeness": completeness,
                "OCR Engine": "Yes" if meta.get("ocr_used") else "Native"
            })
            progress_bar.progress((idx + 1) / len(files))

        st.success(f"Audit completed across {len(results)} sample documents!")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
