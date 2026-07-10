// =====================================================================
// LUMORA — frontend app logic
// No build step, no framework — plain JS. Talks to our own FastAPI
// backend (same origin), which in turn talks to Supabase.
// =====================================================================

const STORAGE_KEY_TOKEN = "lumora_access_token";
const STORAGE_KEY_EMAIL = "lumora_user_email";

// ---------------------------------------------------------------------
// Toasts — replaces browser alert() with something that matches the
// rest of the UI and doesn't block the page.
// ---------------------------------------------------------------------
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast is-${type}`;
  const icon = type === "error" ? "⚠" : type === "success" ? "✓" : "•";
  toast.innerHTML = `<span class="toast-icon">${icon}</span><span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("is-leaving");
    toast.addEventListener("animationend", () => toast.remove(), { once: true });
  }, 3800);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------------------------------------------------------------------
// Small fetch helper — automatically attaches the Bearer token when
// present, and throws a readable error on non-2xx responses.
// ---------------------------------------------------------------------
async function apiFetch(path, options = {}) {
  const token = localStorage.getItem(STORAGE_KEY_TOKEN);
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(path, { ...options, headers });
  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    /* no JSON body */
  }
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : `Request failed (${res.status})`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

// ---------------------------------------------------------------------
// Upload helper — separate from apiFetch because FormData must NOT
// get a manual Content-Type header (the browser sets the multipart
// boundary itself).
// ---------------------------------------------------------------------
async function apiUpload(path, formData) {
  const token = localStorage.getItem(STORAGE_KEY_TOKEN);
  const headers = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(path, { method: "POST", headers, body: formData });
  let data = null;
  try {
    data = await res.json();
  } catch (_) {}
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : `Upload failed (${res.status})`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

// ---------------------------------------------------------------------
// Screen switching
// ---------------------------------------------------------------------
function showAuthScreen() {
  document.getElementById("auth-screen").hidden = false;
  document.getElementById("app-shell").hidden = true;
}

function showAppShell(email) {
  document.getElementById("auth-screen").hidden = true;
  document.getElementById("app-shell").hidden = false;
  document.getElementById("user-email-display").textContent = email || "";
}

// ---------------------------------------------------------------------
// On load: if we have a stored token, verify it's still valid before
// trusting it (tokens expire — don't just assume localStorage is truth).
// ---------------------------------------------------------------------
async function checkExistingSession() {
  const token = localStorage.getItem(STORAGE_KEY_TOKEN);
  if (!token) {
    showAuthScreen();
    return;
  }
  try {
    const me = await apiFetch("/api/auth/me");
    showAppShell(me.email);
  } catch (err) {
    localStorage.removeItem(STORAGE_KEY_TOKEN);
    localStorage.removeItem(STORAGE_KEY_EMAIL);
    showAuthScreen();
  }
}

// ---------------------------------------------------------------------
// Auth tab switching (Log in / Sign up)
// ---------------------------------------------------------------------
const tabLogin = document.getElementById("tab-login");
const tabSignup = document.getElementById("tab-signup");
const loginForm = document.getElementById("login-form");
const signupForm = document.getElementById("signup-form");

tabLogin.addEventListener("click", () => {
  tabLogin.classList.add("is-active");
  tabSignup.classList.remove("is-active");
  tabLogin.setAttribute("aria-selected", "true");
  tabSignup.setAttribute("aria-selected", "false");
  loginForm.hidden = false;
  signupForm.hidden = true;
});

tabSignup.addEventListener("click", () => {
  tabSignup.classList.add("is-active");
  tabLogin.classList.remove("is-active");
  tabSignup.setAttribute("aria-selected", "true");
  tabLogin.setAttribute("aria-selected", "false");
  signupForm.hidden = false;
  loginForm.hidden = true;
});

// ---------------------------------------------------------------------
// Login
// ---------------------------------------------------------------------
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  const messageEl = document.getElementById("login-message");
  const submitBtn = document.getElementById("login-submit");

  messageEl.textContent = "";
  messageEl.className = "form-message";
  submitBtn.disabled = true;
  submitBtn.textContent = "Logging in…";

  try {
    const result = await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    localStorage.setItem(STORAGE_KEY_TOKEN, result.access_token);
    localStorage.setItem(STORAGE_KEY_EMAIL, result.email);
    showAppShell(result.email);
    loadNotes();
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.className = "form-message is-error";
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Log in";
  }
});

// ---------------------------------------------------------------------
// Signup
// ---------------------------------------------------------------------
signupForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = document.getElementById("signup-email").value.trim();
  const password = document.getElementById("signup-password").value;
  const messageEl = document.getElementById("signup-message");
  const submitBtn = document.getElementById("signup-submit");

  messageEl.textContent = "";
  messageEl.className = "form-message";
  submitBtn.disabled = true;
  submitBtn.textContent = "Creating account…";

  try {
    const result = await apiFetch("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    if (result.session && result.session.access_token) {
      // Email confirmation is off — we're logged in immediately.
      localStorage.setItem(STORAGE_KEY_TOKEN, result.session.access_token);
      localStorage.setItem(STORAGE_KEY_EMAIL, email);
      showAppShell(email);
      loadNotes();
    } else {
      // Email confirmation required before login will work.
      messageEl.textContent = "Account created. Check your email to confirm, then log in.";
      messageEl.className = "form-message is-success";
      setTimeout(() => tabLogin.click(), 1600);
    }
  } catch (err) {
    messageEl.textContent = err.message;
    messageEl.className = "form-message is-error";
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Create account";
  }
});

