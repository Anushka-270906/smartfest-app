from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
import re

def normalize_date_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = str(v).strip()
    if not v:
        return v
    m = re.match(r"^(\d{2})[-/](\d{2})[-/](\d{4})$", v)
    if m:
        d, mth, y = m.groups()
        return f"{y}-{mth}-{d}"
    if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        return v
    raise ValueError("Date must be in YYYY-MM-DD or DD-MM-YYYY format")

def normalize_time_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = str(v).strip()
    if not v:
        return v
    m = re.match(r"^(\d{2}:\d{2})(?::\d{2})?$", v)
    if m:
        return m.group(1)
    raise ValueError("Time must be in HH:MM format")

# --- AUTH & USER MODELS ---
class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: str = Field("student", pattern="^(student|coordinator|admin)$")
    department: str = Field(..., min_length=2, max_length=100)
    year: int = Field(1, ge=1, le=5)
    phone: Optional[str] = None
    interests: List[str] = []

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    year: Optional[int] = None
    interests: Optional[List[str]] = None

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    department: str
    year: int
    phone: Optional[str] = None
    interests: List[str] = []
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# --- VENUE MODELS ---
class VenueCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    location: str = Field(..., min_length=2, max_length=150)
    capacity: int = Field(..., gt=0)
    is_available: int = 1

class VenueResponse(BaseModel):
    id: int
    name: str
    location: str
    capacity: int
    is_available: int

class VenueConflictCheck(BaseModel):
    venue_id: int
    date: str
    start_time: str
    end_time: str
    exclude_event_id: Optional[int] = None

    @field_validator("date", mode="before")
    @classmethod
    def clean_date(cls, v):
        return normalize_date_str(v)

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def clean_time(cls, v):
        return normalize_time_str(v)

# --- EVENT MODELS ---
class EventCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=150)
    description: str = Field(..., min_length=5)
    category: str = Field(..., min_length=2, max_length=50)
    date: str
    start_time: str
    end_time: str
    venue_id: int
    max_capacity: int = Field(..., gt=0)
    rules: Optional[str] = None
    eligibility: Optional[str] = None

    @field_validator("date", mode="before")
    @classmethod
    def clean_date(cls, v):
        return normalize_date_str(v)

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def clean_time(cls, v):
        return normalize_time_str(v)

class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    venue_id: Optional[int] = None
    max_capacity: Optional[int] = None
    rules: Optional[str] = None
    eligibility: Optional[str] = None
    status: Optional[str] = None

    @field_validator("date", mode="before")
    @classmethod
    def clean_date(cls, v):
        return normalize_date_str(v)

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def clean_time(cls, v):
        return normalize_time_str(v)

class EventResponse(BaseModel):
    id: int
    title: str
    description: str
    category: str
    date: str
    start_time: str
    end_time: str
    venue_id: int
    venue_name: Optional[str] = None
    venue_location: Optional[str] = None
    coordinator_id: int
    coordinator_name: Optional[str] = None
    coordinator_email: Optional[str] = None
    max_capacity: int
    registered_count: int
    available_seats: int
    rules: Optional[str] = None
    eligibility: Optional[str] = None
    status: str
    is_registered: Optional[bool] = False
    qr_code_token: Optional[str] = None
    attendance_status: Optional[str] = None

# --- REGISTRATION MODELS ---
class RegistrationCreate(BaseModel):
    event_id: int

class RegistrationResponse(BaseModel):
    id: int
    user_id: int
    event_id: int
    event_title: str
    event_category: str
    event_date: str
    event_start_time: str
    event_end_time: str
    venue_name: str
    status: str
    qr_code_token: str
    registration_date: str
    checked_in_at: Optional[str] = None

# --- CHECK-IN MODELS ---
class CheckInRequest(BaseModel):
    qr_code_token: str
    event_id: Optional[int] = None

class CheckInResponse(BaseModel):
    success: bool
    message: str
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    student_department: Optional[str] = None
    event_title: Optional[str] = None
    checked_in_at: Optional[str] = None

# --- FEEDBACK MODELS ---
class FeedbackCreate(BaseModel):
    event_id: int
    rating: int = Field(..., ge=1, le=5)
    comments: Optional[str] = None

class FeedbackResponse(BaseModel):
    id: int
    user_id: int
    user_name: str
    event_id: int
    event_title: str
    rating: int
    comments: Optional[str] = None
    created_at: str

# --- NOTIFICATION MODELS ---
class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: str
    is_read: int
    created_at: str

class BroadcastCreate(BaseModel):
    title: str
    message: str
    type: str = "announcement"
    event_id: Optional[int] = None # If provided, only sends to registered students for that event
    role: Optional[str] = None     # If provided, only sends to that role
