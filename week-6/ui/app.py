"""
ZYROO INTERNSHIP PROGRAM - WEEK 6
Module: Streamlit Web Interface - AI Document Intelligence & Workflow Studio
Focus: Enterprise integration, glassmorphic design, RAG assistant, review queue, and analytics
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

import streamlit as st
import pandas as pd

# Ensure week 6 src modules are discoverable
_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.abspath(os.path.join(_current_dir, "..", "src"))
for d in [_current_dir, _src_dir]:
    if d not in sys.path:
        sys.path.insert(0, d)

import config
import database
import storage
import processor
import classifier
import extractor
import validator
import anomaly
import rag_engine
import workflow
import audit

# ==============================================================================
# STREAMLIT PAGE CONFIGURATION & CUSTOM STYLES
# ==============================================================================
st.set_page_config(
    page_title="ZYROO | AI Document Intelligence & Workflow Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database schema and directories on boot
database.init_db()
storage.ensure_storage_structure()

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background: radial-gradient(circle at top right, #111827 0%, #080c14 100%);
        color: #f3f4f6;
    }
    
    /* Hero Header */
    .hero-container {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.95) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px 32px;
        margin-bottom: 24px;
        backdrop-filter: blur(14px);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
    }
    
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 6px;
    }
    
    .hero-subtitle {
        color: #94a3b8;
        font-size: 0.95rem;
    }
    
    /* Metrics Card */
    .metric-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 16px 20px;
        text-align: center;
        backdrop-filter: blur(8px);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(99, 102, 241, 0.5);
    }
    .metric-num {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f8fafc;
        margin-top: 4px;
    }
    .metric-label {
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
    }
    
    /* Status Badges */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    .badge-completed { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); }
    .badge-approved { background: rgba(5, 150, 105, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-review { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.3); }
    .badge-rejected { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(248, 113, 113, 0.3); }
    .badge-processing { background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(129, 140, 248, 0.3); }
    .badge-anomaly { background: rgba(225, 29, 72, 0.15); color: #fb7185; border: 1px solid rgba(251, 113, 133, 0.3); }
    
    /* Citation Box */
    .citation-box {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 8px;
        padding: 12px 16px;
        margin-top: 10px;
        font-size: 0.88rem;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ==============================================================================
# SIDEBAR CONTROLS & USER CONTEXT
# ==============================================================================
with st.sidebar:
    st.image("https://img.shields.io/badge/ZYROO-Platform%20v6.0-6366f1?style=for-the-badge", use_container_width=True)
    st.markdown("### ⚙️ Operational Settings")
    
    user_role = st.selectbox(
        "User Access Role (RBAC)",
        options=config.VALID_ROLES,
        index=0,
        help="Admin & Reviewer can approve/reject. Viewer has read-only privileges."
    )
    user_name = st.text_input("Reviewer Name / ID", value="Sohaib (Lead AI Intern)")
    
    st.markdown("---")
    st.markdown("### 🛡️ System Guardrails")
    st.write(f"**Confidence Threshold:** `{config.CLASSIFIER_CONFIDENCE_THRESHOLD * 100:.0f}%`")
    st.write(f"**High-Value Threshold:** `${config.HIGH_VALUE_INVOICE_THRESHOLD:,.0f}`")
    st.write(f"**Max File Size:** `{config.MAX_UPLOAD_SIZE_BYTES / (1024*1024):.0f} MB`")
    
    st.markdown("---")
    st.markdown("### 📦 Quick Sample Actions")
    if st.button("🔄 Reload Repository Metrics", use_container_width=True):
        st.rerun()


# ==============================================================================
# HERO HEADER
# ==============================================================================
st.markdown("""
<div class="hero-container">
    <div class="hero-title">⚡ ZYROO AI Document Intelligence & Workflow Platform</div>
    <div class="hero-subtitle">
        Enterprise Document Extraction • Mathematical Verification • Calibrated ML Classification • RAG Assistant • Human Review Queue • Immutable Auditing
    </div>
