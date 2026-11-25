
const t = (key, params) => (window.i18n ? window.i18n.t(key, params) : key);

function escapeHtml(str) {
    return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

let currentChatId = null;
let currentUserId = null;
let pendingLeaderboardHighlightUserId = null;
let chatsCache = [];
const tabDataCache = new Map();
const TAB_CACHE_TTL_MS = 20000;
let historyMode = 'mine'; // 'mine' or 'all'
let currentTab = 'profile';

function getActiveChatMeta() {
    const found = chatsCache.find(c => String(c.id) === String(currentChatId) || String(c.chat_id) === String(currentChatId));
    return found || null;
}

function getActiveModules() {
    const meta = getActiveChatMeta();
    return (meta && meta.modules) || {
        roles_enabled: true,
        team_draft_enabled: true,
        score_tracking_enabled: true,
        mvp_voting_enabled: true,
        inventory_enabled: true,
        billing_enabled: true,
        late_tracking_enabled: true
    };
}

function getActiveRoles() {
    const meta = getActiveChatMeta();
    if (meta && Array.isArray(meta.roles) && meta.roles.length > 0) {
        return meta.roles;
    }
    return ['GK', 'LB', 'CB', 'RB', 'LWB', 'RWB', 'CDM', 'CM', 'CAM', 'LM', 'RM', 'LW', 'RW', 'ST', 'CF'];
}

function getCachedData(key) {
    const entry = tabDataCache.get(key);
    if (!entry) return null;
    if ((Date.now() - entry.ts) > TAB_CACHE_TTL_MS) {
        tabDataCache.delete(key);
        return null;
    }
    return entry.data;
}

function setCachedData(key, data) {
    tabDataCache.set(key, { ts: Date.now(), data });
}

function invalidateUserCache() {
    for (const k of Array.from(tabDataCache.keys())) {
        if (k.startsWith(`profile:${currentChatId}`) || k.startsWith(`leaderboard:${currentChatId}`)) {
            tabDataCache.delete(k);
        }
    }
}

function resolveInitialTab() {
    try {
        const urlParams = new URLSearchParams(window.location.search);
        const path = (window.location.pathname || '').toLowerCase();
        
        // 1. Direct path check
        if (path.includes('history')) return 'history';
        if (path.includes('leaderboard') || path.includes('top')) return 'leaderboard';
        if (path.includes('profile')) return 'profile';
        
        // 2. Query param ?tab=
        const tabParam = (urlParams.get('tab') || '').toLowerCase();
        if (['history', 'matches'].includes(tabParam)) return 'history';
        if (['leaderboard', 'top', 'rating'].includes(tabParam)) return 'leaderboard';
        if (['profile', 'me'].includes(tabParam)) return 'profile';

        // 3. Telegram WebApp start_param
        const startParam = (
            (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe && window.Telegram.WebApp.initDataUnsafe.start_param) ||
            urlParams.get('tgWebAppStartParam') ||
            ''
        ).toLowerCase();
        
        if (['history', 'matches'].includes(startParam)) return 'history';
        if (['leaderboard', 'top', 'rating'].includes(startParam)) return 'leaderboard';
        if (['profile', 'me'].includes(startParam)) return 'profile';
    } catch (e) {
        console.warn('Error resolving initial tab:', e);
    }
    return 'profile';
}

window.loadCurrentTab = () => switchTab(currentTab, { forceRefresh: true });
window.jumpToMyLeaderboardRank = async function() {
    const tgUid = tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id;
    pendingLeaderboardHighlightUserId = currentUserId || tgUid || null;
    await switchTab('leaderboard');
};
window.scrollToLeaderboardRank = function(uid) {
    const row = document.getElementById(`leaderboard-row-${uid}`);
    if (!row) return;
    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    row.classList.remove('rank-pulse');
    void row.offsetWidth;
    row.classList.add('rank-pulse');
};
const tg = window.Telegram ? window.Telegram.WebApp : null;
if (!tg) {
    console.error("Telegram WebApp object not found!");
}
const loader = document.getElementById('loader');

const pages = {
    profile: document.getElementById('page-profile'),
    leaderboard: document.getElementById('page-leaderboard'),
    history: document.getElementById('page-history')
};

async function fetchAPI(endpoint, options = {}) {
    const initData = window.Telegram.WebApp.initData;
    
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `tma ${initData}`
    };
    
    const response = await fetch('/api' + endpoint, {
        ...options,
        headers: { ...headers, ...options.headers }
    });
    
    if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'API Error');
    }
    return await response.json();
}

