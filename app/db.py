import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import content
from .config import settings

log = logging.getLogger("hackathon.db")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
SQLITE_DB_PATH = DATA_DIR / "hackathon.db"

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class DatabaseNotConfigured(RuntimeError):
    pass


# ------------------ Local SQLite Fallback Setup ------------------
def _init_sqlite():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS registrations (
        id TEXT PRIMARY KEY,
        team_code TEXT UNIQUE NOT NULL,
        team_name TEXT NOT NULL,
        team_name_key TEXT UNIQUE NOT NULL,
        college_name TEXT NOT NULL,
        track TEXT NOT NULL,
        leader_name TEXT NOT NULL,
        leader_email TEXT NOT NULL,
        leader_phone TEXT NOT NULL,
        leader_department TEXT NOT NULL,
        leader_year TEXT NOT NULL,
        leader_gender TEXT,
        leader_id_number TEXT,
        member_count INTEGER NOT NULL,
        members_data TEXT NOT NULL DEFAULT '[]',
        idea_title TEXT NOT NULL,
        idea_summary TEXT NOT NULL,
        idea_description TEXT NOT NULL,
        idea_ppt_filename TEXT,
        idea_ppt_path TEXT,
        terms_accepted INTEGER NOT NULL DEFAULT 0,
        terms_version TEXT,
        terms_accepted_at TEXT,
        amount_paid REAL NOT NULL DEFAULT 0,
        payment_status TEXT NOT NULL DEFAULT 'pending',
        payment_mode TEXT,
        razorpay_order_id TEXT,
        razorpay_payment_id TEXT,
        razorpay_signature TEXT,
        payment_timestamp TEXT,
        review_status TEXT NOT NULL DEFAULT 'submitted',
        admin_notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS preregistration_alerts (
        id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        email_key TEXT UNIQUE NOT NULL,
        college TEXT NOT NULL,
        track_interest TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sequences (
        name TEXT PRIMARY KEY,
        val INTEGER NOT NULL
    );
    """)
    cur.execute("INSERT OR IGNORE INTO sequences (name, val) VALUES ('team_code_seq', 100);")
    conn.commit()
    conn.close()

_init_sqlite()


def get_sqlite_conn():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def next_team_sequence() -> int:
    """Returns the next auto-increment sequence for team codes."""
    if settings.has_supabase:
        try:
            client = get_supabase_client()
            res = client.rpc("next_team_seq").execute()
            if res.data:
                return int(res.data)
        except Exception:
            log.warning("Supabase sequence RPC failed; fallback to local sequence counter")

    conn = get_sqlite_conn()
    cur = conn.cursor()
    cur.execute("UPDATE sequences SET val = val + 1 WHERE name = 'team_code_seq'")
    cur.execute("SELECT val FROM sequences WHERE name = 'team_code_seq'")
    row = cur.fetchone()
    val = row[0] if row else 101
    conn.commit()
    conn.close()
    return val


def get_supabase_client():
    from supabase import Client, create_client
    if not settings.has_supabase:
        raise DatabaseNotConfigured("Supabase credentials not configured in environment.")
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


# ------------------ Unified Repository ------------------
class Repository:
    """
    Unified Data Access Layer:
    If Supabase credentials are configured, performs operations against Supabase.
    Otherwise, performs operations against local SQLite database so development, testing,
    and UI previews run completely smoothly out of the box.
    """

    @staticmethod
    def get_paid_teams_count() -> int:
        if settings.has_supabase:
            try:
                res = (
                    get_supabase_client().table("registrations")
                    .select("id", count="exact", head=True)
                    .eq("payment_status", "paid")
                    .execute()
                )
                return res.count or 0
            except Exception as e:
                log.warning("Supabase stats query error: %s", e)

        conn = get_sqlite_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM registrations WHERE payment_status = 'paid'")
        count = cur.fetchone()[0]
        conn.close()
        return count

    @staticmethod
    def is_team_name_taken(name: str) -> bool:
        key = name.strip().lower()
        if not key:
            return False

        if settings.has_supabase:
            try:
                res = (
                    get_supabase_client().table("registrations")
                    .select("id").eq("team_name_key", key).limit(1).execute()
                )
                return bool(res.data)
            except Exception as e:
                log.warning("Supabase check team name error: %s", e)

        conn = get_sqlite_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM registrations WHERE team_name_key = ? LIMIT 1", (key,))
        row = cur.fetchone()
        conn.close()
        return bool(row)

    @staticmethod
    def add_notify_lead(full_name: str, email: str, college: str, track_interest: str) -> bool:
        email_key = email.strip().lower()
        now = datetime.now(timezone.utc).isoformat()

        if settings.has_supabase:
            try:
                get_supabase_client().table("preregistration_alerts").insert({
                    "full_name": full_name,
                    "email": email,
                    "college": college,
                    "track_interest": track_interest,
                }).execute()
                return True
            except Exception as e:
                log.warning("Supabase add lead failed: %s", e)
                # If error is duplicate key, ignore

        conn = get_sqlite_conn()
        cur = conn.cursor()
        try:
            cur.execute("""
            INSERT INTO preregistration_alerts (id, full_name, email, email_key, college, track_interest, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), full_name, email, email_key, college, track_interest, now))
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # duplicate email
        finally:
            conn.close()
        return True

    @staticmethod
    def save_registration(data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves a pending registration."""
        reg_id = data.get("id") or str(uuid.uuid4())
        data["id"] = reg_id
        data["team_name_key"] = data["team_name"].strip().lower()
        now = datetime.now(timezone.utc).isoformat()
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)

        if settings.has_supabase:
            try:
                # Prepare members_data for JSON column
                db_data = dict(data)
                if isinstance(db_data.get("members_data"), str):
                    db_data["members_data"] = json.loads(db_data["members_data"])
                res = get_supabase_client().table("registrations").insert(db_data).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                log.warning("Supabase save registration failed: %s", e)

        # Fallback to local SQLite
        conn = get_sqlite_conn()
        cur = conn.cursor()
        members_json = (
            json.dumps(data["members_data"])
            if not isinstance(data.get("members_data"), str)
            else data["members_data"]
        )

        cur.execute("""
        INSERT INTO registrations (
            id, team_code, team_name, team_name_key, college_name, track,
            leader_name, leader_email, leader_phone, leader_department, leader_year, leader_gender, leader_id_number,
            member_count, members_data, idea_title, idea_summary, idea_description,
            idea_ppt_filename, idea_ppt_path, terms_accepted, terms_version, terms_accepted_at,
            amount_paid, payment_status, payment_mode, razorpay_order_id, razorpay_payment_id,
            razorpay_signature, payment_timestamp, review_status, admin_notes, created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?
        )
        """, (
            reg_id, data["team_code"], data["team_name"], data["team_name_key"], data["college_name"], data["track"],
            data["leader_name"], data["leader_email"], data["leader_phone"], data["leader_department"],
            data["leader_year"], data.get("leader_gender"), data.get("leader_id_number"),
            data["member_count"], members_json, data["idea_title"], data["idea_summary"], data["idea_description"],
            data.get("idea_ppt_filename"), data.get("idea_ppt_path"),
            1 if data.get("terms_accepted") else 0, data.get("terms_version"), data.get("terms_accepted_at"),
            data.get("amount_paid", 0), data.get("payment_status", "pending"), data.get("payment_mode", "razorpay"),
            data.get("razorpay_order_id"), data.get("razorpay_payment_id"),
            data.get("razorpay_signature"), data.get("payment_timestamp"),
            data.get("review_status", "submitted"), data.get("admin_notes", ""),
            data["created_at"], data["updated_at"]
        ))
        conn.commit()
        conn.close()
        return data

    @staticmethod
    def get_registration_by_order_id(order_id: str) -> Optional[Dict[str, Any]]:
        if settings.has_supabase:
            try:
                res = (
                    get_supabase_client().table("registrations")
                    .select("*").eq("razorpay_order_id", order_id).limit(1).execute()
                )
                if res.data:
                    return res.data[0]
            except Exception as e:
                log.warning("Supabase get by order failed: %s", e)

        conn = get_sqlite_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM registrations WHERE razorpay_order_id = ? LIMIT 1", (order_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("members_data"), str):
            d["members_data"] = json.loads(d["members_data"])
        d["terms_accepted"] = bool(d.get("terms_accepted"))
        return d

    @staticmethod
    def get_registration_by_team_code(team_code: str) -> Optional[Dict[str, Any]]:
        code = team_code.strip().upper()
        if settings.has_supabase:
            try:
                res = (
                    get_supabase_client().table("registrations")
                    .select("*").eq("team_code", code).limit(1).execute()
                )
                if res.data:
                    return res.data[0]
            except Exception as e:
                log.warning("Supabase get by code failed: %s", e)

        conn = get_sqlite_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM registrations WHERE team_code = ? LIMIT 1", (code,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("members_data"), str):
            d["members_data"] = json.loads(d["members_data"])
        d["terms_accepted"] = bool(d.get("terms_accepted"))
        return d

    @staticmethod
    def get_registration_by_id(reg_id: str) -> Optional[Dict[str, Any]]:
        if settings.has_supabase:
            try:
                res = (
                    get_supabase_client().table("registrations")
                    .select("*").eq("id", reg_id).limit(1).execute()
                )
                if res.data:
                    return res.data[0]
            except Exception as e:
                log.warning("Supabase get by id failed: %s", e)

        conn = get_sqlite_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM registrations WHERE id = ? LIMIT 1", (reg_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("members_data"), str):
            d["members_data"] = json.loads(d["members_data"])
        d["terms_accepted"] = bool(d.get("terms_accepted"))
        return d

    @staticmethod
    def mark_payment_successful(
        reg_id: str,
        payment_id: str,
        signature: str,
        amount: float,
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        if settings.has_supabase:
            try:
                get_supabase_client().table("registrations").update({
                    "payment_status": "paid",
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature,
                    "amount_paid": amount,
                    "payment_timestamp": now,
                    "updated_at": now,
                }).eq("id", reg_id).execute()
                return True
            except Exception as e:
                log.warning("Supabase update payment failed: %s", e)

        conn = get_sqlite_conn()
        cur = conn.cursor()
        cur.execute("""
        UPDATE registrations
        SET payment_status = 'paid',
            razorpay_payment_id = ?,
            razorpay_signature = ?,
            amount_paid = ?,
            payment_timestamp = ?,
            updated_at = ?
        WHERE id = ?
        """, (payment_id, signature, amount, now, now, reg_id))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def get_all_registrations(
        query: str = "",
        track: str = "",
        review_status: str = "",
        payment_status: str = "",
    ) -> List[Dict[str, Any]]:
        conn = get_sqlite_conn()
        cur = conn.cursor()
        sql = "SELECT * FROM registrations WHERE 1=1"
        params: List[Any] = []

        if query:
            q = f"%{query.strip().lower()}%"
            sql += """ AND (
                LOWER(team_name) LIKE ? OR
                LOWER(team_code) LIKE ? OR
                LOWER(leader_name) LIKE ? OR
                LOWER(college_name) LIKE ? OR
                LOWER(leader_email) LIKE ?
            )"""
            params.extend([q, q, q, q, q])

        if track:
            sql += " AND track = ?"
            params.append(track)

        if review_status:
            sql += " AND review_status = ?"
            params.append(review_status)

        if payment_status:
            sql += " AND payment_status = ?"
            params.append(payment_status)

        sql += " ORDER BY created_at DESC"
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()

        results = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("members_data"), str):
                try:
                    d["members_data"] = json.loads(d["members_data"])
                except Exception:
                    d["members_data"] = []
            d["terms_accepted"] = bool(d.get("terms_accepted"))
            results.append(d)
        return results

    @staticmethod
    def update_review_status(reg_id: str, status: str, admin_notes: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        if settings.has_supabase:
            try:
                get_supabase_client().table("registrations").update({
                    "review_status": status,
                    "admin_notes": admin_notes,
                    "updated_at": now,
                }).eq("id", reg_id).execute()
                return True
            except Exception as e:
                log.warning("Supabase update status failed: %s", e)

        conn = get_sqlite_conn()
        cur = conn.cursor()
        cur.execute("""
        UPDATE registrations
        SET review_status = ?,
            admin_notes = ?,
            updated_at = ?
        WHERE id = ?
        """, (status, admin_notes, now, reg_id))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def delete_registration(reg_id: str) -> Optional[str]:
        """Deletes registration record and returns the file path to clean up."""
        file_path = None
        reg = Repository.get_registration_by_id(reg_id)
        if reg:
            file_path = reg.get("idea_ppt_path")

        if settings.has_supabase:
            try:
                get_supabase_client().table("registrations").delete().eq("id", reg_id).execute()
                if file_path:
                    try:
                        get_supabase_client().storage.from_(settings.SUPABASE_BUCKET).remove([file_path])
                    except Exception:
                        pass
            except Exception as e:
                log.warning("Supabase delete failed: %s", e)

        conn = get_sqlite_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
        conn.commit()
        conn.close()
        return file_path

    @staticmethod
    def get_metrics() -> Dict[str, Any]:
        """Calculates dashboard metrics cards."""
        conn = get_sqlite_conn()
        cur = conn.cursor()

        # Total registered
        cur.execute("SELECT COUNT(*) FROM registrations")
        total_registered = cur.fetchone()[0]

        # Paid vs pending
        cur.execute("SELECT COUNT(*) FROM registrations WHERE payment_status = 'paid'")
        paid_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM registrations WHERE payment_status = 'pending'")
        pending_count = cur.fetchone()[0]

        # Total revenue
        cur.execute("SELECT COALESCE(SUM(amount_paid), 0) FROM registrations WHERE payment_status = 'paid'")
        total_revenue = cur.fetchone()[0]

        # Total confirmed participants (all members + leader of paid teams)
        cur.execute("SELECT COALESCE(SUM(member_count), 0) FROM registrations WHERE payment_status = 'paid'")
        confirmed_participants = cur.fetchone()[0]

        # Leads count
        cur.execute("SELECT COUNT(*) FROM preregistration_alerts")
        notify_leads = cur.fetchone()[0]

        # Teams per track
        cur.execute("SELECT track, COUNT(*) FROM registrations GROUP BY track")
        track_rows = cur.fetchall()
        teams_per_track = {t: 0 for t in content.TRACKS}
        for row in track_rows:
            if row[0] in teams_per_track:
                teams_per_track[row[0]] = row[1]
            else:
                teams_per_track[row[0]] = row[1]

        conn.close()

        return {
            "total_teams": total_registered,
            "paid_teams": paid_count,
            "pending_teams": pending_count,
            "confirmed_participants": confirmed_participants,
            "total_revenue": total_revenue,
            "notify_leads": notify_leads,
            "teams_per_track": teams_per_track,
        }
