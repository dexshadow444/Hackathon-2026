import csv
import hashlib
import hmac
import io
import json
import logging
import os
import random
import re
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

log = logging.getLogger("hackathon.services")

# Admin Session Serializer
_signer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="admin-session-auth")
ADMIN_COOKIE_NAME = "hackathon_admin_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12  # 12 hours


def hash_password(password: str) -> str:
    salt = settings.SECRET_KEY[:16]
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


def verify_password(plain_password: str, expected_password: str) -> bool:
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
        "fee_per_member_inr": settings.REGISTRATION_FEE_PER_MEMBER_INR,
        "fee_inr": settings.REGISTRATION_FEE_PER_MEMBER_INR,
        "min_members": settings.MIN_TEAM_MEMBERS,
        "max_members": settings.MAX_TEAM_MEMBERS,
        "location": settings.EVENT_LOCATION,
    }


def generate_team_code() -> str:
    """Generates unique team code in format HACK-27-{seq}-{suffix4}."""
    seq = next_team_sequence()
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=4))
    return f"HACK-27-{seq:03d}-{suffix}"


# ---------------- File Upload Validation & Storage ----------------
# Requirement 13: STRICTLY PPT and PPTX only
ALLOWED_EXTENSIONS = {".pptx", ".ppt"}
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


def extract_drive_folder_id() -> str:
    """Extracts or returns the Google Drive folder ID configured in .env."""
    if settings.GOOGLE_DRIVE_FOLDER_ID:
        return settings.GOOGLE_DRIVE_FOLDER_ID
    if settings.GOOGLE_DRIVE_FOLDER_URL:
        # Match .../folders/([a-zA-Z0-9_-]+)
        m = re.search(r"folders/([a-zA-Z0-9_-]+)", settings.GOOGLE_DRIVE_FOLDER_URL)
        if m:
            return m.group(1)
    return ""


