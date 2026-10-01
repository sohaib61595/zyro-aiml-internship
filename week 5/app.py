"""
ZYROO INTERNSHIP PROGRAM - WEEK 5
Module: Streamlit Web Interface & Workflow Automation Studio
Focus: Workflow automation, validation, review, auditability and dashboard analytics

Pages / Tabs:
1. 📥 Ingestion & Target Workflow: Upload, automated classification, extraction, validation, and rule decision.
2. 👥 Human Review Queue: Dedicated queue for 'Needs Review' docs with Approve/Reject actions & field editor.
3. ⚡ Batch Workflow Processing: Multi-select stored documents, fault-tolerant batch execution, individual metrics.
4. 🔍 Workflow Repository & Audit Explorer: Multi-field search, status filtering, drilldown audit timeline.
5. 📊 Workflow Metrics & Analytics: Key KPIs, status distribution, document type counts, processing time trends.
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

import streamlit as st
import pandas as pd

# Ensure week 5 modules are in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database
import storage
import processor
import classifier
import extractor
import validator
import audit
import workflow

# ==============================================================================
# STREAMLIT PAGE CONFIGURATION & CUSTOM STYLES
# ==============================================================================
st.set_page_config(
    page_title="ZYROO | AI Document Workflow Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Glassmorphic & Modern AI Theme
CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background: radial-gradient(circle at top right, #111827, #0b0f19 80%);
        color: #f3f4f6;
    }
    
    /* Hero Header */
    .hero-container {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px 32px;
        margin-bottom: 24px;
        backdrop-filter: blur(12px);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    
    .hero-title {
        font-size: 2.1rem;
        font-weight: 700;
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
        border-color: rgba(99, 102, 241, 0.4);
    }
    .metric-num {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .metric-lbl {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
    }
    
    /* Status Badges */
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-new { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-proc { background: rgba(147, 51, 234, 0.2); color: #c084fc; border: 1px solid rgba(147, 51, 234, 0.3); }
    .badge-rev { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-app { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-rej { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .badge-comp { background: rgba(5, 150, 105, 0.2); color: #10b981; border: 1px solid rgba(5, 150, 105, 0.3); }
    
    /* Audit Event Card */
    .audit-item {
        border-left: 3px solid #6366f1;
        padding: 10px 16px;
        margin-bottom: 12px;
        background: rgba(30, 41, 59, 0.4);
        border-radius: 0 8px 8px 0;
    }
    .audit-header {
        font-size: 0.85rem;
        font-weight: 600;
        color: #e2e8f0;
        display: flex;
        justify-content: space-between;
    }
    .audit-note {
        font-size: 0.8rem;
        color: #94a3b8;
        margin-top: 4px;
    }
    
    /* Validation Pill */
    .val-pass { color: #34d399; font-weight: 600; font-size: 0.85rem; }
    .val-fail { color: #f87171; font-weight: 600; font-size: 0.85rem; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ==============================================================================
# DATABASE & STORAGE INITIALIZATION
# ==============================================================================
@st.cache_resource
def setup_environment():
    database.init_db()
    storage.ensure_storage_structure()
    return True

setup_environment()


# ==============================================================================
# HERO HEADER & GLOBAL METRICS BAR
# ==============================================================================
st.markdown("""
<div class="hero-container">
    <div class="hero-title">⚡ ZYROO AI Document Intelligence & Workflow Platform</div>