async function init() {
    const urlParams = new URLSearchParams(window.location.search);
    const urlChatId = urlParams.get('chat_id');
    
    // Retry logic for initData (common on mobile Telegram clients)
    let retryCount = 0;
    while (!window.Telegram.WebApp.initData && retryCount < 5) {
        console.warn(`initData missing, retry ${retryCount}...`);
        await new Promise(r => setTimeout(r, 200));
        retryCount++;
    }

    try {
        currentTab = resolveInitialTab();
        if (urlChatId) {
            currentChatId = urlChatId;
            const [chatsRes] = await Promise.all([
                fetchAPI('/chats').catch(e => {
                    console.warn("Failed to load chats:", e);
                    return [];
                }),
                switchTab(currentTab)
            ]);
            chatsCache = Array.isArray(chatsRes) ? chatsRes : [];
            if (chatsCache.length > 0) {
                const currentChat = chatsCache.find(c => String(c.id) === String(currentChatId)) || chatsCache[0];
                const groupDisplay = document.getElementById('group-name-display');
                if (groupDisplay) groupDisplay.innerText = currentChat.title;
                const header = document.getElementById('group-header');
                if (header) header.style.display = 'flex';
                // Re-apply preset-aware modules if group preset differs from football defaults
                if (currentChat && currentChat.sport_type && currentChat.sport_type !== 'football') {
                    await switchTab(currentTab);
                }
            }
        } else {
            let chats = [];
            try {
                chats = await fetchAPI('/chats');
                chatsCache = Array.isArray(chats) ? chats : [];
            } catch (e) {
                console.warn("Failed to load chats:", e);
            }

            if (chatsCache.length > 0) {
                currentChatId = chatsCache[0].id;
                const groupDisplay = document.getElementById('group-name-display');
                if (groupDisplay) groupDisplay.innerText = chatsCache[0].title;
                const header = document.getElementById('group-header');
                if (header) header.style.display = 'flex';
            } else {
                currentChatId = '0';
            }
            await switchTab(currentTab);
        }

        if (tg) {
            tg.expand();
            tg.ready();
        }
    } catch (e) {
        console.error(e);
        loader.style.display = 'none';
        
        // Improve error message for debugging
        let errorTitle = t('error_loading_title');
        let errorDetail = e.message;
        
        if (e.message === 'Failed to fetch' || e.message === 'Load failed') {
            errorDetail = t('error_no_connection');
        }

        const escapeHTML = str => str ? String(str).replace(/[&<>'"]/g, 
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag] || tag)
        ) : '';

        document.body.innerHTML = `
            <div class="card" style="margin:20px; text-align:center;">
                <h3 style="color:#f44336">${escapeHTML(errorTitle)}</h3>
                <p class="subtitle" style="word-break: break-all;">${escapeHTML(errorDetail)}</p>
                <button onclick="location.reload()" class="group-btn" style="margin-top:20px; background:var(--accent-color); color:white; justify-content:center;">${t('btn_try_again')}</button>
            </div>
        `;
        if (tg) {
            tg.expand();
            tg.ready();
        }
    }
}

window.switchTab = async function(tab, opts = {}) {
    const forceRefresh = Boolean(opts && opts.forceRefresh);
    currentTab = tab;
    const cacheKey = tab === 'history' ? `history:${currentChatId}:${historyMode}` : `${tab}:${currentChatId}`;
    const hasWarmCache = !forceRefresh && Boolean(getCachedData(cacheKey));
    if (!hasWarmCache && loader) loader.style.display = 'flex';
    
    try {
        if (tab === 'profile') await renderProfile(forceRefresh);
        else if (tab === 'leaderboard') await renderLeaderboard(forceRefresh);
        else if (tab === 'history') await renderHistory(null, forceRefresh);

        Object.values(pages).forEach(p => p.classList.remove('active'));
        document.querySelectorAll('.nav-item').forEach(t => t.classList.remove('active'));
        
        if (pages[tab]) pages[tab].classList.add('active');
        const activeNav = document.querySelector(`.nav-item[onclick*="switchTab('${tab}')"]`);
        if (activeNav) activeNav.classList.add('active');
        if (window.i18n) window.i18n.applyDOM();
    } catch (e) {
        console.error(e);
    } finally {
        if (loader) loader.style.display = 'none';
    }
}

