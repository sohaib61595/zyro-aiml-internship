"""
ZYROO INTERNSHIP PROGRAM - WEEK 4
AI Document Intelligence & Workflow Platform
Document Management Layer & SQLite Repository Platform

Flow: Upload → Validate → Hash → Read/OCR → Clean → Classify → Extract → Store File → Store Metadata → Search/Filter → View
"""

import os
import io
import json
import time
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from PIL import Image

import streamlit as st
import pandas as pd

# Core Week 4 Modules
import db_repository
import storage_manager
from pipeline import process_document_pipeline
from ocr_engine import is_tesseract_available


# ==============================================================================
# 1. STREAMLIT APP CONFIGURATION & STYLING
# ==============================================================================

st.set_page_config(
    page_title="Document Intelligence & Management | Zyroo Week 4",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern styling
st.markdown("""
<style>
    /* Header Gradient & Typography */
    .app-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #1E3A8A 0%, #2563EB 50%, #4F46E5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.1rem;
    }
    .app-subheader {
        color: #4B5563;
        font-size: 1.05rem;
        margin-bottom: 1.2rem;
    }
    
    /* Status Badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .status-processed {
        background-color: #DEF7EC;
        color: #03543F;
        border: 1px solid #31C48D;
    }
    .status-review {
        background-color: #FEF08A;
        color: #713F12;
        border: 1px solid #FACC15;
    }
    .status-failed {
        background-color: #FDE8E8;
        color: #9B1C1C;
        border: 1px solid #F98080;
    }
    
    /* Type Badges */
    .type-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .type-invoice { background-color: #E0E7FF; color: #3730A3; border: 1px solid #C7D2FE; }
    .type-resume { background-color: #D1FAE5; color: #065F46; border: 1px solid #A7F3D0; }
    .type-other { background-color: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; }
    
    /* Metric Cards */
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin-bottom: 0.5rem;
    }
    
    /* Duplicate Alert Card */
    .dup-banner {
        background: linear-gradient(90deg, #FEF3C7 0%, #FFFBEB 100%);
        border: 1px solid #F59E0B;
        border-left: 5px solid #D97706;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


# Initialize Database & Storage hierarchy on startup
db_repository.init_db()
storage_manager.ensure_storage_structure()


# ==============================================================================
# 2. SIDEBAR SYSTEM STATUS & NAVIGATION
# ==============================================================================

with st.sidebar:
    st.image("https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/Python-Dark.svg", width=38)
    st.markdown("### **Zyroo Document Platform**")
    st.markdown("`Week 4: Management & Repository Layer`")
    st.divider()

    st.markdown("#### ⚙️ Ingestion Settings")
    enable_ocr_preproc = st.toggle(
        "Enable OCR Preprocessing",
        value=True,
        help="Applies grayscale, contrast boost, Otsu binarization, and median denoising to scans."
    )
    
    st.divider()
    st.markdown("#### 🔍 Engine Diagnostics")
    tess_avail = is_tesseract_available()
    if tess_avail:
        st.success("Tesseract OCR Active", icon="✅")
    else:
        st.warning("Tesseract OCR Not Detected", icon="⚠️")

    st.markdown(f"**Database:** `document_repository.db`")
    stats = db_repository.get_repository_stats()
    st.metric("Total Stored Documents", stats["total_documents"])

    st.divider()
    if st.button("🔄 Refresh System Stats", use_container_width=True):
        st.rerun()

    st.caption("Official ZYROO AI/ML Internship")


# ==============================================================================
# 3. TOP BANNER
# ==============================================================================

st.markdown('<div class="app-header">AI Document Intelligence & Management Layer</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subheader">'
    '<b>Week 4:</b> Structured File Storage • SQLite Document Repository • Duplicate Detection • Multi-Field Search • Status Workflows'
    '</div>',
    unsafe_allow_html=True
)

tab_upload, tab_repository, tab_detail, tab_analytics = st.tabs([
    "📤 Ingestion & Upload",
    "🗄️ Document Repository & Search",
    "🔍 Document Detail View",
    "📊 Repository Analytics"
])


# ==============================================================================
# TAB 1: INGESTION & UPLOAD (Tasks 1, 2, 3, 7, 8)
# ==============================================================================

with tab_upload:
    st.markdown("#### 📄 Document Ingestion Pipeline")
    st.caption("Target Flow: Upload → Validate → Hash → OCR/Read → Clean → Classify → Extract → Store File → Store Metadata")

    samples_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
    sample_options = ["-- None (Upload your own file) --"]
    if os.path.exists(samples_dir):
        sample_options += sorted(os.listdir(samples_dir))

    col_up, col_smp = st.columns([3, 2])
    with col_up:
        uploaded_file = st.file_uploader(
            "Upload Document (PDF, PNG, JPG, JPEG):",
            type=["pdf", "png", "jpg", "jpeg"],
            help="Max allowed file size is 20MB. Non-supported extensions will be safely rejected."
        )
    with col_smp:
        selected_sample = st.selectbox(
            "⚡ Quick Test Samples (Preloaded):",
            options=sample_options,
            help="Select sample files to evaluate invoices, resumes, scanned receipts, or edge cases."
        )

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
        col_btn, _ = st.columns([2, 5])
        with col_btn:
            process_btn = st.button("🚀 Process & Ingest Document", type="primary", use_container_width=True)

        if process_btn:
            with st.spinner("Executing pipeline (Hash → Extract → Classify → Store)..."):
                start_t = time.time()
                res = process_document_pipeline(
                    file_bytes=doc_bytes,
                    original_filename=doc_filename,
                    apply_ocr_preprocessing=enable_ocr_preproc
                )
                elapsed = round(time.time() - start_t, 3)

            # --- CASE 1: Validation / Ingestion Failure (Task 8) ---
            if not res["success"] and not res.get("is_duplicate"):
                st.error(f"❌ {res['message']}")

            # --- CASE 2: Duplicate Document Detected (Task 3) ---
            elif res.get("is_duplicate"):
                existing = res["document_record"]
                st.markdown(f"""
                <div class="dup-banner">
                    <h4 style="margin:0; color:#92400E;">⚠️ Duplicate Document Detected!</h4>
                    <p style="margin:0.4rem 0 0 0; color:#78350F;">
                        This document has already been ingested. SHA-256 hash matches existing record <b>#{existing.get('id')}</b>.<br>
                        Displaying existing record details below without creating duplicate entries.
                    </p>
                </div>
                """, unsafe_allow_html=True)

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Document ID", f"#{existing.get('id')}")
                col2.metric("Category", existing.get('document_type'))
                col3.metric("Status", existing.get('status'))
                col4.metric("Upload Date", existing.get('upload_date'))

                st.info(f"**Stored File:** `{existing.get('file_path')}`")
                st.text_area("Extracted Text Preview:", value=existing.get("text_preview", ""), height=120, disabled=True)

            # --- CASE 3: Successful Ingestion (Tasks 1, 2, 7) ---
            else:
                doc_record = res["document_record"]
                status = res["status"]
                doc_type = doc_record["document_type"]

                status_class = "status-processed" if status == "Processed" else ("status-review" if status == "Needs Review" else "status-failed")
                type_class = "type-invoice" if doc_type == "Invoice" else ("type-resume" if doc_type == "Resume" else "type-other")

                st.success(f"✅ Ingestion Complete in {elapsed}s! Document record #{doc_record['id']} created.")

                col_res1, col_res2, col_res3, col_res4 = st.columns(4)
                with col_res1:
                    st.markdown(f"**Category:** <span class='type-badge {type_class}'>{doc_type}</span>", unsafe_allow_html=True)
                    st.caption(f"Confidence: {int(round(doc_record['confidence'] * 100))}%")
                with col_res2:
                    st.markdown(f"**Status:** <span class='status-badge {status_class}'>{status}</span>", unsafe_allow_html=True)
                    st.caption(f"{res.get('status_reason', '')}")
                with col_res3:
                    st.metric("Primary Entity", doc_record.get("company", "Not Found"))
                with col_res4:
                    st.metric("Identifier / Amount", f"{doc_record.get('invoice_number')} | {doc_record.get('total_amount')}")

                st.markdown("##### 📁 Storage & Integrity Verification")
                st.code(
                    f"Original Filename : {doc_record['original_filename']}\n"
                    f"Stored Filename   : {doc_record['stored_filename']}\n"
                    f"Organized Path    : {doc_record['file_path']}\n"
                    f"SHA-256 Hash      : {doc_record['file_hash']}",
                    language="text"
                )

                with st.expander("📄 Text Preview & JSON Metadata", expanded=False):
                    st.write("**Text Excerpt:**")
                    st.text_area("", value=doc_record.get("text_preview", ""), height=100, disabled=True, label_visibility="collapsed")
                    st.write("**Extracted JSON Entities:**")
                    try:
                        st.json(json.loads(doc_record.get("extracted_json", "{}")))
                    except Exception:
                        st.text(doc_record.get("extracted_json", "{}"))


# ==============================================================================
# TAB 2: DOCUMENT REPOSITORY & SEARCH (Tasks 4, 5)
# ==============================================================================

with tab_repository:
    st.markdown("#### 🗄️ Searchable Document Repository")
    st.caption("Perform multi-field search and apply filters across stored invoices, resumes, and other documents.")

    # Search & Filter Controls
    search_col, filter_type_col, filter_status_col, sort_col = st.columns([3, 1.5, 1.5, 1.5])
    
    with search_col:
        search_query = st.text_input(
            "🔎 Multi-Field Search:",
            placeholder="Search filename, company, invoice #, text...",
            key="repo_search_query"
        )
    with filter_type_col:
        filter_type = st.selectbox(
            "Document Type:",
            options=["All", "Invoice", "Resume", "Other"],
            index=0,
            key="repo_filter_type"
        )
    with filter_status_col:
        filter_status = st.selectbox(
            "Status:",
            options=["All", "Processed", "Needs Review", "Failed"],
            index=0,
            key="repo_filter_status"
        )
    with sort_col:
        sort_order = st.selectbox(
            "Sort Order:",
            options=["Newest", "Oldest", "Filename", "Company"],
            index=0,
            key="repo_sort_order"
        )

    # Date Range Filter & Clear Button
    col_date1, col_date2, col_clear, _ = st.columns([1.5, 1.5, 1, 3])
    with col_date1:
        start_date_val = st.date_input("From Date:", value=None, key="repo_start_date")
    with col_date2:
        end_date_val = st.date_input("To Date:", value=None, key="repo_end_date")
    with col_clear:
        st.write("")
        st.write("")
        if st.button("🧹 Clear Filters", use_container_width=True):
            st.session_state["repo_search_query"] = ""
            st.session_state["repo_filter_type"] = "All"
            st.session_state["repo_filter_status"] = "All"
            st.session_state["repo_sort_order"] = "Newest"
            st.rerun()

    # Execute SQLite Search Query (Task 4 & 5)
    s_date_str = start_date_val.strftime("%Y-%m-%d") if start_date_val else None
    e_date_str = end_date_val.strftime("%Y-%m-%d") if end_date_val else None

    results = db_repository.search_documents(
        search_query=search_query,
        document_type=filter_type if filter_type != "All" else None,
        status=filter_status if filter_status != "All" else None,
        start_date=s_date_str,
        end_date=e_date_str,
        sort_by=sort_order.lower()
    )

    st.markdown(f"**Found {len(results)} matching document(s)**")

    if results:
        # Display as tabular dataframe
        display_data = []
        for r in results:
            display_data.append({
                "ID": r["id"],
                "Original Filename": r["original_filename"],
                "Type": r["document_type"],
                "Entity / Company": r["company"],
                "Reference #": r["invoice_number"],
                "Total / Info": r["total_amount"],
                "Status": r["status"],
                "Upload Date": r["upload_date"],
                "Confidence": f"{int(round(r['confidence'] * 100))}%"
            })
        
        df_docs = pd.DataFrame(display_data)
        st.dataframe(
            df_docs,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn(format="#%d", width="small"),
                "Confidence": st.column_config.TextColumn(width="small")
            }
        )

        st.caption("💡 Tip: Select a document by ID in the **'Document Detail View'** tab to inspect, preview, download, or edit its metadata.")
    else:
        st.info("No documents match the current search query or filter criteria. Try adjusting your search term or clearing filters.")


# ==============================================================================
# TAB 3: DOCUMENT DETAIL VIEW (Tasks 6, 7, 8)
# ==============================================================================

with tab_detail:
    st.markdown("#### 🔍 Document Detail Inspector")
    st.caption("Inspect extracted fields, preview original files, download documents, and manage processing status.")

    all_docs = db_repository.search_documents(sort_by="newest", limit=200)
    if not all_docs:
        st.warning("No documents currently stored in the repository. Ingest a document in the 'Ingestion & Upload' tab first.")
    else:
        doc_options = {
            f"#{d['id']} - {d['original_filename']} ({d['document_type']} | {d['status']})": d['id']
            for d in all_docs
        }
        selected_label = st.selectbox("Select Document to Inspect:", options=list(doc_options.keys()))
        selected_id = doc_options[selected_label]

        doc = db_repository.get_document_by_id(selected_id)
        if doc:
            st.divider()

            # Metadata header
            d_type = doc["document_type"]
            d_status = doc["status"]
            status_cls = "status-processed" if d_status == "Processed" else ("status-review" if d_status == "Needs Review" else "status-failed")
            type_cls = "type-invoice" if d_type == "Invoice" else ("type-resume" if d_type == "Resume" else "type-other")

            h_col1, h_col2, h_col3 = st.columns([3, 1, 1])
            with h_col1:
                st.markdown(f"### `{doc['original_filename']}`")
                st.caption(f"Stored as: `{doc['stored_filename']}` • Uploaded: `{doc['upload_date']}`")
            with h_col2:
                st.markdown(f"<span class='type-badge {type_cls}'>{d_type}</span>", unsafe_allow_html=True)
                st.caption(f"ML Confidence: {int(round(doc['confidence'] * 100))}%")
            with h_col3:
                st.markdown(f"<span class='status-badge {status_cls}'>{d_status}</span>", unsafe_allow_html=True)
                st.caption(f"Size: {round(doc['file_size'] / 1024, 1)} KB")

            # Extracted Fields Section
            st.markdown("##### 📌 Extracted Key Fields")
            f1, f2, f3, f4 = st.columns(4)
            if d_type == "Invoice":
                f1.metric("Company / Vendor", doc["company"])
                f2.metric("Invoice Number", doc["invoice_number"])
                f3.metric("Total Amount", doc["total_amount"])
                # Extract date from JSON if available
                date_val = "Not Found"
                try:
                    j_data = json.loads(doc.get("extracted_json", "{}"))
                    date_val = j_data.get("flat_values", {}).get("date", "Not Found")
                except Exception:
                    pass
                f4.metric("Invoice Date", date_val)
            elif d_type == "Resume":
                f1.metric("Candidate Name", doc["company"])
                f2.metric("Email Address", doc["invoice_number"])
                phone_val = "Not Found"
                skills_val = "Not Found"
                try:
                    j_data = json.loads(doc.get("extracted_json", "{}"))
                    phone_val = j_data.get("flat_values", {}).get("phone", "Not Found")
                    skills_val = j_data.get("flat_values", {}).get("skills", "Not Found")
                except Exception:
                    pass
                f3.metric("Phone", phone_val)
                f4.metric("Key Skills", f"{skills_val[:25]}..." if skills_val != "Not Found" else "Not Found")
            else:
                f1.metric("Document Title", doc["company"])
                f2.metric("Subject", doc["invoice_number"])
                f3.metric("Date Reference", doc["total_amount"])
                f4.metric("Category", "General Document")

            # Status Notes
            if doc.get("notes"):
                st.info(f"**Audit & Status Notes:** {doc['notes']}")

            # Storage & File Location
            st.markdown("##### 📂 File System Location & Cryptographic Verification")
            st.code(
                f"Absolute Path : {doc['file_path']}\n"
                f"SHA-256 Hash  : {doc['file_hash']}",
                language="text"
            )

            # Preview & Download actions
            st.markdown("##### 📥 Document Preview & Export")
            p_col1, p_col2 = st.columns([1, 2])
            
            with p_col1:
                # Download Button
                file_exists = os.path.exists(doc["file_path"])
                if file_exists:
                    with open(doc["file_path"], "rb") as f_down:
                        file_data = f_down.read()
                    st.download_button(
                        label="⬇️ Download Document File",
                        data=file_data,
                        file_name=doc["original_filename"],
                        mime=doc["mime_type"],
                        use_container_width=True
                    )
                else:
                    st.warning("Physical file not found at recorded path.")

            with p_col2:
                # Inline preview if image or text preview
                if file_exists and doc["mime_type"].startswith("image/"):
                    try:
                        img_preview = Image.open(doc["file_path"])
                        st.image(img_preview, caption="Document Image Preview", use_container_width=True)
                    except Exception as ie:
                        st.caption(f"Could not render image: {ie}")

            # Text preview
            st.markdown("##### 📝 Text Excerpt")
            st.text_area("", value=doc.get("text_preview", ""), height=120, disabled=True)

            # Management & Status Override Section
            st.divider()
            st.markdown("##### ⚙️ Record Management")
            m_col1, m_col2, m_col3 = st.columns([2, 2, 2])

            with m_col1:
                new_status = st.selectbox(
                    "Override Processing Status:",
                    options=["Processed", "Needs Review", "Failed"],
                    index=["Processed", "Needs Review", "Failed"].index(doc["status"]),
                    key=f"status_select_{doc['id']}"
                )
                if st.button("Update Status", key=f"btn_status_{doc['id']}"):
                    db_repository.update_document_status(doc["id"], new_status)
                    st.success(f"Status updated to '{new_status}'!")
                    st.rerun()

            with m_col2:
                st.write("")
                st.write("")
                # Edit field modal / expander
                with st.expander("✏️ Correct Extracted Fields"):
                    new_company = st.text_input("Entity / Company:", value=doc["company"], key=f"comp_{doc['id']}")
                    new_inv_no = st.text_input("Invoice / Identifier #:", value=doc["invoice_number"], key=f"inv_{doc['id']}")
                    new_amount = st.text_input("Total Amount / Metrics:", value=doc["total_amount"], key=f"amt_{doc['id']}")
                    if st.button("Save Corrections", key=f"save_corr_{doc['id']}"):
                        db_repository.update_document_fields(doc["id"], company=new_company, invoice_number=new_inv_no, total_amount=new_amount)
                        st.success("Fields updated in database!")
                        st.rerun()

            with m_col3:
                st.write("")
                st.write("")
                del_file_check = st.checkbox("Delete physical file from storage", value=True, key=f"del_chk_{doc['id']}")
                if st.button("🗑️ Delete Document Record", type="secondary", key=f"del_btn_{doc['id']}"):
                    ok, msg = db_repository.delete_document(doc["id"], delete_file_from_disk=del_file_check)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)


# ==============================================================================
# TAB 4: REPOSITORY ANALYTICS (Dashboard & Integrity)
# ==============================================================================

with tab_analytics:
    st.markdown("#### 📊 Repository Metrics & Health")
    cur_stats = db_repository.get_repository_stats()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Documents", cur_stats["total_documents"])
    m2.metric("Processed", cur_stats["statuses"].get("Processed", 0))
    m3.metric("Needs Review", cur_stats["statuses"].get("Needs Review", 0))
    m4.metric("Total Storage (KB)", round(cur_stats["total_bytes"] / 1024, 1))

    st.divider()
    c_chart1, c_chart2 = st.columns(2)

    with c_chart1:
        st.markdown("##### 📑 Document Distribution by Category")
        types_df = pd.DataFrame([
            {"Category": k, "Count": v}
            for k, v in cur_stats["types"].items()
        ])
        st.bar_chart(types_df.set_index("Category"))

    with c_chart2:
        st.markdown("##### 🚦 Processing Status Breakdown")
        status_df = pd.DataFrame([
            {"Status": k, "Count": v}
            for k, v in cur_stats["statuses"].items()
        ])
        st.bar_chart(status_df.set_index("Status"))

    st.markdown("##### 📁 Storage Directory Inspection")
    inv_count = len(os.listdir(os.path.join(storage_manager.STORAGE_BASE_DIR, "invoices"))) if os.path.exists(os.path.join(storage_manager.STORAGE_BASE_DIR, "invoices")) else 0
    res_count = len(os.listdir(os.path.join(storage_manager.STORAGE_BASE_DIR, "resumes"))) if os.path.exists(os.path.join(storage_manager.STORAGE_BASE_DIR, "resumes")) else 0
    oth_count = len(os.listdir(os.path.join(storage_manager.STORAGE_BASE_DIR, "other"))) if os.path.exists(os.path.join(storage_manager.STORAGE_BASE_DIR, "other")) else 0

    s1, s2, s3 = st.columns(3)
    s1.metric("Storage: Invoices Folder", f"{inv_count} files")
    s2.metric("Storage: Resumes Folder", f"{res_count} files")
    s3.metric("Storage: Other Folder", f"{oth_count} files")
