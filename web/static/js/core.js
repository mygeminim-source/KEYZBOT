/* KEYZBOT Core — Browser ID, socket, DOM refs, shared state, helpers */
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
let _userScrolledUp = false;
let thinkingEl = null;
let lastToolCall = null;
let toolCallDone = false;
let toolCallEl = null;
let pendingImages = [];
let providersData = {providers: [], active: "", presets: []};

// ─── Helpers ─────────────────────────────────────────────────────────────────
function esc(str) { const d = document.createElement("div"); d.textContent = str || ""; return d.innerHTML; }

function scrollBottom(force) {
    requestAnimationFrame(() => {
        if (!force && _userScrolledUp) { _updateScrollBtn(); return; }
        if (force) _userScrolledUp = false;
        container.scrollTop = container.scrollHeight;
        _updateScrollBtn();
    });
}

// ─── Modals ──────────────────────────────────────────────────────────────────
function openModal(id) { document.getElementById(id).classList.remove("hidden"); }
function closeModal(id) { document.getElementById(id).classList.add("hidden"); }

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
    if (saved) document.documentElement.setAttribute("data-theme", saved);
})();

// ─── Scroll-to-bottom button ────────────────────────────────────────────────
(function initScrollBtn() {
    const btn = document.getElementById('scroll-bottom-btn');
    if (!btn || !container) return;
    let _prevScrollTop = container.scrollTop;
    function _atBottom() {
        return container.scrollHeight - container.scrollTop - container.clientHeight < 80;
    }
    window._updateScrollBtn = function() {
        if (_atBottom()) { btn.classList.remove('visible'); _userScrolledUp = false; }
        else if (container.scrollHeight > container.clientHeight + 100) { btn.classList.add('visible'); }
    };
    container.addEventListener('scroll', function() {
        const atBottom = _atBottom();
        if (atBottom) { _userScrolledUp = false; btn.classList.remove('visible'); }
        else {
            if (container.scrollTop < _prevScrollTop - 5) _userScrolledUp = true;
            if (container.scrollHeight > container.clientHeight + 100) btn.classList.add('visible');
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

// ─── Topbar / Config ────────────────────────────────────────────────────────
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
    fetch("/api/config").then(r => r.json()).then(cfg => updateTopbarTags(cfg)).catch(() => {});
}

// ─── Counting Animation ─────────────────────────────────────────────────────
function countUp(el, target, duration, suffix) {
    if (!el) return;
    suffix = suffix || "";
    target = parseInt(target) || 0;
    if (target <= 0) { el.textContent = "0" + suffix; return; }
    const raw = parseInt(el.textContent);
    const start = isNaN(raw) ? 0 : raw;
    if (start === target) { el.textContent = target + suffix; return; }
    const diff = target - start;
    const steps = Math.min(Math.abs(diff), 20);
    const stepTime = Math.max(15, (duration || 600) / steps);
    let step = 0;
    const timer = setInterval(() => {
        step++;
        const progress = step / steps;
        const eased = 1 - Math.pow(1 - progress, 3);
        const val = Math.round(start + diff * eased);
        el.textContent = val + suffix;
        if (step >= steps) {
            el.textContent = target + suffix;
            clearInterval(timer);
        }
    }, stepTime);
}

window.addEventListener("load", () => input.focus());
