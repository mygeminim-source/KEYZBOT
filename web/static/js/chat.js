/* KEYZBOT Chat — Message builders, markdown rendering, tool calls, thinking */
const IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"];
const IMG_MAX = 1024;

// ─── Message Builders ────────────────────────────────────────────────────────
function hideWelcome() { if (welcomeEl) welcomeEl.style.display = "none"; }
function showWelcome() { if (welcomeEl) welcomeEl.style.display = "flex"; }
function clearMessages() {
    messagesEl.querySelectorAll(".msg-row, .tool-accordion, .msg-ephemeral").forEach(r => r.remove());
    _userScrolledUp = false;
    const sbb = document.getElementById('scroll-bottom-btn');
    if (sbb) sbb.classList.remove('visible');
}

function clearChatUI() {
    const rows = messagesEl.querySelectorAll(".msg-row, .tool-accordion, .msg-ephemeral");
    if (rows.length === 0) { showWelcome(); return; }
    _userScrolledUp = false;
    const sbb = document.getElementById('scroll-bottom-btn');
    if (sbb) sbb.classList.remove('visible');
    rows.forEach(function(row, i) {
        row.style.transition = "opacity .25s ease " + (i * 0.03) + "s, transform .25s ease " + (i * 0.03) + "s";
        row.style.opacity = "0";
        row.style.transform = "translateY(-6px)";
    });
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
    row._dismissTimer = setTimeout(function() { dismissEphemeral(row); }, duration);
}

function dismissEphemeral(el) {
    var row = el.closest ? el.closest(".msg-ephemeral") : el;
    if (!row || row.classList.contains("removing")) return;
    if (row._dismissTimer) clearTimeout(row._dismissTimer);
    row.classList.add("removing");
    setTimeout(function() {
        row.remove();
        if (messagesEl.querySelectorAll(".msg-row, .tool-accordion").length === 0) showWelcome();
    }, 300);
}

function addError(text) {
    const row = document.createElement("div");
    row.className = "msg-row bot";
    row.innerHTML = `<div class="msg-avatar">K</div><div class="msg-bubble"><div class="msg-error">Error: ${esc(text)}</div></div>`;
    messagesEl.appendChild(row);
}