// ---------------------------------------------------------------------
// Logout
// ---------------------------------------------------------------------
document.getElementById("logout-btn").addEventListener("click", () => {
  localStorage.removeItem(STORAGE_KEY_TOKEN);
  localStorage.removeItem(STORAGE_KEY_EMAIL);
  showAuthScreen();
});

// ---------------------------------------------------------------------
// App shell tab navigation
// ---------------------------------------------------------------------
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("is-active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("is-active"));

    btn.classList.add("is-active");
    const panel = document.getElementById(`panel-${btn.dataset.tab}`);
    if (panel) panel.classList.add("is-active");
  });
});

// ---------------------------------------------------------------------
// Notes tab
// ---------------------------------------------------------------------
const uploadForm = document.getElementById("upload-form");
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("upload-file");
const dropzoneFilenameEl = document.getElementById("dropzone-filename");
const uploadRow = document.getElementById("upload-row");
const notesListEl = document.getElementById("notes-list");
const notesEmptyEl = document.getElementById("notes-empty");
const notesSectionLabelEl = document.getElementById("notes-section-label");

const FILE_ICON_LABEL = { pdf: "PDF", docx: "DOC", txt: "TXT" };

function statusBadge(status) {
  const label = status === "ready" ? "Ready" : status === "processing" ? "Processing" : "Error";
  return `<span class="status-badge status-${status}"><span class="status-dot"></span>${label}</span>`;
}

function renderNotes(notes) {
  notesListEl.querySelectorAll(".note-card").forEach((el) => el.remove());

  if (!notes.length) {
    notesEmptyEl.style.display = "flex";
    notesSectionLabelEl.hidden = true;
    return;
  }
  notesEmptyEl.style.display = "none";
  notesSectionLabelEl.hidden = false;

  notes.forEach((note) => {
    const card = document.createElement("div");
    card.className = "note-card";
    card.dataset.noteId = note.id;
    const date = new Date(note.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" });
    card.innerHTML = `
      <div class="note-info">
        <div class="note-file-icon">${FILE_ICON_LABEL[note.file_type] || note.file_type.toUpperCase()}</div>
        <div class="note-text">
          <span class="note-title">${escapeHtml(note.title)}</span>
          <span class="note-meta">Uploaded ${date}</span>
        </div>
      </div>
      <div class="note-actions">
        ${statusBadge(note.status)}
        <button class="btn-delete" data-delete-id="${note.id}">Delete</button>
      </div>
    `;
    notesListEl.appendChild(card);
  });
}

async function loadNotes() {
  try {
    const notes = await apiFetch("/api/notes");
    renderNotes(notes);
  } catch (err) {
    console.error("Failed to load notes:", err.message);
  }
}

// --- Dropzone interactions ---
function setSelectedFile(file) {
  if (!file) return;
  dropzoneFilenameEl.textContent = file.name;
  uploadRow.hidden = false;
}

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) setSelectedFile(fileInput.files[0]);
});

["dragenter", "dragover"].forEach((evt) => {
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("is-dragover");
  });
});

["dragleave", "drop"].forEach((evt) => {
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("is-dragover");
  });
});

dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (!file) return;
  fileInput.files = e.dataTransfer.files;
  setSelectedFile(file);
});

// --- Upload submit ---
uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const titleInput = document.getElementById("upload-title");
  const submitBtn = document.getElementById("upload-submit");

  if (!fileInput.files.length) return;

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  if (titleInput.value.trim()) formData.append("title", titleInput.value.trim());

  submitBtn.disabled = true;
  submitBtn.textContent = "Processing…";

  try {
    const result = await apiUpload("/api/notes", formData);
    showToast(`"${result.title}" uploaded — split into ${result.chunk_count} chunks.`, "success");
    fileInput.value = "";
    titleInput.value = "";
    dropzoneFilenameEl.textContent = "";
    uploadRow.hidden = true;
    await loadNotes();
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Upload note";
  }
});

notesListEl.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-delete-id]");
  if (!btn) return;
  const noteId = btn.dataset.deleteId;
  const card = btn.closest(".note-card");
  btn.textContent = "Deleting…";
  btn.disabled = true;
  try {
    await apiFetch(`/api/notes/${noteId}`, { method: "DELETE" });
    card.style.transition = "opacity 0.2s ease";
    card.style.opacity = "0";
    setTimeout(() => loadNotes(), 180);
    showToast("Note deleted.", "success");
  } catch (err) {
    showToast(`Could not delete note: ${err.message}`, "error");
    btn.textContent = "Delete";
    btn.disabled = false;
  }
});

// ---------------------------------------------------------------------
// Boot — check session first; if logged in, also load notes
// ---------------------------------------------------------------------
checkExistingSession().then(() => {
  if (!document.getElementById("app-shell").hidden) {
    loadNotes();
  }
});
