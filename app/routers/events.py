from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from app.database import get_db_connection
from app.models import EventCreate, EventUpdate, EventResponse
from app.dependencies import get_current_user, require_role, get_optional_current_user

router = APIRouter(prefix="/api/events", tags=["Events"])

@router.get("", response_model=List[EventResponse])
def get_events(
    category: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    coordinator_id: Optional[int] = None,
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
    SELECT e.*, 
           v.name as venue_name, v.location as venue_location,
           u.name as coordinator_name, u.email as coordinator_email
    FROM events e
    JOIN venues v ON e.venue_id = v.id
    JOIN users u ON e.coordinator_id = u.id
    WHERE 1=1
    """
    params = []

    # If status not explicitly requested, default to published for general browsing
    if status_filter:
        query += " AND e.status = ?"
        params.append(status_filter)
    
    if category and category.lower() != "all":
        query += " AND LOWER(e.category) = LOWER(?)"
        params.append(category)

    if search:
        search_pattern = f"%{search.strip().lower()}%"
        query += " AND (LOWER(e.title) LIKE ? OR LOWER(e.description) LIKE ? OR LOWER(v.name) LIKE ?)"
        params.extend([search_pattern, search_pattern, search_pattern])

    if coordinator_id:
        query += " AND e.coordinator_id = ?"
        params.append(coordinator_id)

    query += " ORDER BY e.date ASC, e.start_time ASC;"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    registered_ids = set()
    if current_user:
        cursor.execute("SELECT event_id FROM registrations WHERE user_id = ? AND status IN ('confirmed', 'attended');", (current_user["id"],))
        registered_ids = {r["event_id"] for r in cursor.fetchall()}

    results = []
    for r in rows:
        d = dict(r)
        d["available_seats"] = max(0, d["max_capacity"] - d["registered_count"])
        d["is_registered"] = d["id"] in registered_ids
        results.append(EventResponse(**d))

    conn.close()
    return results

@router.get("/{event_id}", response_model=EventResponse)
def get_event_detail(event_id: int, current_user: Optional[dict] = Depends(get_optional_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT e.*, 
           v.name as venue_name, v.location as venue_location,
           u.name as coordinator_name, u.email as coordinator_email
    FROM events e
    JOIN venues v ON e.venue_id = v.id
    JOIN users u ON e.coordinator_id = u.id
    WHERE e.id = ?;
    """, (event_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found.")

    d = dict(row)
    d["available_seats"] = max(0, d["max_capacity"] - d["registered_count"])
    d["is_registered"] = False
    if current_user:
        cursor.execute("SELECT qr_code_token, status FROM registrations WHERE user_id = ? AND event_id = ? AND status IN ('confirmed', 'attended');", (current_user["id"], event_id))
        reg_row = cursor.fetchone()
        if reg_row:
            d["is_registered"] = True
            d["qr_code_token"] = reg_row["qr_code_token"]
            d["attendance_status"] = reg_row["status"]

    conn.close()
    return EventResponse(**d)

@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(data: EventCreate, current_user: dict = Depends(require_role(["coordinator", "admin"]))):
    if data.start_time >= data.end_time:
        raise HTTPException(
            status_code=400,
            detail=f"Start time ({data.start_time}) must be earlier than end time ({data.end_time})."
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Verify Venue exists and is available
    cursor.execute("SELECT id, name, capacity, is_available FROM venues WHERE id = ?;", (data.venue_id,))
    venue = cursor.fetchone()
    if not venue:
        conn.close()
        raise HTTPException(status_code=400, detail="Specified venue does not exist.")
    if venue["is_available"] == 0:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Venue '{venue['name']}' is currently under maintenance.")
    if data.max_capacity > venue["capacity"]:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Requested max capacity ({data.max_capacity}) exceeds venue physical capacity limit ({venue['capacity']})."
        )

    # 2. Check for venue time conflict (FR-3.4)
    cursor.execute("""
    SELECT id, title, start_time, end_time FROM events
    WHERE venue_id = ? AND date = ? AND status != 'cancelled'
      AND max(start_time, ?) < min(end_time, ?);
    """, (data.venue_id, data.date, data.start_time, data.end_time))
    conflict = cursor.fetchone()
    if conflict:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"Scheduling Conflict: Venue is already booked for '{conflict['title']}' from {conflict['start_time']} to {conflict['end_time']}."
        )

    # 3. Determine initial status: Admin creates as 'approved' / 'published', Coordinator creates as 'draft'
    initial_status = "published" if current_user["role"] == "admin" else "draft"

    cursor.execute("""
    INSERT INTO events (
        title, description, category, date, start_time, end_time,
        venue_id, coordinator_id, max_capacity, registered_count,
        rules, eligibility, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?);
    """, (
        data.title.strip(),
        data.description.strip(),
        data.category.strip(),
        data.date,
        data.start_time,
        data.end_time,
        data.venue_id,
        current_user["id"],
        data.max_capacity,
        data.rules.strip() if data.rules else None,
        data.eligibility.strip() if data.eligibility else None,
        initial_status
    ))
    event_id = cursor.lastrowid
    conn.commit()

    cursor.execute("""
    SELECT e.*, v.name as venue_name, v.location as venue_location,
           u.name as coordinator_name, u.email as coordinator_email
    FROM events e
    JOIN venues v ON e.venue_id = v.id
    JOIN users u ON e.coordinator_id = u.id
    WHERE e.id = ?;
    """, (event_id,))
    row = cursor.fetchone()
    conn.close()

    d = dict(row)
    d["available_seats"] = max(0, d["max_capacity"] - d["registered_count"])
    return EventResponse(**d)

@router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int, 
    data: EventUpdate, 
    current_user: dict = Depends(require_role(["coordinator", "admin"]))
):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM events WHERE id = ?;", (event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found.")

    # Only creator coordinator or admin can edit
    if current_user["role"] == "coordinator" and event["coordinator_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(status_code=403, detail="You can only edit events you coordinate.")

    updates = []
    params = []

    new_date = data.date or event["date"]
    new_venue_id = data.venue_id or event["venue_id"]
    new_start_time = data.start_time or event["start_time"]
    new_end_time = data.end_time or event["end_time"]

    # Check venue conflict if venue, date, or timing changed
    if (new_venue_id != event["venue_id"] or new_date != event["date"] or 
        new_start_time != event["start_time"] or new_end_time != event["end_time"]):
        cursor.execute("""
        SELECT id, title, start_time, end_time FROM events
        WHERE venue_id = ? AND date = ? AND id != ? AND status != 'cancelled'
          AND max(start_time, ?) < min(end_time, ?);
        """, (new_venue_id, new_date, event_id, new_start_time, new_end_time))
        conflict = cursor.fetchone()
        if conflict:
            conn.close()
            raise HTTPException(
                status_code=409,
                detail=f"Scheduling Conflict: Venue is booked for '{conflict['title']}' ({conflict['start_time']} - {conflict['end_time']})."
            )

    fields = [
        ("title", data.title), ("description", data.description),
        ("category", data.category), ("date", data.date),
        ("start_time", data.start_time), ("end_time", data.end_time),
        ("venue_id", data.venue_id), ("max_capacity", data.max_capacity),
        ("rules", data.rules), ("eligibility", data.eligibility),
        ("status", data.status)
    ]
    for key, val in fields:
        if val is not None:
            updates.append(f"{key} = ?")
            params.append(val)

    if updates:
        params.append(event_id)
        cursor.execute(f"UPDATE events SET {', '.join(updates)} WHERE id = ?;", tuple(params))

        # If venue or schedule changed, trigger notification to registered students (FR-4.3)
        if new_date != event["date"] or new_start_time != event["start_time"] or new_venue_id != event["venue_id"]:
            cursor.execute("SELECT user_id FROM registrations WHERE event_id = ? AND status = 'confirmed';", (event_id,))
            registrations = cursor.fetchall()
            for reg in registrations:
                cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type)
                VALUES (?, ?, ?, 'schedule_change');
                """, (
                    reg["user_id"],
                    f"Schedule/Venue Update: {event['title']}",
                    f"Notice: Schedule or venue for '{event['title']}' has been updated to {new_date} from {new_start_time} to {new_end_time}."
                ))

        conn.commit()

    cursor.execute("""
    SELECT e.*, v.name as venue_name, v.location as venue_location,
           u.name as coordinator_name, u.email as coordinator_email
    FROM events e
    JOIN venues v ON e.venue_id = v.id
    JOIN users u ON e.coordinator_id = u.id
    WHERE e.id = ?;
    """, (event_id,))
    row = cursor.fetchone()
    conn.close()

    d = dict(row)
    d["available_seats"] = max(0, d["max_capacity"] - d["registered_count"])
    return EventResponse(**d)

@router.post("/{event_id}/submit")
def submit_for_approval(event_id: int, current_user: dict = Depends(require_role(["coordinator", "admin"]))):
    """Swimlane Workflow: Coordinator submits draft to Administrator for review."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?;", (event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found.")

    cursor.execute("UPDATE events SET status = 'pending' WHERE id = ?;", (event_id,))
    
    # Notify administrators of new pending event
    cursor.execute("SELECT id FROM users WHERE role = 'admin';")
    admins = cursor.fetchall()
    for a in admins:
        cursor.execute("""
        INSERT INTO notifications (user_id, title, message, type)
        VALUES (?, ?, ?, 'announcement');
        """, (
            a["id"],
            f"Event Pending Review: {event['title']}",
            f"Coordinator {current_user['name']} has submitted '{event['title']}' for administrative review and publication approval."
        ))

    conn.commit()
    conn.close()
    return {"message": "Event submitted for administrative approval."}

@router.post("/{event_id}/approve")
def approve_event(event_id: int, current_user: dict = Depends(require_role(["admin"]))):
    """Swimlane Workflow: Administrator approves event and publishes it."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?;", (event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found.")

    cursor.execute("UPDATE events SET status = 'published' WHERE id = ?;", (event_id,))

    # Notify coordinator
    cursor.execute("""
    INSERT INTO notifications (user_id, title, message, type)
    VALUES (?, ?, ?, 'announcement');
    """, (
        event["coordinator_id"],
        f"Event Approved: {event['title']}",
        f"Your event '{event['title']}' has been reviewed, approved, and published to the fest catalog."
    ))

    conn.commit()
    conn.close()
    return {"message": "Event approved and published campus-wide."}

@router.post("/{event_id}/reject")
def reject_event(event_id: int, reason: Optional[str] = "Needs revision", current_user: dict = Depends(require_role(["admin"]))):
    """Swimlane Workflow: Administrator rejects event with notes."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?;", (event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found.")

    cursor.execute("UPDATE events SET status = 'draft' WHERE id = ?;", (event_id,))
    cursor.execute("""
    INSERT INTO notifications (user_id, title, message, type)
    VALUES (?, ?, ?, 'announcement');
    """, (
        event["coordinator_id"],
        f"Revision Requested: {event['title']}",
        f"Administrator returned event '{event['title']}' for adjustments: {reason}"
    ))
    conn.commit()
    conn.close()
    return {"message": "Event returned to draft status for revision."}

@router.post("/{event_id}/cancel")
def cancel_event(event_id: int, current_user: dict = Depends(require_role(["coordinator", "admin"]))):
    """Cancel event and notify all enrolled participants (FR-1.6 & FR-4.3)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?;", (event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found.")

    cursor.execute("UPDATE events SET status = 'cancelled' WHERE id = ?;", (event_id,))

    # Notify all registered students
    cursor.execute("SELECT user_id FROM registrations WHERE event_id = ? AND status = 'confirmed';", (event_id,))
    registrations = cursor.fetchall()
    for r in registrations:
        cursor.execute("""
        INSERT INTO notifications (user_id, title, message, type)
        VALUES (?, ?, ?, 'cancellation');
        """, (
            r["user_id"],
            f"Event Cancelled: {event['title']}",
            f"Notice: The event '{event['title']}' scheduled for {event['date']} has been cancelled."
        ))

    conn.commit()
    conn.close()
    return {"message": "Event successfully cancelled. Registered participants have been notified."}