async function renderProfile(forceRefresh = false) {
    const cacheKey = `profile:${currentChatId}`;
    let data = !forceRefresh ? getCachedData(cacheKey) : null;
    if (!data) {
        data = await fetchAPI(`/users/me/profile?chat_id=${currentChatId}`);
        setCachedData(cacheKey, data);
    }
    currentUserId = data.user_id || currentUserId;
    
    // Determine language: data.language, or tg user language_code, or localStorage, or query param
    if (data.language && window.i18n && !localStorage.getItem('webapp_lang')) { window.i18n.setLanguage(data.language.toLowerCase()); }

    const chatMeta = getActiveChatMeta();
    const mods = getActiveModules();
    const isSport = !chatMeta || !chatMeta.preset_category || chatMeta.preset_category === 'sport';
    const roleLabel = isSport ? t('profile_primary_role') : t('profile_role_title');
    const lblGames = isSport ? t('profile_matches') : t('profile_events');
    const lblGoals = t('profile_goals');
    const lblPrimaryPos = isSport ? t('profile_primary_pos') : t('profile_role_title');
    const lblAltPos = t('profile_alt_pos');
    const lblEdit = t('profile_edit');
    const lblNotSet = t('profile_not_set');



    const userName = data.name || t('profile_default_name');
    const activeCard = data.active_card;
    let cardBadgeHtml = '';
    if (activeCard) {
        const isRed = (activeCard.card_type === 'RED');
        const expDate = activeCard.expires_at ? new Date(activeCard.expires_at).toLocaleDateString() : '';

        const cardTitle = isRed ? t('card_red') : t('card_yellow');
        const reasonPart = activeCard.reason ? `. ${t('card_reason_prefix')}${activeCard.reason}` : '';
        const suspendedPart = isRed ? ` ${t('card_suspended_warning')}` : '';
        const rawTooltip = t('card_tooltip', {
            title: cardTitle,
            weeks: activeCard.weeks,
            date: expDate,
            days: activeCard.days_left,
            reason: reasonPart,
            suspended: suspendedPart
        });
        const badgeDays = t('card_days_left', { days: activeCard.days_left });


        

        const cardEmoji = isRed ? '🟥' : '🟨';
        const tooltip = escapeHTML(rawTooltip);
        const borderCol = isRed ? 'rgba(239, 68, 68, 0.4)' : 'rgba(234, 179, 8, 0.4)';
        const bgCol = isRed ? 'rgba(239, 68, 68, 0.12)' : 'rgba(234, 179, 8, 0.12)';
        const textCol = isRed ? '#f87171' : '#facc15';

        cardBadgeHtml = `
            <div title="${tooltip}" onclick="alert('${tooltip.replace(/'/g, "\\'")}')" style="display:inline-flex; align-items:center; gap:6px; background:${bgCol}; border:1px solid ${borderCol}; padding:4px 10px; border-radius:16px; margin-top:6px; cursor:pointer; max-width:fit-content;">
                <span>${cardEmoji}</span>
                <span style="font-size:12px; font-weight:600; color:${textCol};">${cardTitle} (${badgeDays})</span>
            </div>
        `;
    }

    const safeUserName = String(userName).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    const jsUserName = String(userName).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    const presetIcon = (chatMeta && chatMeta.preset_icon) || '';

    const html = `
        <div class="card flex-row" style="margin-top: 16px; padding: 24px;">
            <div class="avatar">${userName.charAt(0)}</div>
            <div style="flex:1; min-width:0;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <h3 style="font-size: 20px; margin:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${safeUserName}</h3>
                    <button onclick="editProfileName('${jsUserName}')" title="${lblEdit}" style="background:rgba(255,255,255,0.08); border:1px solid var(--border-color); color:var(--text-color); border-radius:8px; padding:3px 8px; font-size:12px; cursor:pointer; flex-shrink:0;">✏️</button>
                </div>
                ${mods.roles_enabled ? `
                <div class="subtitle" style="margin-top:4px;">
                    ${roleLabel}: <b style="color:var(--text-color)">${escapeHtml(data.position)}</b>
                </div>` : (chatMeta && chatMeta.preset_name ? `<div class="subtitle" style="margin-top:4px;">${presetIcon} ${escapeHtml(chatMeta.preset_name)}</div>` : '')}
                ${cardBadgeHtml}
            </div>
        </div>
        
        <div class="flex-row" style="padding: 0 16px; gap: 12px;">
            <div class="card stat-badge clickable-mmr" style="margin: 0; cursor:pointer;" onclick="jumpToMyLeaderboardRank()">
                <span class="stat-value">${data.rating}</span>
                <span class="subtitle" style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">MMR ↗</span>
            </div>
            <div class="card stat-badge" style="margin: 0; cursor:pointer;" onclick="switchTab('history')">
                <span class="stat-value">${data.games_played}</span>
                <span class="subtitle" style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">${lblGames}</span>
            </div>
            ${mods.mvp_voting_enabled ? `
            <div class="card stat-badge" style="margin: 0;">
                <span class="stat-value">${data.mvp_count}</span>
                <span class="subtitle" style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">MVP</span>
            </div>` : ''}
        </div>
        
        ${(mods.roles_enabled || mods.score_tracking_enabled) ? `
        <div class="card" style="margin-top: 16px;">
            ${mods.roles_enabled ? `
            <div style="margin-bottom:${isSport || mods.score_tracking_enabled ? '16px' : '0'}; ${isSport || mods.score_tracking_enabled ? 'border-bottom:1px solid var(--border-color); padding-bottom:12px;' : ''}">
                <h4 class="subtitle" style="text-transform:uppercase; font-weight:700; font-size:11px; margin-bottom:8px; color:var(--accent-color)">${lblPrimaryPos}</h4>
                <div class="flex-between">
                    <span style="font-weight:600; font-size:17px;">${escapeHtml(data.position)}</span>
                    <button onclick="editPrimaryPosition()" style="background:var(--accent-color); color:white; border:none; padding:6px 16px; border-radius:8px; font-weight:600; font-size:12px; cursor:pointer;">${lblEdit}</button>
                </div>
            </div>
            ${isSport ? `
            <div style="margin-bottom:${mods.score_tracking_enabled ? '16px' : '0'}; ${mods.score_tracking_enabled ? 'border-bottom:1px solid var(--border-color); padding-bottom:12px;' : ''}">
                <h4 class="subtitle" style="text-transform:uppercase; font-weight:700; font-size:11px; margin-bottom:8px; color:var(--accent-color)">${lblAltPos}</h4>
                <div class="flex-between">
                    <span style="font-weight:600; font-size:15px;">${data.alt_positions && data.alt_positions.length ? data.alt_positions.map(escapeHtml).join(', ') : lblNotSet}</span>
                    <button onclick="editAltPositions()" style="background:rgba(255,255,255,0.05); color:var(--text-color); border:1px solid var(--border-color); padding:6px 16px; border-radius:8px; font-weight:600; font-size:12px; cursor:pointer;">${lblEdit}</button>
                </div>
            </div>` : ''}` : ''}

            ${mods.score_tracking_enabled ? `
            <div class="flex-between">
                <h4 class="subtitle" style="text-transform:uppercase; font-weight:700; font-size:11px;">${lblGoals}</h4>
                <span style="font-weight:700; font-size:18px; color:var(--accent-color)">${data.total_goals || 0} ${presetIcon || '⚽'}</span>
            </div>` : ''}
        </div>` : ''}
    `;
    if(pages.profile) pages.profile.innerHTML = html;
}

