/* KEYZBOT Sidebar — Sessions, sidebar toggle, hamburger menu */
// ─── Sidebar Toggle ──────────────────────────────────────────────────────────
function toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebar-overlay");
    sidebar.classList.toggle("hidden");
    overlay.classList.toggle("active");
}
function closeSidebar() {
    document.getElementById("sidebar").classList.add("hidden");
    document.getElementById("sidebar-overlay").classList.remove("active");
}

// ─── Session Management ──────────────────────────────────────────────────────
function renderSessions(chats) {
    const list = document.getElementById("sessions-list");
    if (!list) return;
    list.innerHTML = "";
    if (!chats || !Array.isArray(chats)) return;
    chats.forEach(chat => {
        const item = document.createElement("div");
        item.className = "session-item" + (chat.id === activeChatId ? " active" : "");
        const safeId = esc(chat.id);
        const safeName = esc(chat.name);
        item.innerHTML = `
            <span class="session-icon"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></span>
            <span class="session-name">${safeName}</span>
            <span class="session-time">${chat.messages || 0}</span>
            <div class="session-actions">
                <button class="session-action" title="Rename"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
                <button class="session-action delete" title="Delete"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>
            </div>`;
        // Bind events safely without inline onclick (prevents XSS via chat name)
        item.onclick = () => switchChat(chat.id);
        const renameBtn = item.querySelector(".session-action:not(.delete)");
        if (renameBtn) renameBtn.onclick = (e) => { e.stopPropagation(); openRename(chat.id, chat.name); };
        const deleteBtn = item.querySelector(".session-action.delete");
        if (deleteBtn) deleteBtn.onclick = (e) => { e.stopPropagation(); deleteChat(chat.id); };
        list.appendChild(item);
    });
}

function newChat() { socket.emit("new_chat"); clearMessages(); showWelcome(); closeSidebar(); }
function switchChat(chatId) { if (chatId === activeChatId) return; socket.emit("switch_chat", { chat_id: chatId }); closeSidebar(); }
function deleteChat(chatId) { socket.emit("delete_chat", { chat_id: chatId }); }

function openRename(chatId, currentName) {
    renameTargetId = chatId;
    document.getElementById("rename-input").value = currentName;
    openModal("rename-modal");
    setTimeout(() => document.getElementById("rename-input").focus(), 100);
}

function confirmRename() {
    const name = document.getElementById("rename-input").value.trim();
    if (name && renameTargetId) socket.emit("rename_chat", { chat_id: renameTargetId, name });
    closeModal("rename-modal");
}

document.getElementById("rename-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); confirmRename(); }
});

// ─── Setup Modal ────────────────────────────────────────────────────────────
function showSetupModal() {
    const overlay = document.getElementById("setup-overlay");
    if (!overlay) return;
    overlay.style.display = "flex";
    setupStep = 1;
    updateSetupStep();
    populateDateDropdowns();
    overlay.querySelectorAll(".setup-lang").forEach(btn => {
        btn.onclick = function() {
            overlay.querySelectorAll(".setup-lang").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
        };
    });
    document.getElementById("setup-prev").onclick = function() { if (setupStep > 1) { setupStep--; updateSetupStep(); } };
    document.getElementById("setup-next").onclick = function() { if (setupStep < 3) { setupStep++; updateSetupStep(); } else { submitSetup(); } };
}

function updateSetupStep() {
    const overlay = document.getElementById("setup-overlay");
    overlay.querySelectorAll(".setup-step").forEach(s => s.classList.remove("active"));
    const current = overlay.querySelector('[data-step="' + setupStep + '"]');
    if (current) current.classList.add("active");
    overlay.querySelectorAll(".setup-dots .dot").forEach((d, i) => { d.classList.toggle("active", i === setupStep - 1); });
    document.getElementById("setup-prev").style.visibility = setupStep > 1 ? "visible" : "hidden";
    const nextBtn = document.getElementById("setup-next");
    nextBtn.textContent = setupStep === 3 ? "Mulai" : "Selanjutnya";
}

function populateDateDropdowns() {
    const daySel = document.getElementById("setup-day");
    const monthSel = document.getElementById("setup-month");
    const yearSel = document.getElementById("setup-year");
    for (let d = 1; d <= 31; d++) { const opt = document.createElement("option"); opt.value = d; opt.textContent = d; daySel.appendChild(opt); }
    const months = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"];
    months.forEach((m, i) => { const opt = document.createElement("option"); opt.value = i + 1; opt.textContent = m; monthSel.appendChild(opt); });
    const currentYear = new Date().getFullYear();
    for (let y = currentYear; y >= 1950; y--) { const opt = document.createElement("option"); opt.value = y; opt.textContent = y; yearSel.appendChild(opt); }
}

