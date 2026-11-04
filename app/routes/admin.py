import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

from ..config import settings
from ..db import Repository
from ..services import (
    ADMIN_COOKIE_NAME,
    create_admin_session,
    generate_csv_export,
    generate_excel_export,
    get_authenticated_admin,
    get_presentation_file_path,
    verify_password,
)

log = logging.getLogger("hackathon.admin")
router = APIRouter()


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/api/admin/login")
def admin_login(body: LoginIn, response: Response):
    expected_user = settings.ADMIN_USERNAME
    expected_pass = settings.ADMIN_PASSWORD

    if not expected_user or not expected_pass:
        raise HTTPException(status_code=500, detail="Admin credentials not configured in environment.")

    if body.username != expected_user or not verify_password(body.password, expected_pass):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = create_admin_session(body.username)
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=60 * 60 * 12,  # 12 hours
    )
    return {"ok": True, "user": body.username, "token": token}


@router.post("/api/admin/logout")
def admin_logout(response: Response):
    response.delete_cookie(ADMIN_COOKIE_NAME)
    return {"ok": True, "message": "Logged out successfully."}


@router.get("/api/admin/me")
def admin_me(user: str = Depends(get_authenticated_admin)):
    return {"ok": True, "user": user}


@router.get("/api/admin/metrics")
def get_admin_metrics(user: str = Depends(get_authenticated_admin)):
    return Repository.get_metrics()


@router.get("/api/admin/registrations")
def list_registrations(
    q: str = Query("", description="Search term"),
    track: str = Query("", description="Filter track"),
    review_status: str = Query("", description="Filter review status"),
    payment_status: str = Query("", description="Filter payment status"),
    user: str = Depends(get_authenticated_admin),
):
    regs = Repository.get_all_registrations(
        query=q,
        track=track,
        review_status=review_status,
        payment_status=payment_status,
    )
    return {"registrations": regs, "count": len(regs)}


@router.get("/api/admin/registration/{reg_id}")
def get_registration_dossier(
    reg_id: str,
    user: str = Depends(get_authenticated_admin),
):
    reg = Repository.get_registration_by_id(reg_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found.")
    return reg


class StatusUpdateIn(BaseModel):
    review_status: str
    admin_notes: Optional[str] = ""


@router.post("/api/admin/registration/{reg_id}/status")
def update_status(
    reg_id: str,
    body: StatusUpdateIn,
    user: str = Depends(get_authenticated_admin),
):
    valid_statuses = {"submitted", "under_review", "shortlisted", "waitlist", "rejected"}
    if body.review_status not in valid_statuses:
        raise HTTPException(status_code=422, detail="Invalid review status.")

    ok = Repository.update_review_status(
        reg_id=reg_id,
        status=body.review_status,
        admin_notes=body.admin_notes or "",
        admin_user=user,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Registration not found or update failed.")
    return {"ok": True, "message": "Review status updated successfully."}


# Requirement 18: Admin Edit Participant and Team Details
class RegistrationUpdateIn(BaseModel):
    team_name: Optional[str] = None
    college_name: Optional[str] = None
    track: Optional[str] = None
    leader_name: Optional[str] = None
    leader_email: Optional[str] = None
    leader_phone: Optional[str] = None
    leader_department: Optional[str] = None
    leader_year: Optional[str] = None
    members_data: Optional[List[Dict[str, Any]]] = None
    idea_title: Optional[str] = None
    idea_summary: Optional[str] = None
    idea_description: Optional[str] = None
    payment_status: Optional[str] = None
    admin_notes: Optional[str] = None
    edit_reason: Optional[str] = "Admin manual modification"


@router.put("/api/admin/registration/{reg_id}")
def update_registration_details(
    reg_id: str,
    body: RegistrationUpdateIn,
    user: str = Depends(get_authenticated_admin),
):
    existing = Repository.get_registration_by_id(reg_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Registration not found.")

    payload = body.dict(exclude_unset=True)
    edit_reason = payload.pop("edit_reason", "Admin manual update")

    # If team_name is changing, check uniqueness
    if "team_name" in payload and payload["team_name"].strip().lower() != existing["team_name"].strip().lower():
        if Repository.is_team_name_taken(payload["team_name"], exclude_id=reg_id):
            raise HTTPException(status_code=422, detail="This team name is already taken by another team.")

    updated = Repository.update_registration_details(
        reg_id=reg_id,
        updated_fields=payload,
        admin_user=user,
        notes=edit_reason,
    )
    if not updated:
        raise HTTPException(status_code=400, detail="Could not update registration.")

    return {"ok": True, "message": "Participant and team details updated successfully.", "registration": updated}


# Requirement 18: Action Audit Trail Table endpoint
@router.get("/api/admin/audit-logs")
def get_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    reg_id: Optional[str] = None,
    user: str = Depends(get_authenticated_admin),
):
    logs = Repository.get_audit_logs(limit=limit, registration_id=reg_id)
    return {"ok": True, "logs": logs, "count": len(logs)}


@router.get("/api/admin/registration/{reg_id}/file")
def download_presentation_file(
    reg_id: str,
    user: str = Depends(get_authenticated_admin),
):
    reg = Repository.get_registration_by_id(reg_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found.")

    stored_key = reg.get("idea_ppt_path")
    original_name = reg.get("idea_ppt_filename") or f"{reg.get('team_code')}_presentation.pptx"

    if not stored_key:
        if reg.get("google_drive_web_link"):
            return RedirectResponse(reg["google_drive_web_link"])
        raise HTTPException(status_code=404, detail="No file attached to this registration.")

    # If Supabase storage is used:
    if settings.has_supabase:
        try:
            from ..db import get_supabase_client
            client = get_supabase_client()
            signed_url_res = client.storage.from_(settings.SUPABASE_BUCKET).create_signed_url(stored_key, 60)
            if signed_url_res and "signedURL" in signed_url_res:
                return RedirectResponse(signed_url_res["signedURL"])
        except Exception:
            pass

    # Local fallback
    local_path = get_presentation_file_path(stored_key)
    if not local_path or not local_path.exists():
        if reg.get("google_drive_web_link"):
            return RedirectResponse(reg["google_drive_web_link"])
        raise HTTPException(status_code=404, detail="Stored file could not be found.")

    media_type = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if original_name.endswith(".pptx")
        else "application/vnd.ms-powerpoint"
    )

    return FileResponse(
        path=local_path,
        filename=original_name,
        media_type=media_type,
    )


@router.delete("/api/admin/registration/{reg_id}")
def delete_registration(
    reg_id: str,
    user: str = Depends(get_authenticated_admin),
):
    file_path = Repository.delete_registration(reg_id, admin_user=user)
    if file_path:
        local_p = get_presentation_file_path(file_path)
        if local_p and local_p.exists():
            try:
                local_p.unlink()
            except Exception:
                pass
    return {"ok": True, "message": "Registration deleted successfully."}


@router.get("/api/admin/export/excel")
def export_excel(user: str = Depends(get_authenticated_admin)):
    regs = Repository.get_all_registrations()
    buf = generate_excel_export(regs)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=JM_Vertex_Hackathon_Registrations.xlsx"}
    )


@router.get("/api/admin/export/csv")
def export_csv(user: str = Depends(get_authenticated_admin)):
    regs = Repository.get_all_registrations()
    csv_str = generate_csv_export(regs)
    bom_csv = "\ufeff" + csv_str
    return Response(
        content=bom_csv.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=JM_Vertex_Hackathon_Registrations.csv"}
    )
