import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, StringConstraints, field_validator

from .. import content
from ..config import settings
from ..content import TERMS_CHECKBOX_LABEL, TERMS_POINTS, TERMS_VERSION
from ..db import Repository
from ..limiter import limiter
from ..services import (
    create_payment_order,
    generate_team_code,
    get_presentation_file_path,
    registration_info,
    registration_state,
    save_uploaded_presentation,
    verify_payment,
)

log = logging.getLogger("hackathon.public")
router = APIRouter()

ASSETS = Path(__file__).resolve().parent.parent / "assets"
NOT_SURE = "Not sure yet"

INDIAN_MOBILE_REGEX = re.compile(r"^[6-9]\d{9}$")


def validate_mobile(phone: str, field_name: str = "Mobile number") -> str:
    cleaned = re.sub(r"\s+|-", "", phone.strip())
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = cleaned[1:]
    if not INDIAN_MOBILE_REGEX.match(cleaned):
        raise HTTPException(
            status_code=422,
            detail={field_name: "Must be a valid 10-digit Indian mobile number starting with 6–9."}
        )
    return cleaned


@router.get("/api/config")
def get_config():
    s = settings
    return {
        "event": {
            "name": s.EVENT_NAME,
            "tagline": s.TAGLINE,
            "organiser": s.ORGANISER,
            "venue": s.VENUE,
            "location": s.EVENT_LOCATION,
            "about": content.ABOUT,
            "start": s.HACKATHON_START_DATE.isoformat(),
            "end": s.HACKATHON_END_DATE.isoformat(),
        },
        "tracks": content.TRACKS,
        "fee_per_member_inr": s.REGISTRATION_FEE_PER_MEMBER_INR,
        "fee_inr": s.REGISTRATION_FEE_PER_MEMBER_INR,
        "team_size": {"min": s.MIN_TEAM_MEMBERS, "max": s.MAX_TEAM_MEMBERS},
        "timeline": [
            {"label": "Registration opens", "at": s.REGISTRATION_OPEN_DATE.isoformat()},
            {"label": "Registration deadline", "at": s.REGISTRATION_DEADLINE.isoformat()},
            {"label": "Hackathon kickoff", "at": s.HACKATHON_START_DATE.isoformat()},
            {"label": "Prototype showcase & finish", "at": s.HACKATHON_END_DATE.isoformat()},
        ],
        "faq": [{"q": q, "a": a} for q, a in content.FAQ],
        "contact": {"email": s.CONTACT_EMAIL, "phone": s.CONTACT_PHONE},
        "registration": registration_info(),
        "google_drive_folder_url": s.GOOGLE_DRIVE_FOLDER_URL,
        "terms": {
            "version": TERMS_VERSION,
            "checkbox_label": TERMS_CHECKBOX_LABEL,
            "points": TERMS_POINTS,
        },
    }


@router.get("/api/registration-status")
def registration_status():
    return registration_info()


@router.get("/api/stats")
def stats():
    paid_count = Repository.get_paid_teams_count()
    return {"paid_teams": paid_count}


@router.get("/api/check-team-name")
@limiter.limit("60/minute")
def check_team_name(request: Request, name: str = Query("", max_length=128)):
    cleaned = name.strip()
    if not cleaned:
        return {"available": False, "message": "Enter a team name."}
    if len(cleaned) < 2:
        return {"available": False, "message": "Team name must be at least 2 characters."}
    if len(cleaned) > 128:
        return {"available": False, "message": "Team name cannot exceed 128 characters."}

    taken = Repository.is_team_name_taken(cleaned)
    if taken:
        return {"available": False, "message": "This team name is already taken."}
    return {"available": True, "message": "This team name is available."}


class NotifyIn(BaseModel):
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    email: EmailStr
    college: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
    track_interest: str

    @field_validator("track_interest")
    @classmethod
    def valid_track(cls, v: str) -> str:
        if v not in content.TRACKS and v != NOT_SURE:
            raise ValueError("Choose one of the listed tracks.")
        return v


