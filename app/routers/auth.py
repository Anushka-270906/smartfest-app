from fastapi import APIRouter, HTTPException, status, Depends, Response
import json
from app.database import get_db_connection
from app.models import UserRegister, UserLogin, UserResponse, TokenResponse, UserProfileUpdate
from app.security import hash_password, verify_password, create_access_token
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(data: UserRegister, response: Response):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if email is already registered
    cursor.execute("SELECT id FROM users WHERE email = ?;", (data.email.lower(),))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    pwd_hash = hash_password(data.password)
    interests_json = json.dumps(data.interests)

    cursor.execute("""
    INSERT INTO users (name, email, password_hash, role, department, year, phone, interests)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        data.name.strip(),
        data.email.lower(),
        pwd_hash,
        data.role,
        data.department.strip(),
        data.year,
        data.phone.strip() if data.phone else None,
        interests_json
    ))
    user_id = cursor.lastrowid
    conn.commit()

    # Retrieve created record
    cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
    row = cursor.fetchone()
    conn.close()

    user_dict = dict(row)
    user_dict["interests"] = json.loads(user_dict["interests"]) if user_dict["interests"] else []
    del user_dict["password_hash"]

    # Generate JWT
    token = create_access_token({"sub": str(user_id), "role": data.role})
    response.set_cookie(key="access_token", value=token, httponly=True, samesite="lax", max_age=86400)

    return TokenResponse(access_token=token, user=UserResponse(**user_dict))

@router.post("/login", response_model=TokenResponse)
def login_user(data: UserLogin, response: Response):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?;", (data.email.lower(),))
    row = cursor.fetchone()
    conn.close()

    if not row or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please verify your credentials."
        )

    user_dict = dict(row)
    user_dict["interests"] = json.loads(user_dict["interests"]) if user_dict["interests"] else []
    del user_dict["password_hash"]

    token = create_access_token({"sub": str(row["id"]), "role": row["role"]})
    response.set_cookie(key="access_token", value=token, httponly=True, samesite="lax", max_age=86400)

    return TokenResponse(access_token=token, user=UserResponse(**user_dict))

@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(**current_user)

@router.put("/profile", response_model=UserResponse)
def update_profile(data: UserProfileUpdate, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()

    updates = []
    params = []

    if data.name is not None:
        updates.append("name = ?")
        params.append(data.name.strip())
    if data.phone is not None:
        updates.append("phone = ?")
        params.append(data.phone.strip())
    if data.department is not None:
        updates.append("department = ?")
        params.append(data.department.strip())
    if data.year is not None:
        updates.append("year = ?")
        params.append(data.year)
    if data.interests is not None:
        updates.append("interests = ?")
        params.append(json.dumps(data.interests))

    if updates:
        params.append(current_user["id"])
        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?;", tuple(params))
        conn.commit()

    cursor.execute("SELECT * FROM users WHERE id = ?;", (current_user["id"],))
    row = cursor.fetchone()
    conn.close()

    user_dict = dict(row)
    user_dict["interests"] = json.loads(user_dict["interests"]) if user_dict["interests"] else []
    del user_dict["password_hash"]

    return UserResponse(**user_dict)

@router.post("/logout")
def logout_user(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Successfully logged out."}
