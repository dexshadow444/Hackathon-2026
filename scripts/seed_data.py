"""Seed script that creates realistic sample teams across various tracks and review statuses,
enabling instant demonstration of the Admin Dashboard, metrics cards, search, filters,
and Excel/CSV exports."""
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.content import TERMS_VERSION, TRACKS
from app.db import Repository, next_team_sequence

SAMPLE_TEAMS = [
    {
        "team_name": "Neural Pioneers",
        "college_name": "Indian Institute of Science, Bangalore",
        "track": TRACKS[1],  # Health, Education & Digital Innovation
        "leader_name": "Aarav Sharma",
        "leader_email": "aarav.sharma@example.edu.in",
        "leader_phone": "9876543210",
        "leader_department": "Artificial Intelligence",
        "leader_year": "3rd Year",
        "leader_gender": "Male",
        "leader_id_number": "IISCB-2023-AI-042",
        "members": [
            {"name": "Priya Patel", "mobile": "9876543211", "email": "priya.p@example.edu.in", "department": "Data Science", "year": "3rd Year"},
            {"name": "Rohan Gupta", "mobile": "9876543212", "email": "rohan.g@example.edu.in", "department": "Computer Science", "year": "3rd Year"},
            {"name": "Sneha Reddy", "mobile": "9876543213", "email": "sneha.r@example.edu.in", "department": "Electronics", "year": "2nd Year"},
        ],
        "idea_title": "NeuroScan: Edge AI for Early Diabetic Retinopathy Triage",
        "idea_summary": "A mobile-attached fundus camera and lightweight ONNX edge model providing instantaneous diabetic retinopathy screening in rural primary healthcare centers with 94% clinical accuracy.",
        "idea_description": "Comprehensive 24-hour prototype architecture comprising a quantized MobileNetV3 backbone running on client WebAssembly/WebGPU, syncing anonymized diagnostic telemetric data to FastAPI backend with automated referral generation.",
        "amount_paid": 500.0,
        "payment_status": "paid",
        "payment_id": "pay_sample_test_001",
        "review_status": "shortlisted",
        "admin_notes": "High novelty, outstanding edge deployment concept.",
    },
    {
        "team_name": "CyberShield Vanguard",
        "college_name": "National Institute of Technology, Surathkal",
        "track": TRACKS[0],  # Human Safety, Rights & Empowerment
        "leader_name": "Vasudha Krishnan",
        "leader_email": "vasudha.k@example.ac.in",
        "leader_phone": "9845012345",
        "leader_department": "Information Technology",
        "leader_year": "4th Year",
        "leader_gender": "Female",
        "leader_id_number": "NITK-22-IT-108",
        "members": [
            {"name": "Karthik Menon", "mobile": "9845012346", "email": "karthik.m@example.ac.in", "department": "Information Technology", "year": "4th Year"},
            {"name": "Divya Rao", "mobile": "9845012347", "email": "divya.r@example.ac.in", "department": "Computer Science", "year": "3rd Year"},
            {"name": "Tanmay Verma", "mobile": "9845012348", "email": "tanmay.v@example.ac.in", "department": "Cybersecurity", "year": "4th Year"},
            {"name": "Aditi Joshi", "mobile": "9845012349", "email": "aditi.j@example.ac.in", "department": "Information Technology", "year": "3rd Year"},
        ],
        "idea_title": "SurakshaMesh: Offline Mesh SOS Network for Women & Disaster Relief",
        "idea_summary": "Decentralized BLE & LoRa emergency SOS messaging protocol transmitting encrypted distress signals with precise triangulation even in full cellular network blackouts.",
        "idea_description": "ESP32 hardware node integration paired with a Progressive Web App that relays distress beacons peer-to-peer across mesh nodes until reaching an internet-connected gateway.",
        "amount_paid": 500.0,
        "payment_status": "paid",
        "payment_id": "pay_sample_test_002",
        "review_status": "under_review",
        "admin_notes": "Good hardware prototype potential.",
    },
    {
        "team_name": "EcoGrid Nexus",
        "college_name": "Indian Institute of Technology, Madras",
        "track": TRACKS[2],  # Sustainability, Smart Communities & Social Entrepreneurship
        "leader_name": "Vikramaditya Bose",
        "leader_email": "vikram.bose@example.iitm.ac.in",
        "leader_phone": "9711223344",
        "leader_department": "Electrical Engineering",
        "leader_year": "Postgraduate",
        "leader_gender": "Male",
        "leader_id_number": "IITM-PG-EE-502",
        "members": [
            {"name": "Ananya Sen", "mobile": "9711223345", "email": "ananya.s@example.iitm.ac.in", "department": "Energy Systems", "year": "Postgraduate"},
            {"name": "Gaurav Malhotra", "mobile": "9711223346", "email": "gaurav.m@example.iitm.ac.in", "department": "Computer Science", "year": "4th Year"},
            {"name": "Ritika Das", "mobile": "9711223347", "email": "ritika.d@example.iitm.ac.in", "department": "Civil Infrastructure", "year": "3rd Year"},
        ],
        "idea_title": "VoltShare: Peer-to-Peer Rooftop Solar Energy Micro-Trading",
        "idea_summary": "Automated microgrid smart contracts enabling housing societies to balance intermittent peak solar loads and dynamically trade surplus energy credits at localized tariffs.",
        "idea_description": "Smart energy meter IoT telemetry simulated with MQTT brokers feeding real-time auction match engine and dynamic pricing algorithm written in Python and FastAPI.",
        "amount_paid": 500.0,
        "payment_status": "paid",
        "payment_id": "pay_sample_test_003",
        "review_status": "submitted",
        "admin_notes": "Awaiting initial technical review.",
    },
    {
        "team_name": "Quantum Solvers",
        "college_name": "Birla Institute of Technology and Science, Pilani",
        "track": TRACKS[1],
        "leader_name": "Nikhil Agarwal",
        "leader_email": "nikhil.ag@example.bits.ac.in",
        "leader_phone": "9650011223",
        "leader_department": "Computer Science",
        "leader_year": "2nd Year",
        "leader_gender": "Male",
        "leader_id_number": "BITS-2024-CS-311",
        "members": [
            {"name": "Isha Chawla", "mobile": "9650011224", "email": "isha.c@example.bits.ac.in", "department": "Mathematics", "year": "2nd Year"},
            {"name": "Devansh Singh", "mobile": "9650011225", "email": "devansh.s@example.bits.ac.in", "department": "Computer Science", "year": "2nd Year"},
            {"name": "Meera Nambiar", "mobile": "9650011226", "email": "meera.n@example.bits.ac.in", "department": "Economics", "year": "2nd Year"},
        ],
        "idea_title": "AdaptiveEdu: Multimodal Voice Tutor for Regional Dialects",
        "idea_summary": "Interactive voice-first pedagogical engine trained on foundational regional Indian languages providing contextual STEM coaching for rural primary students.",
        "idea_description": "Speech-to-text pipeline integrating Whisper small model fine-tuned on Indic dialects with streaming audio response synthesis.",
        "amount_paid": 0.0,
        "payment_status": "pending",
        "payment_id": "",
        "review_status": "submitted",
        "admin_notes": "Payment retry expected.",
    },
]