@router.post("/api/notify-me")
@limiter.limit("10/minute")
def notify_me(request: Request, body: NotifyIn):
    Repository.add_notify_lead(
        full_name=body.full_name,
        email=body.email,
        college=body.college,
        track_interest=body.track_interest,
    )
    return {"ok": True, "message": "Thank you! We will email you with updates as soon as registration opens."}


@router.get("/download/idea-template")
def download_idea_template():
    path = ASSETS / "idea-presentation-template.pptx"
    if not path.exists():
        return JSONResponse(status_code=404, content={"message": "Template file is not available."})
    return FileResponse(
        path,
        filename="Hackathon-Idea-Presentation-Template.pptx",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


# ---------- Registration API (Step 1, 2, 3 Form Submission) ----------
@router.post("/api/register")
@limiter.limit("15/minute")
async def register_team(
    request: Request,
    team_name: str = Form(...),
    college_name: str = Form(...),
    track: str = Form(...),
    leader_name: str = Form(...),
    leader_email: str = Form(...),
    leader_phone: str = Form(...),
    leader_department: str = Form(...),
    leader_year: str = Form(...),
    leader_gender: Optional[str] = Form(None),
    leader_id_number: Optional[str] = Form(None),
    members_data: str = Form(...),
    idea_title: str = Form(...),
    idea_summary: str = Form(...),
    idea_description: str = Form(...),
    idea_presentation: UploadFile = File(...),
    terms_accepted: str = Form(...),
):
    # 1. Check registration availability
    state = registration_state()
    if state != "open":
        raise HTTPException(
            status_code=403,
            detail="Registration is currently closed or has not opened yet."
        )

    # 2. Check Terms Acceptance (Section 6: HTTP 422 if missing or false)
    accepted_bool = terms_accepted.lower() in ("true", "1", "yes", "on")
    if not accepted_bool:
        raise HTTPException(
            status_code=422,
            detail={"terms_accepted": "You must accept the Terms & Conditions on behalf of your team to proceed."}
        )

    # 3. Clean and validate Team & Leader
    team_name = team_name.strip()
    if not (1 <= len(team_name) <= 128):
        raise HTTPException(status_code=422, detail={"team_name": "Team name must be between 1 and 128 characters."})
    if Repository.is_team_name_taken(team_name):
        raise HTTPException(status_code=422, detail={"team_name": "Team name is already taken. Please choose another."})

    college_name = college_name.strip()
    if not (1 <= len(college_name) <= 256):
        raise HTTPException(status_code=422, detail={"college_name": "College / Institution name is required (max 256 characters)."})

    track = track.strip()
    if track not in content.TRACKS:
        raise HTTPException(status_code=422, detail={"track": "Please select a valid hackathon track."})

    leader_name = leader_name.strip()
    if not (1 <= len(leader_name) <= 128):
        raise HTTPException(status_code=422, detail={"leader_name": "Team Leader name is required (max 128 characters)."})

    leader_phone_clean = validate_mobile(leader_phone, "leader_phone")

    leader_email = leader_email.strip()
    if "@" not in leader_email or "." not in leader_email:
        raise HTTPException(status_code=422, detail={"leader_email": "Enter a valid email address."})

    leader_department = leader_department.strip()
    if not leader_department:
        raise HTTPException(status_code=422, detail={"leader_department": "Leader department is required."})

    leader_year = leader_year.strip()
    if not leader_year:
        raise HTTPException(status_code=422, detail={"leader_year": "Leader year of study is required."})

    # 4. Validate Members (Crew: 1 to 4 members => total team size 2 to 5)
    try:
        members_list = json.loads(members_data)
        if not isinstance(members_list, list):
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=422, detail={"members_data": "Invalid member list format."})

    total_team_size = len(members_list) + 1
    if not (settings.MIN_TEAM_MEMBERS <= total_team_size <= settings.MAX_TEAM_MEMBERS):
        raise HTTPException(
            status_code=422,
            detail={"member_count": f"Total team size must be between {settings.MIN_TEAM_MEMBERS} and {settings.MAX_TEAM_MEMBERS} students (including leader). Currently: {total_team_size}."}
        )

    # Validate each member
    cleaned_members = []
    for idx, m in enumerate(members_list, start=1):
        m_name = (m.get("name") or "").strip()
        m_mobile = (m.get("mobile") or "").strip()
        m_email = (m.get("email") or "").strip()
        m_dept = (m.get("department") or "").strip()
        m_year = (m.get("year") or "").strip()

        if not m_name:
            raise HTTPException(status_code=422, detail={f"member_{idx}_name": f"Member #{idx} name is required."})
        m_mobile_clean = validate_mobile(m_mobile, f"member_{idx}_mobile")
        if "@" not in m_email or "." not in m_email:
            raise HTTPException(status_code=422, detail={f"member_{idx}_email": f"Member #{idx} email is invalid."})

        cleaned_members.append({
            "name": m_name,
            "mobile": m_mobile_clean,
            "email": m_email,
            "department": m_dept,
            "year": m_year,
        })

    # 5. Validate Idea Submission
    idea_title = idea_title.strip()
    if not (1 <= len(idea_title) <= 100):
        raise HTTPException(status_code=422, detail={"idea_title": "Idea title must be between 1 and 100 characters."})

    idea_summary = idea_summary.strip()
    if not (1 <= len(idea_summary) <= 10000):
        raise HTTPException(status_code=422, detail={"idea_summary": "Abstract must be between 1 and 10,000 characters."})

    idea_description = idea_description.strip()
    if not (1 <= len(idea_description) <= 50000):
        raise HTTPException(status_code=422, detail={"idea_description": "Idea description must be between 1 and 50,000 characters."})

    # 6. Generate unique team code first for file and payment linking
    team_code = generate_team_code()

    # 7. Save presentation file securely & link to Google Drive
    orig_filename, stored_path, drive_id, drive_link = await save_uploaded_presentation(
        idea_presentation, team_code=team_code
    )

    # 8. Dynamic Fee Calculation (₹99 per member)
    total_fee_inr = total_team_size * settings.REGISTRATION_FEE_PER_MEMBER_INR

    # Create a Razorpay payment order for the exact team fee.
    payment_order = create_payment_order(team_code, total_fee_inr)

    terms_now = datetime.now(timezone.utc).isoformat()

    registration_record = {
        "team_code": team_code,
        "team_name": team_name,
        "college_name": college_name,
        "track": track,
        "leader_name": leader_name,
        "leader_email": leader_email,
        "leader_phone": leader_phone_clean,
        "leader_department": leader_department,
        "leader_year": leader_year,
        "leader_gender": leader_gender or "",
        "leader_id_number": leader_id_number or "",
        "member_count": total_team_size,
        "members_data": cleaned_members,
        "idea_title": idea_title,
        "idea_summary": idea_summary,
        "idea_description": idea_description,
        "idea_ppt_filename": orig_filename,
        "idea_ppt_path": stored_path,
        "google_drive_file_id": drive_id,
        "google_drive_web_link": drive_link,
        "terms_accepted": True,
        "terms_version": TERMS_VERSION,
        "terms_accepted_at": terms_now,
        "amount_paid": 0,
        "payment_status": "pending",
        "payment_mode": "razorpay",
        "razorpay_order_id": payment_order["order_id"],
        "review_status": "submitted",
        "admin_notes": "",
    }

    saved = Repository.save_registration(registration_record)

    return {
        "ok": True,
        "team_code": team_code,
        "order": payment_order,
        "amount_inr": total_fee_inr,
        "fee_per_member": settings.REGISTRATION_FEE_PER_MEMBER_INR,
        "member_count": total_team_size,
        "team_name": team_name,
        "leader_name": leader_name,
        "leader_email": leader_email,
        "leader_phone": leader_phone_clean,
        "presentation_filename": orig_filename,
        "drive_link": drive_link or settings.GOOGLE_DRIVE_FOLDER_URL,
    }


class PaymentVerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/api/payment/verify")
def verify_registration_payment(body: PaymentVerifyIn):
    reg = Repository.get_registration_by_order_id(body.razorpay_order_id)
    if not reg:
        raise HTTPException(status_code=404, detail="Registration order not found.")

    is_valid = verify_payment(
        body.razorpay_order_id,
        body.razorpay_payment_id,
        body.razorpay_signature,
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail="Payment verification failed or signature is invalid.")

    # Calculate expected fee based on team member count
    member_cnt = reg.get("member_count") or (len(reg.get("members_data") or []) + 1)
    fee = float(member_cnt * settings.REGISTRATION_FEE_PER_MEMBER_INR)

    Repository.mark_payment_successful(
        reg_id=reg["id"],
        payment_id=body.razorpay_payment_id,
        signature=body.razorpay_signature,
        amount=fee,
    )

    return {
        "ok": True,
        "team_code": reg["team_code"],
        "redirect_url": f"/confirmation/{reg['team_code']}",
    }


@router.get("/api/registration/{team_code}")
def get_public_registration(team_code: str):
    """Provides ticket details for confirmation page."""
    reg = Repository.get_registration_by_team_code(team_code)
    if not reg:
        raise HTTPException(status_code=404, detail="Team code not found.")

    return {
        "team_code": reg["team_code"],
        "team_name": reg["team_name"],
        "college_name": reg["college_name"],
        "track": reg["track"],
        "leader_name": reg["leader_name"],
        "leader_email": reg["leader_email"],
        "leader_phone": reg["leader_phone"],
        "leader_department": reg["leader_department"],
        "leader_year": reg["leader_year"],
        "member_count": reg["member_count"],
        "members": reg.get("members_data") or [],
        "idea_title": reg["idea_title"],
        "idea_ppt_filename": reg.get("idea_ppt_filename"),
        "google_drive_web_link": reg.get("google_drive_web_link") or settings.GOOGLE_DRIVE_FOLDER_URL,
        "amount_paid": reg.get("amount_paid", 0),
        "payment_status": reg.get("payment_status", "pending"),
        "payment_id": reg.get("razorpay_payment_id", ""),
        "payment_timestamp": reg.get("payment_timestamp") or reg.get("created_at"),
        "terms_accepted_at": reg.get("terms_accepted_at"),
        "terms_version": reg.get("terms_version", TERMS_VERSION),
    }


