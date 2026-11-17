function getAdminText(keyOrEn, ruFallbackOrParams, params) {
    const lang = localStorage.getItem('webapp_lang') || 'en';
    if (window.i18n && window.i18n.t) {
        const p = (ruFallbackOrParams && typeof ruFallbackOrParams === 'object') ? ruFallbackOrParams : params;
        const translated = window.i18n.t(keyOrEn, p);
        if (translated && translated !== keyOrEn) {
            return translated;
        }
    }
    if (typeof ruFallbackOrParams === 'string') {
        return lang === 'ru' ? ruFallbackOrParams : keyOrEn;
    }
    return keyOrEn;
}

function promptConfirm(message) {
    return new Promise((resolve) => {
        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.showConfirm) {
            window.Telegram.WebApp.showConfirm(message, (ok) => resolve(!!ok));
        } else {
            resolve(window.confirm(message));
        }
    });
}

function promptAlert(message) {
    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.showAlert) {
        window.Telegram.WebApp.showAlert(message);
    } else {
        alert(message);
    }
}

function escapeHtml(raw) {
    return String(raw || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function showAdminToast(message) {
    promptAlert(message);
}

let initData = "";
let currentGroupId = null;
let groupsCache = [];
let pendingSettingSaves = [];

function init() {
    if (window.Telegram && window.Telegram.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        
        // Robust initData retrieval
        const urlParams = new URLSearchParams(window.location.search);
        const urlInitData = urlParams.get('initData');
        initData = window.Telegram.WebApp.initData || urlInitData || "";
        
        if (!window.Telegram.WebApp.initData && urlInitData) {
            console.log("Main Admin: Using initData from URL params");
        }
    }
    
    // For local dev without TG:
    if (!initData) {
        console.warn("No initData found. If in browser, API calls may fail.");
    }

    loadGroups();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

let currentGameId = null;
let currentGameData = null;

// View Navigation
function switchView(viewId) {
    document.querySelectorAll('.view-section').forEach(el => {
        if (el.id === viewId) return;
        el.classList.remove('active');
        setTimeout(() => {
            if (!el.classList.contains('active')) {
                el.classList.add('hidden');
            }
        }, 300);
    });
    
    const target = document.getElementById(viewId);
    if (target) {
        target.classList.remove('hidden');
        // trigger reflow
        void target.offsetWidth;
        target.classList.add('active');
    }
}

function showGroupsView() {
    switchView('view-groups');
}

// API Helper (supports both apiCall(endpoint, options) and apiCall(endpoint, methodStr, bodyObj))
async function apiCall(endpoint, optionsOrMethod = {}, maybeBody = undefined) {
    const headers = {
        'Authorization': `tma ${initData}`,
        'Content-Type': 'application/json'
    };
    let fetchOptions = {};
    if (typeof optionsOrMethod === 'string') {
        fetchOptions.method = optionsOrMethod;
        if (maybeBody !== undefined) {
            fetchOptions.body = JSON.stringify(maybeBody);
        }
    } else {
        fetchOptions = { ...(optionsOrMethod || {}) };
    }
    
    let url = endpoint.startsWith('/api/') ? endpoint : `/api/dashboard${endpoint}`;
    try {
        const response = await fetch(url, { ...fetchOptions, headers });
        if (!response.ok) {
            let detail = response.statusText;
            try {
                const err = await response.json();
                detail = err.detail || detail;
            } catch(e) {}
            throw new Error(`API Error ${response.status}: ${detail}`);
        }
        return await response.json();
    } catch (e) {
        if (e.message === 'Failed to fetch' || e.message === 'Load failed') {
            throw new Error("Network Error: Connection to server failed.");
        }
        throw e;
    }
}

function applyBillingModeSettingsUI(billingMode, currency) {
    const isFree = billingMode === 'free_corporate';
    const priceWrap = document.getElementById('group-setting-price-wrap');
    const payWrap = document.getElementById('group-setting-payment-wrap');
    if (priceWrap) priceWrap.style.opacity = isFree ? '0.45' : '1';
    if (payWrap) payWrap.style.opacity = isFree ? '0.45' : '1';
    const priceInput = document.getElementById('setting-price');
    const payInput = document.getElementById('setting-payment-info');
    if (priceInput) priceInput.disabled = isFree;
    if (payInput) payInput.disabled = isFree;

    const curr = currency || (document.getElementById('setting-currency') && document.getElementById('setting-currency').value) || 'CZK';
    const priceLabel = document.getElementById('lbl-setting-price');
    if (priceLabel) {
        const tmpl = getAdminText('lbl_def_price');
        priceLabel.textContent = tmpl.replaceAll('{currency}', curr);
    }
}

// Load Data

function switchGroupTab(tab) {
    currentGroupViewTab = tab;
    
    // Update tab buttons
    document.querySelectorAll('.group-tab-btn').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`tab-group-${tab}`);
    if (btn) btn.classList.add('active');
    
    // Hide all containers
    const gamesEl = document.getElementById('games-list');
    const commEl = document.getElementById('group-community-container');
    const settEl = document.getElementById('group-settings-container');
    const invEl = document.getElementById('group-inventory-container');
    
    if (gamesEl) gamesEl.classList.toggle('hidden', tab !== 'games');
    if (commEl) commEl.classList.toggle('hidden', tab !== 'community');
    if (settEl) settEl.classList.toggle('hidden', tab !== 'settings');
    if (invEl) invEl.classList.toggle('hidden', tab !== 'inventory');
    
    if (tab === 'community' && currentGroupId) {
        loadGroupCommunity(currentGroupId);
    } else if (tab === 'inventory' && currentGroupId) {
        loadGroupInventory(currentGroupId);
    }
}

