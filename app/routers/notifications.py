from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.database import get_db_connection
from app.models import NotificationResponse, BroadcastCreate
from app.dependencies import get_current_user, require_role

router = APIRouter(prefix="/api/notifications", tags=["Notifications & Alerts"])

@router.get("", response_model=List[NotificationResponse])
def get_my_notifications(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM notifications 
    WHERE user_id = ? 
    ORDER BY created_at DESC LIMIT 50;
    """, (current_user["id"],))
    rows = cursor.fetchall()
    conn.close()
    return [NotificationResponse(**dict(r)) for r in rows]

@router.get("/unread-count")
def get_unread_count(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT COUNT(*) FROM notifications 
    WHERE user_id = ? AND is_read = 0;
    """, (current_user["id"],))
    count = cursor.fetchone()[0]
    conn.close()
    return {"unread_count": count}

@router.put("/{notif_id}/read")
def mark_as_read(notif_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE notifications SET is_read = 1 
    WHERE id = ? AND user_id = ?;
    """, (notif_id, current_user["id"]))
    conn.commit()
    conn.close()
    return {"message": "Notification marked as read."}

@router.put("/read-all")
def mark_all_as_read(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE notifications SET is_read = 1 
    WHERE user_id = ?;
    """, (current_user["id"],))
    conn.commit()
    conn.close()
    return {"message": "All notifications marked as read."}

@router.post("/broadcast", status_code=status.HTTP_201_CREATED)
def send_broadcast(data: BroadcastCreate, current_user: dict = Depends(require_role(["coordinator", "admin"]))):
    """
    Sends targeted or fest-wide announcements (FR-4.6).
    If event_id is specified, alerts only students enrolled in that competition.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    recipients = []

    if data.event_id:
        cursor.execute("SELECT user_id FROM registrations WHERE event_id = ? AND status = 'confirmed';", (data.event_id,))
        recipients = [r["user_id"] for r in cursor.fetchall()]
    elif data.role:
        cursor.execute("SELECT id FROM users WHERE role = ?;", (data.role,))
        recipients = [r["id"] for r in cursor.fetchall()]
    else:
        # All users
        cursor.execute("SELECT id FROM users;")
        recipients = [r["id"] for r in cursor.fetchall()]

    for uid in recipients:
        cursor.execute("""
        INSERT INTO notifications (user_id, title, message, type)
        VALUES (?, ?, ?, ?);
        """, (uid, data.title.strip(), data.message.strip(), data.type))

    conn.commit()
    conn.close()

    # Simulated External Email/SMS Gateway Dispatch Log (Experiment 9)
    print(f"[Email/SMS Gateway Dispatch] Dispatched '{data.title}' to {len(recipients)} recipients via HTTPS SMTP/SMS Gateway.")

    return {
        "message": f"Broadcast successfully dispatched to {len(recipients)} recipient(s).",
        "recipients_count": len(recipients),
        "gateway_status": "SENT_VIA_MOCK_GATEWAY"
    }