</div>
""", unsafe_allow_html=True)


# ==============================================================================
# NAVIGATION TABS
# ==============================================================================
tabs = st.tabs([
    "📥 Ingestion & Pipeline",
    "👥 Human Review Queue",
    "⚡ Batch Processing Studio",
    "🤖 AI Assistant & RAG",
    "🔍 Repository & Audit Explorer",
    "📊 Executive Analytics & Metrics"
])


# ==============================================================================
# TAB 1: INGESTION & PIPELINE
# ==============================================================================
with tabs[0]:
    st.markdown("### 📥 Document Ingestion & Complete Intelligence Pipeline")
    st.caption("Upload digital PDFs, scanned receipts, contracts, or candidate CVs to trigger automated processing.")

    col_up, col_opts = st.columns([2, 1])
    with col_up:
        uploaded_file = st.file_uploader(
            "Choose a document to ingest",
            type=["pdf", "png", "jpg", "jpeg", "tiff"],
            help="Supported: Clean PDFs, scanned receipts, resumes, invoices, agreements."
        )
    with col_opts:
        st.markdown("**Processing Options**")
        apply_ocr = st.checkbox("Enable Adaptive OCR Preprocessing (Otsu)", value=True)
        auto_index_rag = st.checkbox("Index text into RAG vector repository", value=True)

    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        filename = uploaded_file.name

        col_btn, _ = st.columns([1, 4])
        with col_btn:
            run_btn = st.button("🚀 Ingest & Process Document", type="primary", use_container_width=True)

        if run_btn:
            with st.status("Executing Document Intelligence Pipeline...", expanded=True) as status_box:
                st.write("1. Verifying file signature, magic bytes & path safety...")
                time.sleep(0.1)

                st.write("2. Computing cryptographic SHA-256 hash & checking duplicates...")
                time.sleep(0.1)

                st.write("3. Extracting digital text & executing OCR fallback...")
                t0 = time.perf_counter()
                res = workflow.ingest_and_execute_workflow(
                    file_bytes=file_bytes,
                    original_filename=filename,
                    apply_ocr_preprocessing=apply_ocr
                )
                t_total = round((time.perf_counter() - t0) * 1000, 1)

                if res.get("is_duplicate"):
                    status_box.update(label="Duplicate Document Identified!", state="complete")
                    st.warning(f"⚠️ {res['message']}")
                    st.json(res["document_record"])
                elif not res.get("success"):
                    status_box.update(label="Document Ingestion Failed!", state="error")
                    st.error(f"❌ {res['message']}")
                else:
                    status_box.update(label=f"Pipeline Completed Successfully in {res.get('processing_time_ms')}ms!", state="complete")
                    st.success(f"✅ Document #{res['document_id']} successfully processed → **{res['status']}**")

                    # Display Detailed Results
                    doc_rec = res["document_record"]
                    val_data = res["validation_result"]
                    anom_data = res["anomaly_result"]
                    decision = res["decision"]

                    # Top stats cards
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-label">Document Type</div>
                            <div class="metric-num" style="color: #38bdf8;">{res['document_type']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c2:
                        conf_val = f"{int(round(res['confidence']*100))}%" if res['confidence'] is not None else "N/A"
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-label">ML Confidence</div>
                            <div class="metric-num" style="color: #818cf8;">{conf_val}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c3:
                        status_color = "#34d399" if res['status'] == "Completed" else "#fbbf24"
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-label">Workflow Status</div>
                            <div class="metric-num" style="color: {status_color};">{res['status']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c4:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-label">Processing Time</div>
                            <div class="metric-num" style="color: #c084fc;">{res.get('processing_time_ms', 0)}ms</div>
                        </div>
                        """, unsafe_allow_html=True)

                    st.markdown("---")
                    
                    # Extracted Fields & Validation
                    col_fields, col_val = st.columns([1, 1])
                    with col_fields:
                        st.markdown("#### 📋 Extracted Entities")
                        ext_json = json.loads(doc_rec.get("extracted_json") or "{}")
                        flat_vals = ext_json.get("flat_values", {})
                        for k, v in flat_vals.items():
                            st.write(f"**{k.replace('_', ' ').title()}:** `{v}`")

                    with col_val:
                        st.markdown("#### 🛡️ Validation & Consistency Checks")
                        if val_data.get("is_valid"):
                            st.success("✅ All required fields and format checks passed.")
                        else:
                            st.error(f"❌ Validation Failed for: {', '.join(val_data.get('failed_fields', []))}")
                            for fld, err in val_data.get("field_errors", {}).items():
                                st.write(f"- ⚠️ **{fld}:** {err}")

                        # Anomalies
                        if anom_data.get("has_anomalies"):
                            st.markdown("#### 🚨 Anomaly Detection Alerts")
                            for a in anom_data.get("anomalies", []):
                                st.warning(f"**[{a.get('code')}]** {a.get('message')}")
                        else:
                            st.info("ℹ️ No anomalies or calculation mismatches detected.")

                    st.markdown("---")
                    with st.expander("📄 View Extracted Text Preview"):
                        st.text(doc_rec.get("text_preview", "No preview available."))

                    with st.expander("⏱️ View Stage Latency Breakdown (Profiling)"):
                        st.json(res.get("stage_timings", {}))


