import csv
import hashlib
import hmac
import io
import os
import random
import string
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from fastapi import HTTPException, Request, UploadFile
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import IST, settings
from .content import TERMS_VERSION
from .db import UPLOAD_DIR, Repository, next_team_sequence

# Admin Session Serializer
_signer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="admin-session-auth")
ADMIN_COOKIE_NAME = "hackathon_admin_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12  # 12 hours


def hash_password(password: str) -> str:
    salt = settings.SECRET_KEY[:16]
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


def verify_password(plain_password: str, expected_password: str) -> bool:
    # If the configured password looks like a sha256 hash (64 hex), check hash; else check direct compare
    salt = settings.SECRET_KEY[:16]
    hashed_input = hashlib.sha256(f"{salt}{plain_password}".encode("utf-8")).hexdigest()
    if len(expected_password) == 64:
        return hmac.compare_digest(hashed_input, expected_password)
    return hmac.compare_digest(plain_password, expected_password)


def create_admin_session(username: str) -> str:
    return _signer.dumps({"user": username, "created_at": datetime.now(timezone.utc).isoformat()})


def verify_admin_session(token: str) -> Optional[str]:
    try:
        data = _signer.loads(token, max_age=SESSION_MAX_AGE_SECONDS)
        return data.get("user")
    except (BadSignature, SignatureExpired):
        return None


def get_authenticated_admin(request: Request) -> str:
    token = request.cookies.get(ADMIN_COOKIE_NAME)
    if not token:
        # Also check Authorization header Bearer token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        raise HTTPException(status_code=401, detail="Admin authentication required.")

    username = verify_admin_session(token)
    if not username:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please log in again.")
    return username


def registration_state(now: datetime | None = None) -> str:
    """Returns 'not_open', 'open' or 'closed'."""
    if settings.force_unlock:
        return "open"
    now = now or datetime.now(IST)
    if now < settings.REGISTRATION_OPEN_DATE:
        return "not_open"
    if now > settings.REGISTRATION_DEADLINE:
        return "closed"
    return "open"


def registration_info() -> dict:
    return {
        "state": registration_state(),
        "open_at": settings.REGISTRATION_OPEN_DATE.isoformat(),
        "deadline": settings.REGISTRATION_DEADLINE.isoformat(),
        "fee_inr": settings.REGISTRATION_FEE_INR,
    }


def generate_team_code() -> str:
    """Generates unique team code in format HACK-27-{seq}-{suffix4}."""
    seq = next_team_sequence()
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=4))
    return f"HACK-27-{seq:03d}-{suffix}"


# ---------------- File Upload Validation & Storage ----------------
ALLOWED_EXTENSIONS = {".pptx", ".ppt", ".pdf"}
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