// ─── Tool Calls ──────────────────────────────────────────────────────────────
function addToolCall(name, args) {
    if (toolCallEl && toolCallDone) {
        const id = toolCallEl.id;
        const argsStr = esc(args || "");
        const argsPreview = argsStr.length > 60 ? argsStr.substring(0, 60) + "..." : argsStr;
        const header = toolCallEl.querySelector(".tool-accordion-header");
        if (header) {
            header.querySelector(".tool-name").textContent = name;
            header.querySelector(".tool-args").textContent = argsPreview;
        }
        const body = document.getElementById(id + "-result");
        if (body) body.innerHTML = "<pre>Loading...</pre>";
        toolCallEl.classList.remove("done");
        toolCallDone = false;
        lastToolCall = id;
        scrollBottom();
        return;
    }
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
    if (result.includes('--- a/') && result.includes('+++ b/') && result.includes('@@')) {
        resultEl.innerHTML = renderDiff(result);
    } else {
        resultEl.innerHTML = `<pre>${esc(result)}</pre>`;
    }
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
function addThinking() {
    if (thinkingEl) return;
    thinkingEl = document.createElement("div");
    thinkingEl.className = "msg-row bot";
    thinkingEl.innerHTML = `<div class="msg-avatar">K</div><div class="msg-bubble"><div class="thinking"><div class="thinking-dots"><span></span><span></span><span></span></div><span>Thinking...</span></div></div>`;
    messagesEl.appendChild(thinkingEl);
    scrollBottom();
}
function removeThinking() { if (thinkingEl) { thinkingEl.remove(); thinkingEl = null; } }

// ─── Markdown Rendering ─────────────────────────────────────────────────────
function renderMarkdown(text) {
    if (!text) return "";
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
    const codeBlocks = [];
    let processed = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
        const idx = codeBlocks.length;
        codeBlocks.push({ lang: lang || 'text', code: code.replace(/\n$/, '') });
        return '\x00CODEBLOCK' + idx + '\x00';
    });
    processed = processed.replace(/```([\s\S]*?)```/g, (_, code) => {
        const idx = codeBlocks.length;
        codeBlocks.push({ lang: 'text', code: code.replace(/\n$/, '') });
        return '\x00CODEBLOCK' + idx + '\x00';
    });
    const boxBlocks = [];
    processed = processed.replace(/(^(?:.*[┌┐└┘│─├┤┬┴┼].*$\n?)+)/gm, (match) => {
        const idx = boxBlocks.length;
        boxBlocks.push(match.replace(/\n$/, ''));
        return '\x00BOXBLOCK' + idx + '\x00';
    });
    processed = esc(processed);
    processed = processed.replace(/\x00CODEBLOCK(\d+)\x00/g, (_, idx) => {
        const b = codeBlocks[parseInt(idx)];
        return `<pre><code class="language-${b.lang}">${esc(b.code)}</code></pre>`;
    });
    processed = processed.replace(/\x00BOXBLOCK(\d+)\x00/g, (_, idx) => {
        const content = boxBlocks[parseInt(idx)];
        return '<div class="ascii-box"><pre>' + esc(content) + '</pre></div>';
    });
    processed = processed.replace(/`([^`\n]+)`/g, '<code>$1</code>');
    processed = processed.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    processed = processed.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    processed = processed.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    processed = processed.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');
    processed = processed.replace(/^---+$/gm, '<hr>');
    processed = processed.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    processed = processed.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
    processed = processed.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    processed = processed.replace(/(^\|.+\|$\n?)+/gm, (match) => {
        const lines = match.trim().split('\n').filter(l => l.trim());
        if (lines.length < 2) return match;
        const sepIdx = lines.findIndex(l => /^\|[\s\-:|]+\|$/.test(l.trim()));
        if (sepIdx < 1) return match;
        const headerLines = lines.slice(0, sepIdx);
        const bodyLines = lines.slice(sepIdx + 1);
        const parseRow = (line) => line.split('|').slice(1, -1).map(cell => cell.trim());
        let html = '<div class="table-wrap"><table><thead>';
        headerLines.forEach(hl => { const cells = parseRow(hl); html += '<tr>' + cells.map(c => '<th>' + c + '</th>').join('') + '</tr>'; });
        html += '</thead>';
        if (bodyLines.length > 0) {
            html += '<tbody>';
            bodyLines.forEach(bl => { const cells = parseRow(bl); html += '<tr>' + cells.map(c => '<td>' + c + '</td>').join('') + '</tr>'; });
            html += '</tbody>';
        }
        html += '</table></div>';
        return html;
    });
    processed = processed.replace(/(^- .+$\n?)+/gm, (match) => {
        const items = match.trim().split('\n').map(line => '<li>' + line.replace(/^- /, '') + '</li>').join('');
        return '<ul>' + items + '</ul>';
    });
    processed = processed.replace(/(^\d+\. .+$\n?)+/gm, (match) => {
        const items = match.trim().split('\n').map(line => '<li>' + line.replace(/^\d+\. /, '') + '</li>').join('');
        return '<ol>' + items + '</ol>';
    });
    processed = processed.replace(/<\/blockquote>\s*<blockquote>/g, '<br>');
    const blocks = processed.split(/\n{2,}/);
    const finalParts = [];
    for (const block of blocks) {
        const trimmed = block.trim();
        if (!trimmed) continue;
        if (/^<(h[1-3]|pre|ul|ol|blockquote|hr|div)/.test(trimmed)) finalParts.push(trimmed);
        else finalParts.push('<p>' + trimmed.replace(/\n/g, '<br>') + '</p>');
    }
    let html = finalParts.join('');
    html = html.replace(/<p>\s*<\/p>/g, '');
    return html;
}

function renderDiff(text) {
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
        if (wrap.scrollWidth > wrap.clientWidth) wrap.classList.add('scrolling');
        else wrap.classList.remove('scrolling');
    });
}
