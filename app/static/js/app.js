// ==========================================================================
// SMARTFEST FULL-STACK APPLICATION CLIENT
// Connected to FastAPI REST Backend & SQLite Relational DB
// ==========================================================================

const API_BASE = "";

// Global State
let currentUser = null;
let currentToken = localStorage.getItem("smartfest_token") || null;
let activeCategory = "all";
let cachedEvents = [];
let cachedVenues = [];
let myRegisteredEventIds = new Set();

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initAuth();
  initModals();
});

// --------------------------------------------------------------------------
// THEME SWITCHING (LIGHT / DARK WITH LOCALSTORAGE)
// --------------------------------------------------------------------------
function initTheme() {
  const themeToggleBtn = document.getElementById("themeToggleBtn");
  const sunIcon = document.getElementById("themeSunIcon");
  const moonIcon = document.getElementById("themeMoonIcon");

  const savedTheme = localStorage.getItem("smartfest_theme") || "dark";
  applyTheme(savedTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "light";
      const nextTheme = current === "dark" ? "light" : "dark";
      applyTheme(nextTheme);
      localStorage.setItem("smartfest_theme", nextTheme);
    });
  }

  function applyTheme(theme) {
    if (theme === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
      if (sunIcon) sunIcon.style.display = "block";
      if (moonIcon) moonIcon.style.display = "none";
    } else {
      document.documentElement.removeAttribute("data-theme");
      if (sunIcon) sunIcon.style.display = "none";
      if (moonIcon) moonIcon.style.display = "block";
    }
  }
}

// --------------------------------------------------------------------------
// AUTHENTICATION & SESSION MANAGEMENT
// --------------------------------------------------------------------------
async function initAuth() {
  // Check if token exists
  if (currentToken) {
    try {
      const res = await apiFetch("/api/auth/me");
      if (res && res.id) {
        currentUser = res;
        setupUserSession();
        return;
      }
    } catch (err) {
      console.warn("Session expired or invalid:", err);
      logout();
    }
  }

  // Not logged in -> Show Auth View
  showAuthView();
}

async function setupUserSession() {
  document.getElementById("authContainer").style.display = "none";
  document.getElementById("appContainer").style.display = "flex";

  // Update User Header Chip
  const userChipName = document.getElementById("headerUserName");
  const userChipRole = document.getElementById("headerUserRole");
  const userChipAvatar = document.getElementById("headerUserAvatar");

  if (userChipName) userChipName.innerText = currentUser.name;
  if (userChipRole) userChipRole.innerText = currentUser.role.toUpperCase();
  if (userChipAvatar) userChipAvatar.innerText = currentUser.name.charAt(0);

  // Sync registered event IDs if student
  if (currentUser.role === "student") {
    await refreshMyRegisteredEventIds();
  }

  // Render role-specific navigation and landing dashboard
  renderNavigationForRole(currentUser.role);
  updateNotificationBadge();
}

async function refreshMyRegisteredEventIds() {
  if (!currentUser || currentUser.role !== "student") {
    myRegisteredEventIds = new Set();
    return;
  }
  try {
    const regs = await apiFetch("/api/registrations/my");
    myRegisteredEventIds = new Set(
      regs.filter(r => r.status === "confirmed" || r.status === "attended").map(r => r.event_id)
    );
  } catch (err) {
    console.warn("Could not sync user registrations:", err);
  }
}

function showAuthView() {
  document.getElementById("authContainer").style.display = "block";
  document.getElementById("appContainer").style.display = "none";
}

function logout() {
  localStorage.removeItem("smartfest_token");
  currentToken = null;
  currentUser = null;
  showToast("Logged out successfully.");
  showAuthView();
}

async function quickDemoLogin(email, password) {
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");

    localStorage.setItem("smartfest_token", data.access_token);
    currentToken = data.access_token;
    currentUser = data.user;
    setupUserSession();
    showToast(`Welcome, ${currentUser.name} (${currentUser.role})!`);
  } catch (err) {
    alert("Demo login error: " + err.message);
  }
}

// --------------------------------------------------------------------------
// API HELPER WITH JWT HEADER
// --------------------------------------------------------------------------
async function apiFetch(endpoint, options = {}) {
  const headers = options.headers || {};
  if (currentToken) {
    headers["Authorization"] = `Bearer ${currentToken}`;
  }
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(endpoint, { ...options, headers });
  if (res.status === 401) {
    logout();
    throw new Error("Session expired. Please log in.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    let errorMsg = `Request failed (${res.status})`;
    if (data && data.detail) {
      if (Array.isArray(data.detail)) {
        errorMsg = data.detail.map(d => {
          const loc = Array.isArray(d.loc) ? d.loc.filter(l => l !== 'body').join('.') : '';
          const msg = d.msg || JSON.stringify(d);
          return loc ? `${loc}: ${msg}` : msg;
        }).join("; ");
      } else if (typeof data.detail === "object") {
        errorMsg = data.detail.msg || JSON.stringify(data.detail);
      } else {
        errorMsg = String(data.detail);
      }
    } else if (data && data.message) {
      errorMsg = data.message;
    }
    throw new Error(errorMsg);
  }
  return data;
}

// --------------------------------------------------------------------------
// TOAST NOTIFICATIONS
// --------------------------------------------------------------------------
function showToast(message, isError = false) {
  if (typeof message === "object" && message !== null) {
    if (message.message) message = message.message;
    else message = JSON.stringify(message);
  }
  const toast = document.createElement("div");
  toast.style.position = "fixed";
  toast.style.bottom = "24px";
  toast.style.right = "24px";
  toast.style.background = isError ? "var(--badge-red-bg)" : "var(--accent-primary)";
  toast.style.color = isError ? "var(--badge-red-text)" : "#ffffff";
  toast.style.border = isError ? "1px solid var(--badge-red-text)" : "none";
  toast.style.padding = "12px 20px";
  toast.style.borderRadius = "8px";
  toast.style.boxShadow = "var(--shadow-lg)";
  toast.style.fontSize = "0.9rem";
  toast.style.fontWeight = "600";
  toast.style.zIndex = "9999";
  toast.style.animation = "fadeIn 200ms ease";
  toast.innerText = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 300ms ease";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

function toggleMobileSidebar() {
  const sidebar = document.querySelector(".sidebar");
  if (sidebar) sidebar.classList.toggle("mobile-open");
}

// --------------------------------------------------------------------------
// ROLE-BASED NAVIGATION ROUTING
// --------------------------------------------------------------------------
function renderNavigationForRole(role) {
  const navContainer = document.getElementById("sidebarNavGroups");
  if (!navContainer) return;

  if (role === "student") {
    navContainer.innerHTML = `
      <div class="nav-group-label">Student Portal</div>
      <ul class="nav-list">
        <li><a class="nav-link active" data-target="view-student-dashboard"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path></svg> Dashboard</a></li>
        <li><a class="nav-link" data-target="view-browse-events"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg> Browse Events</a></li>
        <li><a class="nav-link" data-target="view-my-registrations"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line></svg> My Registrations</a></li>
        <li><a class="nav-link" data-target="view-recommendations"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg> AI Suggestions</a></li>
        <li><a class="nav-link" data-target="view-fest-schedule"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg> Fest Schedule</a></li>
      </ul>
    `;
    switchView("view-student-dashboard");
    loadStudentDashboard();
  } else if (role === "coordinator") {
    navContainer.innerHTML = `
      <div class="nav-group-label">Coordinator Hub</div>
      <ul class="nav-list">
        <li><a class="nav-link active" data-target="view-coord-dashboard"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle></svg> Managed Events</a></li>
        <li><a class="nav-link" data-target="view-coord-checkin"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg> Gate Check-In</a></li>
        <li><a class="nav-link" data-target="view-coord-rosters"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg> Attendee Rosters</a></li>
        <li><a class="nav-link" data-target="view-coord-broadcast"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg> Send Broadcast</a></li>
      </ul>
    `;
    switchView("view-coord-dashboard");
    loadCoordinatorDashboard();
  } else if (role === "admin") {
    navContainer.innerHTML = `
      <div class="nav-group-label">Administrator Console</div>
      <ul class="nav-list">
        <li><a class="nav-link active" data-target="view-admin-approvals"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"></polyline><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg> Event Approvals</a></li>
        <li><a class="nav-link" data-target="view-admin-analytics"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg> Analytics & Reports</a></li>
        <li><a class="nav-link" data-target="view-admin-venues"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg> Venue Registry</a></li>
        <li><a class="nav-link" data-target="view-admin-users"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle></svg> User Directory</a></li>
      </ul>
    `;
    switchView("view-admin-approvals");
    loadAdminDashboard();
  }

  // Hook navigation clicks
  document.querySelectorAll(".nav-link").forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
      link.classList.add("active");
      const targetId = link.getAttribute("data-target");
      if (document.querySelector(".sidebar")?.classList.contains("mobile-open")) {
        document.querySelector(".sidebar").classList.remove("mobile-open");
      }
      switchView(targetId);
    });
  });
}

