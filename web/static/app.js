/* KEYZBOT Web UI — Complete Client with Session Management */
// Persistent browser ID for session restoration across refreshes
let BROWSER_ID = localStorage.getItem("keyzbot_browser_id");
if (!BROWSER_ID) {
    BROWSER_ID = "bid_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem("keyzbot_browser_id", BROWSER_ID);
}
const socket = io({ query: { browser_id: BROWSER_ID } });
const messagesEl = document.getElementById("messages");
const container = document.getElementById("messages-container");
const input = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const welcomeEl = document.getElementById("welcome");
const statusBar = document.getElementById("status-bar");

let streamEl = null, streamContentEl = null;
let streamRawText = "";
let hadStream = false;
let activeChatId = "";
let renameTargetId = "";
let isStreaming = false;
let userProfile = {};
let setupStep = 1;

// ─── Socket Events ───────────────────────────────────────────────────────────
socket.on("connected", (data) => {
    statusBar.textContent = "Connected";
    activeChatId = data.active_chat;
    userProfile = data.profile || {};
    updateSidebarUserName();
    renderSessions(data.chats);
    fetchConfig();
    // Show setup modal if first run
    if (data.profile && !data.profile.setup_complete) {
        showSetupModal();
    }
    // Restore messages from previous session
    if (data.messages && data.messages.length > 0) {
        hideWelcome();
        data.messages.forEach(m => {
            if (m.type === "user") addUserMessage(m.text, m.images);
            else if (m.type === "bot") addBotMessage(m.text);
            else if (m.type === "tool_call") addToolCall(m.name, m.args);
            else if (m.type === "tool_result") addToolResultDirect(m.text);
        });
        scrollToBottom();
    }
    // Restore thinking animation if chat is still streaming
    if (data.streaming) {
        showThinking();
    }
    // Show update toast if update available
    if (data.update_available) {
        showUpdateToast();
    }
});

// ── Update Toast ─────────────────────────────────────────────────────────────
function showUpdateToast() {
    document.getElementById("update-toast").style.display = "block";
}

function dismissUpdate() {
    document.getElementById("update-toast").style.display = "none";
}

function doUpdate() {
    const btn = document.getElementById("update-btn");
    const status = document.getElementById("update-status");
    btn.disabled = true;
    btn.textContent = "Updating...";
    status.style.display = "block";
    status.textContent = "Checking for updates...";
    socket.emit("update_now");
}

socket.on("update_available", (data) => {
    showUpdateToast();
});

socket.on("update_status", (data) => {
    const status = document.getElementById("update-status");
    const btn = document.getElementById("update-btn");
    status.style.display = "block";
    status.textContent = data.message || "";
    if (data.status === "restarting") {
        btn.textContent = "Restarting...";
        status.textContent = "Server sedang restart...";
    } else if (data.status === "error") {
        btn.disabled = false;
        btn.textContent = "Update Now";
        status.style.color = "#ef4444";
    }
});

socket.on("status", (s) => {
    // Update topbar tags
    updateTopbarTags(s);
    const sessionTag = document.getElementById("topbar-session");
    if (s.messages) { sessionTag.textContent = s.messages + " msgs"; sessionTag.style.display = ""; }
    else { sessionTag.style.display = "none"; }

    // Sidebar
    const tokenStr = s.tokens ? `${s.tokens} tokens` : "0 tokens";
    const costStr = s.cost ? ` · $${s.cost}` : "";
    document.getElementById("sidebar-tokens").textContent = tokenStr + costStr;
    if (s.tool_count) document.getElementById("tools-count").textContent = s.tool_count + " tools";

    // Status bar
    const wd = s.work_dir || "";
    const shortPath = wd ? wd.split('/').slice(-2).join('/') : "Ready";
    const statusToken = s.tokens ? ` · ${s.tokens}t` : "";
    const statusCost = s.cost ? ` · $${s.cost}` : "";
    statusBar.textContent = shortPath + statusToken + statusCost;
});

socket.on("chats_updated", (data) => renderSessions(data.chats));

socket.on("chat_switched", (data) => {
    activeChatId = data.active_chat;
    // Clear any in-flight stream state
    streamEl = null; streamContentEl = null; streamRawText = "";
    hadStream = false;
    isStreaming = false;
    renderSessions(data.chats);
    // Clear UI
    clearMessages();
    if (data.messages && data.messages.length > 0) {
        hideWelcome();
        data.messages.forEach(m => {
            if (m.type === "user") addUserMessage(m.text, m.images);
            else if (m.type === "bot") addBotMessage(m.text);
            else if (m.type === "tool_call") addToolCall(m.name, m.args);
            else if (m.type === "tool_result") {
                if (m.text.includes('--- a/') && m.text.includes('+++ b/')) {
                    addToolCall("tool", "");
                    const id = lastToolCall;
                    if (id) {
                        const resultEl = document.getElementById(id + "-result");
                        if (resultEl) resultEl.innerHTML = renderDiff(m.text);
                    }
                } else {
                    addToolResultDirect(m.text);
                }
            }
        });
    } else {
        showWelcome();
    }
    scrollBottom();
});

socket.on("chat_deleted", (data) => {
    activeChatId = data.active_chat;
    renderSessions(data.chats);
    // Clear current messages
    clearMessages();
    if (data.cleared) {
        showWelcome();
    } else if (data.messages && data.messages.length > 0) {
        // Restore messages of the new active chat
        hideWelcome();
        data.messages.forEach(m => {
            if (m.type === "user") addUserMessage(m.text, m.images);
            else if (m.type === "bot") addBotMessage(m.text);
            else if (m.type === "tool_call") addToolCall(m.name, m.args);
            else if (m.type === "tool_result") addToolResultDirect(m.text);
        });
        scrollBottom();
    } else {
        showWelcome();
    }
});

socket.on("command_result", (data) => {
    removeThinking();
    // /clear or /reset — clear messages with smooth transition, no result text
    if (data.command && (data.command === "/clear" || data.command.startsWith("/clear ") || data.command === "/reset")) {
        clearChatUI();
        return;
    }
    hideWelcome();
    addCommandResult(data.text);
    scrollBottom();
});

socket.on("ephemeral_result", (data) => {
    hideWelcome();
    removeThinking();
    addEphemeralMessage(data.text, 60000);
});

socket.on("thinking", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    if (data.active) addThinking();
});