# ==============================================================================
# TAB 2: HUMAN REVIEW QUEUE
# ==============================================================================
with tabs[1]:
    st.markdown("### 👥 Human Review Queue")
    st.caption("Inspect documents requiring manual intervention, edit fields, and record approval/rejection decisions.")

    review_docs = database.search_documents(status_filter=workflow.STATE_NEEDS_REVIEW)
    if not review_docs:
        st.success("🎉 Review queue is empty! No documents currently require human review.")
    else:
        st.info(f"📋 **{len(review_docs)} document(s)** currently in 'Needs Review' queue.")
        
        doc_options = {f"Doc #{d['id']} - {d['original_filename']} ({d['document_type']})": d['id'] for d in review_docs}
        selected_label = st.selectbox("Select document to review", list(doc_options.keys()))
        selected_id = doc_options[selected_label]
        target_doc = database.get_document_by_id(selected_id)

        if target_doc:
            col_info, col_act = st.columns([2, 1])
            with col_info:
                st.markdown(f"#### 📄 Inspection: {target_doc['original_filename']}")
                st.write(f"**Reason for Review:** `{target_doc.get('review_reason')}`")
                st.write(f"**Document Type:** `{target_doc.get('document_type')}` | **Confidence:** `{target_doc.get('confidence')}`")
                
                # Check for anomalies
                try:
                    anom_json = json.loads(target_doc.get("anomaly_json") or "{}")
                    if anom_json.get("has_anomalies"):
                        st.markdown("**🚨 Detected Anomalies:**")
                        for a in anom_json.get("anomalies", []):
                            st.error(f"- {a.get('message')}")
                except Exception:
                    pass

                # Field In-Place Editor
                st.markdown("##### ✏️ Field Verification & Editor")
                with st.form(f"edit_form_{selected_id}"):
                    curr_company = st.text_input("Company / Name", value=target_doc.get("company", ""))
                    curr_inv = st.text_input("Invoice / ID", value=target_doc.get("invoice_number", ""))
                    curr_total = st.text_input("Total Amount / Date", value=target_doc.get("total_amount", ""))
                    
                    save_fields_btn = st.form_submit_button("💾 Update & Re-validate Fields")
                    if save_fields_btn:
                        up_dict = {
                            "company": curr_company,
                            "name": curr_company,
                            "invoice_number": curr_inv,
                            "email": curr_inv,
                            "total_amount": curr_total
                        }
                        ok, msg, _ = workflow.edit_document_fields(
                            doc_id=selected_id,
                            updated_fields=up_dict,
                            performed_by=f"{user_name} ({user_role})"
                        )
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

            with col_act:
                st.markdown("#### ⚖️ Review Decision Actions")
                st.write(f"**Acting as:** `{user_name}` (`{user_role}`)")
                
                if user_role == config.ROLE_VIEWER:
                    st.warning("🔒 Role 'Viewer' has read-only access. Switch role to Reviewer or Admin to take actions.")
                else:
                    # Approve Form
                    with st.expander("✅ Approve Document", expanded=True):
                        app_notes = st.text_area("Approval Notes (Optional)", value="Verified and accepted.", key="app_notes")
                        if st.button("Confirm Approval", type="primary", use_container_width=True):
                            ok, msg = workflow.approve_document(
                                doc_id=selected_id,
                                reviewer_notes=app_notes,
                                performed_by=user_name,
                                user_role=user_role
                            )
                            if ok:
                                st.success(msg)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(msg)

                    # Reject Form
                    with st.expander("❌ Reject Document"):
                        rej_reason = st.text_area("Rejection Justification (Mandatory)", value="", key="rej_notes")
                        if st.button("Confirm Rejection", use_container_width=True):
                            ok, msg = workflow.reject_document(
                                doc_id=selected_id,
                                rejection_reason=rej_reason,
                                performed_by=user_name,
                                user_role=user_role
                            )
                            if ok:
                                st.success(msg)
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(msg)

            with st.expander("📜 View Audit Trail for This Document"):
                history = audit.get_document_history(selected_id)
                for h in history:
                    st.write(f"• **{h['timestamp'][:19]}** | `{h['action']}`: {h['previous_status']} ➔ **{h['new_status']}** | *By: {h['performed_by']}* — {h['reason']}")


