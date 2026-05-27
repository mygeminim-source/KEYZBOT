/* KEYZBOT Socket Events — all socket.on handlers */
// Reconnect buffer: chunks arriving before 'connected' are buffered here
let _reconnectBuffer = [];
let _awaitingConnect = false;

socket.io.on("reconnect_attempt", () => { _awaitingConnect = true; _reconnectBuffer = []; });

// ─── Socket Events ───────────────────────────────────────────────────────────
socket.on("connected", (data) => {
    statusBar.textContent = "Connected";
    activeChatId = data.active_chat;
    userProfile = data.profile || {};
    updateSidebarUserName();
    renderSessions(data.chats);
    fetchConfig();
    if (data.profile && !data.profile.setup_complete) showSetupModal();
    // Reset stream state before restoring
    streamEl = null; streamContentEl = null; streamRawText = "";
    isStreaming = false; hadStream = false;
    if (data.messages && data.messages.length > 0) {
        clearMessages(); hideWelcome();
        data.messages.forEach(m => {
            if (m.type === "user") addUserMessage(m.text, m.images);
            else if (m.type === "bot") addBotMessage(m.text);
            else if (m.type === "tool_call") addToolCall(m.name, m.args);
            else if (m.type === "tool_result") addToolResultDirect(m.text);
        });
        scrollBottom();
    }
    if (data.streaming) {
        if (data.stream_text && data.stream_text.length > 0) {
            // Restore partial streaming text from before refresh
            hideWelcome(); removeThinking(); hadStream = true; isStreaming = true;
            streamRawText = data.stream_text;
            const { row, contentEl } = createBotMessage();
            streamEl = row; streamContentEl = contentEl;
            messagesEl.appendChild(row);
            contentEl.innerHTML = renderMarkdown(streamRawText) + '<span class="cursor"></span>';
            highlightCode(contentEl); checkTableScroll(contentEl);
            scrollBottom();
        } else {
            addThinking();
        }
    } else if (data.stream_done && data.stream_text && data.stream_text.length > 0) {
        // Stream finished while we were disconnected — render the final text
        hideWelcome(); removeThinking();
        addBotMessage(data.stream_text);
        scrollBottom();
    }
    // Flush buffered chunks that arrived during reconnect
    _awaitingConnect = false;
    if (_reconnectBuffer.length > 0 && streamContentEl) {
        _reconnectBuffer.forEach(chunk => {
            streamRawText = (streamRawText || "") + chunk;
        });
        streamContentEl.innerHTML = renderMarkdown(streamRawText) + '<span class="cursor"></span>';
        highlightCode(streamContentEl); checkTableScroll(streamContentEl);
        scrollBottom();
    }
    _reconnectBuffer = [];
    if (data.version) {
        const verEl = document.getElementById("sidebar-version");
        if (verEl) {
            if (data.update_available) {
                verEl.textContent = "v" + data.version + " (auto-updating...)";
                verEl.style.color = "var(--accent)";
                verEl.style.opacity = "1";
            } else {
                verEl.textContent = "v" + data.version;
            }
        }
    }
    if (data.update_available) {
        const toast = document.getElementById("update-toast");
        const btn = document.getElementById("update-btn");
        const status = document.getElementById("update-status");
        if (toast) toast.style.display = "block";
        if (btn) btn.style.display = "none";
        if (status) { status.style.display = "block"; status.textContent = "Auto-updating..."; status.style.color = "var(--accent)"; }
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
    // Auto-update is now server-side — just show status to user
    const toast = document.getElementById("update-toast");
    const btn = document.getElementById("update-btn");
    const status = document.getElementById("update-status");
    if (toast) toast.style.display = "block";
    if (btn) { btn.style.display = "none"; }
    if (status) { status.style.display = "block"; status.textContent = "Auto-updating in 30s..."; status.style.color = "var(--accent)"; }
});
socket.on("update_status", (data) => {
    const status = document.getElementById("update-status");
    const btn = document.getElementById("update-btn");
    if (status) { status.style.display = "block"; status.textContent = data.message || ""; status.style.color = "var(--accent)"; }
    if (btn) btn.style.display = "none";
    if (data.status === "restarting") {
        if (status) status.textContent = "Server sedang restart...";
        // Auto-reload after 3 seconds
        setTimeout(() => location.reload(), 3000);
    }
    else if (data.status === "error") {
        if (status) { status.textContent = "Update failed: " + (data.message || "unknown"); status.style.color = "#ef4444"; }
    }
});

socket.on("status", (s) => {
    updateTopbarTags(s);
    const sessionTag = document.getElementById("topbar-session");
    if (s.messages) { countUp(sessionTag, s.messages, 600, " msgs"); sessionTag.style.display = ""; }
    else { sessionTag.style.display = "none"; }
    const tokenStr = s.tokens ? `${s.tokens} tokens` : "0 tokens";
    const costStr = s.cost ? ` · $${s.cost}` : "";
    document.getElementById("sidebar-tokens").textContent = tokenStr + costStr;
    if (s.tool_count) countUp(document.getElementById("tools-count"), s.tool_count, 800, " tools");
    const wd = s.work_dir || "";
    const shortPath = wd ? wd.split('/').slice(-2).join('/') : "Ready";
    const statusToken = s.tokens ? ` · ${s.tokens}t` : "";
    const statusCost = s.cost ? ` · $${s.cost}` : "";
    statusBar.textContent = shortPath + statusToken + statusCost;
});

socket.on("chats_updated", (data) => renderSessions(data.chats));

socket.on("chat_switched", (data) => {
    activeChatId = data.active_chat;
    streamEl = null; streamContentEl = null; streamRawText = "";
    hadStream = false; isStreaming = false;
    renderSessions(data.chats);
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
                } else { addToolResultDirect(m.text); }
            }
        });
    } else { showWelcome(); }
    scrollBottom();
});