socket.on("chat_start", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    hideWelcome();
    removeThinking();
    hadStream = false;
    isStreaming = true;
    addUserMessage(data.user, data.images);
    scrollBottom();
});

socket.on("bot_stream_start", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    removeThinking();
    hadStream = true;
    isStreaming = true;
    streamRawText = "";
    // Reset tool state for new response
    lastToolCall = null; toolCallDone = false; toolCallEl = null;
    const { row, contentEl } = createBotMessage();
    streamEl = row; streamContentEl = contentEl;
    messagesEl.appendChild(row);
    scrollBottom();
});

socket.on("bot_stream_chunk", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    // Auto-create stream element if missing (reconnect recovery)
    if (!streamContentEl) {
        removeThinking();
        hadStream = true;
        isStreaming = true;
        streamRawText = "";
        const { row, contentEl } = createBotMessage();
        streamEl = row; streamContentEl = contentEl;
        messagesEl.appendChild(row);
    }
    streamRawText = (streamRawText || "") + data.text;
    streamContentEl.innerHTML = renderMarkdown(streamRawText) + '<span class="cursor"></span>';
    highlightCode(streamContentEl);
    checkTableScroll(streamContentEl);
    scrollBottom();
});

socket.on("bot_stream_end", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    if (streamContentEl) {
        const cursor = streamContentEl.querySelector('.cursor');
        if (cursor) cursor.remove();
        addCopyButtons(streamContentEl);
        checkTableScroll(streamContentEl);
    }
    streamEl = null; streamContentEl = null; streamRawText = "";
    isStreaming = false;
    scrollBottom();
});

socket.on("tool_call", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    removeThinking();
    addToolCall(data.name, data.args);
    scrollBottom();
});

socket.on("tool_result", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    addToolResult(data.name, data.result);
    scrollBottom();
});

socket.on("chat_done", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    if (!hadStream && data.text) {
        removeThinking();
        addBotMessage(data.text);
    }
    isStreaming = false;
    sendBtn.disabled = !input.value.trim();
    scrollBottom();
});

socket.on("chat_error", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    removeThinking();
    addError(data.error);
    sendBtn.disabled = !input.value.trim();
    scrollBottom();
});

socket.on("upload_result", (data) => {
    if (data.error) addError("Upload: " + data.error);
    else addCommandResult(`Uploaded: **${data.name}** (${(data.size/1024).toFixed(1)} KB)\n\`${data.path}\``);
    scrollBottom();
});

socket.on("cron_fire", (data) => {
    addCommandResult(`Cron **#${data.job_id}** fired`);
    socket.emit("user_message", { text: data.prompt });
    scrollBottom();
});

// ─── Sub-Agent Events ───────────────────────────────────────────────────────
socket.on("agent_done", (data) => {
    addCommandResult(`Agent **${data.name}** completed:\n${data.result || "(no output)"}`);
    scrollBottom();
});

socket.on("agent_error", (data) => {
    addError(`Agent **${data.name}** failed: ${data.error}`);
    scrollBottom();
});

socket.on("agent_tool_call", (data) => {
    addCommandResult(`Agent **${data.name}** using tool: \`${data.tool}\``);
    scrollBottom();
});

socket.on("agent_tool_result", (data) => {
    addCommandResult(`Agent **${data.name}** tool \`${data.tool}\` done`);
    scrollBottom();
});

socket.on("profile_saved", (data) => {
    userProfile = data;
    updateSidebarUserName();
});

// ─── Setup Modal ────────────────────────────────────────────────────────────
function showSetupModal() {
    const overlay = document.getElementById("setup-overlay");
    if (!overlay) return;
    overlay.style.display = "flex";
    setupStep = 1;
    updateSetupStep();
    populateDateDropdowns();
    // Language toggle
    overlay.querySelectorAll(".setup-lang").forEach(btn => {
        btn.onclick = function() {
            overlay.querySelectorAll(".setup-lang").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
        };
    });
    // Navigation
    document.getElementById("setup-prev").onclick = function() {
        if (setupStep > 1) { setupStep--; updateSetupStep(); }
    };
    document.getElementById("setup-next").onclick = function() {
        if (setupStep < 3) { setupStep++; updateSetupStep(); }
        else { submitSetup(); }
    };
}

function updateSetupStep() {
    const overlay = document.getElementById("setup-overlay");
    overlay.querySelectorAll(".setup-step").forEach(s => s.classList.remove("active"));
    const current = overlay.querySelector('[data-step="' + setupStep + '"]');
    if (current) current.classList.add("active");
    // Dots
    overlay.querySelectorAll(".setup-dots .dot").forEach((d, i) => {
        d.classList.toggle("active", i === setupStep - 1);
    });
    // Prev button
    document.getElementById("setup-prev").style.visibility = setupStep > 1 ? "visible" : "hidden";
    // Next button text
    const nextBtn = document.getElementById("setup-next");
    nextBtn.textContent = setupStep === 3 ? "Mulai" : "Selanjutnya";
}

function populateDateDropdowns() {
    const daySel = document.getElementById("setup-day");
    const monthSel = document.getElementById("setup-month");
    const yearSel = document.getElementById("setup-year");
    for (let d = 1; d <= 31; d++) {
        const opt = document.createElement("option");
        opt.value = d; opt.textContent = d;
        daySel.appendChild(opt);
    }
    const months = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"];
    months.forEach((m, i) => {
        const opt = document.createElement("option");
        opt.value = i + 1; opt.textContent = m;
        monthSel.appendChild(opt);
    });
    const currentYear = new Date().getFullYear();
    for (let y = currentYear; y >= 1950; y--) {
        const opt = document.createElement("option");
        opt.value = y; opt.textContent = y;
        yearSel.appendChild(opt);
    }
}

function submitSetup() {
    const name = document.getElementById("setup-name").value.trim();
    if (!name) { document.getElementById("setup-name").focus(); return; }
    const day = document.getElementById("setup-day").value;
    const month = document.getElementById("setup-month").value;
    const year = document.getElementById("setup-year").value;
    let birthdate = "";
    if (day && month && year) {
        birthdate = day + " " + document.getElementById("setup-month").options[document.getElementById("setup-month").selectedIndex].text + " " + year;
    }
    const langBtn = document.querySelector(".setup-lang.active");
    const lang = langBtn ? langBtn.dataset.lang : "id";
    socket.emit("save_profile", { name: name, birthdate: birthdate, language: lang });
    // Hide modal
    document.getElementById("setup-overlay").style.display = "none";
}

