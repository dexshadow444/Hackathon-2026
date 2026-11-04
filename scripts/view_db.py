"""
JM Vertex Hackathon 2027 · Database Table Viewer & Exporter
Allows viewing SQLite database tables directly in your terminal,
or exporting them to Excel-compatible CSV files.

Usage:
  python scripts/view_db.py                  # View registrations table
  python scripts/view_db.py --table members  # View crew members table
  python scripts/view_db.py --table audit    # View admin action audit log
  python scripts/view_db.py --table leads    # View pre-registration alerts
  python scripts/view_db.py --flat           # View wide flattened registrations
  python scripts/view_db.py --export-csv     # Export data/registrations.csv
"""
import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "hackathon.db"
CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "registrations.csv"
MEMBERS_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "team_members.csv"


def get_conn():
    if not DB_PATH.exists():
        print(f"Error: Database file not found at {DB_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def print_ascii_table(headers: list, rows: list, max_col_width: int = 32):
    if not rows:
        print("(No records found)")
        return

    # Truncate and convert everything to string
    str_rows = []
    for r in rows:
        formatted_row = []
        for val in r:
            s = str(val if val is not None else "")
            if len(s) > max_col_width:
                s = s[: max_col_width - 3] + "..."
            formatted_row.append(s)
        str_rows.append(formatted_row)

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in str_rows:
        for idx, val in enumerate(row):
            if idx < len(col_widths):
                col_widths[idx] = max(col_widths[idx], len(val))

    # Format borders
    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header_str = "|" + "|".join(f" {h:<{col_widths[i]}} " for i, h in enumerate(headers)) + "|"

    print(sep)
    print(header_str)
    print(sep)
    for row in str_rows:
        row_str = "|" + "|".join(f" {row[i]:<{col_widths[i]}} " if i < len(row) else f" {'':<{col_widths[i]}} " for i in range(len(col_widths))) + "|"
        print(row_str)
    print(sep)
    print(f"Total Rows: {len(rows)}\n")


def view_registrations():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT
        team_code,
        team_name,
        track,
        college_name,
        leader_name,
        leader_phone,
        member_count,
        payment_status,
        amount_paid,
        review_status,
        created_at
    FROM registrations
    ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    headers = [
        "Team Code", "Team Name", "Track", "College", "Leader", "Leader Phone",
        "Members", "Payment", "Fee (INR)", "Review", "Registered At"
    ]
    print("\n=== [TABLE: REGISTRATIONS] ===")
    print_ascii_table(headers, [list(r) for r in rows], max_col_width=24)
    conn.close()


def view_members():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT
        team_code,
        member_index,
        name,
        mobile,
        email,
        department,
        year,
        created_at
    FROM team_members
    ORDER BY team_code, member_index
    """)
    rows = cur.fetchall()
    headers = ["Team Code", "#", "Member Name", "Mobile", "Email", "Department", "Year", "Created At"]
    print("\n=== [TABLE: TEAM_MEMBERS] ===")
    print_ascii_table(headers, [list(r) for r in rows], max_col_width=22)
    conn.close()


def view_audit_logs():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT
        created_at,
        admin_user,
        team_code,
        action_type,
        changes_json,
        notes
    FROM admin_audit_logs
    ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    headers = ["Timestamp", "Admin User", "Team Code", "Action", "Changes Diff", "Notes"]
    print("\n=== [TABLE: ADMIN_AUDIT_LOGS] ===")
    print_ascii_table(headers, [list(r) for r in rows], max_col_width=30)
    conn.close()


def view_leads():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT
        full_name,
        email,
        college,
        track_interest,
        created_at
    FROM preregistration_alerts
    ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    headers = ["Full Name", "Email", "College", "Track Interest", "Subscribed At"]
    print("\n=== [TABLE: PREREGISTRATION_ALERTS (LEADS)] ===")
    print_ascii_table(headers, [list(r) for r in rows], max_col_width=25)
    conn.close()


def view_flat_registrations():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM v_registrations_flat ORDER BY [Registered At] DESC")
    rows = cur.fetchall()
    headers = [col[0] for col in cur.description]
    print("\n=== [VIEW: V_REGISTRATIONS_FLAT] ===")
    print_ascii_table(headers, [list(r) for r in rows], max_col_width=20)
    conn.close()


def export_csv_files():
    conn = get_conn()
    cur = conn.cursor()

    # 1. Export registrations (flat view)
    cur.execute("SELECT * FROM v_registrations_flat ORDER BY [Registered At] DESC")
    rows = cur.fetchall()
    headers = [col[0] for col in cur.description]

    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in rows:
            writer.writerow(list(r))
    print(f"[OK] Exported: {CSV_PATH} ({len(rows)} records)")

    # 2. Export team members
    cur.execute("SELECT * FROM team_members ORDER BY team_code, member_index")
    m_rows = cur.fetchall()
    m_headers = [col[0] for col in cur.description]

    with open(MEMBERS_CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(m_headers)
        for r in m_rows:
            writer.writerow(list(r))
    print(f"[OK] Exported: {MEMBERS_CSV_PATH} ({len(m_rows)} records)")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="View SQLite Database as Formatted Tables")
    parser.add_argument("--table", choices=["registrations", "members", "audit", "leads"], default="registrations", help="Table to display")
    parser.add_argument("--flat", action="store_true", help="Display wide flattened spreadsheet view")
    parser.add_argument("--export-csv", action="store_true", help="Export to CSV spreadsheet files in data/ folder")

    args = parser.parse_args()

    # Always ensure CSV files exist in data/ for direct Excel opening
    export_csv_files()

    if args.export_csv:
        print("\nCSV export complete. You can open 'data/registrations.csv' in Excel.")
        return

    if args.flat:
        view_flat_registrations()
    elif args.table == "registrations":
        view_registrations()
    elif args.table == "members":
        view_members()
    elif args.table == "audit":
        view_audit_logs()
    elif args.table == "leads":
        view_leads()


if __name__ == "__main__":
    main()
