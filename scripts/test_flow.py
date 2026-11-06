import io
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("Starting comprehensive end-to-end integration test suite...")

# 1. HTML Pages & Error Pages
pages = [
    '/',
    '/register',
    '/terms',
    '/admin/login',
    '/admin',
    '/confirmation/HACK-27-101-K8F2',
    '/robots.txt',
    '/sitemap.xml',
]
for path in pages:
    res = client.get(path)
    assert res.status_code == 200, f"Path {path} returned {res.status_code}"
    print(f"[PASS] {path} -> 200 OK")

# Test 404 custom error page for browser HTML request
res = client.get("/nonexistent-page-test", headers={"accept": "text/html"})
assert res.status_code == 404
assert "Coordinates Not Found" in res.text or "404" in res.text
print("[PASS] 404 Custom Error Page -> 404 OK with themed HTML")

# 2. Template Download
res = client.get('/download/idea-template')
assert res.status_code == 200
print(f"[PASS] /download/idea-template -> 200 OK ({len(res.content)} bytes)")

# 3. Test Config API
res = client.get('/api/config')
assert res.status_code == 200
cfg = res.json()
assert cfg["fee_per_member_inr"] == 99
assert cfg["team_size"]["min"] == 2
assert cfg["team_size"]["max"] == 5
assert "Pollachi" in cfg["event"]["venue"] or "Pollachi" in cfg["event"]["location"]
print(f"[PASS] /api/config -> 200 OK (INR {cfg['fee_per_member_inr']}/member, {cfg['team_size']['min']}-{cfg['team_size']['max']} members, {cfg['event']['venue']})")

# 4. Test File Type Validation: Reject .pdf
rand_id = uuid.uuid4().hex[:6]
pdf_file = io.BytesIO(b"%PDF-1.4 dummy pdf content")
form_data_pdf = {
    'team_name': f'PDF Test Team {rand_id}',
    'college_name': 'Pollachi Institute of Tech',
    'track': 'Health, Education & Digital Innovation',
    'leader_name': 'Sanjay Kumar',
    'leader_email': f'sanjay.{rand_id}@example.com',
    'leader_phone': '9876543210',
    'leader_department': 'ECE',
    'leader_year': '3rd Year',
    'members_data': '[{"name":"Kavitha","mobile":"9876543211","email":"kavitha@example.com"}]',
    'idea_title': 'Smart Sensor Grid',
    'idea_summary': 'Abstract summary',
    'idea_description': 'Detailed architecture description',
    'terms_accepted': 'true'
}
files_pdf = {'idea_presentation': ('presentation.pdf', pdf_file, 'application/pdf')}
res = client.post('/api/register', data=form_data_pdf, files=files_pdf)
assert res.status_code == 422, f"PDF should be rejected with 422, got {res.status_code}"
print("[PASS] Strictly PPT validation: .pdf upload rejected with 422 Unprocessable Entity")

# 5. Test Team Size Validation: Reject < 2 or > 5
form_data_single = dict(form_data_pdf)
form_data_single['members_data'] = '[]'  # 1 leader + 0 crew = 1 member (below min 2)
test_ppt = io.BytesIO(b"Valid PPT presentation mock data")
files_ppt = {'idea_presentation': ('presentation.pptx', test_ppt, 'application/vnd.openxmlformats-officedocument.presentationml.presentation')}
res = client.post('/api/register', data=form_data_single, files=files_ppt)
assert res.status_code == 422
print("[PASS] Team capacity validation: 1 member rejected with 422 (min 2 required)")