function updateSidebarUserName() {
    const el = document.getElementById("sidebar-user-name");
    if (el && userProfile.name) {
        el.textContent = userProfile.name;
        // Update avatar to first letter of name
        const avatar = document.querySelector(".sidebar-user-avatar");
        if (avatar) avatar.textContent = userProfile.name.charAt(0).toUpperCase();
    }
}

// ─── Session Management ──────────────────────────────────────────────────────
function renderSessions(chats) {
    const list = document.getElementById("sessions-list");
    list.innerHTML = "";
    chats.forEach(chat => {
        const item = document.createElement("div");
        item.className = "session-item" + (chat.id === activeChatId ? " active" : "");
        item.innerHTML = `
            <span class="session-icon"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></span>
            <span class="session-name">${esc(chat.name)}</span>
            <span class="session-time">${chat.messages || 0}</span>
            <div class="session-actions">
                <button class="session-action" onclick="event.stopPropagation(); openRename('${chat.id}', '${esc(chat.name)}')" title="Rename"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
                <button class="session-action delete" onclick="event.stopPropagation(); deleteChat('${chat.id}')" title="Delete"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>
            </div>
        `;
        item.onclick = () => switchChat(chat.id);
        list.appendChild(item);
    });
}

function newChat() {
    socket.emit("new_chat");
    clearMessages();
    showWelcome();
    closeSidebar();
}

function switchChat(chatId) {
    if (chatId === activeChatId) return;
    socket.emit("switch_chat", { chat_id: chatId });
    closeSidebar();
}

function deleteChat(chatId) {
    socket.emit("delete_chat", { chat_id: chatId });
}

function openRename(chatId, currentName) {
    renameTargetId = chatId;
    document.getElementById("rename-input").value = currentName;
    openModal("rename-modal");
    setTimeout(() => document.getElementById("rename-input").focus(), 100);
}

function confirmRename() {
    const name = document.getElementById("rename-input").value.trim();
    if (name && renameTargetId) {
        socket.emit("rename_chat", { chat_id: renameTargetId, name });
    }
    closeModal("rename-modal");
}

// Enter key in rename input
document.getElementById("rename-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); confirmRename(); }
});

function closeSidebar() {
    document.getElementById("sidebar").classList.add("hidden");
    document.getElementById("sidebar-overlay").classList.remove("active");
}

// ─── Input ───────────────────────────────────────────────────────────────────
function send() {
    const text = input.value.trim();
    if (!text && pendingImages.length === 0) return;
    const images = pendingImages.slice();
    pendingImages = [];
    renderImagePreviews();
    input.value = "";
    autoResize();
    sendBtn.disabled = true;
    socket.emit("user_message", { text, images });
}

function sendSuggestion(text) { input.value = text; send(); }

function runCmd(cmd) {
    socket.emit("user_message", { text: cmd });
    closeSidebar();
}

