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
        google_drive_file_id TEXT,
        google_drive_web_link TEXT,
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

    # Safe column additions if table already existed from previous run
    for col_def in [
        ("google_drive_file_id", "TEXT"),
        ("google_drive_web_link", "TEXT"),
    ]:
        try:
            cur.execute(f"ALTER TABLE registrations ADD COLUMN {col_def[0]} {col_def[1]};")
        except sqlite3.OperationalError:
            pass  # column already exists

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

    # Relational team members table for normalized table viewing
    cur.execute("""
    CREATE TABLE IF NOT EXISTS team_members (
        id TEXT PRIMARY KEY,
        registration_id TEXT NOT NULL,
        team_code TEXT NOT NULL,
        member_index INTEGER NOT NULL,
        name TEXT NOT NULL,
        mobile TEXT NOT NULL,
        email TEXT NOT NULL,
        department TEXT,
        year TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (registration_id) REFERENCES registrations(id) ON DELETE CASCADE
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_members_team ON team_members (team_code);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_members_reg ON team_members (registration_id);")

    # Flat tabular view expanding crew members into distinct spreadsheet columns
    cur.execute("DROP VIEW IF EXISTS v_registrations_flat;")
    cur.execute("""
    CREATE VIEW v_registrations_flat AS
    SELECT
        team_code AS [Team Code],
        team_name AS [Team Name],
        track AS [Track],
        college_name AS [College],
        payment_status AS [Payment Status],
        amount_paid AS [Amount (INR)],
        review_status AS [Review Status],
        member_count AS [Total Members],
        leader_name AS [Leader Name],
        leader_phone AS [Leader Phone],
        leader_email AS [Leader Email],
        leader_department AS [Leader Dept],
        leader_year AS [Leader Year],
        json_extract(members_data, '$[0].name') AS [Member 1 Name],
        json_extract(members_data, '$[0].mobile') AS [Member 1 Mobile],
        json_extract(members_data, '$[0].email') AS [Member 1 Email],
        json_extract(members_data, '$[0].department') AS [Member 1 Dept],
        json_extract(members_data, '$[0].year') AS [Member 1 Year],
        json_extract(members_data, '$[1].name') AS [Member 2 Name],
        json_extract(members_data, '$[1].mobile') AS [Member 2 Mobile],
        json_extract(members_data, '$[1].email') AS [Member 2 Email],
        json_extract(members_data, '$[1].department') AS [Member 2 Dept],
        json_extract(members_data, '$[1].year') AS [Member 2 Year],
        json_extract(members_data, '$[2].name') AS [Member 3 Name],
        json_extract(members_data, '$[2].mobile') AS [Member 3 Mobile],
        json_extract(members_data, '$[2].email') AS [Member 3 Email],
        json_extract(members_data, '$[2].department') AS [Member 3 Dept],
        json_extract(members_data, '$[2].year') AS [Member 3 Year],
        json_extract(members_data, '$[3].name') AS [Member 4 Name],
        json_extract(members_data, '$[3].mobile') AS [Member 4 Mobile],
        json_extract(members_data, '$[3].email') AS [Member 4 Email],
        json_extract(members_data, '$[3].department') AS [Member 4 Dept],
        json_extract(members_data, '$[3].year') AS [Member 4 Year],
        idea_title AS [Idea Title],
        idea_summary AS [Idea Summary],
        google_drive_web_link AS [Drive Link],
        created_at AS [Registered At]
    FROM registrations;
    """)

    # Backfill team_members from registrations if empty
    cur.execute("SELECT COUNT(*) FROM team_members;")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id, team_code, members_data, created_at FROM registrations;")
        for r_id, t_code, m_json, c_at in cur.fetchall():
            try:
                m_list = json.loads(m_json) if isinstance(m_json, str) else []
                for idx, m in enumerate(m_list, start=1):
                    cur.execute("""
                    INSERT INTO team_members (
                        id, registration_id, team_code, member_index, name, mobile, email, department, year, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(uuid.uuid4()), r_id, t_code, idx,
                        m.get("name", ""), m.get("mobile", ""), m.get("email", ""),
                        m.get("department", ""), m.get("year", ""), c_at or datetime.now(timezone.utc).isoformat()
                    ))
            except Exception:
                pass

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admin_audit_logs (
        id TEXT PRIMARY KEY,
        registration_id TEXT NOT NULL,
        team_code TEXT,
        team_name TEXT,
        admin_user TEXT NOT NULL,
        action_type TEXT NOT NULL,
        changes_json TEXT NOT NULL DEFAULT '{}',
        notes TEXT,
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
    and previews run completely smoothly out of the box.
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
    def is_team_name_taken(name: str, exclude_id: str = "") -> bool:
        key = name.strip().lower()
        if not key:
            return False

        if settings.has_supabase:
            try:
                q = get_supabase_client().table("registrations").select("id").eq("team_name_key", key)
                if exclude_id:
                    q = q.neq("id", exclude_id)
                res = q.limit(1).execute()
                return bool(res.data)
            except Exception as e:
                log.warning("Supabase check team name error: %s", e)

        conn = get_sqlite_conn()
        cur = conn.cursor()
        if exclude_id:
            cur.execute("SELECT id FROM registrations WHERE team_name_key = ? AND id != ? LIMIT 1", (key, exclude_id))
        else:
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
            idea_ppt_filename, idea_ppt_path, google_drive_file_id, google_drive_web_link,
            terms_accepted, terms_version, terms_accepted_at,
            amount_paid, payment_status, payment_mode, razorpay_order_id, razorpay_payment_id,
            razorpay_signature, payment_timestamp, review_status, admin_notes, created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?
        )
        """, (
            reg_id, data["team_code"], data["team_name"], data["team_name_key"], data["college_name"], data["track"],
            data["leader_name"], data["leader_email"], data["leader_phone"], data["leader_department"],
            data["leader_year"], data.get("leader_gender"), data.get("leader_id_number"),
            data["member_count"], members_json, data["idea_title"], data["idea_summary"], data["idea_description"],
            data.get("idea_ppt_filename"), data.get("idea_ppt_path"),
            data.get("google_drive_file_id"), data.get("google_drive_web_link"),
            1 if data.get("terms_accepted") else 0, data.get("terms_version"), data.get("terms_accepted_at"),
            data.get("amount_paid", 0), data.get("payment_status", "pending"), data.get("payment_mode", "razorpay"),
            data.get("razorpay_order_id"), data.get("razorpay_payment_id"),
            data.get("razorpay_signature"), data.get("payment_timestamp"),
            data.get("review_status", "submitted"), data.get("admin_notes", ""),
            data["created_at"], data["updated_at"]
        ))

        # Insert crew members into relational team_members table
        members_list = data.get("members_data") or []
        if isinstance(members_list, str):
            try:
                members_list = json.loads(members_list)
            except Exception:
                members_list = []
        for idx, m in enumerate(members_list, start=1):
            cur.execute("""
            INSERT INTO team_members (
                id, registration_id, team_code, member_index, name, mobile, email, department, year, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), reg_id, data["team_code"], idx,
                m.get("name", ""), m.get("mobile", ""), m.get("email", ""),
                m.get("department", ""), m.get("year", ""), data["created_at"]
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
            try:
                d["members_data"] = json.loads(d["members_data"])
            except Exception:
                d["members_data"] = []
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
            try:
                d["members_data"] = json.loads(d["members_data"])
            except Exception:
                d["members_data"] = []
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
            try:
                d["members_data"] = json.loads(d["members_data"])
            except Exception:
                d["members_data"] = []
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
        if settings.has_supabase:
            try:
                client = get_supabase_client()
                q = client.table("registrations").select("*")
                if track:
                    q = q.eq("track", track)
                if review_status:
                    q = q.eq("review_status", review_status)
                if payment_status:
                    q = q.eq("payment_status", payment_status)
                if query:
                    clean_q = query.strip()
                    pattern = f"%{clean_q}%"
                    q = q.or_(f"team_name.ilike.{pattern},team_code.ilike.{pattern},leader_name.ilike.{pattern},college_name.ilike.{pattern},leader_email.ilike.{pattern}")

                res = q.order("created_at", desc=True).execute()
                if res.data is not None:
                    results = []
                    for r in res.data:
                        d = dict(r)
                        if isinstance(d.get("members_data"), str):
                            try:
                                d["members_data"] = json.loads(d["members_data"])
                            except Exception:
                                d["members_data"] = []
                        d["terms_accepted"] = bool(d.get("terms_accepted"))
                        results.append(d)
                    return results
            except Exception as e:
                log.warning("Supabase get_all_registrations failed (%s); falling back to SQLite", e)

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
    def update_review_status(reg_id: str, status: str, admin_notes: str, admin_user: str = "admin") -> bool:
        now = datetime.now(timezone.utc).isoformat()
        reg = Repository.get_registration_by_id(reg_id)
        if not reg:
            return False

        old_status = reg.get("review_status", "")
        old_notes = reg.get("admin_notes", "")

        if settings.has_supabase:
            try:
                get_supabase_client().table("registrations").update({
                    "review_status": status,
                    "admin_notes": admin_notes,
                    "updated_at": now,
                }).eq("id", reg_id).execute()
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

        # Record audit log if status or notes changed
        if old_status != status or old_notes != admin_notes:
            changes = {}
            if old_status != status:
                changes["review_status"] = {"from": old_status, "to": status}
            if old_notes != admin_notes:
                changes["admin_notes"] = {"from": old_notes, "to": admin_notes}

            Repository.record_admin_audit(
                registration_id=reg_id,
                team_code=reg.get("team_code", ""),
                team_name=reg.get("team_name", ""),
                admin_user=admin_user,
                action_type="UPDATE_STATUS",
                changes=changes,
                notes=f"Review status set to {status}",
            )
        return True

    @staticmethod
    def update_registration_details(
        reg_id: str,
        updated_fields: Dict[str, Any],
        admin_user: str,
        notes: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Updates participant and team details by admin, and creates an audit record."""
        current = Repository.get_registration_by_id(reg_id)
        if not current:
            return None

        now = datetime.now(timezone.utc).isoformat()
        changes: Dict[str, Any] = {}

        # Allowed editable fields
        editable_fields = [
            "team_name", "college_name", "track",
            "leader_name", "leader_email", "leader_phone",
            "leader_department", "leader_year", "leader_gender", "leader_id_number",
            "members_data", "member_count",
            "idea_title", "idea_summary", "idea_description",
            "admin_notes", "payment_status"
        ]

        updates: Dict[str, Any] = {"updated_at": now}

        for f in editable_fields:
            if f in updated_fields:
                new_val = updated_fields[f]
                old_val = current.get(f)

                if f == "members_data":
                    if isinstance(new_val, str):
                        try:
                            new_val = json.loads(new_val)
                        except Exception:
                            new_val = []
                    if old_val != new_val:
                        changes[f] = {"from": len(old_val) if isinstance(old_val, list) else 0, "to": len(new_val)}
                        updates[f] = json.dumps(new_val)
                        # Also update member count if not explicitly set
                        updates["member_count"] = len(new_val) + 1
                elif f == "team_name":
                    new_clean = str(new_val).strip()
                    if new_clean != old_val:
                        changes[f] = {"from": old_val, "to": new_clean}
                        updates["team_name"] = new_clean
                        updates["team_name_key"] = new_clean.lower()
                else:
                    if old_val != new_val:
                        changes[f] = {"from": old_val, "to": new_val}
                        updates[f] = new_val

        if not changes:
            return current  # Nothing changed

        # Apply to Supabase if configured
        if settings.has_supabase:
            try:
                sb_data = dict(updates)
                if "members_data" in sb_data and isinstance(sb_data["members_data"], str):
                    sb_data["members_data"] = json.loads(sb_data["members_data"])
                get_supabase_client().table("registrations").update(sb_data).eq("id", reg_id).execute()
            except Exception as e:
                log.warning("Supabase update registration failed: %s", e)

        # Apply to SQLite
        conn = get_sqlite_conn()
        cur = conn.cursor()
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [reg_id]
        cur.execute(f"UPDATE registrations SET {set_clause} WHERE id = ?", values)

        # Re-sync team_members table if members_data was modified
        if "members_data" in updates:
            m_data = updates["members_data"]
            m_list = json.loads(m_data) if isinstance(m_data, str) else m_data
            cur.execute("DELETE FROM team_members WHERE registration_id = ?", (reg_id,))
            for idx, m in enumerate(m_list, start=1):
                cur.execute("""
                INSERT INTO team_members (
                    id, registration_id, team_code, member_index, name, mobile, email, department, year, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()), reg_id, current.get("team_code", ""), idx,
                    m.get("name", ""), m.get("mobile", ""), m.get("email", ""),
                    m.get("department", ""), m.get("year", ""), now
                ))

        conn.commit()
        conn.close()

        # Record audit log
        Repository.record_admin_audit(
            registration_id=reg_id,
            team_code=current.get("team_code", ""),
            team_name=current.get("team_name", ""),
            admin_user=admin_user,
            action_type="EDIT_PARTICIPANT_DETAILS",
            changes=changes,
            notes=notes or f"Updated {len(changes)} fields by admin {admin_user}",
        )

        return Repository.get_registration_by_id(reg_id)

    @staticmethod
    def record_admin_audit(
        registration_id: str,
        team_code: str,
        team_name: str,
        admin_user: str,
        action_type: str,
        changes: Dict[str, Any],
        notes: str = "",
    ) -> bool:
        """Records an admin action into the audit table."""
        audit_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        changes_json = json.dumps(changes)

        if settings.has_supabase:
            try:
                get_supabase_client().table("admin_audit_logs").insert({
                    "id": audit_id,
                    "registration_id": registration_id,
                    "team_code": team_code,
                    "team_name": team_name,
                    "admin_user": admin_user,
                    "action_type": action_type,
                    "changes_json": changes,
                    "notes": notes,
                    "created_at": now,
                }).execute()
                return True
            except Exception as e:
                log.warning("Supabase record audit log failed: %s", e)

        conn = get_sqlite_conn()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO admin_audit_logs (
            id, registration_id, team_code, team_name, admin_user, action_type, changes_json, notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (audit_id, registration_id, team_code, team_name, admin_user, action_type, changes_json, notes, now))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def get_audit_logs(limit: int = 100, registration_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns action audit trail sorted by latest first."""
        if settings.has_supabase:
            try:
                client = get_supabase_client()
                q = client.table("admin_audit_logs").select("*")
                if registration_id:
                    q = q.eq("registration_id", registration_id)
                res = q.order("created_at", desc=True).limit(limit).execute()
                if res.data is not None:
                    logs = []
                    for r in res.data:
                        d = dict(r)
                        if isinstance(d.get("changes_json"), str):
                            try:
                                d["changes"] = json.loads(d["changes_json"])
                            except Exception:
                                d["changes"] = {}
                        else:
                            d["changes"] = d.get("changes_json") or {}
                        logs.append(d)
                    return logs
            except Exception as e:
                log.warning("Supabase get_audit_logs failed (%s); falling back to SQLite", e)

        conn = get_sqlite_conn()
        cur = conn.cursor()
        if registration_id:
            cur.execute("""
            SELECT * FROM admin_audit_logs
            WHERE registration_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """, (registration_id, limit))
        else:
            cur.execute("""
            SELECT * FROM admin_audit_logs
            ORDER BY created_at DESC
            LIMIT ?
            """, (limit,))
        rows = cur.fetchall()
        conn.close()

        logs = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("changes_json"), str):
                try:
                    d["changes"] = json.loads(d["changes_json"])
                except Exception:
                    d["changes"] = {}
            else:
                d["changes"] = d.get("changes_json") or {}
            logs.append(d)
        return logs

    @staticmethod
    def delete_registration(reg_id: str, admin_user: str = "admin") -> Optional[str]:
        """Deletes registration record and returns the file path to clean up."""
        file_path = None
        reg = Repository.get_registration_by_id(reg_id)
        if reg:
            file_path = reg.get("idea_ppt_path")
            Repository.record_admin_audit(
                registration_id=reg_id,
                team_code=reg.get("team_code", ""),
                team_name=reg.get("team_name", ""),
                admin_user=admin_user,
                action_type="DELETE_REGISTRATION",
                changes={"deleted_team": reg.get("team_name", "")},
                notes="Registration permanently deleted by admin",
            )

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
        cur.execute("DELETE FROM team_members WHERE registration_id = ?", (reg_id,))
        conn.commit()
        conn.close()
        return file_path

    @staticmethod
    def get_metrics() -> Dict[str, Any]:
        """Calculates dashboard metrics cards."""
        if settings.has_supabase:
            try:
                client = get_supabase_client()
                res = client.table("registrations").select("payment_status,amount_paid,member_count,track").execute()
                data = res.data or []

                total_registered = len(data)
                paid_count = sum(1 for r in data if r.get("payment_status") == "paid")
                pending_count = sum(1 for r in data if r.get("payment_status") == "pending")
                total_revenue = sum(float(r.get("amount_paid") or 0) for r in data if r.get("payment_status") == "paid")
                confirmed_participants = sum(int(r.get("member_count") or 1) for r in data if r.get("payment_status") == "paid")

                notify_leads = 0
                try:
                    leads_res = client.table("preregistration_alerts").select("id", count="exact", head=True).execute()
                    notify_leads = leads_res.count or 0
                except Exception:
                    pass

                teams_per_track = {t: 0 for t in content.TRACKS}
                for r in data:
                    t = r.get("track")
                    if t in teams_per_track:
                        teams_per_track[t] += 1
                    elif t:
                        teams_per_track[t] = 1

                return {
                    "total_teams": total_registered,
                    "paid_teams": paid_count,
                    "pending_teams": pending_count,
                    "confirmed_participants": confirmed_participants,
                    "total_revenue": total_revenue,
                    "notify_leads": notify_leads,
                    "teams_per_track": teams_per_track,
                }
            except Exception as e:
                log.warning("Supabase get_metrics failed (%s); falling back to SQLite", e)

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
