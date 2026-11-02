import io
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("Starting end-to-end integration tests...")

# 1. HTML Pages
for path in ['/', '/register', '/terms', '/admin/login', '/admin', '/confirmation/HACK-27-101-K8F2', '/robots.txt', '/sitemap.xml']:
    res = client.get(path)
    assert res.status_code == 200, f"Path {path} returned {res.status_code}"
    print(f"[PASS] {path} -> 200 OK")

# 2. Template Download
res = client.get('/download/idea-template')
assert res.status_code == 200
print(f"[PASS] /download/idea-template -> 200 OK ({len(res.content)} bytes)")

# 3. Test Full Team Registration Flow
test_file = io.BytesIO(b"Sample presentation content for test")
rand_id = uuid.uuid4().hex[:6]
team_name = f"AeroShield Robotics {rand_id}"

form_data = {
    'team_name': team_name,
    'college_name': 'Indian Institute of Science',
    'track': 'Health, Education & Digital Innovation',
    'leader_name': 'Arjun Mehta',
    'leader_email': f'arjun.mehta.{rand_id}@example.com',
    'leader_phone': '9876543210',
    'leader_department': 'Computer Science',
    'leader_year': '3rd Year',
    'leader_gender': 'Male',
    'leader_id_number': 'IISc-2023-CS-01',
    'members_data': '[{"name":"Sneha Roy","mobile":"9876543211","email":"sneha@example.com","department":"AI","year":"3rd Year"},{"name":"Karan Dave","mobile":"9876543212","email":"karan@example.com","department":"DS","year":"3rd Year"},{"name":"Ananya Rao","mobile":"9876543213","email":"ananya@example.com","department":"ECE","year":"2nd Year"}]',
    'idea_title': 'Diabetic Retinopathy Edge Scanner',
    'idea_summary': 'Instant retinopathy scan using mobile edge vision models.',
    'idea_description': 'FastAPI backend, ONNX runtime, MobileNet quantized model.',
    'terms_accepted': 'true'
}
files = {'idea_presentation': ('presentation.pptx', test_file, 'application/vnd.openxmlformats-officedocument.presentationml.presentation')}

res = client.post('/api/register', data=form_data, files=files)
assert res.status_code == 200, f"Register failed: {res.text}"
reg_data = res.json()
print(f"[PASS] Registration created: Team Code {reg_data['team_code']} (Order: {reg_data['order']['order_id']})")

# 4. Test Payment Verification
verify_payload = {
    'razorpay_order_id': reg_data['order']['order_id'],
    'razorpay_payment_id': 'pay_test_verified_123',
    'razorpay_signature': 'test_signature_valid'
}
res = client.post('/api/payment/verify', json=verify_payload)
assert res.status_code == 200, f"Payment verify failed: {res.text}"
print(f"[PASS] Payment verified! Redirect: {res.json()['redirect_url']}")

# 5. Test Public Ticket Lookup
res = client.get(f"/api/registration/{reg_data['team_code']}")
assert res.status_code == 200
ticket = res.json()
assert ticket['payment_status'] == 'paid'
assert ticket['team_name'] == team_name
print(f"[PASS] Public Ticket API verified: Team '{ticket['team_name']}' is confirmed as PAID!")

print("All end-to-end tests passed successfully with 100% accuracy!")