</div>
""", unsafe_allow_html=True)

# Fetch platform metrics
metrics = database.get_workflow_metrics()

col_m1, col_m2, col_m3, col_m4, col_m5, col_m6 = st.columns(6)
with col_m1:
    st.markdown(f'<div class="metric-card"><div class="metric-num" style="color: #60a5fa;">{metrics["total_documents"]}</div><div class="metric-lbl">Total Documents</div></div>', unsafe_allow_html=True)
with col_m2:
    st.markdown(f'<div class="metric-card"><div class="metric-num" style="color: #10b981;">{metrics["completed_count"]}</div><div class="metric-lbl">Completed</div></div>', unsafe_allow_html=True)
with col_m3:
    st.markdown(f'<div class="metric-card"><div class="metric-num" style="color: #fbbf24;">{metrics["needs_review_count"]}</div><div class="metric-lbl">Needs Review</div></div>', unsafe_allow_html=True)
with col_m4:
    st.markdown(f'<div class="metric-card"><div class="metric-num" style="color: #34d399;">{metrics["approved_count"]}</div><div class="metric-lbl">Approved</div></div>', unsafe_allow_html=True)
with col_m5:
    st.markdown(f'<div class="metric-card"><div class="metric-num" style="color: #f87171;">{metrics["rejected_count"]}</div><div class="metric-lbl">Rejected</div></div>', unsafe_allow_html=True)
with col_m6:
    avg_t = f"{metrics['avg_processing_time_ms']} ms" if metrics['avg_processing_time_ms'] > 0 else "N/A"
    st.markdown(f'<div class="metric-card"><div class="metric-num" style="color: #c084fc;">{avg_t}</div><div class="metric-lbl">Avg Process Time</div></div>', unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)


# ==============================================================================
# TAB NAVIGATION
# ==============================================================================
tab_ingest, tab_review, tab_batch, tab_repo, tab_metrics = st.tabs([
    "📥 Ingestion & Target Workflow",
    f"👥 Human Review Queue ({metrics['needs_review_count']})",
    "⚡ Batch Workflow Processing",
    "🔍 Workflow Repository & Audit",
    "📊 Operational Analytics & Dashboard"
])


# ==============================================================================
# TAB 1: INGESTION & TARGET WORKFLOW
# ==============================================================================
with tab_ingest:
    st.subheader("Document Ingestion & Automated Target Workflow")
    st.markdown("""
    Move documents through the strict Week 5 lifecycle:  
    **Upload → Process → Classify → Extract → Validate → Apply Rules → Complete / Route to Review → Audit History**
    """)
    
    col_u1, col_u2 = st.columns([1, 1])
    
    with col_u1:
        st.markdown("#### 1. Select or Upload Document")
        uploaded_files = st.file_uploader(
            "Upload Invoices, Resumes, or Other documents (PDF, PNG, JPG)",
            type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True
        )
        
        apply_ocr = st.checkbox("Enable Adaptive Preprocessed OCR (Otsu & Denoising)", value=True)
        
        # Load sample selector for instant demonstration
        samples_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
        sample_options = ["None (Upload custom file)"]
        if os.path.exists(samples_dir):
            sample_options += sorted(os.listdir(samples_dir))
            
        chosen_sample = st.selectbox("Or choose a pre-loaded sample document:", sample_options)

    with col_u2:
        st.markdown("#### 2. Workflow Automation Rules")
        st.info("""
        • **Invoice Validation**: Invoice Number, Date, Company Name, and Total Amount must be valid.
        • **Resume Validation**: Candidate Name, Email (RFC regex), and Technical Skills required.
        • **Classification Confidence**: Routed to `Needs Review` if calibrated confidence < 75%.
        • **High Value Threshold**: Invoices >= $10,000 flagged for executive review.
        • **Terminal States**: Automated completion only occurs when all checks pass.
        """)
        
        run_process = st.button("🚀 Ingest & Execute Target Workflow", type="primary", use_container_width=True)

    if run_process:
        files_to_process = []
        
        # Custom uploads
        if uploaded_files:
            for uf in uploaded_files:
                files_to_process.append((uf.name, uf.read()))
        # Sample selection
        elif chosen_sample != "None (Upload custom file)":
            sample_path = os.path.join(samples_dir, chosen_sample)
            with open(sample_path, "rb") as f:
                files_to_process.append((chosen_sample, f.read()))
        else:
            st.warning("Please upload a document or choose a sample to process.")

        if files_to_process:
            for fname, fbytes in files_to_process:
                with st.spinner(f"Executing automated workflow for '{fname}'..."):
                    result = workflow.ingest_and_execute_workflow(
                        file_bytes=fbytes,
                        original_filename=fname,
                        apply_ocr_preprocessing=apply_ocr
                    )

                if result.get("is_duplicate"):
                    st.warning(f"⚠️ **Duplicate Document Detected**: {result.get('message')}")
                    doc_rec = result.get("document_record")
                    if doc_rec:
                        st.json(doc_rec)
                    continue

                if not result.get("success"):
                    st.error(f"❌ Ingestion Failed: {result.get('message')}")
                    continue

                st.success(f"✅ Workflow Execution Finished: Document #{result['document_id']} → **{result['status']}**")
                
                # Visual Decision Breakdown
                dec = result["decision"]
                val = result["validation_result"]
                doc = result["document_record"]
                
                c_res1, c_res2, c_res3 = st.columns([1, 1, 1])
                with c_res1:
                    st.markdown("**Workflow Decision**")
                    status_class = f"badge-{result['status'].lower().replace(' ', '-')}"
                    st.markdown(f"<span class='badge {status_class}'>{result['status']}</span>", unsafe_allow_html=True)
                    st.markdown(f"**Decision Code**: `{dec.decision_code}`")
                    st.markdown(f"**Reason**: {dec.reason}")
                    st.markdown(f"**Processing Time**: `{result['processing_time_ms']} ms`")

                with c_res2:
                    st.markdown("**Classification & Confidence**")
                    st.markdown(f"**Type**: `{result['document_type']}`")
                    if result["confidence"] is not None:
                        conf_pct = int(round(result["confidence"] * 100))
                        badge_color = "#10b981" if conf_pct >= 75 else "#f59e0b"
                        st.markdown(f"**Confidence**: <span style='color: {badge_color}; font-weight: 700;'>{conf_pct}%</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("**Confidence**: `N/A (Model uncalibrated)`")

                with c_res3:
                    st.markdown("**Validation Summary**")
                    if val["is_valid"]:
                        st.markdown("<span class='val-pass'>✔ ALL FIELDS VALIDATED</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<span class='val-fail'>✖ {len(val['failed_fields'])} FIELD(S) FAILED</span>", unsafe_allow_html=True)
                        for fld, err in val["field_errors"].items():
                            st.caption(f"• **{fld}**: {err}")

                with st.expander("🔍 View Extracted Fields & Audit Trail"):
                    st.json(val["field_results"])
                    history = audit.get_document_history(result["document_id"])
                    st.dataframe(pd.DataFrame(history)[["action", "previous_status", "new_status", "timestamp", "performed_by", "reason"]], use_container_width=True)


# ==============================================================================
# TAB 2: HUMAN REVIEW QUEUE (Requirement 6)
# ==============================================================================
with tab_review:
    st.subheader("👥 Human Review Queue (Needs Review)")
    st.markdown("Inspect documents with missing fields, invalid formats, or low model confidence. Approve or Reject with documented audit reasons.")
    
    # Fetch all documents in Needs Review
    review_docs = database.search_documents(status="Needs Review", limit=200)
    
    if not review_docs:
        st.success("🎉 Review queue is currently empty! All documents are approved or completed.")
    else:
        st.markdown(f"**{len(review_docs)} document(s)** currently awaiting human review:")
        
        # Selector for document to review
        doc_options = {f"#{d['id']} - {d['original_filename']} ({d['document_type']})": d['id'] for d in review_docs}
        selected_label = st.selectbox("Select document to review:", list(doc_options.keys()))
        selected_id = doc_options[selected_label]
        
        target_doc = database.get_document_by_id(selected_id)
        
        if target_doc:
            rev_col1, rev_col2 = st.columns([1, 1])
            
            with rev_col1:
                st.markdown("#### Document Overview")
                st.markdown(f"**Filename**: `{target_doc['original_filename']}`")
                st.markdown(f"**Document Type**: `{target_doc['document_type']}`")
                
                conf = target_doc.get("confidence")
                if conf is not None:
                    st.markdown(f"**Model Confidence**: `{round(conf*100, 1)}%`")
                else:
                    st.markdown("**Model Confidence**: `N/A`")
                    
                st.markdown(f"**Review Reason**: <span style='color: #fbbf24;'>{target_doc.get('review_reason')}</span>", unsafe_allow_html=True)
                st.markdown(f"**Upload Timestamp**: `{target_doc.get('upload_date')}`")
                
                with st.expander("📄 Clean Text Preview", expanded=False):
                    st.text(target_doc.get("text_preview", "No preview available."))

            with rev_col2:
                st.markdown("#### Validation Results & Field Correction")
                
                # Parse validation JSON
                val_json = {}
                try:
                    val_json = json.loads(target_doc.get("validation_json", "{}"))
                except Exception:
                    pass

                failed_flds = val_json.get("failed_fields", [])
                field_errors = val_json.get("field_errors", {})

                if failed_flds:
                    st.error(f"Failed Validation: {', '.join(failed_flds)}")
                    for fld, err in field_errors.items():
                        st.caption(f"• **{fld}**: {err}")
                else:
                    st.info("Triggered review by policy rule (e.g., high value or low confidence).")

                # Field Correction Form
                with st.form(key=f"edit_form_{selected_id}"):
                    st.markdown("##### Correct Extracted Information")
                    edit_company = st.text_input("Company / Candidate Name", value=target_doc.get("company", ""))
                    edit_inv_no = st.text_input("Invoice Number / Email", value=target_doc.get("invoice_number", ""))
                    edit_amount = st.text_input("Total Amount / Skills", value=target_doc.get("total_amount", ""))
                    
                    submit_corrections = st.form_submit_button("💾 Save Field Corrections")
                    if submit_corrections:
                        # Re-validate fields
                        doc_t = target_doc.get("document_type")
                        updated_vals = {}
                        if doc_t == "Invoice":
                            updated_vals = {"invoice_number": edit_inv_no, "date": target_doc.get("upload_date")[:10], "company": edit_company, "total_amount": edit_amount}
                        elif doc_t == "Resume":
                            updated_vals = {"name": edit_company, "email": edit_inv_no, "skills": edit_amount}
                        else:
                            updated_vals = {"document_title": edit_company}

                        new_val = validator.validate_document(doc_t, updated_vals)
                        
                        database.update_document_fields(
                            doc_id=selected_id,
                            fields={
                                "company": edit_company,
                                "invoice_number": edit_inv_no,
                                "total_amount": edit_amount,
                                "validation_json": json.dumps(new_val),
                                "notes": "Fields manually corrected in Review Queue."
                            }
                        )
                        audit.log_event(
                            document_id=selected_id,
                            action=audit.ACTION_FIELD_EDIT,
                            previous_status="Needs Review",
                            new_status="Needs Review",
                            reason=f"Reviewer corrected metadata. Valid: {new_val['is_valid']}",
                            performed_by="Human Reviewer"
                        )
                        st.success("Metadata updated and re-validated! You may now Approve.")
                        st.rerun()

            st.markdown("---")
            # Human Review Actions: Approve / Reject
            act_col1, act_col2 = st.columns([1, 1])
            
            with act_col1:
                st.markdown("#### ✅ Accept Document")
                approve_notes = st.text_area("Approval Notes (Optional):", placeholder="e.g. Verified with department head.", key=f"app_notes_{selected_id}")
                if st.button("Approve Document", type="primary", use_container_width=True, key=f"btn_app_{selected_id}"):
                    ok, msg = workflow.approve_document(
                        doc_id=selected_id,
                        reviewer_notes=approve_notes,
                        performed_by="Human Reviewer"
                    )
                    if ok:
                        st.success(f"✔ {msg}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Approval failed: {msg}")

            with act_col2:
                st.markdown("#### ❌ Reject Document")
                st.caption("Requirement: A short reason is mandatory when rejecting a document.")
                reject_reason = st.text_area("Rejection Reason (Mandatory):", placeholder="e.g. Unreadable blurred receipt missing tax numbers.", key=f"rej_reason_{selected_id}")
                if st.button("Reject Document", type="secondary", use_container_width=True, key=f"btn_rej_{selected_id}"):
                    if not reject_reason.strip() or len(reject_reason.strip()) < 4:
                        st.error("Rejection reason is required (minimum 4 characters)!")
                    else:
                        ok, msg = workflow.reject_document(
                            doc_id=selected_id,
                            rejection_reason=reject_reason,
                            performed_by="Human Reviewer"
                        )
                        if ok:
                            st.warning(f"✖ {msg}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Rejection failed: {msg}")

            st.markdown("---")
            st.markdown("#### Document Complete Audit Trail")
            doc_history = audit.get_document_history(selected_id)
            for h in doc_history:
                badge_col = audit.format_audit_badge_color(h["action"])
                st.markdown(f"""
                <div class="audit-item" style="border-left-color: {badge_col};">
                    <div class="audit-header">
                        <span>[{h['action']}] {h['previous_status']} ➔ {h['new_status']}</span>
                        <span style="color: #94a3b8; font-size: 0.75rem;">{h['timestamp']} • {h['performed_by']}</span>
                    </div>
                    <div class="audit-note">{h['reason']}</div>
                </div>
                """, unsafe_allow_html=True)


# ==============================================================================
# TAB 3: BATCH WORKFLOW PROCESSING (Requirement 7)
# ==============================================================================
with tab_batch:
    st.subheader("⚡ Batch Workflow Processing Engine")
    st.markdown("""
    Select multiple stored documents to re-run workflow rules concurrently.  
    **Key Requirement**: Fault-tolerant design ensures that **one failed document does not stop or abort the batch**.
    """)
    
    all_stored_docs = database.search_documents(limit=500)
    
    if not all_stored_docs:
        st.info("No documents found in database. Ingest some documents first.")
    else:
        # Multi-select options
        df_all = pd.DataFrame(all_stored_docs)
        
        col_b_filter1, col_b_filter2 = st.columns([1, 1])
        with col_b_filter1:
            state_prefilter = st.multiselect("Pre-filter by State:", ["New", "Processing", "Needs Review", "Completed", "Approved", "Rejected"], default=["Needs Review"])
        
        filtered_batch_candidates = [d for d in all_stored_docs if not state_prefilter or d.get("status") in state_prefilter]
        
        batch_lookup = {f"#{d['id']} - {d['original_filename']} ({d['status']})": d['id'] for d in filtered_batch_candidates}
        
        selected_batch_labels = st.multiselect(
            f"Select documents to batch process ({len(filtered_batch_candidates)} available):",
            options=list(batch_lookup.keys()),
            default=list(batch_lookup.keys())[:5]
        )
        
        target_batch_ids = [batch_lookup[lbl] for lbl in selected_batch_labels]
        
        col_run1, col_run2 = st.columns([1, 1])
        with col_run1:
            run_batch = st.button("▶ Run Batch Workflow Evaluation", type="primary", use_container_width=True)
            
        with col_run2:
            simulate_fault = st.checkbox("Inject Simulated Faulty Document ID (#99999) to verify fault tolerance", value=False)
            if simulate_fault:
                target_batch_ids.append(99999)

        if run_batch:
            if not target_batch_ids:
                st.warning("Please select at least one document for batch processing.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                status_text.text("Running batch evaluation...")

                batch_res = workflow.execute_batch_workflow(target_batch_ids)

                progress_bar.progress(100)
                status_text.text("Batch processing complete!")

                # Batch KPI Cards
                b_c1, b_c2, b_c3, b_c4 = st.columns(4)
                with b_c1:
                    st.metric("Total Selected", batch_res["total_selected"])
                with b_c2:
                    st.metric("Processed Successfully", batch_res["processed_count"])
                with b_c3:
                    st.metric("Needs Review", batch_res["review_count"])
                with b_c4:
                    st.metric("Failed Items", batch_res["failed_count"])

                st.markdown("#### Individual Document Results")
                b_table = []
                for item in batch_res["results"]:
                    b_table.append({
                        "ID": item["document_id"],
                        "Filename": item.get("original_filename", "N/A"),
                        "Previous State": item.get("old_status", "N/A"),
                        "Target State": item.get("new_status", "N/A"),
                        "Success": "✔ Success" if item.get("success") else "✖ Failed",
                        "Reason / Error": item.get("reason") or item.get("error", "")
                    })
                st.dataframe(pd.DataFrame(b_table), use_container_width=True)
                st.success("Batch completed. Each document was recorded independently in audit logs.")


# ==============================================================================
# TAB 4: WORKFLOW REPOSITORY & AUDIT SEARCH (Requirements 5 & 8)
# ==============================================================================
with tab_repo:
    st.subheader("🔍 Workflow Search, Filter & Audit Trail Explorer")
    
    col_s1, col_s2, col_s3, col_s4 = st.columns([2, 1, 1, 1])
    with col_s1:
        search_q = st.text_input("Search filename, company, invoice #, or reason:", placeholder="e.g. Apex, INV-2026, John Doe")
    with col_s2:
        filter_status = st.selectbox("Status Filter:", ["All", "Needs Review", "Approved", "Rejected", "Completed", "New", "Processing"])
    with col_s3:
        filter_type = st.selectbox("Document Type:", ["All", "Invoice", "Resume", "Other"])
    with col_s4:
        sort_choice = st.selectbox("Sort By:", ["newest", "oldest", "filename_asc", "status", "confidence_desc"])

    # Execute search
    results = database.search_documents(
        search_query=search_q,
        document_type=filter_type,
        status=filter_status,
        sort_by=sort_choice,
        limit=200
    )

    st.markdown(f"**Found {len(results)} matching document(s):**")
    
    if results:
        # Build clean display table
        table_rows = []
        for r in results:
            conf_val = f"{int(round(r['confidence']*100))}%" if r.get('confidence') is not None else "N/A"
            table_rows.append({
                "ID": r["id"],
                "Filename": r["original_filename"],
                "Type": r["document_type"],
                "Status": r["status"],
                "Confidence": conf_val,
                "Company / Name": r["company"],
                "Invoice # / Email": r["invoice_number"],
                "Amount / Skills": r["total_amount"],
                "Upload Date": r["upload_date"][:16],
                "Latest Action": r.get("latest_action", "N/A"),
                "Action Time": r.get("latest_action_time", "N/A")[:16]
            })
        
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True)

        st.markdown("---")
        st.markdown("#### 📜 Document Audit History Drilldown")
        drilldown_id = st.number_input("Enter Document ID to view audit history:", min_value=1, value=results[0]["id"] if results else 1, step=1)
        
        if st.button("Fetch Complete Audit Trail"):
            hist = audit.get_document_history(int(drilldown_id))
            if not hist:
                st.warning(f"No audit records found for Document #{drilldown_id}.")
            else:
                st.markdown(f"**Audit Trail for Document #{drilldown_id} ({len(hist)} events):**")
                for item in hist:
                    b_color = audit.format_audit_badge_color(item["action"])
                    st.markdown(f"""
                    <div class="audit-item" style="border-left-color: {b_color};">
                        <div class="audit-header">
                            <span>[{item['action']}] {item['previous_status']} ➔ {item['new_status']}</span>
                            <span style="color: #94a3b8; font-size: 0.75rem;">{item['timestamp']} • {item['performed_by']}</span>
                        </div>
                        <div class="audit-note">{item['reason']}</div>
                    </div>
                    """, unsafe_allow_html=True)


# ==============================================================================
# TAB 5: OPERATIONAL ANALYTICS & DASHBOARD (Requirement 9)
# ==============================================================================
with tab_metrics:
    st.subheader("📊 Operational Analytics & Workflow Metrics Dashboard")
    
    kpi_col1, kpi_col2, kpi_col3 = st.columns([1, 1, 1])
    
    with kpi_col1:
        st.markdown("#### Status Breakdown")
        status_data = metrics.get("status_distribution", {})
        if status_data:
            df_status = pd.DataFrame(list(status_data.items()), columns=["Status", "Count"])
            st.bar_chart(df_status.set_index("Status"), color="#6366f1")
        else:
            st.info("No status data available.")

    with kpi_col2:
        st.markdown("#### Document Type Distribution")
        type_data = metrics.get("type_distribution", {})
        if type_data:
            df_type = pd.DataFrame(list(type_data.items()), columns=["Type", "Count"])
            st.bar_chart(df_type.set_index("Type"), color="#38bdf8")
        else:
            st.info("No type data available.")

    with kpi_col3:
        st.markdown("#### Processing Performance")
        st.markdown(f"• **Average Processing Time**: `{metrics['avg_processing_time_ms']} ms`")
        st.markdown(f"• **Fastest Processing Time**: `{metrics['min_processing_time_ms']} ms`")
        st.markdown(f"• **Longest Processing Time**: `{metrics['max_processing_time_ms']} ms`")
        
        avg_c = f"{round(metrics['avg_confidence']*100, 1)}%" if metrics.get('avg_confidence') else "N/A"
        st.markdown(f"• **Average Model Confidence**: `{avg_c}`")
        st.markdown(f"• **Low Confidence Flags**: `{metrics['low_confidence_count']} documents`")
        st.markdown(f"• **Review Queue Backlog**: `{metrics['needs_review_count']} documents`")

    st.markdown("---")
    st.markdown("#### ⚡ Real-Time System Audit Event Stream")
    recent_events = database.get_recent_audit_logs(limit=25)
    if recent_events:
        st.dataframe(pd.DataFrame(recent_events)[["id", "document_id", "original_filename", "action", "previous_status", "new_status", "timestamp", "performed_by", "reason"]], use_container_width=True)
    else:
        st.info("No audit logs recorded yet.")
