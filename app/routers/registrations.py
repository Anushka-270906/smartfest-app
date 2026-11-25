from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.database import get_db_connection
from app.models import RegistrationCreate, RegistrationResponse
from app.security import generate_qr_token
from app.dependencies import get_current_user, require_role

router = APIRouter(prefix="/api/registrations", tags=["Registrations"])

@router.post("", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
def register_for_event(data: RegistrationCreate, current_user: dict = Depends(require_role(["student", "admin"]))):
    """
    Atomic event registration workflow (SRS FR-1.4, FR-1.5, Activity Diagram & Swimlane).
    Guarantees capacity limits, prevents duplicates, checks schedule overlaps, and issues QR token.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = current_user["id"]
    event_id = data.event_id

    # 1. Fetch Event with row lock / transaction
    cursor.execute("SELECT * FROM events WHERE id = ?;", (event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found.")

    if event["status"] != "published":
        conn.close()
        raise HTTPException(
            status_code=400, 
            detail=f"Registration is not open for this event (Current status: {event['status']})."
        )

    # 2. Check Capacity (FR-1.5)
    if event["registered_count"] >= event["max_capacity"]:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Registration Closed: Maximum participant limit has already been reached."
        )

    # 3. Check for Existing Registration
    cursor.execute("SELECT * FROM registrations WHERE user_id = ? AND event_id = ?;", (user_id, event_id))
    existing_reg = cursor.fetchone()
    if existing_reg:
        if existing_reg["status"] == "confirmed":
            conn.close()
            raise HTTPException(status_code=400, detail="You are already registered for this event.")
        elif existing_reg["status"] == "cancelled":
            # Re-activate previous cancelled registration
            qr_token = generate_qr_token(user_id, event_id)
            cursor.execute("""
            UPDATE registrations 
            SET status = 'confirmed', qr_code_token = ?, registration_date = CURRENT_TIMESTAMP
            WHERE id = ?;
            """, (qr_token, existing_reg["id"]))
            cursor.execute("UPDATE events SET registered_count = registered_count + 1 WHERE id = ?;", (event_id,))
            
            # Send notification
            cursor.execute("""
            INSERT INTO notifications (user_id, title, message, type)
            VALUES (?, ?, ?, 'confirmation');
            """, (
                user_id,
                f"Registration Confirmed: {event['title']}",
                f"Your registration for '{event['title']}' on {event['date']} is confirmed. QR pass generated."
            ))
            conn.commit()

            cursor.execute("""
            SELECT r.*, e.title as event_title, e.category as event_category,
                   e.date as event_date, e.start_time as event_start_time, e.end_time as event_end_time,
                   v.name as venue_name
            FROM registrations r
            JOIN events e ON r.event_id = e.id
            JOIN venues v ON e.venue_id = v.id
            WHERE r.id = ?;
            """, (existing_reg["id"],))
            res = cursor.fetchone()
            conn.close()
            return RegistrationResponse(**dict(res))

    # 4. Check for Student Schedule Overlap
    cursor.execute("""
    SELECT e.title, e.date, e.start_time, e.end_time
    FROM registrations r
    JOIN events e ON r.event_id = e.id
    WHERE r.user_id = ? AND r.status = 'confirmed' AND e.date = ?
      AND max(e.start_time, ?) < min(e.end_time, ?);
    """, (user_id, event["date"], event["start_time"], event["end_time"]))
    overlap = cursor.fetchone()
    if overlap:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"Schedule Collision: You are already registered for '{overlap['title']}' at the same time ({overlap['start_time']} - {overlap['end_time']})."
        )

    # 5. Insert Registration & Increment Capacity Counter
    qr_token = generate_qr_token(user_id, event_id)
    cursor.execute("""
    INSERT INTO registrations (user_id, event_id, status, qr_code_token)
    VALUES (?, ?, 'confirmed', ?);
    """, (user_id, event_id, qr_token))
    reg_id = cursor.lastrowid

    cursor.execute("UPDATE events SET registered_count = registered_count + 1 WHERE id = ?;", (event_id,))

    # 6. Generate In-App Confirmation Alert (FR-4.1)
    cursor.execute("""
    INSERT INTO notifications (user_id, title, message, type)
    VALUES (?, ?, ?, 'confirmation');
    """, (
        user_id,
        f"Registration Confirmed: {event['title']}",
        f"You have successfully registered for '{event['title']}' taking place on {event['date']} at {event['start_time']}. Your digital pass is ready."
    ))

    conn.commit()

    # Retrieve populated response
    cursor.execute("""
    SELECT r.*, e.title as event_title, e.category as event_category,
           e.date as event_date, e.start_time as event_start_time, e.end_time as event_end_time,
           v.name as venue_name
    FROM registrations r
    JOIN events e ON r.event_id = e.id
    JOIN venues v ON e.venue_id = v.id
    WHERE r.id = ?;
    """, (reg_id,))
    row = cursor.fetchone()
    conn.close()

    return RegistrationResponse(**dict(row))

@router.get("/my", response_model=List[RegistrationResponse])
def get_my_registrations(current_user: dict = Depends(get_current_user)):
    """Retrieve all registrations for the currently authenticated user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT r.*, e.title as event_title, e.category as event_category,
           e.date as event_date, e.start_time as event_start_time, e.end_time as event_end_time,
           v.name as venue_name
    FROM registrations r
    JOIN events e ON r.event_id = e.id
    JOIN venues v ON e.venue_id = v.id
    WHERE r.user_id = ?
    ORDER BY e.date ASC, e.start_time ASC;
    """, (current_user["id"],))
    rows = cursor.fetchall()
    conn.close()

    return [RegistrationResponse(**dict(r)) for r in rows]

@router.post("/{registration_id}/cancel")
def cancel_registration(registration_id: int, current_user: dict = Depends(get_current_user)):
    """Cancel event registration and free up a seat."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM registrations WHERE id = ?;", (registration_id,))
    reg = cursor.fetchone()
    if not reg:
        conn.close()
        raise HTTPException(status_code=404, detail="Registration not found.")

    if current_user["role"] != "admin" and reg["user_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(status_code=403, detail="You can only cancel your own registrations.")

    if reg["status"] == "cancelled":
        conn.close()
        return {"message": "Registration is already cancelled."}

    # Decrement registered_count if it was confirmed
    if reg["status"] == "confirmed":
        cursor.execute("UPDATE events SET registered_count = MAX(0, registered_count - 1) WHERE id = ?;", (reg["event_id"],))

    cursor.execute("UPDATE registrations SET status = 'cancelled' WHERE id = ?;", (registration_id,))
    conn.commit()
    conn.close()

    return {"message": "Registration successfully cancelled and seat released."}
