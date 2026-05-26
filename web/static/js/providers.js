/* KEYZBOT Provider Config — grid, save, switch, test, add/remove providers */
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
    if (id === 'opengateway') return `<img src="/keyzbot.svg" width="36" height="36" style="border-radius:10px">`;
    const c = color || '#6b7280';
    const letters = id.substring(0, 2).toUpperCase();
    return `<div style="width:36px;height:36px;border-radius:10px;background:${c}20;color:${c};display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;letter-spacing:-0.5px">${letters}</div>`;
}

function toggleProviderEdit(id) {
    const edit = document.getElementById('edit-' + id);
    if (!edit) return;
    const wasOpen = edit.classList.contains('show');
    document.querySelectorAll('.pcard-edit').forEach(e => e.classList.remove('show'));
    if (!wasOpen) edit.classList.add('show');
}

function toggleKeyVisibility(btn) {
    const inp = btn.parentElement.querySelector('input');
    inp.type = inp.type === 'password' ? 'text' : 'password';
}

function filterProviders() {
    const q = document.getElementById('provider-search').value.toLowerCase();
    document.querySelectorAll('.pcard').forEach(card => {
        const name = card.dataset.name || '';
        card.style.display = name.includes(q) ? '' : 'none';
    });
}

function switchProvider(id) { socket.emit("switch_provider", {provider_id: id}); }

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
    const resultEl = document.getElementById('result-' + id);
    if (resultEl) {
        resultEl.className = 'pcard-test-result show';
        resultEl.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><circle cx="12" cy="12" r="10"/></svg> Testing connection...';
    }
    socket.emit("test_provider", {base_url: url, api_key: key, model: model});
}

function removeProvider(id) {
    if (confirm(`Remove provider "${id}"?`)) socket.emit("remove_provider", {provider_id: id});
}

function toggleAddProviderForm() {
    const form = document.getElementById('add-provider-form');
    if (!form) return;
    const btn = document.getElementById('toggle-add-form-btn');
    if (form.style.display === 'none') { form.style.display = ''; if (btn) btn.style.display = 'none'; }
    else { form.style.display = 'none'; if (btn) btn.style.display = ''; }
}

function addCustomProvider() {
    const id = document.getElementById('custom-id').value.trim().toLowerCase().replace(/\s+/g, '-');
    const name = document.getElementById('custom-name').value.trim();
    const url = document.getElementById('custom-url').value.trim();
    const key = document.getElementById('custom-key').value.trim();
    const model = document.getElementById('custom-model').value.trim();
    if (!id || !name || !url || !model) { statusBar.textContent = "ID, Name, URL, and Model are required"; return; }
    socket.emit("add_custom_provider", {id, name, base_url: url, api_key: key, model, models: [model]});
    ['custom-id','custom-name','custom-url','custom-key','custom-model'].forEach(x => document.getElementById(x).value = '');
    document.getElementById('add-provider-form').style.display = 'none';
    const toggleBtn = document.getElementById('toggle-add-form-btn');
    if (toggleBtn) toggleBtn.style.display = '';
    statusBar.textContent = `Provider "${name}" added`;
}