window.editProfileName = function(currentName) {
    closeModal();
    const lang = (window.i18n && window.i18n.getLang ? window.i18n.getLang() : localStorage.getItem('webapp_lang')) || 'en';
    const title = lang === 'ru' ? 'Изменить имя' : (lang === 'cs' ? 'Změnit jméno' : 'Edit Display Name');
    const saveLbl = lang === 'ru' ? 'Сохранить' : (lang === 'cs' ? 'Uložit' : 'Save');
    const safeVal = String(currentName || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');

    const modalHtml = `
        <div id="modal-container">
            <div id="modal-overlay" style="position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.9); backdrop-filter:blur(15px); z-index:3000; display:flex; align-items:center; justify-content:center; animation: fadeIn 0.2s ease;">
                <div class="card" style="width:90%; max-width:340px; padding:24px;">
                    <h3 style="margin-bottom:14px; text-align:center;">${title}</h3>
                    <input type="text" id="profile-name-input" value="${safeVal}" maxlength="64" style="width:100%; box-sizing:border-box; padding:11px 12px; border-radius:10px; border:1px solid var(--border-color); background:rgba(255,255,255,0.06); color:var(--text-color); font-size:15px; margin-bottom:16px;">
                    <div class="flex-row" style="gap:10px;">
                        <button onclick="closeModal()" style="flex:1; padding:12px; border-radius:10px; background:rgba(255,255,255,0.05); color:white; border:none; font-weight:600; cursor:pointer;">${t('btn_cancel')}</button>
                        <button onclick="saveProfileName()" style="flex:1; padding:12px; border-radius:10px; background:var(--accent-color); color:white; border:none; font-weight:600; cursor:pointer;">${saveLbl}</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const inp = document.getElementById('profile-name-input');
    if (inp) inp.focus();
};

window.saveProfileName = async function() {
    const inp = document.getElementById('profile-name-input');
    const newName = inp ? inp.value.trim() : '';
    if (newName.length < 2) {
        alert('Name must be at least 2 characters');
        return;
    }
    closeModal();
    if (loader) loader.style.display = 'flex';
    try {
        await fetchAPI('/users/me/profile', {
            method: 'POST',
            body: JSON.stringify({ name: newName })
        });
        invalidateUserCache();
        await renderProfile(true);
    } catch (e) {
        alert(e.message);
    } finally {
        if (loader) loader.style.display = 'none';
    }
};

window.editPrimaryPosition = function() {
    const positions = getActiveRoles();
    const chatMeta = getActiveChatMeta();
    const isSport = !chatMeta || !chatMeta.preset_category || chatMeta.preset_category === 'sport';
    const title = isSport ? t('pos_primary_title') : t('profile_role_title');
    const desc = isSport ? t('pos_primary_desc') : t('profile_role_desc');
    const html = `
        <div id="modal-overlay" style="position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.9); backdrop-filter:blur(15px); z-index:3000; display:flex; align-items:center; justify-content:center; animation: fadeIn 0.2s ease;">
            <div class="card" style="width:90%; max-width:400px; padding:24px; max-height:85vh; overflow-y:auto; border:1px solid rgba(255,255,255,0.1)">
                <h3 style="margin-bottom:8px; text-align:center;">${title}</h3>
                <p class="subtitle" style="text-align:center; margin-bottom:24px; font-size:13px;">${desc}</p>
                <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px;">
                    ${positions.map(p => `<button onclick="savePrimary('${p}')" class="pos-btn">${p}</button>`).join('')}
                </div>
                <button onclick="closeModal()" style="margin-top:24px; width:100%; color:var(--hint-color); background:none; border:none; cursor:pointer; font-weight:600;">${t('btn_cancel')}</button>
            </div>
        </div>
    `;
    renderModal(html);
}

window.editAltPositions = async function() {
    let data = getCachedData(`profile:${currentChatId}`);
    if (!data) {
        loader.style.display = 'flex';
        data = await fetchAPI(`/users/me/profile?chat_id=${currentChatId}`);
        setCachedData(`profile:${currentChatId}`, data);
        loader.style.display = 'none';
    }
    
    const currentAlts = data.alt_positions || [];
    const positions = getActiveRoles();
    
    const html = `
        <div id="modal-overlay" style="position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.9); backdrop-filter:blur(15px); z-index:3000; display:flex; align-items:center; justify-content:center; animation: fadeIn 0.2s ease;">
            <div class="card" style="width:90%; max-width:400px; padding:24px; max-height:85vh; overflow-y:auto; border:1px solid rgba(255,255,255,0.1)">
                <h3 style="margin-bottom:8px; text-align:center;">${t('pos_alt_title')}</h3>
                <p class="subtitle" style="text-align:center; margin-bottom:24px; font-size:13px;">${t('pos_alt_desc')}</p>
                <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px;">
                    ${positions.map(p => `<button onclick="toggleAlt('${p}')" id="alt-${p}" class="pos-btn ${currentAlts.includes(p) ? 'active' : ''}">${p}</button>`).join('')}
                </div>
                <div style="display:flex; gap:12px; margin-top:32px;">
                    <button onclick="closeModal()" class="group-btn" style="flex:1; justify-content:center; background:rgba(255,255,255,0.05); color:var(--hint-color); border:1px solid var(--border-color)">${t('btn_cancel')}</button>
                    <button onclick="saveAlts()" class="group-btn" style="flex:1; justify-content:center; background:var(--accent-color); color:white">${t('btn_save')}</button>
                </div>
            </div>
        </div>
    `;
    window.selectedAlts = [...currentAlts];
    renderModal(html);
}

function renderModal(html) {
    const div = document.createElement('div');
    div.id = 'modal-container';
    div.innerHTML = html;
    document.body.appendChild(div);
}

window.savePrimary = async function(pos) {
    closeModal();
    loader.style.display = 'flex';
    try {
        await fetchAPI('/users/me/profile', {
            method: 'POST',
            body: JSON.stringify({ position: pos })
        });
        invalidateUserCache();
        await renderProfile(true);
    } catch(e) { tg.showAlert(e.message); }
    finally { loader.style.display = 'none'; }
}

window.toggleAlt = function(pos) {
    const idx = window.selectedAlts.indexOf(pos);
    if (idx > -1) window.selectedAlts.splice(idx, 1);
    else window.selectedAlts.push(pos);
    document.getElementById(`alt-${pos}`).classList.toggle('active');
}

window.saveAlts = async function() {
    const alts = window.selectedAlts;
    closeModal();
    loader.style.display = 'flex';
    try {
        const profile = getCachedData(`profile:${currentChatId}`) || await fetchAPI(`/users/me/profile?chat_id=${currentChatId}`);
        await fetchAPI('/users/me/profile', {
            method: 'POST',
            body: JSON.stringify({ 
                position: profile.position,
                alt_positions: alts 
            })
        });
        invalidateUserCache();
        await renderProfile(true);
    } catch(e) { tg.showAlert(e.message); }
    finally { loader.style.display = 'none'; }
}

window.closeModal = function() {
    const modal = document.getElementById('modal-container');
    if (modal) modal.remove();
    const overlay = document.getElementById('modal-overlay');
    if (overlay) overlay.remove();
}

const escapeHTML = str => str ? String(str).replace(/[&<>'"]/g, 
    tag => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#39;',
        '"': '&quot;'
    }[tag] || tag)
) : '';

window.showGroupSelector = async function() {
    try {
        let chats = chatsCache;
        if (!chats || chats.length === 0) {
            loader.style.display = 'flex';
            chats = await fetchAPI('/chats');
            chatsCache = Array.isArray(chats) ? chats : [];
        }
        const listHtml = chats.map(c => `
            <button onclick="selectGroup('${c.id}', '${escapeHTML(c.title)}')" class="group-btn" style="width:100%; margin-bottom:10px; padding:14px 16px; border-radius:12px; justify-content:space-between; background:${c.id == currentChatId ? 'var(--accent-color)' : 'rgba(255,255,255,0.05)'}; color:${c.id == currentChatId ? 'white' : 'var(--text-color)'}; font-weight:600; cursor:pointer;">
                <span>${escapeHTML(c.preset_icon ? `${c.preset_icon} ${c.title}` : c.title)}</span>
                ${c.id == currentChatId ? '✓' : ''}
            </button>
        `).join('');

        const modalHtml = `
            <div id="modal-overlay" style="position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.9); backdrop-filter:blur(15px); z-index:3000; display:flex; align-items:center; justify-content:center; animation: fadeIn 0.2s ease;">
                <div class="card" style="width:90%; max-width:400px; padding:24px; max-height:85vh; overflow-y:auto; border:1px solid rgba(255,255,255,0.1)">
                    <h3 style="margin-bottom:8px; text-align:center;">${t('title_select_group')}</h3>
                    <p class="subtitle" style="text-align:center; margin-bottom:24px; font-size:13px;">${t('select_group_desc')}</p>
                    <div>${listHtml}</div>
                    <button onclick="closeModal()" style="margin-top:20px; width:100%; color:var(--hint-color); background:none; border:none; cursor:pointer; font-weight:600;">${t('btn_cancel')}</button>
                </div>
            </div>
        `;
        renderModal(modalHtml);
    } catch (e) {
        console.error("showGroupSelector error:", e);
    } finally {
        loader.style.display = 'none';
    }
};

window.selectGroup = async function(chatId, title) {
    currentChatId = chatId;
    const groupDisplay = document.getElementById('group-name-display');
    if (groupDisplay) groupDisplay.innerText = title;
    closeModal();
    await switchTab(currentTab);
};

async function renderLeaderboard(forceRefresh = false) {
    const cacheKey = `leaderboard:${currentChatId}`;
    let data = !forceRefresh ? getCachedData(cacheKey) : null;
    if (!data) {
        data = await fetchAPI(`/chats/${currentChatId}/leaderboard`);
        setCachedData(cacheKey, data);
    }

    const mods = getActiveModules();
    const tgUid = tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id;
    const meId = currentUserId || tgUid;
    const myIdx = meId ? data.findIndex(p => String(p.user_id) === String(meId)) : -1;

    const myRankBanner = myIdx >= 0 ? `
        <div class="card flex-between" onclick="scrollToLeaderboardRank(${Number(data[myIdx].user_id)})" style="cursor:pointer; margin-top:8px; background:rgba(56,189,248,0.12); border-color:rgba(56,189,248,0.45); padding:12px 18px;">
            <span style="font-weight:700; font-size:14px;">🏅 ${t('leaderboard_your_rank', { rank: myIdx + 1, rating: data[myIdx].rating })}</span>
            <span style="font-size:12px; color:var(--accent-color); font-weight:700;">↓</span>
        </div>
    ` : '';

    const listHtml = data.map((p, idx) => {
        const isMe = meId && String(p.user_id) === String(meId);
        const subText = mods.score_tracking_enabled
            ? t('leaderboard_games_goals', { games: p.games, goals: p.goals })
            : t('leaderboard_events_only', { games: p.games });
        return `
        <div id="leaderboard-row-${Number(p.user_id)}" class="card flex-between ${isMe ? 'leaderboard-me' : ''}" style="padding: 12px 20px;">
            <div class="flex-row">
                <div style="font-weight:bold; color:${isMe ? 'var(--accent-color)' : 'var(--hint-color)'}; width:26px; font-size:14px;">#${idx+1}</div>
                <div>
                    <div style="font-weight:bold; font-size:16px;">${escapeHTML(p.name)} ${isMe ? `<span style="color:var(--accent-color); font-size:12px;">${t('player_you')}</span>` : ''}</div>
                    <div class="subtitle" style="font-size:12px;">${subText}</div>
                </div>
            </div>
            <div style="font-weight:bold; color:var(--accent-color); font-size:18px;">${p.rating}</div>
        </div>`;
    }).join('');

    if (pages.leaderboard) {
        pages.leaderboard.innerHTML = `<h2>${t('leaderboard_title')}</h2>` + myRankBanner + listHtml;
    }

    const highlightTarget = pendingLeaderboardHighlightUserId;
    if (highlightTarget) {
        pendingLeaderboardHighlightUserId = null;
        requestAnimationFrame(() => window.scrollToLeaderboardRank(highlightTarget));
    }
}

window.renderHistory = async function(mode = null, forceRefresh = false) {
    if (mode) historyMode = mode;
    const cacheKey = `history:${currentChatId}:${historyMode}`;
    let data = !forceRefresh ? getCachedData(cacheKey) : null;
    if (!data) {
        const endpoint = historyMode === 'all' 
            ? `/history/${currentChatId}` 
            : `/users/me/history?chat_id=${currentChatId}`;
        data = await fetchAPI(endpoint);
        setCachedData(cacheKey, data);
    }
    const chatMeta = getActiveChatMeta();
    const mods = getActiveModules();
    const eventNoun = (chatMeta && chatMeta.terminology && chatMeta.terminology.event_noun) || null;
    const presetIcon = (chatMeta && chatMeta.preset_icon) || '⚽';
    
    if (data.length === 0) {
        if(pages.history) pages.history.innerHTML = `
            <div class="history-filter">
                <button class="${historyMode === 'mine' ? 'active' : ''}" onclick="renderHistory('mine')">${t('history_my_games')}</button>
                <button class="${historyMode === 'all' ? 'active' : ''}" onclick="renderHistory('all')">${t('history_all_games')}</button>
            </div>
            <div class="card" style="text-align:center">${t('history_no_games')}</div>
        `;
        return;
    }

    // Numbering: if we have all games, we can number them based on total count
    // If we only have some, it's harder. But usually we want "Game 1, 2, 3"
    // Let's assume the games are returned in descending order.
    // To number them correctly, we might need the full count or just use what we have.
    // The user mentioned Game 1, 2, 7, 8. This suggests a global sequence.
    
    const listHtml = data.map((g, idx) => {
        const ratingChange = g.rating_change || 0;
        let resColor = ratingChange > 0 ? '#4caf50' : (ratingChange < 0 ? '#f44336' : 'var(--hint-color)');
        let sign = ratingChange > 0 ? '+' : '';
        
        const teamColors = { 'A': '#4caf50', 'B': '#ff9800', 'C': '#3b82f6', 'D': '#ffffff' };
        const teamLabels = { 'A': t('team_green'), 'B': t('team_orange'), 'C': t('team_blue'), 'D': t('team_white') };
        
        let statusText = t('history_draw');
        let statusColor = 'var(--hint-color)';
        if (!mods.score_tracking_enabled) {
            statusText = t('history_attended');
            statusColor = '#4caf50';
        } else if (g.winner_team) {
            if (g.my_team && g.my_team === g.winner_team) {
                statusText = t('history_win');
                statusColor = '#4caf50';
            } else if (g.my_team) {
                statusText = t('history_defeat');
                statusColor = '#f44336';
            } else {
                const wt = teamLabels[g.winner_team] || g.winner_team; statusText = t('history_win_team', { team: wt });
                statusColor = teamColors[g.winner_team] || 'var(--hint-color)';
            }
        }

        let scoreHtml = '';
        if (!mods.score_tracking_enabled) {
            scoreHtml = `<span style="font-size:16px; color:var(--text-color);">${presetIcon} ${escapeHTML(g.location)}</span>`;
        } else if (g.team_count === 3) {
            scoreHtml = `
                <span style="color:#4caf50">${g.score_a ?? 0}</span> : 
                <span style="color:#ff9800">${g.score_b ?? 0}</span> : 
                <span style="color:#3b82f6">${g.score_c ?? 0}</span>
            `;
        } else {
            scoreHtml = `
                <span style="color:#4caf50">${g.score_a ?? 0}</span> : 
                <span style="color:#ff9800">${g.score_b ?? 0}</span>
            `;
        }
        const prefixLabel = eventNoun
            ? `${eventNoun.toUpperCase()} #${g.game_number || g.game_id}`
            : t('history_game_prefix', { num: g.game_number || g.game_id });

        return `
        <div class="card" onclick="showGameDetails(${g.game_id})" style="cursor:pointer; border-left: 4px solid ${historyMode === 'mine' ? resColor : 'transparent'};">
            <div class="flex-between" style="margin-bottom: 8px;">
                <div style="display:flex; flex-direction:column">
                    <span style="font-size: 10px; font-weight: 800; color:var(--accent-color); margin-bottom: 2px;">${prefixLabel}</span>
                    <span style="font-size: 20px; font-weight: 800; letter-spacing: 1px;">
                        ${scoreHtml}
                    </span>
                </div>
                <div style="text-align:right">
                    <div style="font-size: 10px; font-weight: 800; text-transform: uppercase; color:${statusColor}">${statusText}</div>
                    <span class="subtitle" style="font-weight: 600; font-size:12px;">${new Date(g.date).toLocaleDateString('en-GB', {day: '2-digit', month: '2-digit', year: 'numeric', timeZone: g.timezone || 'Europe/Prague'})}</span>
                </div>
            </div>

            <div class="subtitle" style="font-size: 11px; margin-bottom: 12px; display:flex; align-items:center; gap:4px; opacity:0.7">
                <svg style="width:12px;height:12px;fill:currentColor" viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-12-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
                ${g.location}
            </div>
            ${historyMode === 'mine' ? `
            <div class="flex-between">
                <div class="flex-row" style="gap: 8px;">
                    <div style="width:10px; height:10px; border-radius:50%; background:${teamColors[g.my_team] || 'var(--hint-color)'}"></div>
                    <span class="subtitle" style="font-weight:600">${teamLabels[g.my_team] || t('team_unknown')}</span>
                </div>
                <span style="color:${resColor}; font-weight: 800; font-size: 16px;">${sign}${ratingChange} MMR</span>
            </div>` : ''}
        </div>
        `;
    }).join('');
    
    if(pages.history) pages.history.innerHTML = `
        <div class="history-filter" style="display:flex; gap:8px; padding:0 16px; margin-bottom:16px;">
            <button class="filter-btn ${historyMode === 'mine' ? 'active' : ''}" onclick="renderHistory('mine')" style="flex:1; padding:10px; border-radius:12px; border:1px solid var(--border-color); background:${historyMode === 'mine' ? 'var(--accent-color)' : 'transparent'}; color:${historyMode === 'mine' ? 'white' : 'var(--text-color)'}; font-weight:700; font-size:12px; cursor:pointer; transition:all 0.2s;">${t('history_my_games')}</button>
            <button class="filter-btn ${historyMode === 'all' ? 'active' : ''}" onclick="renderHistory('all')" style="flex:1; padding:10px; border-radius:12px; border:1px solid var(--border-color); background:${historyMode === 'all' ? 'var(--accent-color)' : 'transparent'}; color:${historyMode === 'all' ? 'white' : 'var(--text-color)'}; font-weight:700; font-size:12px; cursor:pointer; transition:all 0.2s;">${t('history_all_games')}</button>
        </div>
    ` + listHtml;
}