function submitSetup() {
    const name = document.getElementById("setup-name").value.trim();
    if (!name) { document.getElementById("setup-name").focus(); return; }
    const day = document.getElementById("setup-day").value;
    const month = document.getElementById("setup-month").value;
    const year = document.getElementById("setup-year").value;
    let birthdate = "";
    if (day && month && year) birthdate = day + " " + document.getElementById("setup-month").options[document.getElementById("setup-month").selectedIndex].text + " " + year;
    const langBtn = document.querySelector(".setup-lang.active");
    const lang = langBtn ? langBtn.dataset.lang : "id";
    socket.emit("save_profile", { name: name, birthdate: birthdate, language: lang });
    document.getElementById("setup-overlay").style.display = "none";
}

function updateSidebarUserName() {
    const el = document.getElementById("sidebar-user-name");
    if (el && userProfile.name) {
        el.textContent = userProfile.name;
        const avatar = document.querySelector(".sidebar-user-avatar");
        if (avatar) avatar.textContent = userProfile.name.charAt(0).toUpperCase();
    }
}

// ─── Hamburger Menu ──────────────────────────────────────────────────────────
function _createHamburgerMenu() {
    const menu = document.createElement('div');
    menu.id = 'hamburger-menu';
    menu.className = 'hamburger-menu hidden';
    menu.innerHTML = `
        <div class="hamburger-header">
            <div style="display:flex;align-items:center;gap:10px">
                <img src="/keyzbot.svg" width="24" height="24" style="border-radius:6px;animation:logoFloat 6s ease-in-out infinite">
                <span style="font-weight:800;font-size:15px;letter-spacing:-.3px;background:linear-gradient(90deg,#a78bfa,#6366f1,#818cf8,#a78bfa,#6366f1);background-size:400% 100%;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:brandFlow 8s linear infinite">KEYZBOT</span>
            </div>
            <button class="hamburger-close" onclick="closeHamburger()">&times;</button>
        </div>
        <div class="hamburger-body">
            <div class="hamburger-section">
                <div class="hamburger-section-title">Active Provider</div>
                <div class="hamburger-provider-card" onclick="openProviderModal()">
                    <div class="hamburger-provider-icon">
                        <img src="/keyzbot.svg" width="24" height="24" style="border-radius:6px">
                    </div>
                    <div class="hamburger-provider-info">
                        <span class="provider-name" id="menu-provider-name">-</span>
                        <span class="provider-model" id="menu-provider-model">-</span>
                    </div>
                    <span class="hamburger-arrow">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                    </span>
                </div>
            </div>
            <div class="hamburger-section">
                <div class="hamburger-section-title">Quick Actions</div>
                <button class="hamburger-btn" onclick="openProviderModal()">
                    <span class="hamburger-icon"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.26.604.852.997 1.51 1H21a2 2 0 0 1 0 4h-.09c-.658.003-1.25.396-1.51 1z"/></svg></span>
                    Provider Settings
                </button>
                <button class="hamburger-btn" onclick="closeHamburger(); toggleTheme()">
                    <span class="hamburger-icon"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg></span>
                    Toggle Theme
                </button>
                <button class="hamburger-btn" onclick="closeHamburger(); openModal('export-modal')">
                    <span class="hamburger-icon"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg></span>
                    Export Chat
                </button>
                <button class="hamburger-btn" onclick="closeHamburger(); runCmd('/help')">
                    <span class="hamburger-icon"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></span>
                    Help
                </button>
            </div>
        </div>`;
    document.body.appendChild(menu);
}
_createHamburgerMenu();

function toggleHamburger() {
    const menu = document.getElementById("hamburger-menu");
    if (!menu) return;
    const isOpen = !menu.classList.contains("hidden");
    if (isOpen) closeHamburger();
    else { menu.classList.remove("hidden"); updateHamburgerInfo(); setTimeout(() => document.addEventListener("click", closeHamburgerOutside), 100); }
}

function closeHamburger() {
    const menu = document.getElementById("hamburger-menu");
    if (menu) menu.classList.add("hidden");
    document.removeEventListener("click", closeHamburgerOutside);
}