async def save_uploaded_presentation(file: UploadFile) -> Tuple[str, str]:
    """
    Validates extension and size, saves file under randomised filename in private location.
    Returns (original_filename, stored_path_or_key).
    """
    if not file.filename:
        raise HTTPException(status_code=422, detail="Presentation file is required.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid file type '{ext}'. Only .pptx, .ppt, and .pdf files are accepted.",
        )

    # Read and check size
    contents = await file.read()
    if len(contents) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=422,
            detail="File size exceeds the 10 MB limit. Please compress or select a smaller file.",
        )

    random_name = f"{uuid.uuid4().hex}{ext}"

    # If Supabase storage is configured:
    if settings.has_supabase:
        try:
            from .db import get_supabase_client
            client = get_supabase_client()
            content_type = file.content_type or "application/octet-stream"
            client.storage.from_(settings.SUPABASE_BUCKET).upload(
                path=random_name,
                file=contents,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            return file.filename, random_name
        except Exception as e:
            # Fallback to local
            pass

    # Local private storage
    dest = UPLOAD_DIR / random_name
    with open(dest, "wb") as f:
        f.write(contents)

    return file.filename, random_name


def get_presentation_file_path(filename_or_key: str) -> Optional[Path]:
    """Returns local path if file exists locally."""
    local_path = UPLOAD_DIR / filename_or_key
    if local_path.exists():
        return local_path
    return None


# ---------------- Payment (Razorpay & Sandbox) ----------------
def create_payment_order(team_code: str, amount_inr: int = 500) -> Dict[str, Any]:
    amount_paise = amount_inr * 100

    if settings.has_razorpay:
        try:
            import razorpay
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            order_data = {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": team_code,
                "notes": {"team_code": team_code},
            }
            order = client.order.create(data=order_data)
            return {
                "order_id": order["id"],
                "amount": order["amount"],
                "currency": order["currency"],
                "key_id": settings.RAZORPAY_KEY_ID,
                "is_sandbox": False,
            }
        except Exception as e:
            if settings.is_production:
                raise HTTPException(status_code=500, detail="Payment gateway initialization failed.")

    # Sandbox mode (development only)
    if settings.is_production:
        raise HTTPException(status_code=500, detail="Razorpay keys not configured in production.")

    sandbox_order_id = f"order_sbx_{uuid.uuid4().hex[:12]}"
    return {
        "order_id": sandbox_order_id,
        "amount": amount_paise,
        "currency": "INR",
        "key_id": "rzp_test_sandbox_dummy",
        "is_sandbox": True,
    }


def verify_payment(
    order_id: str,
    payment_id: str,
    signature: str,
) -> bool:
    if settings.has_razorpay:
        try:
            import razorpay
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            params = {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            }
            client.utility.verify_payment_signature(params)
            return True
        except Exception:
            return False

    # Development Sandbox simulation
    if not settings.is_production and order_id.startswith("order_sbx_"):
        # Valid test signature verification
        return True

    return False


# ---------------- Export Helpers (Excel & CSV) ----------------
def generate_excel_export(registrations: list[dict]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hackathon Registrations"

    # Styling palette
    header_fill = PatternFill(start_color="147A47", end_color="147A47", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=10)
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='CFE5EC'),
        right=Side(style='thin', color='CFE5EC'),
        top=Side(style='thin', color='CFE5EC'),
        bottom=Side(style='thin', color='CFE5EC')
    )

    headers = [
        "Team Code", "Team Name", "College / Institution", "Hackathon Track",
        "Payment Status", "Amount (₹)", "Payment ID", "Review Status",
        "Leader Name", "Leader Email", "Leader Phone", "Leader Department", "Leader Year",
        "Leader Gender", "Leader ID", "Crew Count",
        # Member 1
        "Member 1 Name", "Member 1 Mobile", "Member 1 Email", "Member 1 Dept", "Member 1 Year",
        # Member 2
        "Member 2 Name", "Member 2 Mobile", "Member 2 Email", "Member 2 Dept", "Member 2 Year",
        # Member 3
        "Member 3 Name", "Member 3 Mobile", "Member 3 Email", "Member 3 Dept", "Member 3 Year",
        # Member 4 (Optional)
        "Member 4 Name", "Member 4 Mobile", "Member 4 Email", "Member 4 Dept", "Member 4 Year",
        # Member 5 (Optional)
        "Member 5 Name", "Member 5 Mobile", "Member 5 Email", "Member 5 Dept", "Member 5 Year",
        "Idea Title", "Idea Summary", "Idea File Name",
        "Terms Accepted", "Terms Version", "Terms Accepted At (UTC)",
        "Admin Notes", "Registration Date"
    ]

    ws.append(headers)

    # Style header row
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border

    ws.row_dimensions[1].height = 28

    # Populate rows
    for row_idx, reg in enumerate(registrations, start=2):
        members = reg.get("members_data") or []
        if isinstance(members, str):
            try:
                import json
                members = json.loads(members)
            except Exception:
                members = []

        row_data = [
            reg.get("team_code", ""),
            reg.get("team_name", ""),
            reg.get("college_name", ""),
            reg.get("track", ""),
            reg.get("payment_status", "").upper(),
            reg.get("amount_paid", 0),
            reg.get("razorpay_payment_id", ""),
            reg.get("review_status", "").replace("_", " ").title(),
            reg.get("leader_name", ""),
            reg.get("leader_email", ""),
            reg.get("leader_phone", ""),
            reg.get("leader_department", ""),
            reg.get("leader_year", ""),
            reg.get("leader_gender", "") or "",
            reg.get("leader_id_number", "") or "",
            reg.get("member_count", len(members) + 1),
        ]

        # 5 possible additional members (up to 6 total including leader)
        for i in range(5):
            if i < len(members):
                m = members[i]
                row_data.extend([
                    m.get("name", ""),
                    m.get("mobile", ""),
                    m.get("email", ""),
                    m.get("department", "") or "",
                    m.get("year", "") or "",
                ])
            else:
                row_data.extend(["", "", "", "", ""])

        row_data.extend([
            reg.get("idea_title", ""),
            (reg.get("idea_summary", "")[:500] + "...") if len(reg.get("idea_summary", "")) > 500 else reg.get("idea_summary", ""),
            reg.get("idea_ppt_filename", ""),
            "Yes" if reg.get("terms_accepted") else "No",
            reg.get("terms_version", TERMS_VERSION),
            reg.get("terms_accepted_at", ""),
            reg.get("admin_notes", ""),
            reg.get("created_at", ""),
        ])

        ws.append(row_data)

        # Style data cells
        for col_idx in range(1, len(row_data) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = data_font
            cell.border = thin_border
            cell.alignment = left_align

            # Color payment status
            if col_idx == 5:
                status = str(cell.value).upper()
                if status == "PAID":
                    cell.fill = PatternFill(start_color="E6F6EC", end_color="E6F6EC", fill_type="solid")
                    cell.font = Font(name="Calibri", bold=True, color="0F6B3F")
                else:
                    cell.fill = PatternFill(start_color="FFF3E0", end_color="FFF3E0", fill_type="solid")
                    cell.font = Font(name="Calibri", bold=True, color="B26A00")
                cell.alignment = center_align

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def generate_csv_export(registrations: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)

    headers = [
        "Team Code", "Team Name", "College", "Track", "Payment Status", "Amount Paid",
        "Payment ID", "Review Status", "Leader Name", "Leader Email", "Leader Phone",
        "Leader Department", "Leader Year", "Total Team Size",
        "Member 1 Name", "Member 1 Mobile", "Member 1 Email", "Member 1 Dept", "Member 1 Year",
        "Member 2 Name", "Member 2 Mobile", "Member 2 Email", "Member 2 Dept", "Member 2 Year",
        "Member 3 Name", "Member 3 Mobile", "Member 3 Email", "Member 3 Dept", "Member 3 Year",
        "Member 4 Name", "Member 4 Mobile", "Member 4 Email", "Member 4 Dept", "Member 4 Year",
        "Member 5 Name", "Member 5 Mobile", "Member 5 Email", "Member 5 Dept", "Member 5 Year",
        "Idea Title", "Terms Accepted", "Terms Version", "Terms Accepted At (UTC)",
        "Admin Notes", "Created At"
    ]
    writer.writerow(headers)

    for reg in registrations:
        members = reg.get("members_data") or []
        if isinstance(members, str):
            try:
                import json
                members = json.loads(members)
            except Exception:
                members = []

        row = [
            reg.get("team_code", ""),
            reg.get("team_name", ""),
            reg.get("college_name", ""),
            reg.get("track", ""),
            reg.get("payment_status", ""),
            reg.get("amount_paid", 0),
            reg.get("razorpay_payment_id", ""),
            reg.get("review_status", ""),
            reg.get("leader_name", ""),
            reg.get("leader_email", ""),
            reg.get("leader_phone", ""),
            reg.get("leader_department", ""),
            reg.get("leader_year", ""),
            reg.get("member_count", len(members) + 1),
        ]

        for i in range(5):
            if i < len(members):
                m = members[i]
                row.extend([
                    m.get("name", ""),
                    m.get("mobile", ""),
                    m.get("email", ""),
                    m.get("department", "") or "",
                    m.get("year", "") or "",
                ])
            else:
                row.extend(["", "", "", "", ""])

        row.extend([
            reg.get("idea_title", ""),
            "true" if reg.get("terms_accepted") else "false",
            reg.get("terms_version", TERMS_VERSION),
            reg.get("terms_accepted_at", ""),
            reg.get("admin_notes", ""),
            reg.get("created_at", ""),
        ])
        writer.writerow(row)

    return buf.getvalue()