# ==============================================================================
# TAB 3: BATCH PROCESSING STUDIO
# ==============================================================================
with tabs[2]:
    st.markdown("### ⚡ Fault-Tolerant Batch Processing Studio")
    st.caption("Submit multiple files simultaneously. Individual document failures will not stop or crash the batch execution.")

    batch_mode = st.radio("Choose Batch Source", ["Upload Multiple Files", "Load Pre-Curated Test Document Suite (15 Files)"], horizontal=True)

    if batch_mode == "Upload Multiple Files":
        batch_files = st.file_uploader(
            "Upload multiple documents",
            type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True
        )
        if batch_files and st.button("🚀 Process Uploaded Batch", type="primary"):
            file_tuples = [(bf.name, bf.read()) for bf in batch_files]
            with st.spinner("Processing batch queue..."):
                summary = workflow.process_batch_files(file_tuples)
            st.success(f"Batch processed in {summary['total_time_ms']}ms!")
            st.json(summary)

    else:
        st.write("Ingest the complete 15-document evaluation suite from `samples/` directory.")
        if st.button("⚡ Ingest Full Curated Test Pack", type="primary"):
            sample_dir = config.SAMPLES_DIR
            if not os.path.exists(sample_dir):
                st.error("Samples directory not found.")
            else:
                files_found = [f for f in os.listdir(sample_dir) if os.path.isfile(os.path.join(sample_dir, f))]
                file_tuples = []
                for fname in files_found:
                    with open(os.path.join(sample_dir, fname), "rb") as f:
                        file_tuples.append((fname, f.read()))

                with st.spinner(f"Ingesting {len(file_tuples)} curated documents..."):
                    summary = workflow.process_batch_files(file_tuples)

                st.success(f"Processed {summary['total_submitted']} documents in {summary['total_time_ms']}ms!")
                
                # Show cards
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Submitted", summary["total_submitted"])
                c2.metric("Successful", summary["success_count"])
                c3.metric("Duplicates", summary["duplicate_count"])
                c4.metric("Validation / Rejected", summary["failure_count"])

                # Table of results
                res_rows = []
                for r in summary["results"]:
                    res_rows.append({
                        "Filename": r.get("document_record", {}).get("original_filename") or r.get("original_filename", "N/A"),
                        "Status": r.get("status"),
                        "Type": r.get("document_type", "Unknown"),
                        "Time (ms)": r.get("processing_time_ms", 0)
                    })
                st.dataframe(pd.DataFrame(res_rows), use_container_width=True)


