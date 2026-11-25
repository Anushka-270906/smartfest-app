import sqlite3
import os
import json
from datetime import datetime, timezone
from app.config import DB_PATH
from app.security import hash_password, generate_qr_token

def get_db_connection():
    """Create a new SQLite connection with dict-like row access and FKs enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db():
    """Initialize all tables according to DFD data stores and Class Diagrams."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # D1 - User Database
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student', 'coordinator', 'admin')),
        department TEXT NOT NULL,
        year INTEGER DEFAULT 1,
        phone TEXT,
        interests TEXT DEFAULT '[]', -- JSON array of interest tags
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # D4 - Venue Database
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS venues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        location TEXT NOT NULL,
        capacity INTEGER NOT NULL,
        is_available INTEGER DEFAULT 1, -- 1 = available, 0 = under maintenance
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # D2 - Event Database
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL, -- 'Technical', 'Cultural', 'Literary', 'Gaming', 'Robotics', 'Sports'
        date TEXT NOT NULL, -- YYYY-MM-DD
        start_time TEXT NOT NULL, -- HH:MM (24h)
        end_time TEXT NOT NULL, -- HH:MM (24h)
        venue_id INTEGER NOT NULL,
        coordinator_id INTEGER NOT NULL,
        max_capacity INTEGER NOT NULL,
        registered_count INTEGER DEFAULT 0,
        rules TEXT,
        eligibility TEXT,
        status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'pending', 'approved', 'published', 'completed', 'cancelled')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (venue_id) REFERENCES venues (id) ON DELETE RESTRICT,
        FOREIGN KEY (coordinator_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)

    # D3 - Registration Database
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        event_id INTEGER NOT NULL,
        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN ('confirmed', 'cancelled', 'attended')),
        qr_code_token TEXT UNIQUE NOT NULL,
        checked_in_at TIMESTAMP,
        UNIQUE(user_id, event_id),
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
    );
    """)

    # D5 - Notification Database
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'info', -- 'confirmation', 'reminder', 'schedule_change', 'cancellation', 'announcement', 'info'
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)

    # Feedback Database
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        event_id INTEGER NOT NULL,
        rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
        comments TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, event_id),
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    seed_initial_data(conn)
    conn.close()

def seed_initial_data(conn):
    """Seed initial sample users, venues, events and registrations if database is empty."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users;")
    if cursor.fetchone()[0] > 0:
        return  # Already seeded

    print("Seeding initial SmartFest database records...")

    # Seed Users
    # Admin: admin@smartfest.edu / Admin@123
    admin_hash = hash_password("Admin@123")
    cursor.execute("""
    INSERT INTO users (name, email, password_hash, role, department, year, phone, interests)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, ("Dr. S. Mukherjee", "admin@smartfest.edu", admin_hash, "admin", "Dean of Student Affairs", 0, "+91-9876543210", json.dumps(["Governance", "Fest Management"])))

    # Coordinators: riya.coord@smartfest.edu / Coord@123, aman.coord@smartfest.edu / Coord@123
    coord1_hash = hash_password("Coord@123")
    cursor.execute("""
    INSERT INTO users (name, email, password_hash, role, department, year, phone, interests)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, ("Riya Patel", "riya.coord@smartfest.edu", coord1_hash, "coordinator", "Computer Science", 4, "+91-9876543211", json.dumps(["Coding", "Robotics", "AI"])))

    cursor.execute("""
    INSERT INTO users (name, email, password_hash, role, department, year, phone, interests)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, ("Aman Verma", "aman.coord@smartfest.edu", coord1_hash, "coordinator", "Electronics & Comm", 3, "+91-9876543212", json.dumps(["Music", "Dance", "Drama"])))

    # Students: anushka.student@smartfest.edu / Student@123, rahul.student@smartfest.edu / Student@123
    student1_hash = hash_password("Student@123")
    cursor.execute("""
    INSERT INTO users (name, email, password_hash, role, department, year, phone, interests)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, ("Anushka Sharma", "anushka.student@smartfest.edu", student1_hash, "student", "Computer Science", 3, "+91-9876543213", json.dumps(["Coding", "AI", "Robotics", "Web Development"])))

    cursor.execute("""
    INSERT INTO users (name, email, password_hash, role, department, year, phone, interests)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, ("Rahul Mehta", "rahul.student@smartfest.edu", student1_hash, "student", "Mechanical Eng", 2, "+91-9876543214", json.dumps(["Gaming", "Sports", "Music"])))

    # Seed Venues
    venues = [
        ("Main Auditorium", "Central Campus Block A", 500),
        ("Computer Science Lab 3", "Tech Tower 2nd Floor", 60),
        ("Open Air Theatre (OAT)", "North Lawn Amphitheatre", 800),
        ("Seminar Hall 1", "Management Block 1st Floor", 150),
        ("Indoor Sports Complex", "Sports Pavilion Ground Floor", 250)
    ]
    for name, loc, cap in venues:
        cursor.execute("INSERT INTO venues (name, location, capacity) VALUES (?, ?, ?);", (name, loc, cap))

    # Seed Events
    # Event 1: Hackathon (Published, coord 2, venue 2)
    cursor.execute("""
    INSERT INTO events (title, description, category, date, start_time, end_time, venue_id, coordinator_id, max_capacity, registered_count, rules, eligibility, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "Hackathon 2026: AI Frontiers",
        "Build innovative AI/ML applications addressing real-world challenges in healthcare, climate, and education. Teams of 2 to 4 students. Mentors available throughout.",
        "Technical",
        "2026-11-25",
        "09:00",
        "18:00",
        2, # CS Lab 3
        2, # Riya
        50,
        1,
        "1. Max team size 4.\n2. Bring college ID.\n3. Open source tools allowed.\n4. Original code only.",
        "Undergraduate and postgraduate engineering students.",
        "published"
    ))

    # Event 2: Battle of the Bands (Published, coord 3, venue 3)
    cursor.execute("""
    INSERT INTO events (title, description, category, date, start_time, end_time, venue_id, coordinator_id, max_capacity, registered_count, rules, eligibility, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "Battle of the Bands",
        "Annual inter-college musical war! Rock, fusion, acoustic, and pop bands compete for the grand fest championship trophy.",
        "Cultural",
        "2026-11-25",
        "18:30",
        "22:00",
        3, # OAT
        3, # Aman
        120,
        0,
        "1. 15 minutes stage time.\n2. In-house drum kit provided.\n3. Profanity is strictly prohibited.",
        "All registered fest participants.",
        "published"
    ))

    # Event 3: RoboWars Clash (Published, coord 2, venue 5)
    cursor.execute("""
    INSERT INTO events (title, description, category, date, start_time, end_time, venue_id, coordinator_id, max_capacity, registered_count, rules, eligibility, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "RoboWars: Arena Clash",
        "High-voltage combat robotics in an armored combat cage! Wired and wireless bots under 30kg battle till immobilization.",
        "Robotics",
        "2026-11-26",
        "11:00",
        "15:00",
        5, # Indoor Sports Complex
        2, # Riya
        40,
        0,
        "1. Weight limit 30kg.\n2. No pneumatic flames.\n3. Battery safety checks mandatory.",
        "College robotics teams.",
        "published"
    ))

    # Event 4: BGMI Esports Championship (Published, coord 3, venue 4)
    cursor.execute("""
    INSERT INTO events (title, description, category, date, start_time, end_time, venue_id, coordinator_id, max_capacity, registered_count, rules, eligibility, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "Apex Esports: BGMI & Valorant",
        "College mobile and PC gaming tournament across classic maps. LAN servers configured for zero lag.",
        "Gaming",
        "2026-11-26",
        "14:00",
        "18:00",
        4, # Seminar Hall 1
        3, # Aman
        64,
        0,
        "1. Squad of 4.\n2. Bring personal headsets.\n3. Emulators strictly forbidden.",
        "Open to all students.",
        "published"
    ))

    # Event 5: Code Sprint (Pending Admin Approval, coord 2, venue 2)
    cursor.execute("""
    INSERT INTO events (title, description, category, date, start_time, end_time, venue_id, coordinator_id, max_capacity, registered_count, rules, eligibility, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        "Algorithmic Code Sprint",
        "Speed competitive programming contest testing data structures, dynamic programming, and graph algorithms.",
        "Technical",
        "2026-11-27",
        "10:00",
        "12:30",
        2, # CS Lab 3
        2, # Riya
        60,
        0,
        "1. Languages: C++, Java, Python.\n2. Plagiarism checker enforced.\n3. No internet access during test.",
        "Open to all departments.",
        "pending"
    ))

    # Seed Registration for Anushka in Event 1
    qr_token = generate_qr_token(4, 1) # Student 4 (Anushka), Event 1 (Hackathon)
    cursor.execute("""
    INSERT INTO registrations (user_id, event_id, status, qr_code_token)
    VALUES (?, ?, 'confirmed', ?);
    """, (4, 1, qr_token))

    # Seed Notification for Anushka
    cursor.execute("""
    INSERT INTO notifications (user_id, title, message, type)
    VALUES (?, ?, ?, ?);
    """, (
        4,
        "Registration Confirmed: Hackathon 2026",
        "You are successfully registered for Hackathon 2026: AI Frontiers. Your digital pass and QR code are ready.",
        "confirmation"
    ))

    conn.commit()
    print("Database seeding completed successfully.")
