/* KEYZBOT Socket Events — all socket.on handlers */
// ─── Socket Events ───────────────────────────────────────────────────────────
socket.on("connected", (data) => {
    statusBar.textContent = "Connected";
    activeChatId = data.active_chat;
    userProfile = data.profile || {};
    updateSidebarUserName();
    renderSessions(data.chats);
    fetchConfig();
    if (data.profile && !data.profile.setup_complete) showSetupModal();
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
    if (data.streaming) showThinking();
    if (data.update_available) showUpdateToast();
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

socket.on("update_available", () => showUpdateToast());
socket.on("update_status", (data) => {
    const status = document.getElementById("update-status");
    const btn = document.getElementById("update-btn");
    status.style.display = "block";
    status.textContent = data.message || "";
    if (data.status === "restarting") { btn.textContent = "Restarting..."; status.textContent = "Server sedang restart..."; }
    else if (data.status === "error") { btn.disabled = false; btn.textContent = "Update Now"; status.style.color = "#ef4444"; }
});

socket.on("status", (s) => {
    updateTopbarTags(s);
    const sessionTag = document.getElementById("topbar-session");
    if (s.messages) { sessionTag.textContent = s.messages + " msgs"; sessionTag.style.display = ""; }
    else { sessionTag.style.display = "none"; }
    const tokenStr = s.tokens ? `${s.tokens} tokens` : "0 tokens";
    const costStr = s.cost ? ` · $${s.cost}` : "";
    document.getElementById("sidebar-tokens").textContent = tokenStr + costStr;
    if (s.tool_count) document.getElementById("tools-count").textContent = s.tool_count + " tools";
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
    isStreaming = false;
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

socket.on("chat_done", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    if (!hadStream && data.text) { removeThinking(); addBotMessage(data.text); }
    isStreaming = false;
    sendBtn.disabled = !input.value.trim();
    scrollBottom();
});

socket.on("chat_error", (data) => {
    if (data.chat_id && data.chat_id !== activeChatId) return;
    removeThinking(); addError(data.error);
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