window.showGameDetails = async function(gameId) {
    loader.style.display = 'flex';
    try {
        const game = await fetchAPI(`/game/${gameId}`);
        const mods = game.modules || { score_tracking_enabled: true, team_draft_enabled: true, mvp_voting_enabled: true };
        const isSport = !game.preset_category || game.preset_category === 'sport';
        const icon = game.preset_icon || '⚽';
        const grpLabel = (game.terminology && game.terminology.grouping_noun) || 'Group';

        let headerTopHtml = '';
        if (mods.score_tracking_enabled) {
            let scoreHtml = '';
            if (game.team_count === 3) {
                scoreHtml = `<span style="color:#4caf50">${game.score_a ?? 0}</span> : <span style="color:#ff9800">${game.score_b ?? 0}</span> : <span style="color:#3b82f6">${game.score_c ?? 0}</span>`;
            } else {
                scoreHtml = `<span style="color:#4caf50">${game.score_a ?? 0}</span> : <span style="color:#ff9800">${game.score_b ?? 0}</span>`;
            }
            headerTopHtml = `<h1 style="font-size:48px; margin:10px 0; font-weight:900; letter-spacing:-1px;">${scoreHtml}</h1>`;
        } else {
            const evNoun = (game.terminology && game.terminology.event_noun) || 'Event';
            headerTopHtml = `<h2 style="font-size:26px; margin:10px 0; font-weight:800;">${icon} ${escapeHTML(evNoun)} #${game.game_number || game.id}</h2>`;
        }

        const labelA = isSport ? `${t('team_green')} (A)` : `${grpLabel} A`;
        const labelB = isSport ? `${t('team_orange')} (B)` : `${grpLabel} B`;
        const labelC = isSport ? `${t('team_blue')} (C)` : `${grpLabel} C`;

        const renderParticipantStats = (p) => {
            if (!mods.score_tracking_enabled && !mods.mvp_voting_enabled) return '';
            return `<span style="display:flex; align-items:center; gap:4px">
                ${mods.score_tracking_enabled && p.goals > 0 ? `<span style="font-size:12px">${icon}${p.goals}</span>` : ''} 
                ${mods.mvp_voting_enabled && p.is_mvp ? '<span style="font-size:12px">🌟</span>' : ''}
            </span>`;
        };

        const renderSinglePool = (list) => (list || []).map(p => `
            <div style="font-size:15px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center">
                <span style="font-weight:500">${escapeHtml(p.name)}</span>
                ${renderParticipantStats(p)}
            </div>
        `).join('');

        let rosterBodyHtml = '';
        if (!mods.team_draft_enabled || (!game.team_a?.length && !game.team_b?.length && (game.unassigned?.length || 0) > 0)) {
            const allParticipants = [...(game.team_a || []), ...(game.team_b || []), ...(game.team_c || []), ...(game.unassigned || [])];
            rosterBodyHtml = `
                <div style="background: rgba(56, 189, 248, 0.05); padding: 16px; border-radius: 16px; border: 1px solid rgba(56, 189, 248, 0.15);">
                    <h4 style="color:var(--accent-color); margin-bottom:12px; border-bottom:1px solid rgba(56,189,248,0.2); padding-bottom:8px; font-weight:800; font-size:14px; text-transform:uppercase;">${t('sec_main_roster')} (${allParticipants.length})</h4>
                    ${renderSinglePool(allParticipants)}
                </div>
            `;
        } else {
            rosterBodyHtml = `
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:24px;">
                <div style="background: rgba(76, 175, 80, 0.05); padding: 16px; border-radius: 16px; border: 1px solid rgba(76, 175, 80, 0.1);">
                    <h4 style="color:#4caf50; margin-bottom:12px; border-bottom:1px solid rgba(76,175,80,0.2); padding-bottom:8px; font-weight:800; font-size:14px; text-transform:uppercase;">${labelA}</h4>
                    ${renderSinglePool(game.team_a)}
                </div>
                <div style="background: rgba(255, 152, 0, 0.05); padding: 16px; border-radius: 16px; border: 1px solid rgba(255, 152, 0, 0.1);">
                    <h4 style="color:#ff9800; margin-bottom:12px; border-bottom:1px solid rgba(255,152,0,0.2); padding-bottom:8px; font-weight:800; font-size:14px; text-transform:uppercase;">${labelB}</h4>
                    ${renderSinglePool(game.team_b)}
                </div>
            </div>
            ${game.team_c && game.team_c.length ? `
            <div style="margin-top:24px; background: rgba(59, 130, 246, 0.05); padding: 16px; border-radius: 16px; border: 1px solid rgba(59, 130, 246, 0.1);">
                <h4 style="color:#3b82f6; margin-bottom:12px; border-bottom:1px solid rgba(59,130,246,0.2); padding-bottom:8px; font-weight:800; font-size:14px; text-transform:uppercase;">${labelC}</h4>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
                    ${renderSinglePool(game.team_c)}
                </div>
            </div>` : ''}`;
        }

        let html = `
            <div style="text-align:center; margin-bottom:30px;">
                ${headerTopHtml}
                <div class="subtitle" style="font-size:16px; margin-bottom:4px;">📍 ${escapeHtml(game.location)}</div>
                <div class="subtitle" style="font-size:14px;">📅 ${new Date(game.date).toLocaleString('en-GB', {day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: game.timezone || 'Europe/Prague'})}</div>
            </div>
            ${rosterBodyHtml}
            <button onclick="closePopup()" class="group-btn" style="margin-top:40px; height:56px; font-size:18px; justify-content:center; background:var(--accent-color); color:white;">${t('btn_close_popup')}</button>
        `;
        
        const overlay = document.createElement('div');
        overlay.id = 'details-overlay';
        overlay.style = 'position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(15,23,42,0.98); backdrop-filter:blur(20px); z-index:2000; padding:24px; overflow-y:auto; animation: slideUp 0.3s cubic-bezier(0.4, 0, 0.2, 1);';
        overlay.innerHTML = `
            <div style="max-width: 600px; margin: 0 auto; padding-bottom: 40px;">
                ${html}
            </div>
        `;
        document.body.appendChild(overlay);
        document.body.style.overflow = 'hidden'; 
        
    } catch (e) {
        console.error("Game details error:", e);
        if (tg && tg.showAlert) tg.showAlert('Ошибка: ' + e.message);
    } finally {
        loader.style.display = 'none';
    }
}

