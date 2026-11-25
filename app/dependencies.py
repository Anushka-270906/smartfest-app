from fastapi import Depends, HTTPException, status, Header, Cookie
from typing import Optional, List
import json
from app.security import decode_access_token
from app.database import get_db_connection

def get_current_user(
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None)
) -> dict:
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif access_token:
        token = access_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed session subject in token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, name, email, role, department, year, phone, interests, created_at 
    FROM users WHERE id = ?;
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with this token was not found.",
        )

    user = dict(row)
    try:
        user["interests"] = json.loads(user["interests"]) if user["interests"] else []
    except Exception:
        user["interests"] = []

    return user

def get_optional_current_user(
    authorization: Optional[str] = Header(None),
    access_token: Optional[str] = Cookie(None)
) -> Optional[dict]:
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif access_token:
        token = access_token

    if not token:
        return None

    try:
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            return None
        user_id = int(payload["sub"])
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, name, email, role, department, year, phone, interests, created_at 
        FROM users WHERE id = ?;
        """, (user_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        user = dict(row)
        try:
            user["interests"] = json.loads(user["interests"]) if user["interests"] else []
        except Exception:
            user["interests"] = []
        return user
    except Exception:
        return None

def require_role(allowed_roles: List[str]):
    """RBAC Dependency: restricts route to specific roles."""
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}. Your role: {current_user['role']}"
            )
        return current_user
    return role_checker
