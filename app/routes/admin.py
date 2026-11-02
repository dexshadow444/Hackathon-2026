import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
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
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Registration not found or update failed.")
    return {"ok": True, "message": "Review status updated successfully."}


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
        raise HTTPException(status_code=404, detail="No file attached to this registration.")

    # If Supabase storage is used:
    if settings.has_supabase:
        try:
            from ..db import get_supabase_client
            client = get_supabase_client()
            signed_url_res = client.storage.from_(settings.SUPABASE_BUCKET).create_signed_url(stored_key, 60)
            if signed_url_res and "signedURL" in signed_url_res:
                from fastapi.responses import RedirectResponse
                return RedirectResponse(signed_url_res["signedURL"])
        except Exception:
            pass

    # Local fallback
    local_path = get_presentation_file_path(stored_key)
    if not local_path or not local_path.exists():
        raise HTTPException(status_code=404, detail="Stored file could not be found.")

    media_type = "application/octet-stream"
    if original_name.endswith(".pdf"):
        media_type = "application/pdf"
    elif original_name.endswith(".pptx"):
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif original_name.endswith(".ppt"):
        media_type = "application/vnd.ms-powerpoint"

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
    file_path = Repository.delete_registration(reg_id)
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
    # Include UTF-8 BOM so Excel opens accents and symbols cleanly
    bom_csv = "\ufeff" + csv_str
    return Response(
        content=bom_csv.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=JM_Vertex_Hackathon_Registrations.csv"}
    )