function closeHamburgerOutside(e) {
    const menu = document.getElementById("hamburger-menu");
    const btn = document.getElementById("hamburger-btn");
    if ((menu && menu.contains(e.target)) || (btn && btn.contains(e.target))) return;
    closeHamburger();
}

function updateHamburgerInfo() { socket.emit("get_providers"); }

// ─── Input / Commands ────────────────────────────────────────────────────────
function send() {
    const text = input.value.trim();
    if (!text && pendingImages.length === 0) return;
    // Guard: don't send while streaming — queue or show warning
    if (isStreaming) {
        addError("Please wait — the current response is still being generated.");
        scrollBottom();
        return;
    }
    const images = pendingImages.slice();
    pendingImages = [];
    renderImagePreviews();
    input.value = "";
    autoResize();
    sendBtn.disabled = true;
    socket.emit("user_message", { text, images });
}
function sendSuggestion(text) { input.value = text; send(); }
function runCmd(cmd) { socket.emit("user_message", { text: cmd }); closeSidebar(); }

input.addEventListener("keydown", (e) => {
    if (cmdDropdownVisible) {
        if (e.key === "ArrowDown") { e.preventDefault(); cmdNav(1); return; }
        if (e.key === "ArrowUp") { e.preventDefault(); cmdNav(-1); return; }
        if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); cmdSelect(); return; }
        if (e.key === "Escape") { cmdHide(); return; }
    }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
input.addEventListener("input", () => { autoResize(); sendBtn.disabled = !input.value.trim(); cmdCheck(); });

const COMMANDS = [
    {cmd: "/help", desc: "Show all available commands", hint: ""},
    {cmd: "/clear", desc: "Clear chat history", hint: ""},
    {cmd: "/compact", desc: "Compress context to save tokens", hint: ""},
    {cmd: "/model", desc: "Switch AI model", hint: "[model]"},
    {cmd: "/temp", desc: "Set temperature (0-2)", hint: "[0-2]"},
    {cmd: "/provider", desc: "Switch provider", hint: "[id]"},
    {cmd: "/tokens", desc: "Show token usage & cost", hint: ""},
    {cmd: "/status", desc: "Show session status", hint: ""},
    {cmd: "/config", desc: "Show current configuration", hint: ""},
    {cmd: "/system", desc: "Show/edit system prompt", hint: "[text]"},
    {cmd: "/tools", desc: "List available tools", hint: ""},
    {cmd: "/rename", desc: "Rename current chat", hint: "[name]"},
    {cmd: "/export", desc: "Export chat history", hint: ""},
    {cmd: "/reset", desc: "Reset session & clear all", hint: ""},
    {cmd: "/fast", desc: "Toggle fast mode", hint: ""},
    {cmd: "/cd", desc: "Change working directory", hint: "[path]"},
    {cmd: "/pwd", desc: "Show working directory", hint: ""},
    {cmd: "/remember", desc: "Save to memory", hint: "[text]"},
    {cmd: "/recall", desc: "Search memory", hint: "[query]"},
    {cmd: "/forget", desc: "Delete memory entry", hint: "[id]"},
];
let cmdDropdownVisible = false;
let cmdActiveIdx = 0;
let cmdFiltered = [];

function cmdCheck() {
    const val = input.value;
    const dropdown = document.getElementById("cmd-dropdown");
    if (!dropdown) return;
    if (val.startsWith("/") && val.length < 20) {
        const query = val.toLowerCase();
        cmdFiltered = COMMANDS.filter(c => c.cmd.startsWith(query));
        if (cmdFiltered.length > 0 && val.length > 0) {
            cmdActiveIdx = 0; cmdRender();
            dropdown.classList.remove("hidden");
            cmdDropdownVisible = true;
            return;
        }
    }
    cmdHide();
}

function cmdRender() {
    const dropdown = document.getElementById("cmd-dropdown");
    if (!dropdown) return;
    dropdown.innerHTML = cmdFiltered.map((c, i) => `
        <div class="cmd-item ${i === cmdActiveIdx ? 'active' : ''}" data-idx="${i}" onmousedown="cmdClick(${i})">
            <span class="cmd-item-name">${c.cmd}</span>
            <span class="cmd-item-desc">${c.desc}</span>
            <span class="cmd-item-hint">${c.hint}</span>
        </div>`).join("");
}