function switchView(viewId) {
  if (viewId !== "view-coord-checkin" && typeof stopCameraScanner === "function") {
    stopCameraScanner();
  }
  document.querySelectorAll(".view-section").forEach(sec => sec.classList.remove("active"));
  const target = document.getElementById(viewId);
  if (target) {
    target.classList.add("active");
    window.scrollTo({ top: 0, behavior: "smooth" });

    // Trigger data loader for view
    if (viewId === "view-browse-events") loadBrowseEvents();
    if (viewId === "view-my-registrations") loadMyRegistrations();
    if (viewId === "view-recommendations") loadAIRecommendations();
    if (viewId === "view-fest-schedule") loadFestSchedule();
    if (viewId === "view-coord-checkin") loadCheckInScannerView();
    if (viewId === "view-coord-rosters") loadCoordinatorRosters();
    if (viewId === "view-admin-analytics") loadAdminAnalytics();
    if (viewId === "view-admin-venues") loadAdminVenues();
    if (viewId === "view-admin-users") loadAdminUsers();
  }
}

// --------------------------------------------------------------------------
// STUDENT PORTAL LOGIC
// --------------------------------------------------------------------------
async function loadStudentDashboard() {
  try {
    const [events, myRegs, recs] = await Promise.all([
      apiFetch("/api/events?status=published"),
      apiFetch("/api/registrations/my"),
      apiFetch("/api/recommendations")
    ]);

    cachedEvents = events;
    const confirmedCount = myRegs.filter(r => r.status === "confirmed" || r.status === "attended").length;
    myRegisteredEventIds = new Set(myRegs.filter(r => r.status === "confirmed" || r.status === "attended").map(r => r.event_id));

    // Set Metrics
    document.getElementById("studentMetricRegistered").innerText = confirmedCount;
    document.getElementById("studentMetricAvailable").innerText = events.length;
    document.getElementById("studentMetricRecommendations").innerText = recs.length;

    // Render Recommendations Hero Row
    const recContainer = document.getElementById("studentRecCards");
    if (recContainer) {
      if (recs.length === 0) {
        recContainer.innerHTML = '<p style="color: var(--text-tertiary); font-size: 0.9rem;">No recommendations yet. Complete your profile interests to unlock personalized matches.</p>';
      } else {
        recContainer.innerHTML = recs.slice(0, 3).map(e => {
          const isRegistered = myRegisteredEventIds.has(e.id) || e.is_registered === true;
          const seatsLeft = e.max_capacity - e.registered_count;
          const isFull = seatsLeft <= 0;
          return `
          <div class="event-card">
            <div class="event-tag-row">
              <span class="event-category">${e.category}</span>
              ${isRegistered ? '<span class="badge badge-green">✓ Enrolled</span>' : `<span class="badge badge-purple">✨ ${e.match_percentage}% Match</span>`}
            </div>
            <h3 class="event-title">${e.title}</h3>
            <p style="font-size: 0.78rem; color: var(--accent-primary); font-style: italic;">${e.recommendation_reason}</p>
            <div class="event-meta-list">
              <div class="event-meta-item">📅 ${e.date} • ${e.start_time} - ${e.end_time}</div>
              <div class="event-meta-item">📍 ${e.venue_name}</div>
            </div>
            <div class="event-footer">
              <span class="event-seats-left"><strong>${Math.max(0, seatsLeft)}</strong> / ${e.max_capacity} seats left</span>
              ${isRegistered ? `
                <button class="btn btn-primary" disabled style="background: #10b981; border-color: #10b981; opacity: 0.9; cursor: default;">✓ Registered</button>
              ` : isFull ? `
                <button class="btn btn-primary" disabled style="opacity: 0.5;">Registration Full</button>
              ` : `
                <button class="btn btn-primary" onclick="registerForEvent(${e.id})">Register Now</button>
              `}
            </div>
          </div>
        `}).join("");
      }
    }

    // Render Featured Catalog Grid
    renderEventCards("studentFeaturedGrid", events.slice(0, 4));
  } catch (err) {
    console.error("Failed to load student dashboard:", err);
  }
}

