from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from app.database import get_db_connection
from app.models import FeedbackCreate, FeedbackResponse
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])

@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(data: FeedbackCreate, current_user: dict = Depends(get_current_user)):
    """Submit post-event feedback and star rating (SRS FR-5.2)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Verify event exists
    cursor.execute("SELECT id, title FROM events WHERE id = ?;", (data.event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found.")

    # Verify student is registered or attended
    cursor.execute("SELECT status FROM registrations WHERE user_id = ? AND event_id = ?;", (current_user["id"], data.event_id))
    reg = cursor.fetchone()
    if not reg and current_user["role"] == "student":
        conn.close()
        raise HTTPException(status_code=400, detail="You can only submit feedback for events you registered for.")

    # Check if already submitted
    cursor.execute("SELECT id FROM feedback WHERE user_id = ? AND event_id = ?;", (current_user["id"], data.event_id))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="You have already submitted feedback for this event.")

    cursor.execute("""
    INSERT INTO feedback (user_id, event_id, rating, comments)
    VALUES (?, ?, ?, ?);
    """, (current_user["id"], data.event_id, data.rating, data.comments.strip() if data.comments else None))
    feedback_id = cursor.lastrowid
    conn.commit()

    cursor.execute("""
    SELECT f.*, u.name as user_name, e.title as event_title
    FROM feedback f
    JOIN users u ON f.user_id = u.id
    JOIN events e ON f.event_id = e.id
    WHERE f.id = ?;
    """, (feedback_id,))
    row = cursor.fetchone()
    conn.close()

    return FeedbackResponse(**dict(row))

@router.get("/event/{event_id}", response_model=List[FeedbackResponse])
def get_event_feedback(event_id: int):
    """Retrieve all feedback reviews for an event."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT f.*, u.name as user_name, e.title as event_title
    FROM feedback f
    JOIN users u ON f.user_id = u.id
    JOIN events e ON f.event_id = e.id
    WHERE f.event_id = ?
    ORDER BY f.created_at DESC;
    """, (event_id,))
    rows = cursor.fetchall()
    conn.close()
    return [FeedbackResponse(**dict(r)) for r in rows]