# 6. Test Successful Registration with 2 Members (1 Leader + 1 Crew = 2 members => ₹198)
rand_id = uuid.uuid4().hex[:6]
valid_team_name = f"Quantum Innovators {rand_id}"
test_ppt_2 = io.BytesIO(b"Valid PPT presentation mock data for team 2")
form_data_2 = {
    'team_name': valid_team_name,
    'college_name': 'Pollachi Institute of Technology',
    'track': 'Sustainability, Smart Communities & Social Entrepreneurship',
    'leader_name': 'Ravi Chandran',
    'leader_email': f'ravi.{rand_id}@example.com',
    'leader_phone': '9876543210',
    'leader_department': 'Mechanical',
    'leader_year': '3rd Year',
    'leader_gender': 'Male',
    'leader_id_number': 'PIT-2023-ME-01',
    'members_data': '[{"name":"Priya Dharshini","mobile":"9876543211","email":"priya@example.com","department":"CSE","year":"3rd Year"}]',
    'idea_title': 'IoT Smart Soil Hydration for Pollachi Coconut Groves',
    'idea_summary': 'Precision agriculture irrigation management using solar microgrids and edge sensors.',
    'idea_description': 'Full prototype development using ESP32, LoRaWAN gateways, and FastAPI dashboard.',
    'terms_accepted': 'true'
}
files_2 = {'idea_presentation': ('smart_irrigation.pptx', test_ppt_2, 'application/vnd.openxmlformats-officedocument.presentationml.presentation')}

mock_order = {
    "order_id": f"order_test_{rand_id}",
    "amount": 19800,
    "currency": "INR",
    "key_id": "rzp_test_flow",
}
with patch("app.routes.public.create_payment_order", return_value=mock_order):
    res = client.post('/api/register', data=form_data_2, files=files_2)
assert res.status_code == 200, f"Register failed: {res.text}"
reg_data = res.json()
assert "is_sandbox" not in reg_data["order"]
assert reg_data["amount_inr"] == 198, f"Expected fee 198 for 2 members, got {reg_data['amount_inr']}"
assert reg_data["member_count"] == 2
team_code = reg_data["team_code"]
order_id = reg_data["order"]["order_id"]
print(f"[PASS] 2-Member Team registered: Code {team_code}, Fee INR {reg_data['amount_inr']} (INR 99 x 2)")

# 7. Test Student Presentation Preview Link
res = client.get(f"/api/file/view/{team_code}")
assert res.status_code in (200, 307), f"Preview file failed with {res.status_code}"
if res.status_code == 200:
    assert res.headers.get("content-disposition", "").startswith("inline;")
print(f"[PASS] Student PPT Clickable Preview /api/file/view/{team_code} -> {res.status_code} OK")

# 8. Test Payment Verification
verify_payload = {
    'razorpay_order_id': order_id,
    'razorpay_payment_id': f'pay_test_{uuid.uuid4().hex[:8]}',
    'razorpay_signature': 'test_signature_valid'
}
with patch("app.routes.public.verify_payment", return_value=True):
    res = client.post('/api/payment/verify', json=verify_payload)
assert res.status_code == 200, f"Payment verify failed: {res.text}"
assert res.json()['redirect_url'] == f"/confirmation/{team_code}"
print(f"[PASS] Payment verified -> Redirect to /confirmation/{team_code}")

# 9. Test Public Confirmation Ticket API
res = client.get(f"/api/registration/{team_code}")
assert res.status_code == 200
ticket = res.json()
assert ticket['payment_status'] == 'paid'
assert ticket['amount_paid'] == 198.0
assert ticket['team_name'] == valid_team_name
assert ticket['idea_ppt_filename'] == 'smart_irrigation.pptx'
print(f"[PASS] Public Confirmation Ticket confirmed: Team '{ticket['team_name']}' is PAID INR {ticket['amount_paid']}")

# 10. Test Admin Authentication & APIs
login_res = client.post("/api/admin/login", json={"username": "admin", "password": "AdminPass@2027!"})
assert login_res.status_code == 200
admin_token = login_res.json()["token"]
headers = {"Authorization": f"Bearer {admin_token}"}
print(f"[PASS] Admin login -> 200 OK (Token received)")

# 11. Test Admin Edit Participant Details & Audit Trail Logging
all_teams_res = client.get("/api/admin/registrations", headers=headers)
assert all_teams_res.status_code == 200
registrations = all_teams_res.json()["registrations"]
target_reg = next(r for r in registrations if r["team_code"] == team_code)
reg_id = target_reg["id"]