async function loadBrowseEvents() {
  const query = document.getElementById("browseSearchInput")?.value || "";
  const category = activeCategory;
  try {
    let url = `/api/events?status=published`;
    if (category !== "all") url += `&category=${encodeURIComponent(category)}`;
    if (query) url += `&search=${encodeURIComponent(query)}`;

    const events = await apiFetch(url);
    cachedEvents = events;
    if (currentUser && currentUser.role === "student") {
      await refreshMyRegisteredEventIds();
    }
    renderEventCards("browseEventsGrid", events);
  } catch (err) {
    showToast(err.message, true);
  }
}

function renderEventCards(containerId, events) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (events.length === 0) {
    container.innerHTML = `<div style="grid-column: 1 / -1; padding: 2.5rem; text-align: center; color: var(--text-tertiary);">No events found matching your criteria.</div>`;
    return;
  }

  container.innerHTML = events.map(e => {
    const seatsRemaining = e.max_capacity - e.registered_count;
    const isFull = seatsRemaining <= 0;
    const isRegistered = myRegisteredEventIds.has(e.id) || e.is_registered === true;
    const isStudent = currentUser && currentUser.role === "student";

    let actionBtnHtml = "";
    if (isStudent) {
      if (isRegistered) {
        actionBtnHtml = `<button class="btn btn-primary" disabled style="background: #10b981; border-color: #10b981; opacity: 0.9; cursor: default;">✓ Registered</button>`;
      } else if (isFull) {
        actionBtnHtml = `<button class="btn btn-primary" disabled style="opacity: 0.5; cursor: not-allowed;">Registration Full</button>`;
      } else {
        actionBtnHtml = `<button class="btn btn-primary" onclick="registerForEvent(${e.id})">Register Now</button>`;
      }
    }

    return `
      <div class="event-card">
        <div class="event-tag-row">
          <span class="event-category">${e.category}</span>
          ${isRegistered ? '<span class="badge badge-green">✓ You are Enrolled</span>' : isFull ? '<span class="badge badge-red">Full</span>' : `<span class="badge badge-green">${seatsRemaining} Seats Vacant</span>`}
        </div>
        <h3 class="event-title">${e.title}</h3>
        <p class="event-desc">${e.description}</p>
        <div class="event-meta-list">
          <div class="event-meta-item">📅 ${e.date} • ${e.start_time} - ${e.end_time}</div>
          <div class="event-meta-item">📍 ${e.venue_name} (${e.venue_location})</div>
          <div class="event-meta-item">👤 Coord: ${e.coordinator_name}</div>
        </div>
        <div class="event-footer">
          <button class="btn btn-ghost" onclick="openEventDetailModal(${e.id})">View Details</button>
          ${actionBtnHtml}
        </div>
      </div>
    `;
  }).join("");
}

