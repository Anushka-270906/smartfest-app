from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
import json
from app.database import get_db_connection
from app.models import UserResponse
from app.dependencies import require_role

router = APIRouter(prefix="/api/users", tags=["User & Role Management"])

@router.get("", response_model=List[UserResponse])
def get_all_users(
    role: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Admin-only: Retrieve all registered college accounts."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM users WHERE 1=1"
    params = []

    if role:
        query += " AND role = ?"
        params.append(role)

    if search:
        search_pattern = f"%{search.strip().lower()}%"
        query += " AND (LOWER(name) LIKE ? OR LOWER(email) LIKE ? OR LOWER(department) LIKE ?)"
        params.extend([search_pattern, search_pattern, search_pattern])

    query += " ORDER BY created_at DESC;"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        d = dict(r)
        d["interests"] = json.loads(d["interests"]) if d["interests"] else []
        del d["password_hash"]
        results.append(UserResponse(**d))

    return results

@router.put("/{user_id}/role")
def update_user_role(
    user_id: int, 
    new_role: str,
    current_user: dict = Depends(require_role(["admin"]))
):
    """Admin-only: Update user role (e.g. promote Student to Coordinator)."""
    if new_role not in ["student", "coordinator", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'student', 'coordinator', or 'admin'.")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, role FROM users WHERE id = ?;", (user_id,))
    target = cursor.fetchone()
    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")

    # Guard: prevent removing last admin
    if target["id"] == current_user["id"] and new_role != "admin":
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin';")
        admin_count = cursor.fetchone()[0]
        if admin_count <= 1:
            conn.close()
            raise HTTPException(status_code=400, detail="Cannot demote the only remaining administrator.")

    cursor.execute("UPDATE users SET role = ? WHERE id = ?;", (new_role, user_id))
    
    # Notify user of role upgrade
    cursor.execute("""
    INSERT INTO notifications (user_id, title, message, type)
    VALUES (?, ?, ?, 'announcement');
    """, (
        user_id,
        "Account Role Updated",
        f"Your SmartFest account role has been updated to: {new_role.capitalize()}."
    ))

    conn.commit()
    conn.close()

    return {"message": f"User '{target['name']}' role successfully changed to '{new_role}'."}
