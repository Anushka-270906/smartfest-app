# SmartFest — College Fest Coordination Platform

AI/ML-Based Full-Stack College Fest Coordination Platform built with FastAPI and Vanilla JavaScript.

---

## 🚀 How to Run in VS Code (Step-by-Step for Any Laptop)

### Prerequisites
1. **Python 3.10+**: Make sure Python is installed. During installation on Windows, **check the box "Add Python to PATH"**.
2. **VS Code**: Installed with the **Python** extension.

---

### Step 1: Open the Project in VS Code
1. Unzip the project folder if zipped.
2. Open VS Code.
3. Click **File** -> **Open Folder...** -> Select the extracted folder (`smartfest-app`).

---

### Step 2: Open the Terminal in VS Code
In VS Code, press:
- `Ctrl + \`` (backtick, key above Tab) **OR**
- Click menu: **Terminal** -> **New Terminal**.

---

### Step 3: (Recommended) Create & Activate Virtual Environment
In the VS Code terminal:
```bash
# 1. Create a virtual environment
python -m venv venv

# 2. Activate it:
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# On Windows (Command Prompt):
.\venv\Scripts\activate.bat

# On Mac/Linux:
source venv/bin/activate
```
*(If PowerShell shows a script execution policy error, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` then activate again).*

---

### Step 4: Install Dependencies
```bash
pip install -r requirements.txt
```

---

### Step 5: Start the Application
Run:
```bash
python run.py
```
Or with live reload:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### Step 6: Access the App
Open your browser and navigate to:
- **Application URL**: [http://localhost:8000](http://localhost:8000)
- **API Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## ⚡ Demo Login Accounts
Click the quick demo buttons on the login screen, or sign in manually:
- **Student**: `anushka.student@smartfest.edu` / `Student@123`
- **Coordinator**: `riya.coord@smartfest.edu` / `Coord@123`
- **Administrator**: `admin@smartfest.edu` / `Admin@123`

---

## 🧪 Run Automated Tests
```bash
pytest tests
```
