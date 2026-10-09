"""
ZYROO INTERNSHIP PROGRAM - WEEK 6
Module: Production-Facing REST API & Integration Endpoints
Focus: OpenAPI/Swagger documentation, Pydantic validation, RBAC, and standard HTTP error handling
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config
import database
import storage
import workflow
import rag_engine
import audit

logger = logging.getLogger("zyroo_api")

# Initialize database schema on startup
database.init_db()
storage.ensure_storage_structure()

app = FastAPI(
    title="ZYROO AI Document Intelligence & Workflow Platform API",
    description="Enterprise REST API for automated document ingestion, classification, validation, anomaly detection, human review, RAG assistant, and audit trails.",
    version="6.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for cross-origin integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# PYDANTIC SCHEMAS
# ==============================================================================

class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "6.0.0"
    database_connected: bool = True
    storage_accessible: bool = True
    classifier_model_ready: bool = True
    rag_engine_ready: bool = True


class ReviewRequest(BaseModel):
    action: str = Field(..., description="Action to perform: 'APPROVE' or 'REJECT'")
    notes: Optional[str] = Field(default="", description="Reviewer notes or mandatory rejection justification")
    performed_by: Optional[str] = Field(default="API Reviewer", description="Identity of reviewer")
    role: Optional[str] = Field(default=config.ROLE_REVIEWER, description="User role: Admin, Reviewer, or Viewer")


class EditFieldsRequest(BaseModel):
    fields: Dict[str, Any] = Field(..., description="Dictionary of corrected field values")
    performed_by: Optional[str] = Field(default="API Reviewer", description="Identity of editor")


class AssistantQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Question to answer from document intelligence corpus")
    document_id: Optional[int] = Field(default=None, description="Optional target document ID for scoped answering")


class CitationItem(BaseModel):
    document_id: int
    filename: str
    page_number: int
    chunk_index: int
    relevance_percentage: str
    excerpt: str


class AssistantQueryResponse(BaseModel):
    query: str
    success: bool
    answer: str
    citations: List[CitationItem]
    retrieved_chunks_count: int
    max_similarity: float
    is_grounded: bool
    has_sufficient_information: bool


# ==============================================================================
# AUTH & RBAC DEPENDENCIES
# ==============================================================================

def verify_user_role(x_user_role: Optional[str] = Header(default=config.ROLE_REVIEWER)) -> str:
    """Extracts and validates role from header."""
    role = (x_user_role or config.ROLE_REVIEWER).capitalize()
    if role not in config.VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid X-User-Role '{role}'. Allowed roles: {config.VALID_ROLES}."
        )
    return role


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@app.get("/api/v1/health", response_model=HealthResponse, tags=["System Health"])
def get_health():
    """System health diagnostics and service availability."""
    db_ok = True
    try:
        conn = database.get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception:
        db_ok = False

    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        version="6.0.0",
        database_connected=db_ok,
        storage_accessible=os.path.exists(config.STORAGE_DIR),
        classifier_model_ready=True,
        rag_engine_ready=True
    )


@app.post("/api/v1/documents/upload", tags=["Document Ingestion"])
async def upload_document(
    file: UploadFile = File(...),
    apply_ocr: bool = Form(default=True)
):
    """
    Ingests a document through the full production pipeline:
    Validate → Hash → Read/OCR → Classify → Extract → Validate → Anomaly Check → RAG Index → Rule Decision
    """
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to read upload stream: {e}")

    result = workflow.ingest_and_execute_workflow(
        file_bytes=file_bytes,
        original_filename=file.filename or "uploaded_file",
        apply_ocr_preprocessing=apply_ocr
    )

    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message"))

    # If duplicate
    if result.get("is_duplicate"):
        return {
            "status": "duplicate",
            "message": result.get("message"),
            "document_id": result.get("document_id"),
            "file_hash": result.get("file_hash"),
            "document_record": result.get("document_record")
        }

    return result


@app.post("/api/v1/documents/batch-upload", tags=["Document Ingestion"])
async def upload_documents_batch(
    files: List[UploadFile] = File(...),
    apply_ocr: bool = Form(default=True)
):
    """
    Batch ingestion endpoint with fault-tolerant processing:
    Individual document failures do not abort or cancel remaining documents.
    """
    file_tuples = []
    for f in files:
        b = await f.read()
        file_tuples.append((f.filename or "file", b))

    batch_summary = workflow.process_batch_files(
        file_tuples=file_tuples,
        apply_ocr=apply_ocr
    )
    return batch_summary


@app.get("/api/v1/documents", tags=["Document Repository"])
def list_documents(
    query: Optional[str] = Query(default=None, description="Search across filename, company, invoice number, or text"),
    status_filter: Optional[str] = Query(default="All", description="Filter by workflow status"),
    type_filter: Optional[str] = Query(default="All", description="Filter by document type"),
    anomaly_only: bool = Query(default=False, description="Filter documents with anomaly alerts")
):
    """Lists repository documents with multi-field search and status filtering."""
    docs = database.search_documents(
        query=query,
        status_filter=status_filter,
        type_filter=type_filter,
        anomaly_only=anomaly_only
    )
    return {
        "count": len(docs),
        "documents": docs
    }


@app.get("/api/v1/documents/{doc_id}", tags=["Document Repository"])
def get_document_details(doc_id: int):
    """Retrieves document record, extracted JSON, validation result, anomalies and audit history."""
    doc = database.get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document #{doc_id} not found.")

    audit_history = audit.get_document_history(doc_id)
    return {
        "document": doc,
        "extracted_data": json.loads(doc.get("extracted_json") or "{}"),
        "validation_data": json.loads(doc.get("validation_json") or "{}"),
        "anomaly_data": json.loads(doc.get("anomaly_json") or "{}"),
        "audit_trail": audit_history
    }


@app.post("/api/v1/documents/{doc_id}/review", tags=["Review Queue & Actions"])
def review_document(
    doc_id: int,
    req: ReviewRequest,
    user_role: str = Depends(verify_user_role)
):
    """
    Executes human review decision: Approve or Reject.
    Enforces Role-Based Access Control and mandatory rejection reason.
    """
    action_upper = req.action.strip().upper()
    role_to_use = req.role if req.role in config.VALID_ROLES else user_role

    if action_upper == "APPROVE":
        success, msg = workflow.approve_document(
            doc_id=doc_id,
            reviewer_notes=req.notes or "",
            performed_by=req.performed_by or "API Reviewer",
            user_role=role_to_use
        )
    elif action_upper == "REJECT":
        success, msg = workflow.reject_document(
            doc_id=doc_id,
            rejection_reason=req.notes or "",
            performed_by=req.performed_by or "API Reviewer",
            user_role=role_to_use
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action '{req.action}'. Expected 'APPROVE' or 'REJECT'."
        )

    if not success:
        if "Access Denied" in msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    doc = database.get_document_by_id(doc_id)
    return {
        "success": True,
        "message": msg,
        "document_id": doc_id,
        "new_status": doc.get("status") if doc else "Unknown"
    }


@app.post("/api/v1/documents/{doc_id}/edit-fields", tags=["Review Queue & Actions"])
def edit_fields(
    doc_id: int,
    req: EditFieldsRequest,
    user_role: str = Depends(verify_user_role)
):
    """Updates extracted fields for document in review and executes re-validation."""
    if user_role == config.ROLE_VIEWER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role 'Viewer' has read-only access.")

    success, msg, val_result = workflow.edit_document_fields(
        doc_id=doc_id,
        updated_fields=req.fields,
        performed_by=req.performed_by or "API Reviewer"
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    return {
        "success": True,
        "message": msg,
        "validation_result": val_result
    }


@app.post("/api/v1/assistant/query", response_model=AssistantQueryResponse, tags=["AI Assistant & RAG"])
def query_ai_assistant(req: AssistantQueryRequest):
    """
    RAG Assistant Question Answering:
    - Semantically searches indexed document chunks
    - Grounds answers strictly in source documents
    - Produces precise citations (document, page, snippet)
    - Returns negative statement if documents do not contain enough information
    """
    res = rag_engine.answer_document_query(
        query=req.query,
        document_id=req.document_id
    )

    citations = [
        CitationItem(
            document_id=c["document_id"],
            filename=c["filename"],
            page_number=c["page_number"],
            chunk_index=c.get("chunk_index", 0),
            relevance_percentage=c["relevance_percentage"],
            excerpt=c["excerpt"]
        )
        for c in res.get("citations", [])
    ]

    return AssistantQueryResponse(
        query=req.query,
        success=res.get("success", True),
        answer=res.get("answer", ""),
        citations=citations,
        retrieved_chunks_count=res.get("retrieved_chunks_count", 0),
        max_similarity=res.get("max_similarity", 0.0),
        is_grounded=res.get("is_grounded", True),
        has_sufficient_information=res.get("has_sufficient_information", True)
    )


@app.get("/api/v1/analytics/dashboard", tags=["Analytics & Reporting"])
def get_analytics_dashboard():
    """Aggregated platform KPIs, workflow distributions, and latency metrics."""
    return database.get_workflow_metrics()


@app.get("/api/v1/audit/recent", tags=["Audit & Governance"])
def get_recent_audit_trail(limit: int = Query(default=50, ge=1, le=200)):
    """System-wide immutable audit trail events."""
    return audit.get_system_audit_trail(limit=limit)
