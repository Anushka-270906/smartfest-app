import pytest
import os
import sys
import tempfile

# Ensure app is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Point to a fresh temporary database BEFORE importing app modules
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db", prefix="smartfest_test_")
os.close(_test_db_fd)

import app.config as config
config.DB_PATH = _test_db_path

from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create a clean, isolated test database with seed data."""
    init_db()
    yield
    # Cleanup
    try:
        os.unlink(_test_db_path)
    except OSError:
        pass

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200

def test_admin_login():
    response = client.post("/api/auth/login", json={
        "email": "admin@smartfest.edu",
        "password": "Admin@123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["role"] == "admin"

def test_student_registration_and_login():
    # Register a brand-new student
    response = client.post("/api/auth/register", json={
        "name": "Test Student",
        "email": "teststudent@smartfest.edu",
        "password": "Test@12345",
        "role": "student",
        "department": "Information Technology",
        "year": 2,
        "phone": "+91-1234567890",
        "interests": ["AI", "Coding"]
    })
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["role"] == "student"
    assert data["user"]["email"] == "teststudent@smartfest.edu"

    # Login with the same account
    login_res = client.post("/api/auth/login", json={
        "email": "teststudent@smartfest.edu",
        "password": "Test@12345"
    })
    assert login_res.status_code == 200

def test_rbac_student_cannot_create_event():
    # Login as student
    login_res = client.post("/api/auth/login", json={
        "email": "anushka.student@smartfest.edu",
        "password": "Student@123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to create an event (Coordinator/Admin only)
    event_res = client.post("/api/events", json={
        "title": "Unauthorized Event",
        "description": "Should be rejected by RBAC guard",
        "category": "Technical",
        "date": "2026-11-28",
        "start_time": "10:00",
        "end_time": "12:00",
        "venue_id": 1,
        "max_capacity": 50
    }, headers=headers)

    assert event_res.status_code == 403

def test_venue_conflict_detection():
    coord_res = client.post("/api/auth/login", json={
        "email": "riya.coord@smartfest.edu",
        "password": "Coord@123"
    })
    coord_token = coord_res.json()["access_token"]
    coord_headers = {"Authorization": f"Bearer {coord_token}"}

    # Seed Event 1 is at venue 2 (CS Lab 3), date 2026-11-25, 09:00-18:00
    res = client.post("/api/venues/check-conflict", json={
        "venue_id": 2,
        "date": "2026-11-25",
        "start_time": "10:00",
        "end_time": "14:00"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["has_conflict"] is True
    assert "Conflict detected" in data["reason"]

def test_event_approval_workflow():
    # 1. Coordinator creates a draft event (use a free venue/date combo)
    coord_res = client.post("/api/auth/login", json={
        "email": "riya.coord@smartfest.edu",
        "password": "Coord@123"
    })
    coord_token = coord_res.json()["access_token"]
    coord_headers = {"Authorization": f"Bearer {coord_token}"}

    create_res = client.post("/api/events", json={
        "title": "Web3 & Smart Contracts Workshop",
        "description": "Hands-on blockchain smart contract development.",
        "category": "Technical",
        "date": "2026-12-05",
        "start_time": "14:00",
        "end_time": "17:00",
        "venue_id": 4,  # Seminar Hall 1 (free on Dec 5)
        "max_capacity": 40
    }, headers=coord_headers)

    assert create_res.status_code == 201, f"Event creation failed: {create_res.json()}"
    event_id = create_res.json()["id"]
    assert create_res.json()["status"] == "draft"

    # 2. Coordinator submits event for approval
    submit_res = client.post(f"/api/events/{event_id}/submit", headers=coord_headers)
    assert submit_res.status_code == 200

    # 3. Admin approves and publishes event
    admin_res = client.post("/api/auth/login", json={
        "email": "admin@smartfest.edu",
        "password": "Admin@123"
    })
    admin_token = admin_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    approve_res = client.post(f"/api/events/{event_id}/approve", headers=admin_headers)
    assert approve_res.status_code == 200

    # 4. Verify event is now published in public catalog
    get_res = client.get(f"/api/events/{event_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "published"

def test_event_registration_and_qr_checkin():
    # 1. Student registers for Battle of the Bands (Event 2 — no seed registration exists for Anushka)
    student_res = client.post("/api/auth/login", json={
        "email": "anushka.student@smartfest.edu",
        "password": "Student@123"
    })
    student_token = student_res.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}

    reg_res = client.post("/api/registrations", json={"event_id": 2}, headers=student_headers)
    assert reg_res.status_code in [201, 200], f"Registration failed: {reg_res.json()}"
    reg_data = reg_res.json()
    assert reg_data["status"] == "confirmed"
    qr_token = reg_data["qr_code_token"]
    assert qr_token.startswith("SF-")

    # 2. Coordinator scans and verifies QR code at the gate
    coord_res = client.post("/api/auth/login", json={
        "email": "aman.coord@smartfest.edu",
        "password": "Coord@123"
    })
    coord_token = coord_res.json()["access_token"]
    coord_headers = {"Authorization": f"Bearer {coord_token}"}

    checkin_res = client.post("/api/checkin/verify", json={
        "qr_code_token": qr_token,
        "event_id": 2
    }, headers=coord_headers)

    assert checkin_res.status_code == 200
    checkin_data = checkin_res.json()
    assert checkin_data["success"] is True
    assert "Check-In Confirmed" in checkin_data["message"]
    assert checkin_data["checked_in_at"] is not None

    # 3. Test Duplicate Check-In Prevention
    dup_res = client.post("/api/checkin/verify", json={
        "qr_code_token": qr_token,
        "event_id": 2
    }, headers=coord_headers)

    assert dup_res.status_code == 200
    dup_data = dup_res.json()
    assert dup_data["success"] is False
    assert "ALREADY checked in" in dup_data["message"]

def test_ai_recommendations_engine():
    # Student Anushka has interests: ["Coding", "AI", "Robotics", "Web Development"]
    student_res = client.post("/api/auth/login", json={
        "email": "anushka.student@smartfest.edu",
        "password": "Student@123"
    })
    token = student_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    recs_res = client.get("/api/recommendations", headers=headers)
    assert recs_res.status_code == 200
    recs = recs_res.json()
    assert isinstance(recs, list)

    if len(recs) > 0:
        first_rec = recs[0]
        assert "recommendation_score" in first_rec
        assert "match_percentage" in first_rec
        assert "recommendation_reason" in first_rec
        # Technical / Robotics events should rank high for Anushka's interests
        assert first_rec["match_percentage"] > 0

def test_analytics_and_csv_export():
    admin_res = client.post("/api/auth/login", json={
        "email": "admin@smartfest.edu",
        "password": "Admin@123"
    })
    token = admin_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    analytics_res = client.get("/api/analytics/dashboard", headers=headers)
    assert analytics_res.status_code == 200
    data = analytics_res.json()
    assert "total_users" in data
    assert "total_events" in data
    assert "total_registrations" in data

    # CSV Export test
    csv_res = client.get("/api/analytics/export-roster/1", headers=headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")

    # JSON Roster test
    roster_res = client.get("/api/analytics/roster/1", headers=headers)
    assert roster_res.status_code == 200
    roster_data = roster_res.json()
    assert "event_id" in roster_data
    assert "participants" in roster_data
    assert isinstance(roster_data["participants"], list)

def test_flexible_date_and_time_event_creation():
    # Login as coordinator
    coord_res = client.post("/api/auth/login", json={
        "email": "riya.coord@smartfest.edu",
        "password": "Coord@123"
    })
    coord_token = coord_res.json()["access_token"]
    coord_headers = {"Authorization": f"Bearer {coord_token}"}

    # Create event with DD-MM-YYYY date format, time with seconds, and 2-letter title
    create_res = client.post("/api/events", json={
        "title": "SE",
        "description": "Software Engineering project submission and showcase.",
        "category": "Technical",
        "date": "28-11-2026",
        "start_time": "10:00:00",
        "end_time": "13:00:00",
        "venue_id": 3,
        "max_capacity": 50,
        "rules": "arrive on time",
        "eligibility": "all students"
    }, headers=coord_headers)

    assert create_res.status_code == 201, f"Expected 201, got {create_res.status_code}: {create_res.text}"
    ev = create_res.json()
    assert ev["date"] == "2026-11-28"
    assert ev["start_time"] == "10:00"
    assert ev["end_time"] == "13:00"
    assert ev["title"] == "SE"

    # Verify start_time >= end_time is rejected with clear 400 error
    bad_time_res = client.post("/api/events", json={
        "title": "Invalid Timing Event",
        "description": "Event with end time before start time.",
        "category": "Technical",
        "date": "29-11-2026",
        "start_time": "15:00",
        "end_time": "10:00",
        "venue_id": 3,
        "max_capacity": 50
    }, headers=coord_headers)
    assert bad_time_res.status_code == 400

def test_events_endpoint_returns_is_registered_flag():
    # 1. Login as student Anushka
    student_res = client.post("/api/auth/login", json={
        "email": "anushka.student@smartfest.edu",
        "password": "Student@123"
    })
    token = student_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Anushka is registered for Event 2 from previous test
    events_res = client.get("/api/events?status=published", headers=headers)
    assert events_res.status_code == 200
    events = events_res.json()

    ev2 = next((e for e in events if e["id"] == 2), None)
    assert ev2 is not None
    assert ev2["is_registered"] is True

    # Detail view also reflects is_registered
    detail_res = client.get("/api/events/2", headers=headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["is_registered"] is True

    # Clear client cookies to simulate unauthenticated request
    client.cookies.clear()
    anon_res = client.get("/api/events/2")
    assert anon_res.status_code == 200
    assert anon_res.json()["is_registered"] is False
