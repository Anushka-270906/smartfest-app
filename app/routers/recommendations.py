from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from app.database import get_db_connection
from app.dependencies import get_current_user
from app.ml_engine import RecommendationEngine

router = APIRouter(prefix="/api/recommendations", tags=["AI/ML Recommendations"])

@router.get("", response_model=List[Dict[str, Any]])
def get_personalized_recommendations(current_user: dict = Depends(get_current_user)):
    """
    Computes personalized AI/ML event recommendations for the authenticated student.
    Uses TF-IDF + Cosine Similarity matching over interests, department, and past participation.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Fetch all events with venue info
    cursor.execute("""
    SELECT e.*, v.name as venue_name, v.location as venue_location,
           u.name as coordinator_name, u.email as coordinator_email
    FROM events e
    JOIN venues v ON e.venue_id = v.id
    JOIN users u ON e.coordinator_id = u.id;
    """)
    all_events = [dict(r) for r in cursor.fetchall()]

    # 2. Fetch student's registered events
    cursor.execute("""
    SELECT r.event_id, r.status, e.title as event_title, e.category as event_category,
           e.date as event_date, e.start_time as event_start_time, e.end_time as event_end_time
    FROM registrations r
    JOIN events e ON r.event_id = e.id
    WHERE r.user_id = ?;
    """, (current_user["id"],))
    registered_events = [dict(r) for r in cursor.fetchall()]
    conn.close()

    # 3. Compute recommendations
    recommendations = RecommendationEngine.get_recommendations_for_student(
        student_id=current_user["id"],
        student_interests=current_user.get("interests", []),
        student_department=current_user.get("department", ""),
        all_events=all_events,
        registered_events=registered_events,
        top_k=6
    )

    return recommendations