async def upload_to_google_drive(contents: bytes, filename: str, team_code: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempts to upload the presentation file directly to Google Drive
    using Service Account credentials if configured in .env.
    Returns (drive_file_id, web_view_link).
    """
    folder_id = extract_drive_folder_id()
    if not (settings.GOOGLE_SERVICE_ACCOUNT_JSON or settings.GOOGLE_SERVICE_ACCOUNT_FILE):
        # Service account credentials not provided: fall back gracefully to folder URL link
        return None, settings.GOOGLE_DRIVE_FOLDER_URL

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload

        scopes = ['https://www.googleapis.com/auth/drive.file']
        creds = None
        if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
            info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
            creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        elif settings.GOOGLE_SERVICE_ACCOUNT_FILE and os.path.exists(settings.GOOGLE_SERVICE_ACCOUNT_FILE):
            creds = service_account.Credentials.from_service_account_file(settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scopes)

        if not creds:
            return None, settings.GOOGLE_DRIVE_FOLDER_URL

        drive_service = build('drive', 'v3', credentials=creds)

        file_metadata = {
            'name': f"{team_code}_{filename}",
        }
        if folder_id:
            file_metadata['parents'] = [folder_id]

        media = MediaIoBaseUpload(
            io.BytesIO(contents),
            mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation'
            if filename.endswith('.pptx') else 'application/vnd.ms-powerpoint',
            resumable=True
        )

        drive_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, webContentLink'
        ).execute()

        file_id = drive_file.get('id')
        web_link = drive_file.get('webViewLink') or drive_file.get('webContentLink') or settings.GOOGLE_DRIVE_FOLDER_URL
        return file_id, web_link
    except Exception as e:
        log.warning("Google Drive direct upload failed (%s); fallback to local/folder link.", e)
        return None, settings.GOOGLE_DRIVE_FOLDER_URL


async def save_uploaded_presentation(file: UploadFile, team_code: str = "") -> Tuple[str, str, Optional[str], Optional[str]]:
    """
    Validates extension and size, saves file under randomised filename in private location.
    Also handles Google Drive integration.
    Returns (original_filename, stored_path_or_key, drive_file_id, drive_web_link).
    """
    if not file.filename:
        raise HTTPException(status_code=422, detail="Presentation file is required.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid file type '{ext}'. Strictly only .pptx and .ppt PowerPoint presentations are accepted.",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=422,
            detail="File size exceeds the 10 MB limit. Please compress or select a smaller presentation deck.",
        )

    random_name = f"{uuid.uuid4().hex}{ext}"

    # Google Drive upload integration
    drive_file_id, drive_web_link = await upload_to_google_drive(contents, file.filename, team_code or "HACK27")

    # If Supabase storage is configured:
    if settings.has_supabase:
        try:
            from .db import get_supabase_client
            client = get_supabase_client()
            content_type = file.content_type or "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            client.storage.from_(settings.SUPABASE_BUCKET).upload(
                path=random_name,
                file=contents,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            return file.filename, random_name, drive_file_id, drive_web_link
        except Exception:
            pass

    # Local storage
    dest = UPLOAD_DIR / random_name
    with open(dest, "wb") as f:
        f.write(contents)

    return file.filename, random_name, drive_file_id, drive_web_link


def get_presentation_file_path(filename_or_key: str) -> Optional[Path]:
    """Returns local path if file exists locally."""
    local_path = UPLOAD_DIR / filename_or_key
    if local_path.exists():
        return local_path
    return None


# ---------------- Payment (Razorpay & Sandbox) ----------------
def create_payment_order(team_code: str, amount_inr: int = 99) -> Dict[str, Any]:
    amount_paise = amount_inr * 100

    if settings.has_razorpay:
        try:
            import razorpay
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            order_data = {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": team_code,
                "notes": {"team_code": team_code, "amount_inr": amount_inr},
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
        return True

    return False


# ---------------- Export Helpers (Excel & CSV) ----------------
def generate_excel_export(registrations: list[dict]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hackathon Registrations"

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
        "Leader Gender", "Leader ID", "Total Team Members",
        # Up to 4 Crew Members (min 2 to max 5 total members)
        "Member 1 Name", "Member 1 Mobile", "Member 1 Email", "Member 1 Dept", "Member 1 Year",
        "Member 2 Name", "Member 2 Mobile", "Member 2 Email", "Member 2 Dept", "Member 2 Year",
        "Member 3 Name", "Member 3 Mobile", "Member 3 Email", "Member 3 Dept", "Member 3 Year",
        "Member 4 Name", "Member 4 Mobile", "Member 4 Email", "Member 4 Dept", "Member 4 Year",
        "Idea Title", "Idea Summary", "Idea Presentation File", "Google Drive Link",
        "Terms Accepted", "Terms Version", "Terms Accepted At (UTC)",
        "Admin Notes", "Registration Date"
    ]

    ws.append(headers)

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border

    ws.row_dimensions[1].height = 28

    for row_idx, reg in enumerate(registrations, start=2):
        members = reg.get("members_data") or []
        if isinstance(members, str):
            try:
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

        # 4 crew slots (total team up to 5)
        for i in range(4):
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
            reg.get("google_drive_web_link") or settings.GOOGLE_DRIVE_FOLDER_URL,
            "Yes" if reg.get("terms_accepted") else "No",
            reg.get("terms_version", TERMS_VERSION),
            reg.get("terms_accepted_at", ""),
            reg.get("admin_notes", ""),
            reg.get("created_at", ""),
        ])

        ws.append(row_data)

        for col_idx in range(1, len(row_data) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = data_font
            cell.border = thin_border
            cell.alignment = left_align

            if col_idx == 5:
                status = str(cell.value).upper()
                if status == "PAID":
                    cell.fill = PatternFill(start_color="E6F6EC", end_color="E6F6EC", fill_type="solid")
                    cell.font = Font(name="Calibri", bold=True, color="0F6B3F")
                else:
                    cell.fill = PatternFill(start_color="FFF3E0", end_color="FFF3E0", fill_type="solid")
                    cell.font = Font(name="Calibri", bold=True, color="B26A00")
                cell.alignment = center_align

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
        "Idea Title", "Drive Link", "Terms Accepted", "Terms Version", "Terms Accepted At (UTC)",
        "Admin Notes", "Created At"
    ]
    writer.writerow(headers)

    for reg in registrations:
        members = reg.get("members_data") or []
        if isinstance(members, str):
            try:
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

        for i in range(4):
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
            reg.get("google_drive_web_link") or settings.GOOGLE_DRIVE_FOLDER_URL,
            "true" if reg.get("terms_accepted") else "false",
            reg.get("terms_version", TERMS_VERSION),
            reg.get("terms_accepted_at", ""),
            reg.get("admin_notes", ""),
            reg.get("created_at", ""),
        ])
        writer.writerow(row)

    return buf.getvalue()