function cmdNav(dir) {
    cmdActiveIdx = (cmdActiveIdx + dir + cmdFiltered.length) % cmdFiltered.length;
    cmdRender();
    const dropdown = document.getElementById("cmd-dropdown");
    const active = dropdown.querySelector(".cmd-item.active");
    if (active) active.scrollIntoView({block: "nearest"});
}

function cmdSelect() {
    if (cmdFiltered.length === 0) return;
    input.value = cmdFiltered[cmdActiveIdx].cmd + " ";
    cmdHide(); input.focus(); autoResize(); sendBtn.disabled = false;
}

function cmdClick(idx) { cmdActiveIdx = idx; cmdSelect(); }
function cmdHide() {
    const dropdown = document.getElementById("cmd-dropdown");
    if (dropdown) dropdown.classList.add("hidden");
    cmdDropdownVisible = false; cmdFiltered = [];
}

document.addEventListener("click", (e) => { if (cmdDropdownVisible && !e.target.closest("#input-area")) cmdHide(); });

function autoResize() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 200) + "px"; }

// ─── File Upload ─────────────────────────────────────────────────────────────
function compressImage(file, callback) {
    const img = new Image();
    const reader = new FileReader();
    reader.onload = () => {
        img.onload = () => {
            let w = img.width, h = img.height;
            if (w > IMG_MAX || h > IMG_MAX) { const ratio = Math.min(IMG_MAX / w, IMG_MAX / h); w = Math.round(w * ratio); h = Math.round(h * ratio); }
            const canvas = document.createElement("canvas");
            canvas.width = w; canvas.height = h;
            canvas.getContext("2d").drawImage(img, 0, 0, w, h);
            const dataUrl = canvas.toDataURL("image/jpeg", 0.7);
            const b64 = dataUrl.split(",")[1];
            callback({ filename: file.name, b64: b64, mime: "image/jpeg", dataUrl: dataUrl, size_kb: Math.round(b64.length * 3 / 4 / 1024) });
        };
        img.src = reader.result;
    };
    reader.readAsDataURL(file);
}

function handleFileUpload(inputEl) {
    Array.from(inputEl.files).forEach(file => {
        const ext = "." + file.name.split(".").pop().toLowerCase();
        if (IMAGE_EXTS.includes(ext)) {
            compressImage(file, (img) => { pendingImages.push(img); renderImagePreviews(); });
        } else {
            const reader = new FileReader();
            reader.onload = () => {
                socket.emit("file_upload", { filename: file.name, data: reader.result.split(",")[1] });
                addCommandResult(`Uploading: **${file.name}** (${(file.size/1024).toFixed(1)} KB)...`);
                scrollBottom();
            };
            reader.readAsDataURL(file);
        }
    });
    inputEl.value = "";
}

function renderImagePreviews() {
    let bar = document.getElementById("image-preview-bar");
    if (!bar) {
        bar = document.createElement("div");
        bar.id = "image-preview-bar";
        const containerEl = document.querySelector(".input-container");
        containerEl.parentNode.insertBefore(bar, containerEl);
    }
    bar.innerHTML = "";
    pendingImages.forEach((img, i) => {
        const item = document.createElement("div");
        item.className = "img-preview-item";
        item.innerHTML = `<img src="${img.dataUrl}" alt="${esc(img.filename)}"><button class="img-remove" onclick="removePendingImage(${i})">&times;</button>`;
        bar.appendChild(item);
    });
    input.focus();
}

function removePendingImage(idx) { pendingImages.splice(idx, 1); renderImagePreviews(); }

container.addEventListener("dragover", (e) => { e.preventDefault(); });
container.addEventListener("drop", (e) => {
    e.preventDefault();
    Array.from(e.dataTransfer.files).forEach(file => {
        const ext = "." + file.name.split(".").pop().toLowerCase();
        if (IMAGE_EXTS.includes(ext)) {
            compressImage(file, (img) => { pendingImages.push(img); renderImagePreviews(); });
        } else {
            const reader = new FileReader();
            reader.onload = () => {
                socket.emit("file_upload", { filename: file.name, data: reader.result.split(",")[1] });
                addCommandResult(`Uploading: **${file.name}**...`); scrollBottom();
            };
            reader.readAsDataURL(file);
        }
    });
});

// ─── Export ──────────────────────────────────────────────────────────────────
function exportChat(format) { window.open(`/api/export/${format}?sid=${BROWSER_ID}`, "_blank"); closeModal("export-modal"); }