input.addEventListener("keydown", (e) => {
    if (cmdDropdownVisible) {
        if (e.key === "ArrowDown") { e.preventDefault(); cmdNav(1); return; }
        if (e.key === "ArrowUp") { e.preventDefault(); cmdNav(-1); return; }
        if (e.key === "Enter" || e.key === "Tab") {
            e.preventDefault();
            cmdSelect();
            return;
        }
        if (e.key === "Escape") { cmdHide(); return; }
    }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
input.addEventListener("input", () => {
    autoResize();
    sendBtn.disabled = !input.value.trim();
    cmdCheck();
});

// ─── Command Dropdown ──────────────────────────────────────────────────────
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
    // Show dropdown only when input starts with "/" and is at the beginning
    if (val.startsWith("/") && val.length < 20) {
        const query = val.toLowerCase();
        cmdFiltered = COMMANDS.filter(c => c.cmd.startsWith(query));
        if (cmdFiltered.length > 0 && val.length > 0) {
            cmdActiveIdx = 0;
            cmdRender();
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
        </div>
    `).join("");
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
    const cmd = cmdFiltered[cmdActiveIdx].cmd;
    input.value = cmd + " ";
    cmdHide();
    input.focus();
    autoResize();
    sendBtn.disabled = false;
}

function cmdClick(idx) {
    cmdActiveIdx = idx;
    cmdSelect();
}

function cmdHide() {
    const dropdown = document.getElementById("cmd-dropdown");
    if (dropdown) dropdown.classList.add("hidden");
    cmdDropdownVisible = false;
    cmdFiltered = [];
}

// Hide dropdown when clicking outside
document.addEventListener("click", (e) => {
    if (cmdDropdownVisible && !e.target.closest("#input-area")) cmdHide();
});

function autoResize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 200) + "px";
}

function toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebar-overlay");
    sidebar.classList.toggle("hidden");
    overlay.classList.toggle("active");
}

// ─── Keyboard Shortcuts ─────────────────────────────────────────────────────
document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.key === "l") { e.preventDefault(); newChat(); }
    if (e.ctrlKey && e.key === "m") { e.preventDefault(); runCmd("/model"); }
    if (e.ctrlKey && e.key === "k") { e.preventDefault(); toggleSidebar(); }
    if (e.key === "Escape") {
        document.querySelectorAll(".modal:not(.hidden)").forEach(m => m.classList.add("hidden"));
        closeSidebar();
    }
    if (e.key === "/" && document.activeElement !== input) { e.preventDefault(); input.focus(); }
});

// ─── Theme ───────────────────────────────────────────────────────────────────
function toggleTheme() {
    const html = document.documentElement;
    const next = html.getAttribute("data-theme") === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", next);
    localStorage.setItem("keyzbot-theme", next);
    const icon = document.getElementById("theme-icon");
    if (icon) {
        icon.outerHTML = next === "dark"
            ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" id="theme-icon"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>'
            : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" id="theme-icon"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
    }
}
(function() {
    const saved = localStorage.getItem("keyzbot-theme");
    if (saved) {
        document.documentElement.setAttribute("data-theme", saved);
    }
})();

// ─── File Upload ─────────────────────────────────────────────────────────────
const IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"];
const IMG_MAX = 1024; // max width/height for compression
let pendingImages = []; // {filename, b64, mime, dataUrl}

function compressImage(file, callback) {
    const img = new Image();
    const reader = new FileReader();
    reader.onload = () => {
        img.onload = () => {
            let w = img.width, h = img.height;
            if (w > IMG_MAX || h > IMG_MAX) {
                const ratio = Math.min(IMG_MAX / w, IMG_MAX / h);
                w = Math.round(w * ratio);
                h = Math.round(h * ratio);
            }
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
            compressImage(file, (img) => {
                pendingImages.push(img);
                renderImagePreviews();
            });
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
        const container = document.querySelector(".input-container");
        container.parentNode.insertBefore(bar, container);
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

function removePendingImage(idx) {
    pendingImages.splice(idx, 1);
    renderImagePreviews();
}

container.addEventListener("dragover", (e) => { e.preventDefault(); });
container.addEventListener("drop", (e) => {
    e.preventDefault();
    Array.from(e.dataTransfer.files).forEach(file => {
        const ext = "." + file.name.split(".").pop().toLowerCase();
        if (IMAGE_EXTS.includes(ext)) {
            compressImage(file, (img) => {
                pendingImages.push(img);
                renderImagePreviews();
            });
        } else {
            const reader = new FileReader();
            reader.onload = () => {
                socket.emit("file_upload", { filename: file.name, data: reader.result.split(",")[1] });
                addCommandResult(`Uploading: **${file.name}**...`);
                scrollBottom();
            };
            reader.readAsDataURL(file);
        }
    });
});

// ─── Export ──────────────────────────────────────────────────────────────────
function exportChat(format) {
    window.open(`/api/export/${format}?sid=${BROWSER_ID}`, "_blank");
    closeModal("export-modal");
}

// ─── Modals ──────────────────────────────────────────────────────────────────
function openModal(id) { document.getElementById(id).classList.remove("hidden"); }
function closeModal(id) { document.getElementById(id).classList.add("hidden"); }

// ─── Message Builders ────────────────────────────────────────────────────────
function hideWelcome() { if (welcomeEl) welcomeEl.style.display = "none"; }
function showWelcome() { if (welcomeEl) welcomeEl.style.display = "flex"; }
function clearMessages() {
    messagesEl.querySelectorAll(".msg-row, .tool-accordion, .msg-ephemeral").forEach(r => r.remove());
}

function clearChatUI() {
    const rows = messagesEl.querySelectorAll(".msg-row, .tool-accordion, .msg-ephemeral");
    if (rows.length === 0) { showWelcome(); return; }
    // Fade out all messages
    rows.forEach(function(row, i) {
        row.style.transition = "opacity .25s ease " + (i * 0.03) + "s, transform .25s ease " + (i * 0.03) + "s";
        row.style.opacity = "0";
        row.style.transform = "translateY(-6px)";
    });
    // Remove after animation completes — preserve welcome element
    var totalDelay = rows.length * 30 + 250;
    setTimeout(function() {
        rows.forEach(function(row) { row.remove(); });
        showWelcome();
    }, totalDelay);
}

function addUserMessage(text, images) {
    const row = document.createElement("div");
    row.className = "msg-row user";
    let imgHtml = "";
    if (images && images.length > 0) {
        imgHtml = '<div class="msg-images">' + images.map(src =>
            `<img src="${src}" class="msg-image-thumb" onclick="window.open('${src}','_blank')">`
        ).join("") + '</div>';
    }
    row.innerHTML = `<div class="msg-bubble"><div class="msg-content">${imgHtml}${esc(text)}</div></div><div class="msg-avatar" style="background:var(--accent2)">U</div>`;
    messagesEl.appendChild(row);
}

function createBotMessage() {
    const row = document.createElement("div");
    row.className = "msg-row bot";
    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = "K";
    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    const content = document.createElement("div");
    content.className = "msg-content";
    bubble.appendChild(content);
    row.appendChild(avatar);
    row.appendChild(bubble);
    return { row, contentEl: content, cursor: null };
}

function addBotMessage(text) {
    const row = document.createElement("div");
    row.className = "msg-row bot";
    row.innerHTML = `<div class="msg-avatar">K</div><div class="msg-bubble"><div class="msg-content">${renderMarkdown(text)}</div></div>`;
    messagesEl.appendChild(row);
    highlightCode(row);
    addCopyButtons(row);
    checkTableScroll(row);
}

function addCommandResult(text) {
    const row = document.createElement("div");
    row.className = "msg-row bot";
    row.innerHTML = `<div class="msg-avatar">K</div><div class="msg-bubble"><div class="msg-content cmd-result">${renderMarkdown(text)}</div></div>`;
    messagesEl.appendChild(row);
    highlightCode(row);
    addCopyButtons(row);
    checkTableScroll(row);
}

function addEphemeralMessage(text, duration) {
    if (typeof duration === "undefined") duration = 60000;
    const row = document.createElement("div");
    row.className = "msg-row bot msg-ephemeral";
    row.innerHTML = `<div class="msg-avatar">K</div><div class="msg-bubble"><div class="msg-content cmd-result">${renderMarkdown(text)}</div><div class="ephemeral-bar"></div><button class="ephemeral-close" onclick="dismissEphemeral(this)">&times;</button></div>`;
    messagesEl.appendChild(row);
    highlightCode(row);
    addCopyButtons(row);
    checkTableScroll(row);
    scrollBottom();
    // Auto-dismiss after duration
    row._dismissTimer = setTimeout(function() { dismissEphemeral(row); }, duration);
}

function dismissEphemeral(el) {
    var row = el.closest ? el.closest(".msg-ephemeral") : el;
    if (!row || row.classList.contains("removing")) return;
    if (row._dismissTimer) clearTimeout(row._dismissTimer);
    row.classList.add("removing");
    setTimeout(function() {
        row.remove();
        // If chat is now empty, show welcome
        if (messagesEl.querySelectorAll(".msg-row, .tool-accordion").length === 0) {
            showWelcome();
        }
    }, 300);
}

function addError(text) {
    const row = document.createElement("div");
    row.className = "msg-row bot";
    row.innerHTML = `<div class="msg-avatar">K</div><div class="msg-bubble"><div class="msg-error">Error: ${esc(text)}</div></div>`;
    messagesEl.appendChild(row);
}

let lastToolCall = null;
let toolCallDone = false;
let toolCallEl = null;
function addToolCall(name, args) {
    // If previous tool is done, reuse the same element
    if (toolCallEl && toolCallDone) {
        const id = toolCallEl.id;
        const argsStr = esc(args || "");
        const argsPreview = argsStr.length > 60 ? argsStr.substring(0, 60) + "..." : argsStr;
        // Update header
        const header = toolCallEl.querySelector(".tool-accordion-header");
        if (header) {
            header.querySelector(".tool-name").textContent = name;
            header.querySelector(".tool-args").textContent = argsPreview;
        }
        // Reset body
        const body = document.getElementById(id + "-result");
        if (body) body.innerHTML = "<pre>Loading...</pre>";
        // Remove done class
        toolCallEl.classList.remove("done");
        toolCallDone = false;
        lastToolCall = id;
        scrollBottom();
        return;
    }
    // Create new element
    const id = "tc-" + Date.now();
    const el = document.createElement("div");
    el.className = "tool-accordion";
    el.id = id;
    const argsStr = esc(args || "");
    const argsPreview = argsStr.length > 60 ? argsStr.substring(0, 60) + "..." : argsStr;
    el.innerHTML = `
        <div class="tool-accordion-header" onclick="toggleTool('${id}')">
            <div class="tool-icon">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
            </div>
            <span class="tool-name">${esc(name)}</span>
            <span class="tool-args">${argsPreview}</span>
            <svg class="tool-toggle" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
        </div>
        <div class="tool-accordion-body" id="${id}-result"><pre>Loading...</pre></div>`;
    messagesEl.appendChild(el);
    toolCallEl = el;
    toolCallDone = false;
    lastToolCall = id;
}

function addToolResult(name, result) {
    const id = lastToolCall;
    if (!id) return;
    const resultEl = document.getElementById(id + "-result");
    if (!resultEl) return;
    // Render diff if present
    if (result.includes('--- a/') && result.includes('+++ b/') && result.includes('@@')) {
        resultEl.innerHTML = renderDiff(result);
    } else {
        resultEl.innerHTML = `<pre>${esc(result)}</pre>`;
    }
    // Mark as done so next tool call can reuse this element
    toolCallDone = true;
    if (toolCallEl) toolCallEl.classList.add("done");
}

function addToolResultDirect(text) {
    addToolCall("tool", "");
    const id = lastToolCall;
    if (!id) return;
    const resultEl = document.getElementById(id + "-result");
    if (!resultEl) return;
    if (text.includes('--- a/') && text.includes('+++ b/') && text.includes('@@')) {
        resultEl.innerHTML = renderDiff(text);
    } else {
        resultEl.innerHTML = `<pre>${esc(text)}</pre>`;
    }
}

function toggleTool(id) {
    const el = document.getElementById(id);
    if (el) el.classList.toggle("open");
}

// ─── Thinking ────────────────────────────────────────────────────────────────
let thinkingEl = null;
function addThinking() {
    if (thinkingEl) return;
    thinkingEl = document.createElement("div");
    thinkingEl.className = "msg-row bot";
    thinkingEl.innerHTML = `<div class="msg-avatar">K</div><div class="msg-bubble"><div class="thinking"><div class="thinking-dots"><span></span><span></span><span></span></div><span>Thinking...</span></div></div>`;
    messagesEl.appendChild(thinkingEl);
    scrollBottom();
}
function removeThinking() { if (thinkingEl) { thinkingEl.remove(); thinkingEl = null; } }

// ─── Helpers ─────────────────────────────────────────────────────────────────
let _userScrolledUp = false;

function scrollBottom(force) {
    requestAnimationFrame(() => {
        // Don't auto-scroll if user is reading up (unless forced)
        if (!force && _userScrolledUp) {
            _updateScrollBtn();
            return;
        }
        container.scrollTop = container.scrollHeight;
        _updateScrollBtn();
    });
}
function esc(str) { const d = document.createElement("div"); d.textContent = str || ""; return d.innerHTML; }

// ─── Scroll-to-bottom button ────────────────────────────────────────────────
(function initScrollBtn() {
    const btn = document.getElementById('scroll-bottom-btn');
    if (!btn || !container) return;
    let _prevScrollTop = container.scrollTop;

    function _atBottom() {
        return container.scrollHeight - container.scrollTop - container.clientHeight < 80;
    }

    window._updateScrollBtn = function() {
        if (_atBottom()) {
            btn.classList.remove('visible');
            _userScrolledUp = false;
        } else if (container.scrollHeight > container.clientHeight + 100) {
            btn.classList.add('visible');
        }
    };

    container.addEventListener('scroll', function() {
        const atBottom = _atBottom();
        if (atBottom) {
            _userScrolledUp = false;
            btn.classList.remove('visible');
        } else {
            // Only mark as "user scrolled up" if scroll moved upward
            if (container.scrollTop < _prevScrollTop - 5) {
                _userScrolledUp = true;
            }
            if (container.scrollHeight > container.clientHeight + 100) {
                btn.classList.add('visible');
            }
        }
        _prevScrollTop = container.scrollTop;
    }, {passive: true});
})();

// ─── Mobile keyboard viewport fix ───────────────────────────────────────────
(function initKeyboardFix() {
    const inputArea = document.getElementById('input-area');
    if (!inputArea) return;
    const vv = window.visualViewport;
    if (!vv) return;
    function fixLayout() {
        const h = vv.height;
        document.getElementById('app').style.height = h + 'px';
        if (!_userScrolledUp) scrollBottom(true);
    }
    vv.addEventListener('resize', fixLayout);
    vv.addEventListener('scroll', fixLayout);
})();

function renderMarkdown(text) {
    if (!text) return "";
    // Check for diff content first
    if (text.includes('--- a/') && text.includes('+++ b/') && text.includes('@@')) {
        const diffMatch = text.match(/([\s\S]*?)(--- a\/[\s\S]+)$/);
        if (diffMatch) {
            const prefix = diffMatch[1];
            const diffPart = diffMatch[2];
            let html = '';
            if (prefix.trim()) html += '<p>' + esc(prefix.trim()) + '</p>';
            html += renderDiff(diffPart);
            return html;
        }
    }

    // Step 1: Extract code blocks to protect them from processing
    const codeBlocks = [];
    let processed = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
        const idx = codeBlocks.length;
        codeBlocks.push({ lang: lang || 'text', code: code.replace(/\n$/, '') });
        return '\x00CODEBLOCK' + idx + '\x00';
    });
    // Also handle ``` without language tag
    processed = processed.replace(/```([\s\S]*?)```/g, (_, code) => {
        const idx = codeBlocks.length;
        codeBlocks.push({ lang: 'text', code: code.replace(/\n$/, '') });
        return '\x00CODEBLOCK' + idx + '\x00';
    });

    // Step 1b: Extract box-drawing art (┌┐└┘│─├┤┬┴┼) — render as styled pre
    const boxBlocks = [];
    processed = processed.replace(/(^(?:.*[┌┐└┘│─├┤┬┴┼].*$\n?)+)/gm, (match) => {
        const idx = boxBlocks.length;
        boxBlocks.push(match.replace(/\n$/, ''));
        return '\x00BOXBLOCK' + idx + '\x00';
    });

    // Step 2: Escape HTML (but our placeholders are safe)
    processed = esc(processed);

    // Step 3: Restore code blocks as <pre><code>
    processed = processed.replace(/\x00CODEBLOCK(\d+)\x00/g, (_, idx) => {
        const b = codeBlocks[parseInt(idx)];
        return `<pre><code class="language-${b.lang}">${esc(b.code)}</code></pre>`;
    });

    // Step 3b: Restore box-drawing blocks
    processed = processed.replace(/\x00BOXBLOCK(\d+)\x00/g, (_, idx) => {
        const content = boxBlocks[parseInt(idx)];
        return '<div class="ascii-box"><pre>' + esc(content) + '</pre></div>';
    });

    // Step 4: Inline code (single backtick)
    processed = processed.replace(/`([^`\n]+)`/g, '<code>$1</code>');

    // Step 5: Block elements — headers, blockquote, hr
    processed = processed.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    processed = processed.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    processed = processed.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    processed = processed.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');
    processed = processed.replace(/^---+$/gm, '<hr>');

    // Step 6: Bold and italic
    processed = processed.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    processed = processed.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');

    // Step 7: Links
    processed = processed.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

    // Step 8: Tables — parse markdown tables
    processed = processed.replace(/(^\|.+\|$\n?)+/gm, (match) => {
        const lines = match.trim().split('\n').filter(l => l.trim());
        if (lines.length < 2) return match;
        // Check for separator row (|---|---|)
        const sepIdx = lines.findIndex(l => /^\|[\s\-:|]+\|$/.test(l.trim()));
        if (sepIdx < 1) return match;
        const headerLines = lines.slice(0, sepIdx);
        const bodyLines = lines.slice(sepIdx + 1);
        const parseRow = (line) => {
            return line.split('|').slice(1, -1).map(cell => cell.trim());
        };
        let html = '<div class="table-wrap"><table>';
        html += '<thead>';
        headerLines.forEach(hl => {
            const cells = parseRow(hl);
            html += '<tr>' + cells.map(c => '<th>' + c + '</th>').join('') + '</tr>';
        });
        html += '</thead>';
        if (bodyLines.length > 0) {
            html += '<tbody>';
            bodyLines.forEach(bl => {
                const cells = parseRow(bl);
                html += '<tr>' + cells.map(c => '<td>' + c + '</td>').join('') + '</tr>';
            });
            html += '</tbody>';
        }
        html += '</table></div>';
        return html;
    });

    // Step 9: Lists — collect consecutive li lines into <ul>/<ol>
    processed = processed.replace(/(^- .+$\n?)+/gm, (match) => {
        const items = match.trim().split('\n').map(line => {
            return '<li>' + line.replace(/^- /, '') + '</li>';
        }).join('');
        return '<ul>' + items + '</ul>';
    });
    processed = processed.replace(/(^\d+\. .+$\n?)+/gm, (match) => {
        const items = match.trim().split('\n').map(line => {
            return '<li>' + line.replace(/^\d+\. /, '') + '</li>';
        }).join('');
        return '<ol>' + items + '</ol>';
    });

    // Step 9: Clean up consecutive blockquotes
    processed = processed.replace(/<\/blockquote>\s*<blockquote>/g, '<br>');

    // Step 10: Paragraph splitting — split on double newlines
    const blocks = processed.split(/\n{2,}/);
    const finalParts = [];
    for (const block of blocks) {
        const trimmed = block.trim();
        if (!trimmed) continue;
        // Don't wrap block elements in <p>
        if (/^<(h[1-3]|pre|ul|ol|blockquote|hr|div)/.test(trimmed)) {
            finalParts.push(trimmed);
        } else {
            // Single newlines within a paragraph become <br>
            finalParts.push('<p>' + trimmed.replace(/\n/g, '<br>') + '</p>');
        }
    }
    let html = finalParts.join('');

    // Step 11: Clean empty paragraphs
    html = html.replace(/<p>\s*<\/p>/g, '');

    return html;
}

function renderDiff(text) {
    // Detect unified diff pattern: --- a/... \n+++ b/... \n@@ ... @@ \n
    if (!text.includes('--- a/') || !text.includes('+++ b/')) return text;
    const lines = text.split('\n');
    const blocks = [];
    let current = null;
    for (const line of lines) {
        if (line.startsWith('--- ') && lines[lines.indexOf(line) + 1]?.startsWith('+++ ')) {
            if (current) blocks.push(current);
            current = { header: line + '\n' + lines[lines.indexOf(line) + 1], hunks: [], currentHunk: null };
            continue;
        }
        if (!current) continue;
        if (line.startsWith('@@')) {
            if (current.currentHunk) current.hunks.push(current.currentHunk);
            current.currentHunk = { header: line, lines: [] };
        } else if (current.currentHunk && (line.startsWith('+') || line.startsWith('-') || line.startsWith(' ') || line === '')) {
            current.currentHunk.lines.push(line);
        }
    }
    if (current?.currentHunk) current.hunks.push(current.currentHunk);
    if (!current || current.hunks.length === 0) return text;

    let html = '<div class="diff-block">';
    html += `<div class="diff-header">${esc(current.header)}</div>`;
    for (const hunk of current.hunks) {
        html += `<div class="diff-line diff-hunk">${esc(hunk.header)}</div>`;
        for (const l of hunk.lines) {
            if (l.startsWith('+')) html += `<div class="diff-line diff-add">${esc(l)}</div>`;
            else if (l.startsWith('-')) html += `<div class="diff-line diff-del">${esc(l)}</div>`;
            else html += `<div class="diff-line diff-ctx">${esc(l)}</div>`;
        }
    }
    html += '</div>';
    return html;
}

function highlightCode(el) {
    if (typeof Prism !== "undefined") {
        el.querySelectorAll('pre code').forEach(block => Prism.highlightElement(block));
    }
}

function addCopyButtons(el) {
    el.querySelectorAll('pre').forEach(pre => {
        if (pre.querySelector('.copy-btn')) return;
        const btn = document.createElement('button');
        btn.className = 'copy-btn';
        btn.textContent = 'Copy';
        btn.onclick = () => {
            const code = pre.querySelector('code');
            navigator.clipboard.writeText(code ? code.textContent : pre.textContent);
            btn.textContent = 'Copied!';
            setTimeout(() => btn.textContent = 'Copy', 2000);
        };
        pre.style.position = 'relative';
        pre.appendChild(btn);
    });
}

function checkTableScroll(el) {
    el.querySelectorAll('.table-wrap').forEach(wrap => {
        if (wrap.scrollWidth > wrap.clientWidth) {
            wrap.classList.add('scrolling');
        } else {
            wrap.classList.remove('scrolling');
        }
    });
}

function updateTopbarTags(cfg) {
    const modelTag = document.getElementById("topbar-model");
    const permTag = document.getElementById("topbar-perm");
    if (cfg.model) { modelTag.textContent = cfg.model; modelTag.style.display = ""; }
    else { modelTag.style.display = "none"; }
    if (cfg.perm_mode) { permTag.textContent = cfg.perm_mode; permTag.style.display = ""; }
    else { permTag.style.display = "none"; }
    document.getElementById("sidebar-model").textContent = "Model: " + (cfg.model || "-");
}

function fetchConfig() {
    fetch("/api/config")
        .then(r => r.json())
        .then(cfg => updateTopbarTags(cfg))
        .catch(() => {});
}

window.addEventListener("load", () => input.focus());

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
        </div>
    `;
    document.body.appendChild(menu);
}
_createHamburgerMenu();

function toggleHamburger() {
    const menu = document.getElementById("hamburger-menu");
    if (!menu) return;
    const isOpen = !menu.classList.contains("hidden");
    if (isOpen) {
        closeHamburger();
    } else {
        menu.classList.remove("hidden");
        updateHamburgerInfo();
        setTimeout(() => document.addEventListener("click", closeHamburgerOutside), 100);
    }
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

function updateHamburgerInfo() {
    socket.emit("get_providers");
}

// ─── Provider Config (Professional UI) ───────────────────────────────────────
let providersData = {providers: [], active: "", presets: []};

socket.on("providers_data", (data) => {
    providersData = data;
    const activeP = data.providers.find(p => p.id === data.active) ||
                    data.presets.find(p => p.id === data.active);
    if (activeP) {
        document.getElementById("menu-provider-name").textContent = activeP.name || activeP.id;
        document.getElementById("menu-provider-model").textContent = activeP.model || activeP.default_model || "";
    }
    renderProviderGrid();
    updateActiveBanner();
});

socket.on("provider_switched", (data) => {
    updateTopbarTags({ model: data.model, perm_mode: document.getElementById("topbar-perm").textContent || "" });
    statusBar.textContent = `Switched to ${data.provider_id}`;
    socket.emit("get_providers");
});

socket.on("provider_saved", (data) => {
    statusBar.textContent = `Provider ${data.provider_id} saved`;
    socket.emit("get_providers");
});

socket.on("provider_added", (data) => {
    statusBar.textContent = `Added provider: ${data.provider.name}`;
    socket.emit("get_providers");
});

socket.on("provider_removed", (data) => {
    statusBar.textContent = `Removed provider: ${data.provider_id}`;
    socket.emit("get_providers");
});

socket.on("provider_test_result", (data) => {
    // Show test result
    const resultEl = document.querySelector('.pcard-test-result.show');
    if (resultEl) {
        resultEl.className = 'pcard-test-result show ' + (data.success ? 'success' : 'error');
        resultEl.innerHTML = data.success
            ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> ' + data.message
            : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg> ' + data.error;
        setTimeout(() => resultEl.classList.remove('show'), 5000);
    }
});

socket.on("provider_error", (data) => {
    statusBar.textContent = `Error: ${data.error}`;
});

function openProviderModal() {
    closeHamburger();
    socket.emit("get_providers");
    document.getElementById("provider-modal").classList.remove("hidden");
}

function updateActiveBanner() {
    const {providers, active, presets} = providersData;
    const activeP = providers.find(p => p.id === active) || presets.find(p => p.id === active);
    if (!activeP) return;
    document.getElementById("pmodal-active-name").textContent = activeP.name || activeP.id;
    document.getElementById("pmodal-active-model").textContent = activeP.model || activeP.default_model || '';
}

function renderProviderGrid() {
    const grid = document.getElementById("provider-grid");
    if (!grid) return;
    const {providers, active, presets} = providersData;

    const allProviders = [];
    const presetIds = presets.map(p => p.id);
    for (const preset of presets) {
        const saved = providers.find(p => p.id === preset.id);
        allProviders.push({
            ...preset, api_key: saved?.api_key || "",
            base_url: saved?.base_url || preset.base_url,
            model: saved?.model || preset.default_model, custom: false,
        });
    }
    for (const p of providers) {
        if (!presetIds.includes(p.id)) allProviders.push({...p, custom: true});
    }

    grid.innerHTML = allProviders.map(p => {
        const isActive = p.id === active;
        const hasKey = !!p.api_key;
        const icon = getProviderIcon(p.id, p.color);
        const freeBadge = p.free ? '<span class="pcard-free">FREE</span>' : '';
        const guideText = p.guide_text ? p.guide_text.replace(/\n/g, '<br>') : '';
        const guideLink = p.guide_url ? `<a href="${p.guide_url}" target="_blank" class="pmodal-btn secondary" style="text-decoration:none;display:inline-flex;align-items:center;gap:4px">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            Get API Key
        </a>` : '';
        return `
        <div class="pcard ${isActive ? 'active' : ''}" data-id="${p.id}" data-name="${(p.name||p.id).toLowerCase()}">
            <div class="pcard-main" onclick="toggleProviderEdit('${p.id}')">
                <div class="pcard-icon">${icon}</div>
                <div class="pcard-info">
                    <div class="pcard-name">${p.name || p.id} ${freeBadge}</div>
                    <div class="pcard-url">${p.model || p.base_url || ''}</div>
                </div>
                <div class="pcard-right">
                    <div class="pcard-badge ${isActive ? 'active' : (hasKey ? 'ready' : 'no-key')}">${isActive ? 'Active' : (hasKey ? 'Ready' : 'No Key')}</div>
                    ${isActive ? '' : `<button class="pcard-btn use" onclick="event.stopPropagation();switchProvider('${p.id}')">Use</button>`}
                    ${p.custom ? `<button class="pcard-btn delete" onclick="event.stopPropagation();removeProvider('${p.id}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    </button>` : ''}
                </div>
            </div>
            <div class="pcard-edit" id="edit-${p.id}">
                ${guideText ? `<div class="pcard-guide">${guideText}</div>` : ''}
                <div class="pcard-edit-grid">
                    <div class="pmodal-field">
                        <label>API Key</label>
                        <div class="pmodal-key-input">
                            <input type="password" id="key-${p.id}" placeholder="${p.free ? 'Optional / paste key here' : 'sk-...'}" value="${p.api_key || ''}">
                            <button class="pmodal-key-toggle" onclick="toggleKeyVisibility(this)">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                            </button>
                        </div>
                    </div>
                    <div class="pmodal-field">
                        <label>Model</label>
                        <select id="model-${p.id}" class="pmodal-select">
                            ${(p.models || []).map(m => `<option value="${m}" ${m === (p.model || p.default_model) ? 'selected' : ''}>${m}</option>`).join('')}
                        </select>
                    </div>
                    <div class="pmodal-field full">
                        <label>Base URL</label>
                        <input type="text" id="url-${p.id}" placeholder="https://api.example.com/v1" value="${p.base_url || ''}">
                    </div>
                </div>
                <div class="pcard-test-result" id="result-${p.id}"></div>
                <div class="pcard-edit-actions">
                    ${guideLink}
                    <div style="flex:1"></div>
                    <button class="pmodal-btn secondary" onclick="testProvider('${p.id}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                        Test
                    </button>
                    ${p.custom ? `<button class="pmodal-btn danger" onclick="removeProvider('${p.id}')">Delete</button>` : ''}
                    <button class="pmodal-btn primary" onclick="saveProvider('${p.id}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                        Save
                    </button>
                </div>
            </div>
        </div>`;
    }).join("");
}

function getProviderIcon(id, color) {
    if (id === 'opengateway') {
        return `<img src="/keyzbot.svg" width="36" height="36" style="border-radius:10px">`;
    }
    const c = color || '#6b7280';
    const letters = id.substring(0, 2).toUpperCase();
    return `<div style="width:36px;height:36px;border-radius:10px;background:${c}20;color:${c};display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;letter-spacing:-0.5px">${letters}</div>`;
}

function toggleProviderEdit(id) {
    const edit = document.getElementById('edit-' + id);
    if (!edit) return;
    const wasOpen = edit.classList.contains('show');
    // Close all
    document.querySelectorAll('.pcard-edit').forEach(e => e.classList.remove('show'));
    if (!wasOpen) edit.classList.add('show');
}

function toggleKeyVisibility(btn) {
    const input = btn.parentElement.querySelector('input');
    input.type = input.type === 'password' ? 'text' : 'password';
}

function filterProviders() {
    const q = document.getElementById('provider-search').value.toLowerCase();
    document.querySelectorAll('.pcard').forEach(card => {
        const name = card.dataset.name || '';
        card.style.display = name.includes(q) ? '' : 'none';
    });
}


function switchProvider(id) {
    socket.emit("switch_provider", {provider_id: id});
}

function saveProvider(id) {
    const key = document.getElementById('key-' + id)?.value || '';
    const url = document.getElementById('url-' + id)?.value || '';
    const model = document.getElementById('model-' + id)?.value || '';
    socket.emit("save_provider", {provider_id: id, api_key: key, base_url: url, model: model});
    socket.emit("switch_provider", {provider_id: id, api_key: key});
}

function testProvider(id) {
    const key = document.getElementById('key-' + id)?.value || '';
    const url = document.getElementById('url-' + id)?.value || '';
    const model = document.getElementById('model-' + id)?.value || '';
    if (!key) {
        const resultEl = document.getElementById('result-' + id);
        if (resultEl) {
            resultEl.className = 'pcard-test-result show error';
            resultEl.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg> Enter API key first';
        }
        return;
    }
    // Show testing state
    const resultEl = document.getElementById('result-' + id);
    if (resultEl) {
        resultEl.className = 'pcard-test-result show';
        resultEl.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><circle cx="12" cy="12" r="10"/></svg> Testing connection...';
    }
    socket.emit("test_provider", {base_url: url, api_key: key, model: model});
}

function removeProvider(id) {
    if (confirm(`Remove provider "${id}"?`)) {
        socket.emit("remove_provider", {provider_id: id});
    }
}

function toggleAddProviderForm() {
    const form = document.getElementById('add-provider-form');
    if (!form) return;
    const btn = document.getElementById('toggle-add-form-btn');
    if (form.style.display === 'none') {
        form.style.display = '';
        if (btn) btn.style.display = 'none';
    } else {
        form.style.display = 'none';
        if (btn) btn.style.display = '';
    }
}

function addCustomProvider() {
    const id = document.getElementById('custom-id').value.trim().toLowerCase().replace(/\s+/g, '-');
    const name = document.getElementById('custom-name').value.trim();
    const url = document.getElementById('custom-url').value.trim();
    const key = document.getElementById('custom-key').value.trim();
    const model = document.getElementById('custom-model').value.trim();
    if (!id || !name || !url || !model) {
        statusBar.textContent = "ID, Name, URL, and Model are required";
        return;
    }
    socket.emit("add_custom_provider", {id, name, base_url: url, api_key: key, model, models: [model]});
    ['custom-id','custom-name','custom-url','custom-key','custom-model'].forEach(x => document.getElementById(x).value = '');
    // Hide form, show button again
    document.getElementById('add-provider-form').style.display = 'none';
    const toggleBtn = document.getElementById('toggle-add-form-btn');
    if (toggleBtn) toggleBtn.style.display = '';
    statusBar.textContent = `Provider "${name}" added`;
}

