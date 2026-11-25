from fastapi import APIRouter, HTTPException, status, Depends, Response
from typing import Optional
import io
import qrcode
from datetime import datetime, timezone
from app.database import get_db_connection
from app.models import CheckInRequest, CheckInResponse
from app.dependencies import get_current_user, require_role

router = APIRouter(prefix="/api/checkin", tags=["Digital Event Check-In"])

@router.get("/qr/{qr_token}")
def get_qr_image(qr_token: str):
    """Generate and return a scannable PNG QR code for a given registration token."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(qr_token)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return Response(content=buf.getvalue(), media_type="image/png")

@router.post("/verify", response_model=CheckInResponse)
def verify_check_in(
    data: CheckInRequest,
    current_user: dict = Depends(require_role(["coordinator", "admin"]))
):
    """
    Coordinator / Admin scans student QR code at the event gate (SRS FR-5.1).
    Validates token, event match, prevents duplicate check-ins, and records attendance timestamp.
    """
    token = data.qr_code_token.strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query registration by token
    cursor.execute("""
    SELECT r.*, u.name as student_name, u.email as student_email, u.department as student_department,
           e.title as event_title, e.coordinator_id, e.id as event_id
    FROM registrations r
    JOIN users u ON r.user_id = u.id
    JOIN events e ON r.event_id = e.id
    WHERE r.qr_code_token = ?;
    """, (token,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Invalid QR Code: Registration pass not found in the SmartFest registry."
        )

    # If coordinator, ensure they have permissions for this event (or admin)
    if current_user["role"] == "coordinator" and row["coordinator_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(
            status_code=403,
            detail=f"Unauthorized: You are not assigned as coordinator for '{row['event_title']}'."
        )

    # If event_id was explicitly provided, verify match
    if data.event_id and data.event_id != row["event_id"]:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Event Mismatch: This pass belongs to '{row['event_title']}', not the current event scanner."
        )

    if row["status"] == "cancelled":
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Registration Cancelled: Student '{row['student_name']}' cancelled this registration."
        )

    # Check duplicate check-in
    if row["status"] == "attended" or row["checked_in_at"] is not None:
        conn.close()
        return CheckInResponse(
            success=False,
            message=f"Duplicate Check-In Warning: Student '{row['student_name']}' was ALREADY checked in at {row['checked_in_at']}.",
            student_name=row["student_name"],
            student_email=row["student_email"],
            student_department=row["student_department"],
            event_title=row["event_title"],
            checked_in_at=row["checked_in_at"]
        )

    # Record Attendance
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    UPDATE registrations 
    SET status = 'attended', checked_in_at = ? 
    WHERE id = ?;
    """, (now_str, row["id"]))
    conn.commit()
    conn.close()

    return CheckInResponse(
        success=True,
        message=f"Check-In Confirmed! Welcome, {row['student_name']}.",
        student_name=row["student_name"],
        student_email=row["student_email"],
        student_department=row["student_department"],
        event_title=row["event_title"],
        checked_in_at=now_str
    )