socket.on("chat_deleted", (data) => {
    activeChatId = data.active_chat;
    renderSessions(data.chats);
    clearMessages();
    if (data.cleared) showWelcome();
    else if (data.messages && data.messages.length > 0) {
        hideWelcome();
        data.messages.forEach(m => {
            if (m.type === "user") addUserMessage(m.text, m.images);
            else if (m.type === "bot") addBotMessage(m.text);
            else if (m.type === "tool_call") addToolCall(m.name, m.args);
            else if (m.type === "tool_result") addToolResultDirect(m.text);
        });
        scrollBottom();
    } else { showWelcome(); }
});

socket.on("command_result", (data) => {
    removeThinking();
    if (data.command && (data.command === "/clear" || data.command.startsWith("/clear ") || data.command === "/reset")) {
        clearChatUI(); return;
    }
    hideWelcome();
    addCommandResult(data.text);
    scrollBottom();
});

socket.on("ephemeral_result", (data) => {
    hideWelcome(); removeThinking();
    addEphemeralMessage(data.text, 60000);
});

socket.on("thinking", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    if (data.active) addThinking();
});

socket.on("chat_start", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    hideWelcome(); removeThinking();
    hadStream = false; isStreaming = true;
    addUserMessage(data.user, data.images);
    scrollBottom();
});

socket.on("bot_stream_start", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    removeThinking(); hadStream = true; isStreaming = true; streamRawText = "";
    lastToolCall = null; toolCallDone = false; toolCallEl = null;
    const { row, contentEl } = createBotMessage();
    streamEl = row; streamContentEl = contentEl;
    messagesEl.appendChild(row);
    scrollBottom();
});

socket.on("bot_stream_chunk", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    // Buffer chunks during reconnect (before 'connected' event arrives)
    if (_awaitingConnect) {
        _reconnectBuffer.push(data.text);
        return;
    }
    if (!streamContentEl) {
        removeThinking(); hadStream = true; isStreaming = true; streamRawText = "";
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
    // Don't reset isStreaming here — tool calls may follow before next round.
    // isStreaming resets on chat_done or chat_error only.
    scrollBottom();
});