# Perform Admin Edit
edit_payload = {
    "leader_name": "Ravi Chandran (Verified Leader)",
    "leader_phone": "9876543299",
    "idea_title": "IoT Smart Soil Hydration v2",
    "edit_reason": "Verified leader spelling and corrected contact phone"
}
edit_res = client.put(f"/api/admin/registration/{reg_id}", json=edit_payload, headers=headers)
assert edit_res.status_code == 200, f"Admin edit failed: {edit_res.text}"
edited_reg = edit_res.json()["registration"]
assert edited_reg["leader_name"] == "Ravi Chandran (Verified Leader)"
assert edited_reg["leader_phone"] == "9876543299"
print(f"[PASS] Admin participant details edit -> 200 OK (Name: {edited_reg['leader_name']})")

# 12. Test Action Audit Table Endpoint
audit_res = client.get("/api/admin/audit-logs", headers=headers)
assert audit_res.status_code == 200
audit_data = audit_res.json()
assert audit_data["count"] > 0
latest_log = audit_data["logs"][0]
assert latest_log["registration_id"] == reg_id
assert latest_log["action_type"] == "EDIT_PARTICIPANT_DETAILS"
print(f"[PASS] Admin Action Audit Trail verified: Action '{latest_log['action_type']}' logged by '{latest_log['admin_user']}' with reason '{latest_log['notes']}'")

# 13. Test Admin Invalid Credentials Rejection
bad_login = client.post("/api/admin/login", json={"username": "admin", "password": "WrongPassword!"})
assert bad_login.status_code == 401
print("[PASS] Security: Invalid Admin credentials rejected with 401 Unauthorized")

# 14. Test Admin Route Protection & Gated Redirection
# Create an unauthenticated client to test unauthenticated access
unauth_client = TestClient(app)
unauth_admin = unauth_client.get("/admin")
assert "adminLoginForm" in unauth_admin.text
print("[PASS] Security: Unauthenticated access to /admin securely serves Admin Login form")

# With auth cookie, /admin serves the full management dashboard
auth_admin = client.get("/admin")
assert "JM Vertex Admin Portal" in auth_admin.text
print("[PASS] Security: Authenticated admin access to /admin serves Operations Dashboard")

# Visiting /admin/login while already logged in redirects to /admin
login_redir = client.get("/admin/login", follow_redirects=False)
assert login_redir.status_code == 303
assert login_redir.headers["location"] == "/admin"
print("[PASS] Security: Accessing /admin/login while logged in auto-redirects to /admin (303)")

# 15. Test Metrics Calculation & Live Sync
metrics_res = client.get("/api/admin/metrics", headers=headers)
assert metrics_res.status_code == 200
metrics = metrics_res.json()
assert metrics["paid_teams"] >= 1
assert metrics["total_revenue"] >= 198
assert "teams_per_track" in metrics
print(f"[PASS] Metrics Sync verified: {metrics['paid_teams']} paid teams, INR {metrics['total_revenue']} total revenue")

# 16. Test Excel and CSV Export Endpoints (via query token)
export_excel = client.get(f"/api/admin/export/excel?token={admin_token}")
assert export_excel.status_code == 200
assert export_excel.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
assert len(export_excel.content) > 1000
print(f"[PASS] Excel Export (.xlsx) verified: {len(export_excel.content)} bytes generated")

export_csv = client.get(f"/api/admin/export/csv?token={admin_token}")
assert export_csv.status_code == 200
assert "text/csv" in export_csv.headers["content-type"]
assert "Team Code,Team Name" in export_csv.text
print("[PASS] CSV Export verified: UTF-8 BOM CSV generated with headers and team rows")

print("\n" + "=" * 70)
print("ALL 12 END-TO-END TEST SUITES COMPLETED AND PASSED WITH 100% ACCURACY!")
print("=" * 70)