LEADS = [
    ("Siddharth Nair", "sid.nair@sample.edu", "RV College of Engineering", TRACKS[0]),
    ("Tarun Kapoor", "tarun.k@sample.edu", "PES University", TRACKS[1]),
    ("Shreya Banerjee", "shreya.b@sample.edu", "Manipal Institute of Technology", TRACKS[2]),
    ("Harish Sundaram", "harish.s@sample.edu", "Vellore Institute of Technology", "Not sure yet"),
]


def seed():
    print("Seeding sample data...")
    now = datetime.now(timezone.utc).isoformat()

    # Seed leads
    for full_name, email, college, track in LEADS:
        Repository.add_notify_lead(full_name, email, college, track)
    print(f"Seeded {len(LEADS)} pre-registration leads.")

    # Seed teams
    for idx, team in enumerate(SAMPLE_TEAMS, start=101):
        team_code = f"HACK-27-{idx}-K8F2"
        # Check if already exists
        if Repository.is_team_name_taken(team["team_name"]):
            print(f"Team '{team['team_name']}' already exists, skipping.")
            continue

        members = team["members"]
        record = {
            "team_code": team_code,
            "team_name": team["team_name"],
            "college_name": team["college_name"],
            "track": team["track"],
            "leader_name": team["leader_name"],
            "leader_email": team["leader_email"],
            "leader_phone": team["leader_phone"],
            "leader_department": team["leader_department"],
            "leader_year": team["leader_year"],
            "leader_gender": team["leader_gender"],
            "leader_id_number": team["leader_id_number"],
            "member_count": len(members) + 1,
            "members_data": members,
            "idea_title": team["idea_title"],
            "idea_summary": team["idea_summary"],
            "idea_description": team["idea_description"],
            "idea_ppt_filename": "idea_sample_deck.pptx",
            "idea_ppt_path": "sample_deck.pptx",
            "terms_accepted": True,
            "terms_version": TERMS_VERSION,
            "terms_accepted_at": now,
            "amount_paid": team["amount_paid"],
            "payment_status": team["payment_status"],
            "payment_mode": "razorpay",
            "razorpay_order_id": f"order_seed_{idx}",
            "razorpay_payment_id": team["payment_id"],
            "payment_timestamp": now if team["payment_status"] == "paid" else None,
            "review_status": team["review_status"],
            "admin_notes": team["admin_notes"],
        }
        Repository.save_registration(record)
        print(f"Created team: {team_code} - {team['team_name']} ({team['payment_status']})")

    print("Seeding completed successfully!")


if __name__ == "__main__":
    seed()
