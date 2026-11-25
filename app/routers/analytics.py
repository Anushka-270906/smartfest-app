from fastapi import APIRouter, HTTPException, Depends, Response
from typing import Dict, Any
import csv
import io
from app.database import get_db_connection
from app.dependencies import get_current_user, require_role

router = APIRouter(prefix="/api/analytics", tags=["Reports & Analytics"])

@router.get("/dashboard")
def get_analytics_dashboard(current_user: dict = Depends(require_role(["coordinator", "admin"]))):
    """
    Real SQL aggregate analytics calculated directly from live database tables.
    Provides fest-wide metrics, attendance ratios, and category breakdowns.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # User metrics
    cursor.execute("SELECT COUNT(*) FROM users;")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT role, COUNT(*) as count FROM users GROUP BY role;")
    role_counts = {r["role"]: r["count"] for r in cursor.fetchall()}

    # Event metrics
    cursor.execute("SELECT COUNT(*) FROM events;")
    total_events = cursor.fetchone()[0]

    cursor.execute("SELECT status, COUNT(*) as count FROM events GROUP BY status;")
    event_status_counts = {r["status"]: r["count"] for r in cursor.fetchall()}

    # Registration metrics
    cursor.execute("SELECT COUNT(*) FROM registrations;")
    total_registrations = cursor.fetchone()[0]

    cursor.execute("SELECT status, COUNT(*) as count FROM registrations GROUP BY status;")
    reg_status_counts = {r["status"]: r["count"] for r in cursor.fetchall()}

    # Attendance Rate calculation
    attended_count = reg_status_counts.get("attended", 0)
    confirmed_count = reg_status_counts.get("confirmed", 0)
    attendance_rate = 0.0
    if (attended_count + confirmed_count) > 0:
        attendance_rate = round((attended_count / (attended_count + confirmed_count)) * 100, 1)

    # Category-wise registrations popularity
    cursor.execute("""
    SELECT e.category, COUNT(r.id) as reg_count, COUNT(DISTINCT e.id) as event_count
    FROM events e
    LEFT JOIN registrations r ON e.id = r.event_id AND r.status != 'cancelled'
    GROUP BY e.category
    ORDER BY reg_count DESC;
    """)
    category_breakdown = [dict(r) for r in cursor.fetchall()]

    # Top events by registration
    cursor.execute("""
    SELECT e.id, e.title, e.category, e.registered_count, e.max_capacity,
           ROUND(CAST(e.registered_count AS FLOAT) / MAX(1, e.max_capacity) * 100, 1) as fill_percentage
    FROM events e
    WHERE e.status = 'published'
    ORDER BY e.registered_count DESC LIMIT 5;
    """)
    top_events = [dict(r) for r in cursor.fetchall()]

    # Feedback averages
    cursor.execute("SELECT COUNT(*) as review_count, ROUND(AVG(rating), 2) as avg_rating FROM feedback;")
    feedback_stats = dict(cursor.fetchone())

    conn.close()

    return {
        "total_users": total_users,
        "users_by_role": role_counts,
        "total_events": total_events,
        "events_by_status": event_status_counts,
        "total_registrations": total_registrations,
        "registrations_by_status": reg_status_counts,
        "attendance_rate_percentage": attendance_rate,
        "category_popularity": category_breakdown,
        "top_events": top_events,
        "feedback_summary": feedback_stats
    }

@router.get("/roster/{event_id}")
def get_event_roster(event_id: int, current_user: dict = Depends(require_role(["coordinator", "admin"]))):
    """
    Returns JSON list of registered participants for a given event, including check-in status and QR token.
    Accessible by assigned coordinator or administrator.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, coordinator_id FROM events WHERE id = ?;", (event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found.")

    if current_user["role"] == "coordinator" and event["coordinator_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Unauthorized to view rosters for other coordinators' events.")

    cursor.execute("""
    SELECT r.id as reg_id, u.name as student_name, u.email as student_email,
           u.department, u.year, u.phone, r.status as registration_status,
           r.registration_date, r.checked_in_at, r.qr_code_token
    FROM registrations r
    JOIN users u ON r.user_id = u.id
    WHERE r.event_id = ?
    ORDER BY r.registration_date ASC;
    """, (event_id,))
    rows = cursor.fetchall()
    conn.close()

    participants = [dict(r) for r in rows]
    return {
        "event_id": event["id"],
        "event_title": event["title"],
        "total_registered": len(participants),
        "participants": participants
    }

@router.get("/export-roster/{event_id}")
def export_event_roster_csv(event_id: int, current_user: dict = Depends(require_role(["coordinator", "admin"]))):
    """
    Streams a CSV file containing all registered students and their check-in status for an event.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT title, coordinator_id FROM events WHERE id = ?;", (event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found.")

    if current_user["role"] == "coordinator" and event["coordinator_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Unauthorized to export rosters for other coordinators' events.")

    cursor.execute("""
    SELECT r.id as reg_id, u.name as student_name, u.email as student_email,
           u.department, u.year, u.phone, r.status as registration_status,
           r.registration_date, r.checked_in_at, r.qr_code_token
    FROM registrations r
    JOIN users u ON r.user_id = u.id
    WHERE r.event_id = ?
    ORDER BY r.registration_date ASC;
    """, (event_id,))
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Registration ID", "Student Name", "Email", "Department",
        "Year", "Phone", "Status", "Registered At", "Checked In At", "Pass Token"
    ])

    for r in rows:
        writer.writerow([
            r["reg_id"], r["student_name"], r["student_email"], r["department"],
            r["year"], r["phone"] or "N/A", r["registration_status"],
            r["registration_date"], r["checked_in_at"] or "Not Checked In", r["qr_code_token"]
        ])

    csv_data = output.getvalue()
    filename = f"SmartFest_Roster_{event['title'].replace(' ', '_')}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