socket.on("tool_call", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    removeThinking(); addToolCall(data.name, data.args); scrollBottom();
});

socket.on("tool_result", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    addToolResult(data.name, data.result); scrollBottom();
});

// ─── Media Result ─────────────────────────────────────────────────────────
socket.on("media_result", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    const m = data.media;
    const row = document.createElement("div");
    row.className = "msg-row bot media-msg";
    let inner = "";
    if (m.type === "audio") {
        inner = '<div class="media-player audio-player">' +
            '<div class="media-label">Audio</div>' +
            '<audio controls preload="metadata" src="' + m.url + '"></audio>' +
            '<a class="media-download" href="' + m.url + '" download="' + m.filename + '">Download</a>' +
        '</div>';
    } else if (m.type === "image") {
        inner = '<div class="media-player image-player">' +
            '<img src="' + m.url + '" alt="' + (m.prompt || m.kind || 'image') + '" loading="lazy" onclick="window.open(\'' + m.url + '\',\'_blank\')">' +
            '<a class="media-download" href="' + m.url + '" download="' + m.filename + '">Download</a>' +
        '</div>';
    } else if (m.type === "video" || m.type === "gif") {
        var tag = m.type === "gif" ? "img" : "video";
        var attrs = m.type === "gif" ? 'src="' + m.url + '"' : 'controls preload="metadata" src="' + m.url + '"';
        inner = '<div class="media-player video-player">' +
            '<div class="media-label">' + m.type.toUpperCase() + (m.resolution ? " " + m.resolution : "") + '</div>' +
            '<' + tag + ' ' + attrs + '></' + tag + '>' +
            '<a class="media-download" href="' + m.url + '" download="' + m.filename + '">Download</a>' +
        '</div>';
    } else if (m.type === "subtitle") {
        inner = '<div class="media-player subtitle-player">' +
            '<div class="media-label">Subtitles (.srt)</div>' +
            '<pre class="media-subtitle-preview">' + esc(m.filename) + '</pre>' +
            '<a class="media-download" href="' + m.url + '" download="' + m.filename + '">Download</a>' +
        '</div>';
    }
    row.innerHTML = '<div class="msg-avatar">K</div><div class="msg-bubble">' + inner + '</div>';
    messagesEl.appendChild(row);
    scrollBottom();
});

socket.on("chat_done", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    if (!hadStream && data.text) { removeThinking(); addBotMessage(data.text); }
    isStreaming = false;
    hadStream = false;
    streamEl = null; streamContentEl = null; streamRawText = "";
    sendBtn.disabled = !input.value.trim();
    scrollBottom();
});

socket.on("chat_error", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    removeThinking(); addError(data.error);
    isStreaming = false;
    hadStream = false;
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

// ─── Provider Events ────────────────────────────────────────────────────────
socket.on("providers_data", (data) => {
    providersData = data;
    const activeP = data.providers.find(p => p.id === data.active) || data.presets.find(p => p.id === data.active);
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
socket.on("provider_saved", (data) => { statusBar.textContent = `Provider ${data.provider_id} saved`; socket.emit("get_providers"); });
socket.on("provider_added", (data) => { statusBar.textContent = `Added provider: ${data.provider.name}`; socket.emit("get_providers"); });
socket.on("provider_removed", (data) => { statusBar.textContent = `Removed provider: ${data.provider_id}`; socket.emit("get_providers"); });
socket.on("provider_test_result", (data) => {
    const resultEl = document.querySelector('.pcard-test-result.show');
    if (resultEl) {
        resultEl.className = 'pcard-test-result show ' + (data.success ? 'success' : 'error');
        resultEl.innerHTML = data.success
            ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> ' + data.message
            : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg> ' + data.error;
        setTimeout(() => resultEl.classList.remove('show'), 5000);
    }
});
socket.on("provider_error", (data) => { statusBar.textContent = `Error: ${data.error}`; });