# ==============================================================================
# TAB 4: AI ASSISTANT & RAG STUDIO
# ==============================================================================
with tabs[3]:
    st.markdown("### 🤖 Grounded AI Document Assistant & RAG Studio")
    st.caption("Ask semantic questions across all indexed documents. Answers are strictly grounded in source documents with citations.")

    all_docs = database.get_all_documents()
    doc_filter_options = {"All Repository Documents": None}
    for d in all_docs:
        doc_filter_options[f"Doc #{d['id']}: {d['original_filename']}"] = d["id"]

    scoped_doc_label = st.selectbox("Target Scope for Query", list(doc_filter_options.keys()))
    scoped_doc_id = doc_filter_options[scoped_doc_label]

    st.markdown("**Quick Preset Questions:**")
    preset_cols = st.columns(4)
    preset_q = ""
    if preset_cols[0].button("💰 Total Invoice Amounts?"):
        preset_q = "What is the total amount in the standard invoice?"
    if preset_cols[1].button("💻 Engineer Skills?"):
        preset_q = "What technical skills does the software engineer candidate have?"
    if preset_cols[2].button("📄 Compare Invoices?"):
        preset_q = "What are the total amounts across all vendor invoices?"
    if preset_cols[3].button("❓ Unsupported Fact (Negative Case)?"):
        preset_q = "What is the warranty policy on quantum computing servers?"

    user_query = st.text_input("Enter your question", value=preset_q, placeholder="e.g. What is the invoice number and due date for Apex Solutions?")

    if st.button("🔍 Search & Answer", type="primary") and user_query:
        with st.spinner("Retrieving semantic chunks and synthesizing answer..."):
            rag_res = rag_engine.answer_document_query(
                query=user_query,
                document_id=scoped_doc_id
            )

        st.markdown("#### 💡 Assistant Response")
        if not rag_res.get("has_sufficient_information"):
            st.warning(f"⚠️ **{rag_res.get('answer')}**")
            st.caption("The RAG engine verified that no indexed document chunks contain sufficient factual evidence to answer this query.")
        else:
            st.info(f"**Answer:** {rag_res.get('answer')}")

            st.markdown("#### 📚 Source Document Citations")
            citations = rag_res.get("citations", [])
            if citations:
                for idx, c in enumerate(citations, 1):
                    st.markdown(f"""
                    <div class="citation-box">
                        <b>[{idx}] {c['filename']}</b> (Page {c['page_number']}, Chunk {c['chunk_index']}) • <i>Relevance: {c['relevance_percentage']}</i><br>
                        <span style="color: #cbd5e1;">"{c['excerpt']}"</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.write("No direct citations found.")


# ==============================================================================
# TAB 5: REPOSITORY & AUDIT EXPLORER
# ==============================================================================
with tabs[4]:
    st.markdown("### 🔍 Document Repository & Audit Trail Explorer")
    st.caption("Search across metadata, filter by workflow status, and inspect immutable audit logs.")

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        search_query = st.text_input("Search Text", placeholder="Filename, Company, Inv #...")
    with f2:
        status_filter = st.selectbox("Status Filter", ["All"] + workflow.ALL_STATES)
    with f3:
        type_filter = st.selectbox("Type Filter", ["All", "Invoice", "Resume", "Contract", "Other"])
    with f4:
        anomaly_only = st.checkbox("Show Anomaly Alerts Only")

    results = database.search_documents(
        query=search_query,
        status_filter=status_filter,
        type_filter=type_filter,
        anomaly_only=anomaly_only
    )

    st.write(f"Showing **{len(results)} document(s)**:")
    if results:
        table_data = []
        for d in results:
            table_data.append({
                "ID": d["id"],
                "Filename": d["original_filename"],
                "Type": d["document_type"],
                "Status": d["status"],
                "Company / Name": d["company"],
                "Invoice / Email": d["invoice_number"],
                "Amount / Skills": d["total_amount"],
                "Confidence": f"{int(round(d['confidence']*100))}%" if d["confidence"] else "N/A",
                "Uploaded At": d["upload_date"][:16]
            })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True)

        st.markdown("---")
        st.markdown("#### 🔬 Inspect Document JSON & Full Audit History")
        inspect_id = st.selectbox("Select Document ID to Inspect", [d["id"] for d in results])
        selected_inspect = database.get_document_by_id(inspect_id)

        if selected_inspect:
            c_json, c_audit = st.columns([1, 1])
            with c_json:
                st.markdown("##### Structured JSON Data")
                st.json({
                    "extracted": json.loads(selected_inspect.get("extracted_json") or "{}"),
                    "validation": json.loads(selected_inspect.get("validation_json") or "{}"),
                    "anomalies": json.loads(selected_inspect.get("anomaly_json") or "{}")
                })
            with c_audit:
                st.markdown("##### Immutable Audit Trail")
                audits = audit.get_document_history(inspect_id)
                for a in audits:
                    color = audit.format_audit_badge_color(a["action"])
                    st.markdown(f"""
                    <div style="border-left: 3px solid {color}; padding-left: 10px; margin-bottom: 8px;">
                        <span style="font-size:0.75rem; color:#94a3b8;">{a['timestamp'][:19]}</span><br>
                        <b>{a['action']}</b>: {a['previous_status']} ➔ <b>{a['new_status']}</b><br>
                        <span style="font-size:0.85rem; color:#cbd5e1;">{a['reason']}</span>
                    </div>
                    """, unsafe_allow_html=True)


# ==============================================================================
# TAB 6: EXECUTIVE ANALYTICS & METRICS
# ==============================================================================
with tabs[5]:
    st.markdown("### 📊 Executive Analytics & Bottleneck Profiler")
    st.caption("Platform KPIs, status distributions, anomaly frequencies, and processing stage latency analysis.")

    metrics = database.get_workflow_metrics()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Total Documents</div>
        <div class="metric-num">{metrics['total_documents']}</div>
    </div>
    """, unsafe_allow_html=True)

    c2.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Completed</div>
        <div class="metric-num" style="color: #34d399;">{metrics['completed_count']}</div>
    </div>
    """, unsafe_allow_html=True)

    c3.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Needs Review</div>
        <div class="metric-num" style="color: #fbbf24;">{metrics['needs_review_count']}</div>
    </div>
    """, unsafe_allow_html=True)

    c4.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Anomalies Flagged</div>
        <div class="metric-num" style="color: #f87171;">{metrics['anomaly_count']}</div>
    </div>
    """, unsafe_allow_html=True)

    c5.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Avg Processing Time</div>
        <div class="metric-num" style="color: #c084fc;">{metrics['avg_processing_time_ms']}ms</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    col_st, col_tp = st.columns(2)
    with col_st:
        st.markdown("#### 📈 Status Distribution")
        status_df = pd.DataFrame(list(metrics["by_status"].items()), columns=["Status", "Count"])
        st.bar_chart(status_df.set_index("Status"))

    with col_tp:
        st.markdown("#### 📁 Documents by Type")
        type_df = pd.DataFrame(list(metrics["by_type"].items()), columns=["Type", "Count"])
        st.bar_chart(type_df.set_index("Type"))

    st.markdown("---")
    st.markdown("#### ⚡ System Audit Log Stream (Last 25 Events)")
    recent_audits = audit.get_system_audit_trail(limit=25)
    if recent_audits:
        rec_data = []
        for r in recent_audits:
            rec_data.append({
                "Timestamp": r["timestamp"][:19],
                "Doc #": r["document_id"],
                "Action": r["action"],
                "Transition": f"{r['previous_status']} ➔ {r['new_status']}",
                "Performed By": r["performed_by"],
                "Reason": r["reason"]
            })
        st.dataframe(pd.DataFrame(rec_data), use_container_width=True)
