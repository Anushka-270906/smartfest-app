from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from app.database import get_db_connection
from app.models import VenueCreate, VenueResponse, VenueConflictCheck
from app.dependencies import get_current_user, require_role

router = APIRouter(prefix="/api/venues", tags=["Venues & Scheduling"])

@router.get("", response_model=List[VenueResponse])
def get_venues():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM venues ORDER BY name ASC;")
    rows = cursor.fetchall()
    conn.close()
    return [VenueResponse(**dict(r)) for r in rows]

@router.post("", response_model=VenueResponse, status_code=status.HTTP_201_CREATED)
def create_venue(data: VenueCreate, current_user: dict = Depends(require_role(["admin"]))):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM venues WHERE LOWER(name) = LOWER(?);", (data.name.strip(),))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="A venue with this name already exists.")

    cursor.execute("""
    INSERT INTO venues (name, location, capacity, is_available)
    VALUES (?, ?, ?, ?);
    """, (data.name.strip(), data.location.strip(), data.capacity, data.is_available))
    venue_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM venues WHERE id = ?;", (venue_id,))
    row = cursor.fetchone()
    conn.close()
    return VenueResponse(**dict(row))

@router.put("/{venue_id}", response_model=VenueResponse)
def update_venue(venue_id: int, data: VenueCreate, current_user: dict = Depends(require_role(["admin"]))):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM venues WHERE id = ?;", (venue_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Venue not found.")

    cursor.execute("""
    UPDATE venues SET name = ?, location = ?, capacity = ?, is_available = ?
    WHERE id = ?;
    """, (data.name.strip(), data.location.strip(), data.capacity, data.is_available, venue_id))
    conn.commit()

    cursor.execute("SELECT * FROM venues WHERE id = ?;", (venue_id,))
    row = cursor.fetchone()
    conn.close()
    return VenueResponse(**dict(row))

@router.post("/check-conflict")
def check_venue_conflict(data: VenueConflictCheck):
    """
    Algorithmic Room Conflict Verification (FR-3.4, Activity & Swimlane).
    Checks if target venue has any overlapping confirmed/published events for given date and time range.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check venue existence and availability
    cursor.execute("SELECT id, name, capacity, is_available FROM venues WHERE id = ?;", (data.venue_id,))
    venue = cursor.fetchone()
    if not venue:
        conn.close()
        raise HTTPException(status_code=404, detail="Venue not found.")

    if venue["is_available"] == 0:
        conn.close()
        return {
            "has_conflict": True,
            "reason": f"Venue '{venue['name']}' is currently disabled/under maintenance.",
            "conflicting_event": None
        }

    if data.start_time >= data.end_time:
        conn.close()
        return {
            "has_conflict": True,
            "reason": f"Start time ({data.start_time}) must be earlier than end time ({data.end_time}).",
            "conflicting_event": None
        }

    query = """
    SELECT id, title, start_time, end_time, status
    FROM events
    WHERE venue_id = ? AND date = ? AND status != 'cancelled'
      AND max(start_time, ?) < min(end_time, ?)
    """
    params = [data.venue_id, data.date, data.start_time, data.end_time]

    if data.exclude_event_id:
        query += " AND id != ?"
        params.append(data.exclude_event_id)

    cursor.execute(query, tuple(params))
    conflict = cursor.fetchone()
    conn.close()

    if conflict:
        return {
            "has_conflict": True,
            "reason": f"Conflict detected with '{conflict['title']}' ({conflict['start_time']} - {conflict['end_time']}).",
            "conflicting_event": dict(conflict)
        }

    return {
        "has_conflict": False,
        "reason": f"Venue '{venue['name']}' is available for the selected time window.",
        "conflicting_event": None
    }

@router.get("/schedule")
def get_fest_schedule():
    """Returns chronological schedule of all published fest events with venue details."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT e.id, e.title, e.category, e.date, e.start_time, e.end_time,
           v.name as venue_name, v.location as venue_location,
           u.name as coordinator_name
    FROM events e
    JOIN venues v ON e.venue_id = v.id
    JOIN users u ON e.coordinator_id = u.id
    WHERE e.status = 'published'
    ORDER BY e.date ASC, e.start_time ASC;
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