async function registerForEvent(eventId) {
  try {
    const res = await apiFetch("/api/registrations", {
      method: "POST",
      body: JSON.stringify({ event_id: eventId })
    });
    myRegisteredEventIds.add(eventId);
    showToast(`✓ Registered successfully for '${res.event_title}'!`);
    await refreshMyRegisteredEventIds();
    loadStudentDashboard();
    loadBrowseEvents();
    if (document.getElementById("view-recommendations")?.classList.contains("active")) {
      loadAIRecommendations();
    }
    if (document.getElementById("view-my-registrations")?.classList.contains("active")) {
      loadMyRegistrations();
    }
    updateNotificationBadge();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function loadMyRegistrations() {
  const container = document.getElementById("myRegistrationsList");
  if (!container) return;

  try {
    const regs = await apiFetch("/api/registrations/my");
    myRegisteredEventIds = new Set(
      regs.filter(r => r.status === "confirmed" || r.status === "attended").map(r => r.event_id)
    );

    if (regs.length === 0) {
      container.innerHTML = '<p style="color: var(--text-tertiary); text-align: center; padding: 2rem;">You have not registered for any fest events yet.</p>';
      return;
    }

    container.innerHTML = regs.map(r => `
      <div class="event-card" style="margin-bottom: 1rem;">
        <div class="event-tag-row">
          <span class="event-category">${r.event_category}</span>
          <span class="badge ${r.status === 'confirmed' ? 'badge-green' : r.status === 'attended' ? 'badge-blue' : 'badge-red'}">
            ${r.status.toUpperCase()}
          </span>
        </div>
        <h3 class="event-title">${r.event_title}</h3>
        <div class="event-meta-list">
          <div class="event-meta-item">📅 Date & Time: ${r.event_date} • ${r.event_start_time} - ${r.event_end_time}</div>
          <div class="event-meta-item">📍 Venue: ${r.venue_name}</div>
          ${r.checked_in_at ? `<div class="event-meta-item" style="color: var(--badge-green-text);">✓ Checked In: ${r.checked_in_at}</div>` : ''}
        </div>
        <div class="event-footer">
          ${r.status === 'confirmed' ? `
            <button class="btn btn-primary" onclick="openQrPassModal('${r.qr_code_token}', '${r.event_title}')">🎟️ View Gate Pass (QR)</button>
            <button class="btn btn-ghost" style="color: #ef4444;" onclick="cancelRegistration(${r.id})">Cancel Registration</button>
          ` : r.status === 'attended' ? `
            <button class="btn btn-ghost" onclick="openFeedbackModal(${r.event_id}, '${r.event_title}')">⭐ Submit Event Review</button>
          ` : `
            <span style="font-size: 0.82rem; color: var(--text-tertiary);">Registration Cancelled</span>
          `}
        </div>
      </div>
    `).join("");
  } catch (err) {
    showToast(err.message, true);
  }
}

async function cancelRegistration(regId) {
  if (!confirm("Are you sure you want to cancel this registration? Your seat will be given to another student.")) return;
  try {
    await apiFetch(`/api/registrations/${regId}/cancel`, { method: "POST" });
    showToast("Registration cancelled and seat released.");
    await refreshMyRegisteredEventIds();
    loadMyRegistrations();
    loadStudentDashboard();
    loadBrowseEvents();
    if (document.getElementById("view-recommendations")?.classList.contains("active")) {
      loadAIRecommendations();
    }
    updateNotificationBadge();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function loadAIRecommendations() {
  const container = document.getElementById("aiRecommendationsGrid");
  if (!container) return;

  try {
    const recs = await apiFetch("/api/recommendations");
    if (recs.length === 0) {
      container.innerHTML = '<p style="color: var(--text-tertiary); text-align: center; padding: 2rem;">No AI recommendations found. Try updating your profile interest tags.</p>';
      return;
    }

    container.innerHTML = recs.map(e => {
      const isRegistered = myRegisteredEventIds.has(e.id) || e.is_registered === true;
      const seatsLeft = e.max_capacity - e.registered_count;
      const isFull = seatsLeft <= 0;
      return `
      <div class="event-card">
        <div class="event-tag-row">
          <span class="event-category">${e.category}</span>
          ${isRegistered ? '<span class="badge badge-green">✓ Enrolled</span>' : `<span class="badge badge-purple">✨ ${e.match_percentage}% Similarity</span>`}
        </div>
        <h3 class="event-title">${e.title}</h3>
        <p style="font-size: 0.82rem; color: var(--accent-primary); font-weight: 600;">Reason: ${e.recommendation_reason}</p>
        <p class="event-desc">${e.description}</p>
        <div class="event-meta-list">
          <div class="event-meta-item">📅 ${e.date} • ${e.start_time} - ${e.end_time}</div>
          <div class="event-meta-item">📍 ${e.venue_name}</div>
        </div>
        <div class="event-footer">
          <span class="event-seats-left"><strong>${Math.max(0, seatsLeft)}</strong> seats left</span>
          ${isRegistered ? `
            <button class="btn btn-primary" disabled style="background: #10b981; border-color: #10b981; opacity: 0.9; cursor: default;">✓ Registered</button>
          ` : isFull ? `
            <button class="btn btn-primary" disabled style="opacity: 0.5;">Registration Full</button>
          ` : `
            <button class="btn btn-primary" onclick="registerForEvent(${e.id})">Register Now</button>
          `}
        </div>
      </div>
    `}).join("");
  } catch (err) {
    showToast(err.message, true);
  }
}

async function loadFestSchedule() {
  const container = document.getElementById("festScheduleTableBody");
  if (!container) return;

  try {
    const schedule = await apiFetch("/api/venues/schedule");
    if (schedule.length === 0) {
      container.innerHTML = '<tr><td colspan="5" style="text-align: center;">No scheduled events published yet.</td></tr>';
      return;
    }

    container.innerHTML = schedule.map(s => `
      <tr>
        <td><strong>${s.date}</strong></td>
        <td>${s.start_time} - ${s.end_time}</td>
        <td><strong>${s.title}</strong> <span class="badge badge-blue">${s.category}</span></td>
        <td>📍 ${s.venue_name} (${s.venue_location})</td>
        <td>👤 ${s.coordinator_name}</td>
      </tr>
    `).join("");
  } catch (err) {
    showToast(err.message, true);
  }
}

// --------------------------------------------------------------------------
// COORDINATOR HUB LOGIC
// --------------------------------------------------------------------------
async function loadCoordinatorDashboard() {
  try {
    const events = await apiFetch(`/api/events?coordinator_id=${currentUser.id}`);
    const tableBody = document.getElementById("coordEventsTableBody");
    if (!tableBody) return;

    if (events.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No events created yet. Click "+ Create Event" to begin.</td></tr>';
      return;
    }

    tableBody.innerHTML = events.map(e => `
      <tr>
        <td><strong>${e.title}</strong></td>
        <td>${e.category}</td>
        <td>📅 ${e.date} (${e.start_time})</td>
        <td>📍 ${e.venue_name}</td>
        <td><strong>${e.registered_count}</strong> / ${e.max_capacity}</td>
        <td>
          <span class="badge ${e.status === 'published' ? 'badge-green' : e.status === 'pending' ? 'badge-amber' : e.status === 'draft' ? 'badge-purple' : 'badge-red'}">
            ${e.status.toUpperCase()}
          </span>
        </td>
        <td>
          ${e.status === 'draft' ? `
            <button class="btn btn-primary" style="padding: 2px 8px; font-size: 0.75rem;" onclick="submitEventForApproval(${e.id})">Submit for Approval</button>
          ` : ''}
          ${e.status === 'published' ? `
            <button class="btn btn-ghost" style="padding: 2px 8px; font-size: 0.75rem;" onclick="exportEventCsv(${e.id})">Export CSV</button>
            <button class="btn btn-ghost" style="padding: 2px 8px; font-size: 0.75rem; color: #ef4444;" onclick="cancelEvent(${e.id})">Cancel</button>
          ` : ''}
        </td>
      </tr>
    `).join("");
  } catch (err) {
    showToast(err.message, true);
  }
}

async function submitEventForApproval(eventId) {
  try {
    await apiFetch(`/api/events/${eventId}/submit`, { method: "POST" });
    showToast("Event submitted to administration for review!");
    loadCoordinatorDashboard();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function cancelEvent(eventId) {
  if (!confirm("Are you sure you want to cancel this event? All registered students will receive cancellation notifications.")) return;
  try {
    await apiFetch(`/api/events/${eventId}/cancel`, { method: "POST" });
    showToast("Event cancelled and participants notified.");
    loadCoordinatorDashboard();
  } catch (err) {
    showToast(err.message, true);
  }
}

function exportEventCsv(eventId) {
  window.open(`/api/analytics/export-roster/${eventId}`, "_blank");
}

// --- Live Camera & File QR Scanner Logic ---
let qrMediaStream = null;
let qrScanAnimFrame = null;

function stopCameraScanner() {
  if (qrScanAnimFrame) {
    cancelAnimationFrame(qrScanAnimFrame);
    qrScanAnimFrame = null;
  }
  if (qrMediaStream) {
    try {
      qrMediaStream.getTracks().forEach(track => track.stop());
    } catch (e) {
      console.warn("Error stopping camera tracks:", e);
    }
    qrMediaStream = null;
  }
  const box = document.getElementById("qrCameraScannerBox");
  if (box) box.style.display = "none";
  const btnLabel = document.getElementById("cameraBtnLabel");
  if (btnLabel) btnLabel.innerText = "Open Camera Scanner";
}

async function toggleCameraScanner() {
  const box = document.getElementById("qrCameraScannerBox");
  if (!box) return;

  if (qrMediaStream) {
    stopCameraScanner();
    return;
  }

  const video = document.getElementById("qrVideo");
  const canvas = document.getElementById("qrCanvas");
  const statusText = document.getElementById("qrScannerStatusText");
  const btnLabel = document.getElementById("cameraBtnLabel");

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showToast("Camera access is not supported by your browser.", true);
    return;
  }

  try {
    box.style.display = "block";
    if (statusText) statusText.innerText = "Requesting camera permissions...";
    if (btnLabel) btnLabel.innerText = "Stop Camera";

    let stream = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" }
      });
    } catch (e) {
      // Fallback for laptops/desktops without rear-facing camera
      stream = await navigator.mediaDevices.getUserMedia({ video: true });
    }

    qrMediaStream = stream;
    video.srcObject = stream;
    video.setAttribute("playsinline", "true");
    await video.play();

    if (statusText) statusText.innerText = "Scanning... Hold pass QR up to camera";

    const ctx = canvas.getContext("2d", { willReadFrequently: true });

    function tick() {
      if (!qrMediaStream) return;
      if (video.readyState === video.HAVE_ENOUGH_DATA) {
        canvas.height = video.videoHeight;
        canvas.width = video.videoWidth;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);

        if (typeof jsQR !== "undefined") {
          const code = jsQR(imageData.data, imageData.width, imageData.height, {
            inversionAttempts: "dontInvert"
          });

          if (code && code.data) {
            handleDecodedQr(code.data);
            return;
          }
        }
      }
      qrScanAnimFrame = requestAnimationFrame(tick);
    }
    qrScanAnimFrame = requestAnimationFrame(tick);
  } catch (err) {
    stopCameraScanner();
    console.error("Camera access error:", err);
    showToast("Unable to access camera: " + err.message, true);
  }
}

function handleDecodedQr(rawText) {
  stopCameraScanner();
  let token = rawText ? rawText.trim() : "";
  if (token.includes("/qr/")) {
    const parts = token.split("/qr/");
    token = decodeURIComponent(parts[parts.length - 1]);
  }
  token = token.replace(/["']/g, "").trim();

  const tokenInput = document.getElementById("checkInTokenInput");
  if (tokenInput) {
    tokenInput.value = token;
  }
  showToast("✓ QR Code detected!");
  executeCheckInVerification();
}

async function handleQrFileUpload(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  try {
    showToast("Analyzing uploaded QR pass image...");
    const img = new Image();
    const reader = new FileReader();

    reader.onload = (e) => {
      img.onload = () => {
        const canvas = document.createElement("canvas");
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0, img.width, img.height);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);

        if (typeof jsQR === "undefined") {
          showToast("QR scanner library is still initializing, please try again.", true);
          return;
        }

        const code = jsQR(imageData.data, imageData.width, imageData.height);
        if (code && code.data) {
          handleDecodedQr(code.data);
        } else {
          showToast("No readable QR code found in this image. Please ensure the QR code is sharp.", true);
        }
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  } catch (err) {
    console.error("File QR decode error:", err);
    showToast("Failed to process QR image: " + err.message, true);
  } finally {
    event.target.value = "";
  }
}

async function loadCheckInScannerView() {
  // Populate event dropdown in scanner view
  const select = document.getElementById("scannerEventSelect");
  if (!select) return;
  try {
    const url = currentUser.role === "admin" ? "/api/events?status=published" : `/api/events?coordinator_id=${currentUser.id}&status=published`;
    const events = await apiFetch(url);
    select.innerHTML = '<option value="">All Assigned Events</option>' + events.map(e => `<option value="${e.id}">${e.title} (${e.date})</option>`).join("");
  } catch (err) {
    console.error(err);
  }
}

async function executeCheckInVerification() {
  const token = document.getElementById("checkInTokenInput")?.value.trim();
  const eventId = document.getElementById("scannerEventSelect")?.value || null;
  const resultBox = document.getElementById("checkInResultBox");

  if (!token) {
    showToast("Please enter or scan a registration token.", true);
    return;
  }

  try {
    const res = await apiFetch("/api/checkin/verify", {
      method: "POST",
      body: JSON.stringify({
        qr_code_token: token,
        event_id: eventId ? parseInt(eventId) : null
      })
    });

    if (res.success) {
      resultBox.innerHTML = `
        <div style="background: var(--badge-green-bg); border: 1px solid var(--badge-green-text); padding: 1.25rem; border-radius: 8px;">
          <h4 style="color: var(--badge-green-text); font-size: 1.1rem; margin-bottom: 0.4rem;">✓ Check-In Confirmed!</h4>
          <p><strong>Student:</strong> ${res.student_name} (${res.student_email})</p>
          <p><strong>Department:</strong> ${res.student_department}</p>
          <p><strong>Event:</strong> ${res.event_title}</p>
          <p style="font-size: 0.78rem; color: var(--text-tertiary); margin-top: 0.4rem;">Recorded At: ${res.checked_in_at}</p>
        </div>
      `;
      showToast(`✓ Check-in confirmed for ${res.student_name}!`);
      document.getElementById("checkInTokenInput").value = "";
    } else {
      resultBox.innerHTML = `
        <div style="background: var(--badge-amber-bg); border: 1px solid var(--badge-amber-text); padding: 1.25rem; border-radius: 8px;">
          <h4 style="color: var(--badge-amber-text); font-size: 1.1rem; margin-bottom: 0.4rem;">⚠️ Warning: Duplicate Check-In</h4>
          <p>${res.message}</p>
        </div>
      `;
    }
  } catch (err) {
    resultBox.innerHTML = `
      <div style="background: var(--badge-red-bg); border: 1px solid var(--badge-red-text); padding: 1.25rem; border-radius: 8px;">
        <h4 style="color: var(--badge-red-text); font-size: 1.1rem; margin-bottom: 0.4rem;">❌ Check-In Error</h4>
        <p>${err.message}</p>
      </div>
    `;
    showToast(err.message, true);
  }
}

async function loadCoordinatorRosters() {
  const container = document.getElementById("coordRosterEventSelect");
  if (!container) return;
  try {
    const url = currentUser.role === "admin" ? "/api/events" : `/api/events?coordinator_id=${currentUser.id}`;
    const events = await apiFetch(url);
    if (!events || events.length === 0) {
      container.innerHTML = '<option value="">No events available</option>';
      const tableBody = document.getElementById("coordRosterTableBody");
      if (tableBody) tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-tertiary); padding:2rem;">No events found under your account.</td></tr>';
      return;
    }
    container.innerHTML = events.map(e => `<option value="${e.id}">${e.title} (${e.registered_count} Enrolled)</option>`).join("");
    fetchRosterForSelectedEvent();
  } catch (err) {
    console.error(err);
  }
}

async function fetchRosterForSelectedEvent() {
  const eventId = document.getElementById("coordRosterEventSelect")?.value;
  const tableBody = document.getElementById("coordRosterTableBody");
  const countBadge = document.getElementById("coordRosterCountBadge");
  const headerTitle = document.getElementById("coordRosterHeaderTitle");
  if (!eventId || !tableBody) return;

  try {
    const downloadBtn = document.getElementById("coordRosterDownloadBtn");
    if (downloadBtn) {
      downloadBtn.onclick = () => exportEventCsv(eventId);
    }
    tableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-tertiary); padding: 1.5rem;">Loading participant roster...</td></tr>';

    const data = await apiFetch(`/api/analytics/roster/${eventId}`);
    if (headerTitle) headerTitle.innerText = `Enrolled Participants — ${data.event_title}`;
    if (countBadge) {
      countBadge.style.display = "inline-block";
      countBadge.innerText = `${data.total_registered} Registered`;
    }

    if (!data.participants || data.participants.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-tertiary); padding: 2rem;">No students registered for this event yet.</td></tr>';
      return;
    }

    tableBody.innerHTML = data.participants.map(p => {
      const isAttended = p.registration_status === 'attended' || !!p.checked_in_at;
      const statusBadge = isAttended
        ? `<span class="badge badge-published" style="display:inline-flex; align-items:center; gap:4px;">✓ Attended${p.checked_in_at ? ' (' + p.checked_in_at.substring(11, 16) + ')' : ''}</span>`
        : `<span class="badge badge-pending">Registered</span>`;
      return `
        <tr>
          <td><strong>${p.student_name}</strong></td>
          <td>${p.department || 'General'} (Yr ${p.year || 1})</td>
          <td>${p.student_email}</td>
          <td>${p.phone || 'N/A'}</td>
          <td>${p.registration_date ? p.registration_date.substring(0, 10) : 'N/A'}</td>
          <td>${statusBadge}</td>
          <td><code style="font-size: 0.72rem; background: var(--bg-secondary); padding: 2px 6px; border-radius: 4px; border: 1px solid var(--border-subtle);">${p.qr_code_token}</code></td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #ef4444; padding: 1.5rem;">Failed to load roster: ${err.message}</td></tr>`;
    console.error(err);
  }
}

// --------------------------------------------------------------------------
// ADMINISTRATOR CONSOLE LOGIC
// --------------------------------------------------------------------------
async function loadAdminDashboard() {
  loadAdminApprovals();
}

async function loadAdminApprovals() {
  const tableBody = document.getElementById("adminApprovalsTableBody");
  if (!tableBody) return;

  try {
    const pendingEvents = await apiFetch("/api/events?status=pending");
    if (pendingEvents.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-tertiary);">No events pending approval at this time.</td></tr>';
      return;
    }

    tableBody.innerHTML = pendingEvents.map(e => `
      <tr>
        <td><strong>${e.title}</strong></td>
        <td>${e.category}</td>
        <td>📅 ${e.date} • ${e.start_time} - ${e.end_time}</td>
        <td>📍 ${e.venue_name}</td>
        <td>👤 ${e.coordinator_name}</td>
        <td>
          <button class="btn btn-primary" style="padding: 3px 9px; font-size: 0.75rem;" onclick="adminApproveEvent(${e.id})">Approve & Publish</button>
          <button class="btn btn-ghost" style="padding: 3px 9px; font-size: 0.75rem; color: #ef4444;" onclick="adminRejectEvent(${e.id})">Request Revision</button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    showToast(err.message, true);
  }
}

async function adminApproveEvent(eventId) {
  try {
    await apiFetch(`/api/events/${eventId}/approve`, { method: "POST" });
    showToast("Event approved and published campus-wide!");
    loadAdminApprovals();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function adminRejectEvent(eventId) {
  const reason = prompt("Enter adjustment feedback for the coordinator:", "Please verify venue capacity and timing.");
  if (!reason) return;
  try {
    await apiFetch(`/api/events/${eventId}/reject?reason=${encodeURIComponent(reason)}`, { method: "POST" });
    showToast("Event returned to coordinator for revision.");
    loadAdminApprovals();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function loadAdminAnalytics() {
  try {
    const data = await apiFetch("/api/analytics/dashboard");

    document.getElementById("analyticsTotalUsers").innerText = data.total_users;
    document.getElementById("analyticsTotalEvents").innerText = data.total_events;
    document.getElementById("analyticsTotalRegistrations").innerText = data.total_registrations;
    document.getElementById("analyticsAttendanceRate").innerText = `${data.attendance_rate_percentage}%`;

    // Category breakdown
    const catContainer = document.getElementById("analyticsCategoryBreakdown");
    if (catContainer) {
      catContainer.innerHTML = data.category_popularity.map(c => `
        <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid var(--border-subtle);">
          <span><strong>${c.category}</strong> (${c.event_count} events)</span>
          <span><strong>${c.reg_count}</strong> Registrations</span>
        </div>
      `).join("");
    }
  } catch (err) {
    showToast(err.message, true);
  }
}

async function loadAdminVenues() {
  const tableBody = document.getElementById("adminVenuesTableBody");
  if (!tableBody) return;

  try {
    const venues = await apiFetch("/api/venues");
    cachedVenues = venues;
    tableBody.innerHTML = venues.map(v => `
      <tr>
        <td><strong>${v.name}</strong></td>
        <td>📍 ${v.location}</td>
        <td><strong>${v.capacity}</strong> seats</td>
        <td>
          <span class="badge ${v.is_available ? 'badge-green' : 'badge-red'}">
            ${v.is_available ? 'Available' : 'Maintenance'}
          </span>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    showToast(err.message, true);
  }
}

async function loadAdminUsers() {
  const tableBody = document.getElementById("adminUsersTableBody");
  if (!tableBody) return;

  try {
    const users = await apiFetch("/api/users");
    tableBody.innerHTML = users.map(u => `
      <tr>
        <td><strong>${u.name}</strong></td>
        <td>${u.email}</td>
        <td>${u.department} (Yr ${u.year})</td>
        <td><span class="badge badge-blue">${u.role.toUpperCase()}</span></td>
        <td>
          <select class="form-select" style="padding: 2px 6px; font-size: 0.75rem; width: auto;" onchange="changeUserRole(${u.id}, this.value)">
            <option value="student" ${u.role === 'student' ? 'selected' : ''}>Student</option>
            <option value="coordinator" ${u.role === 'coordinator' ? 'selected' : ''}>Coordinator</option>
            <option value="admin" ${u.role === 'admin' ? 'selected' : ''}>Administrator</option>
          </select>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    showToast(err.message, true);
  }
}

async function changeUserRole(userId, newRole) {
  try {
    await apiFetch(`/api/users/${userId}/role?new_role=${newRole}`, { method: "PUT" });
    showToast(`User role successfully updated to ${newRole.toUpperCase()}.`);
  } catch (err) {
    showToast(err.message, true);
    loadAdminUsers();
  }
}

// --------------------------------------------------------------------------
// MODAL CONTROLS & POPUPS
// --------------------------------------------------------------------------
function initModals() {
  // Category pill filters
  document.querySelectorAll(".filter-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activeCategory = pill.getAttribute("data-category");
      loadBrowseEvents();
    });
  });

  // Browse search input
  const searchInput = document.getElementById("browseSearchInput");
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(loadBrowseEvents, 300);
    });
  }

  // Create Event Form Submission
  const createEventForm = document.getElementById("createEventForm");
  if (createEventForm) {
    createEventForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const title = (document.getElementById("ceTitle")?.value || "").trim();
      const category = (document.getElementById("ceCategory")?.value || "").trim();
      const venueSelect = document.getElementById("ceVenue");
      const venue_id = parseInt(venueSelect?.value);
      const rawDate = (document.getElementById("ceDate")?.value || "").trim();
      const rawStartTime = (document.getElementById("ceStartTime")?.value || "").trim();
      const rawEndTime = (document.getElementById("ceEndTime")?.value || "").trim();
      const max_capacity = parseInt(document.getElementById("ceCapacity")?.value);
      const description = (document.getElementById("ceDescription")?.value || "").trim();
      const rules = (document.getElementById("ceRules")?.value || "").trim();
      const eligibility = (document.getElementById("ceEligibility")?.value || "").trim();

      // Normalize date (handle DD-MM-YYYY or DD/MM/YYYY)
      let date = rawDate;
      const dateMatch = rawDate.match(/^(\d{2})[-/](\d{2})[-/](\d{4})$/);
      if (dateMatch) {
        date = `${dateMatch[3]}-${dateMatch[2]}-${dateMatch[1]}`;
      }

      // Normalize time (strip seconds: HH:MM:SS -> HH:MM)
      const start_time = rawStartTime.slice(0, 5);
      const end_time = rawEndTime.slice(0, 5);

      // Client-side validations
      if (!title || title.length < 2) {
        showToast("Event title must be at least 2 characters.", true);
        return;
      }
      if (!category) {
        showToast("Please choose a category.", true);
        return;
      }
      if (!venue_id || isNaN(venue_id)) {
        showToast("Please select a target venue.", true);
        return;
      }
      if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
        showToast("Please enter a valid event date (YYYY-MM-DD or DD-MM-YYYY).", true);
        return;
      }
      if (!start_time || !/^\d{2}:\d{2}$/.test(start_time)) {
        showToast("Please enter a valid start time (HH:MM).", true);
        return;
      }
      if (!end_time || !/^\d{2}:\d{2}$/.test(end_time)) {
        showToast("Please enter a valid end time (HH:MM).", true);
        return;
      }
      if (start_time >= end_time) {
        showToast("Start time must be earlier than end time.", true);
        return;
      }
      if (!max_capacity || isNaN(max_capacity) || max_capacity <= 0) {
        showToast("Please enter a valid seat capacity greater than 0.", true);
        return;
      }
      if (!description || description.length < 5) {
        showToast("Event description must be at least 5 characters.", true);
        return;
      }

      try {
        await apiFetch("/api/events", {
          method: "POST",
          body: JSON.stringify({
            title, category, venue_id, date, start_time, end_time,
            max_capacity, description,
            rules: rules || null,
            eligibility: eligibility || null
          })
        });
        showToast("Event successfully created as draft!");
        closeModal("createEventModal");
        createEventForm.reset();
        loadCoordinatorDashboard();
      } catch (err) {
        showToast(err.message, true);
      }
    });
  }

  // Conflict Check in Create Event Form
  const checkConflictBtn = document.getElementById("ceCheckConflictBtn");
  if (checkConflictBtn) {
    checkConflictBtn.addEventListener("click", async () => {
      const venue_id = document.getElementById("ceVenue")?.value;
      const rawDate = (document.getElementById("ceDate")?.value || "").trim();
      const rawStartTime = (document.getElementById("ceStartTime")?.value || "").trim();
      const rawEndTime = (document.getElementById("ceEndTime")?.value || "").trim();

      if (!venue_id || !rawDate || !rawStartTime || !rawEndTime) {
        showToast("Please select venue, date, start time, and end time first.", true);
        return;
      }

      let date = rawDate;
      const dateMatch = rawDate.match(/^(\d{2})[-/](\d{2})[-/](\d{4})$/);
      if (dateMatch) {
        date = `${dateMatch[3]}-${dateMatch[2]}-${dateMatch[1]}`;
      }
      const start_time = rawStartTime.slice(0, 5);
      const end_time = rawEndTime.slice(0, 5);

      if (start_time >= end_time) {
        const statusBox = document.getElementById("ceConflictStatus");
        if (statusBox) statusBox.innerHTML = `<span style="color: #ef4444; font-weight: 700;">⚠️ Start time must be earlier than end time.</span>`;
        return;
      }

      try {
        const res = await apiFetch("/api/venues/check-conflict", {
          method: "POST",
          body: JSON.stringify({
            venue_id: parseInt(venue_id),
            date,
            start_time,
            end_time
          })
        });

        const statusBox = document.getElementById("ceConflictStatus");
        if (statusBox) {
          if (res.has_conflict) {
            statusBox.innerHTML = `<span style="color: #ef4444; font-weight: 700;">⚠️ ${res.reason}</span>`;
          } else {
            statusBox.innerHTML = `<span style="color: #10b981; font-weight: 700;">✓ ${res.reason}</span>`;
          }
        }
      } catch (err) {
        showToast(err.message, true);
      }
    });
  }

  // Create Venue Form Submission
  const createVenueForm = document.getElementById("createVenueForm");
  if (createVenueForm) {
    createVenueForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("cvName").value;
      const location = document.getElementById("cvLocation").value;
      const capacity = parseInt(document.getElementById("cvCapacity").value);

      try {
        await apiFetch("/api/venues", {
          method: "POST",
          body: JSON.stringify({ name, location, capacity, is_available: 1 })
        });
        showToast("Venue added successfully.");
        closeModal("createVenueModal");
        loadAdminVenues();
      } catch (err) {
        showToast(err.message, true);
      }
    });
  }

  // Broadcast Form Submission
  const broadcastForm = document.getElementById("broadcastForm");
  if (broadcastForm) {
    broadcastForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const submitBtn = broadcastForm.querySelector("button[type='submit']");
      const title = document.getElementById("bcTitle").value.trim();
      const message = document.getElementById("bcMessage").value.trim();
      const role = document.getElementById("bcRole").value || null;

      if (!title || !message) {
        showToast("Please provide both an announcement title and message.", true);
        return;
      }

      try {
        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.innerText = "Dispatching...";
        }
        const res = await apiFetch("/api/notifications/broadcast", {
          method: "POST",
          body: JSON.stringify({ title, message, role, type: "announcement" })
        });
        showToast(`✓ ${res.message}`);
        broadcastForm.reset();

        // Show prominent inline success banner in broadcast panel
        let banner = document.getElementById("broadcastSuccessBanner");
        if (!banner) {
          banner = document.createElement("div");
          banner.id = "broadcastSuccessBanner";
          banner.style.cssText = "margin-bottom: 1.25rem; padding: 0.85rem 1.15rem; background: var(--badge-green-bg); border: 1px solid var(--badge-green-text); color: var(--badge-green-text); border-radius: 8px; font-size: 0.88rem; font-weight: 500; display: flex; align-items: center; justify-content: space-between;";
          broadcastForm.parentNode.insertBefore(banner, broadcastForm);
        }
        banner.innerHTML = `<span>✓ ${res.message}</span><button type="button" onclick="this.parentElement.remove()" style="background:none; border:none; color:inherit; font-weight:bold; cursor:pointer; font-size:1.15rem; line-height:1;">&times;</button>`;
        setTimeout(() => { if (banner && banner.parentElement) banner.remove(); }, 6000);
      } catch (err) {
        showToast(err.message, true);
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerText = "Dispatch Notification & Gateway Push";
        }
      }
    });
  }

  // Feedback Form Submission
  const feedbackForm = document.getElementById("feedbackForm");
  if (feedbackForm) {
    feedbackForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const event_id = parseInt(document.getElementById("fbEventId").value);
      const rating = parseInt(document.getElementById("fbRating").value);
      const comments = document.getElementById("fbComments").value;

      try {
        await apiFetch("/api/feedback", {
          method: "POST",
          body: JSON.stringify({ event_id, rating, comments })
        });
        showToast("✓ Thank you for your feedback!");
        closeModal("feedbackModal");
      } catch (err) {
        showToast(err.message, true);
      }
    });
  }
}

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add("active");
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove("active");
}

function openQrPassModal(qrToken, eventTitle) {
  document.getElementById("qrModalEventTitle").innerText = eventTitle;
  document.getElementById("qrModalStudentName").innerText = currentUser.name;
  document.getElementById("qrModalDept").innerText = `${currentUser.department} (Year ${currentUser.year})`;
  document.getElementById("qrModalToken").innerText = qrToken;
  document.getElementById("qrModalImg").src = `/api/checkin/qr/${encodeURIComponent(qrToken)}`;
  openModal("qrPassModal");
}

function openFeedbackModal(eventId, eventTitle) {
  document.getElementById("fbEventId").value = eventId;
  document.getElementById("fbEventTitle").innerText = eventTitle;
  openModal("feedbackModal");
}

async function openEventDetailModal(eventId) {
  try {
    const e = await apiFetch(`/api/events/${eventId}`);
    document.getElementById("edTitle").innerText = e.title;
    document.getElementById("edCategory").innerText = e.category;
    document.getElementById("edDate").innerText = `${e.date} • ${e.start_time} - ${e.end_time}`;
    document.getElementById("edVenue").innerText = `${e.venue_name} (${e.venue_location})`;
    document.getElementById("edCapacity").innerText = `${e.registered_count} / ${e.max_capacity} enrolled (${e.available_seats} remaining)`;
    document.getElementById("edCoordinator").innerText = `${e.coordinator_name} (${e.coordinator_email})`;
    document.getElementById("edDescription").innerText = e.description;
    document.getElementById("edRules").innerText = e.rules || "Standard college festival code of conduct applies.";
    document.getElementById("edEligibility").innerText = e.eligibility || "Open to all enrolled students.";

    const regBtn = document.getElementById("edRegisterBtn");
    if (regBtn) {
      if (!currentUser || currentUser.role !== "student") {
        regBtn.style.display = "none";
      } else {
        regBtn.style.display = "inline-flex";
        const isRegistered = myRegisteredEventIds.has(e.id) || e.is_registered === true;
        const isFull = e.available_seats <= 0;
        if (isRegistered) {
          regBtn.disabled = true;
          regBtn.innerText = "✓ Already Registered";
          regBtn.style.background = "#10b981";
          regBtn.style.borderColor = "#10b981";
          regBtn.style.opacity = "0.9";
          regBtn.style.cursor = "default";
          regBtn.onclick = null;
        } else if (isFull) {
          regBtn.disabled = true;
          regBtn.innerText = "Registration Full";
          regBtn.style.background = "";
          regBtn.style.borderColor = "";
          regBtn.style.opacity = "0.5";
          regBtn.style.cursor = "not-allowed";
          regBtn.onclick = null;
        } else {
          regBtn.disabled = false;
          regBtn.innerText = "Register for Event";
          regBtn.style.background = "";
          regBtn.style.borderColor = "";
          regBtn.style.opacity = "";
          regBtn.style.cursor = "pointer";
          regBtn.onclick = () => {
            closeModal("eventDetailModal");
            registerForEvent(e.id);
          };
        }
      }
    }
    openModal("eventDetailModal");
  } catch (err) {
    showToast(err.message, true);
  }
}

async function openCreateEventModal() {
  const venueSelect = document.getElementById("ceVenue");
  try {
    const venues = await apiFetch("/api/venues");
    if (!venues || venues.length === 0) {
      showToast("No active venues found. Please contact administration.", true);
      return;
    }
    venueSelect.innerHTML = venues.map(v => `<option value="${v.id}">${v.name} (Cap: ${v.capacity})</option>`).join("");
    document.getElementById("ceConflictStatus").innerHTML = "";

    const dateInput = document.getElementById("ceDate");
    if (dateInput && !dateInput.value) {
      const today = new Date();
      dateInput.value = today.toISOString().split("T")[0];
    }
    openModal("createEventModal");
  } catch (err) {
    showToast(err.message, true);
  }
}

// --------------------------------------------------------------------------
// NOTIFICATION CENTER POPUP
// --------------------------------------------------------------------------
async function updateNotificationBadge() {
  try {
    const res = await apiFetch("/api/notifications/unread-count");
    const badge = document.getElementById("headerNotifBadge");
    if (badge) {
      if (res.unread_count > 0) {
        badge.style.display = "inline-flex";
        badge.innerText = res.unread_count;
      } else {
        badge.style.display = "none";
      }
    }
  } catch (err) {
    console.error("Failed to fetch unread notification count:", err);
  }
}

async function openNotificationCenter() {
  try {
    const notifs = await apiFetch("/api/notifications");
    const list = document.getElementById("notifModalList");
    if (!list) return;

    if (notifs.length === 0) {
      list.innerHTML = '<p style="text-align: center; color: var(--text-tertiary); padding: 1.5rem;">You have no notifications.</p>';
    } else {
      list.innerHTML = notifs.map(n => `
        <div style="padding: 0.85rem; border-bottom: 1px solid var(--border-subtle); background: ${n.is_read ? 'transparent' : 'var(--badge-blue-bg)'}; border-radius: 6px; margin-bottom: 0.4rem;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong style="font-size: 0.9rem; color: var(--text-primary);">${n.title}</strong>
            <span style="font-size: 0.72rem; color: var(--text-tertiary);">${n.created_at}</span>
          </div>
          <p style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 0.25rem;">${n.message}</p>
        </div>
      `).join("");
    }

    openModal("notificationModal");
    // Mark all as read
    await apiFetch("/api/notifications/read-all", { method: "PUT" });
    updateNotificationBadge();
  } catch (err) {
    showToast(err.message, true);
  }
}