# Requirement 15: Student can view their uploaded presentation by clicking the filename
@router.get("/api/file/view/{team_code}")
def view_uploaded_presentation(team_code: str):
    reg = Repository.get_registration_by_team_code(team_code)
    if not reg:
        raise HTTPException(status_code=404, detail="Team not found.")

    stored_path = reg.get("idea_ppt_path")
    original_name = reg.get("idea_ppt_filename") or f"{team_code}_presentation.pptx"

    if not stored_path:
        # Check if direct Google Drive link exists
        if reg.get("google_drive_web_link"):
            return RedirectResponse(reg["google_drive_web_link"])
        raise HTTPException(status_code=404, detail="No file attached to this registration.")

    # Supabase signed URL redirect if used
    if settings.has_supabase:
        try:
            from ..db import get_supabase_client
            client = get_supabase_client()
            signed_url_res = client.storage.from_(settings.SUPABASE_BUCKET).create_signed_url(stored_path, 300)
            if signed_url_res and "signedURL" in signed_url_res:
                return RedirectResponse(signed_url_res["signedURL"])
        except Exception:
            pass

    # Local file serve
    local_path = get_presentation_file_path(stored_path)
    if not local_path or not local_path.exists():
        if reg.get("google_drive_web_link"):
            return RedirectResponse(reg["google_drive_web_link"])
        raise HTTPException(status_code=404, detail="File could not be found.")

    media_type = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if original_name.endswith(".pptx")
        else "application/vnd.ms-powerpoint"
    )

    return FileResponse(
        path=local_path,
        filename=original_name,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{original_name}"'}
    )