window.closePopup = function() {
    const overlay = document.getElementById('details-overlay');
    if(overlay) overlay.remove();
    document.body.style.overflow = '';
}

function syncAppLangBadge() {
    const codeEl = document.getElementById('app-lang-code');
    if (codeEl) {
        const cur = (window.i18n && window.i18n.getLang ? window.i18n.getLang() : localStorage.getItem('webapp_lang')) || 'en';
        codeEl.innerText = String(cur).toUpperCase();
    }
}

window.toggleAppLang = async function() {
    const order = ['en', 'ru', 'cs'];
    const cur = (window.i18n && window.i18n.getLang ? window.i18n.getLang() : localStorage.getItem('webapp_lang')) || 'en';
    const next = order[(order.indexOf(cur) + 1) % order.length] || 'en';
    localStorage.setItem('webapp_lang', next);
    if (window.i18n && window.i18n.setLanguage) {
        await window.i18n.setLanguage(next);
    }
    syncAppLangBadge();
    await loadCurrentTab();
    const existingAd = document.getElementById('app-hub-ad-container');
    if (existingAd && window.SponsorBanner) {
        window.SponsorBanner.loadAndRender(
            [{ el: existingAd, placement: 'app_hub' }],
            { chatId: currentChatId, placement: 'app_hub', lang: next }
        );
    }
};

async function loadAd() {
    try {
        const lang = localStorage.getItem('webapp_lang') || 'en';
        let ep = `/ads/random?placement=app_hub&lang=${encodeURIComponent(lang)}`;
        if (currentChatId) ep += `&chat_id=${currentChatId}`;
        const adRes = await fetchAPI(ep);

        if (adRes.status === 'ok' && adRes.ad) {
            const ad = adRes.ad;
            let adContainer = document.getElementById('app-hub-ad-container');
            if (!adContainer) {
                adContainer = document.createElement('div');
                adContainer.id = 'app-hub-ad-container';
                adContainer.style.margin = '14px 16px';
                document.body.insertBefore(adContainer, document.querySelector('.page-container'));
            }
            if (window.SponsorBanner) {
                window.SponsorBanner.render(adContainer, ad, currentChatId, 'app_hub');
            }
        }
    } catch (e) {
        console.error("Ad load failed", e);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    syncAppLangBadge();
    init();
    setTimeout(loadAd, 1500);
});
