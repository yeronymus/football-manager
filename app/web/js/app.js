const tg = window.Telegram.WebApp;
tg.expand();

const API_BASE = '/api';
const initData = tg.initData || ''; 

// State
let currentChatId = null;
let currentTab = 'profile';
let groupTitle = '';

// Elements
const loader = document.getElementById('loader');
const groupSelector = document.getElementById('group-selector');
const groupList = document.getElementById('group-list');
const groupHeader = document.getElementById('group-header');
const pages = {
    profile: document.getElementById('page-profile'),
    history: document.getElementById('page-history'),
    leaderboard: document.getElementById('page-leaderboard'),
    groupName: document.getElementById('group-name-display')
};

// Initialization
async function init() {
    const urlParams = new URLSearchParams(window.location.search);
    const urlChatId = urlParams.get('chat_id');
    
    // Check if the HTML file itself indicates a specific tab (legacy support)
    const path = window.location.pathname;
    if (path.includes('history.html')) currentTab = 'history';
    if (path.includes('leaderboard.html')) currentTab = 'leaderboard';
    if (path.includes('profile.html')) currentTab = 'profile';

    if (urlChatId) {
        currentChatId = urlChatId;
        // Fetch group title if we only have ID
        const chats = await fetchAPI('/chats');
        const currentChat = chats.find(c => c.id == currentChatId);
        if (currentChat) {
            groupTitle = currentChat.title;
            groupHeader.style.display = 'flex';
            if(pages.groupName) pages.groupName.innerText = groupTitle;
        }
        await switchTab(currentTab);
    } else {
        await showGroupSelector();
    }
}

// Fetch Helper (injects initData via Header)
async function fetchAPI(endpoint) {
    const url = new URL(`${API_BASE}${endpoint}`, window.location.origin);
    const res = await fetch(url, {
        headers: {
            'Authorization': `tma ${initData}`
        }
    });
    if (!res.ok) throw new Error('API Error: ' + res.status);
    return res.json();
}

async function showGroupSelector() {
    loader.style.display = 'flex';
    try {
        const chats = await fetchAPI('/chats');
        if (chats.length === 0) {
            groupList.innerHTML = '<p style="text-align:center; color:var(--hint-color)">Вы пока не состоите ни в одной группе.</p>';
        } else {
            groupList.innerHTML = chats.map(c => `
                <button class="group-btn" onclick="selectGroup(${c.id}, '${c.title.replace(/'/g, "\\'")}')">${c.title}</button>
            `).join('');
        }
        groupSelector.style.display = 'block';
    } catch (e) {
        groupList.innerHTML = `<p style="color:red">Ошибка загрузки: ${e.message}</p>`;
        groupSelector.style.display = 'block';
    } finally {
        loader.style.display = 'none';
    }
}

window.selectGroup = async function(id, title) {
    currentChatId = id;
    groupTitle = title;
    groupSelector.style.display = 'none';
    groupHeader.style.display = 'flex';
    if(pages.groupName) pages.groupName.innerText = title;
    await switchTab(currentTab);
}

window.switchTab = async function(tabId) {
    if (currentTab === tabId) return;
    
    // Update UI
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    document.querySelector(`[onclick="switchTab('${tabId}')"]`).classList.add('active');
    
    Object.values(pages).forEach(p => { if(p) p.style.display = 'none'; });
    if(pages[tabId]) pages[tabId].style.display = 'block';
    
    currentTab = tabId;
    await loadCurrentTab();
}

async function loadCurrentTab() {
    if (!currentChatId) return;
    loader.style.display = 'flex';
    
    try {
        if (currentTab === 'profile') await renderProfile();
        else if (currentTab === 'history') await renderHistory();
        else if (currentTab === 'leaderboard') await renderLeaderboard();
    } catch (e) {
        tg.showAlert('Ошибка: ' + e.message);
    } finally {
        loader.style.display = 'none';
    }
}

// Renderers
async function renderProfile() {
    const data = await fetchAPI(`/users/me/profile?chat_id=${currentChatId}`);
    
    // Render basic stats
    const html = `
        <div class="card flex-row" style="margin-top: 16px; padding: 24px;">
            <div class="avatar">${data.name.charAt(0)}</div>
            <div style="flex:1">
                <h3 style="font-size: 20px;">${data.name}</h3>
                <div class="flex-between">
                    <span class="subtitle">${data.position}</span>
                    <button onclick="editPosition()" class="subtitle" style="background:none; border:none; color:var(--accent-color); font-weight:600; cursor:pointer">Изменить</button>
                </div>
            </div>
        </div>
        
        <div class="flex-row" style="padding: 0 16px; gap: 12px;">
            <div class="card stat-badge" style="margin: 0;">
                <span class="stat-value">${data.rating}</span>
                <span class="subtitle" style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">MMR</span>
            </div>
            <div class="card stat-badge" style="margin: 0;">
                <span class="stat-value">${data.games_played}</span>
                <span class="subtitle" style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">Игр</span>
            </div>
            <div class="card stat-badge" style="margin: 0;">
                <span class="stat-value">${data.mvp_count}</span>
                <span class="subtitle" style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">MVP</span>
            </div>
        </div>
        
        <div class="card" style="margin-top: 16px;">
            <div class="flex-between" style="margin-bottom:12px;">
                <h4 class="subtitle" style="text-transform:uppercase; font-weight:700">Доп. позиции</h4>
                <span style="font-weight:600">${data.alt_positions && data.alt_positions.length ? data.alt_positions.join(', ') : 'Нет'}</span>
            </div>
            <div class="flex-between">
                <h4 class="subtitle" style="text-transform:uppercase; font-weight:700">Всего голов</h4>
                <span style="font-weight:600; color:var(--accent-color)">${data.total_goals || 0} ⚽</span>
            </div>
        </div>
    `;
    if(pages.profile) pages.profile.innerHTML = html;
}

window.editPosition = async function() {
    const positions = ['GK', 'DEF', 'MID', 'FWD'];
    tg.showActionSheet({
        title: 'Выберите позицию',
        buttons: positions.map(p => ({text: p}))
    }, async (index) => {
        if (index !== undefined) {
            const pos = positions[index];
            try {
                await fetchAPI('/users/me/profile', {
                    method: 'POST',
                    body: JSON.stringify({position: pos})
                });
                renderProfile();
            } catch(e) {
                tg.showAlert('Ошибка: ' + e.message);
            }
        }
    });
}

async function renderLeaderboard() {
    const data = await fetchAPI(`/chats/${currentChatId}/leaderboard`);
    
    const listHtml = data.map((p, idx) => `
        <div class="card flex-between" style="padding: 12px 20px;">
            <div class="flex-row">
                <div style="font-weight:bold; color:var(--hint-color); width:20px; font-size:14px;">${idx+1}</div>
                <div>
                    <div style="font-weight:bold; font-size:16px;">${p.name}</div>
                    <div class="subtitle" style="font-size:12px;">${p.games} игр • ${p.goals} голов</div>
                </div>
            </div>
            <div style="font-weight:bold; color:var(--accent-color); font-size:18px;">${p.rating}</div>
        </div>
    `).join('');
    
    if(pages.leaderboard) pages.leaderboard.innerHTML = `<h2>Лидерборд группы</h2>` + listHtml;
}

async function renderHistory() {
    const data = await fetchAPI(`/users/me/history?chat_id=${currentChatId}`);
    
    if (data.length === 0) {
        if(pages.history) pages.history.innerHTML = `<div class="card" style="text-align:center">Игр пока нет.</div>`;
        return;
    }
    
    const listHtml = data.map(g => {
        let resColor = g.rating_change > 0 ? '#4caf50' : (g.rating_change < 0 ? '#f44336' : 'var(--hint-color)');
        let sign = g.rating_change > 0 ? '+' : '';
        
        const teamColors = { 'A': '#4caf50', 'B': '#ff9800', 'C': '#3b82f6', 'D': '#ffffff' };
        const teamLabels = { 'A': 'Зеленые', 'B': 'Оранжевые', 'C': 'Синие', 'D': 'Белые' };
        const teamColor = teamColors[g.my_team] || 'var(--hint-color)';
        const teamLabel = teamLabels[g.my_team] || 'Неизвестно';
        
        let statusText = 'Ничья';
        let statusColor = 'var(--hint-color)';
        if (g.winner_team) {
            if (g.my_team === g.winner_team) {
                statusText = 'Победа';
                statusColor = '#4caf50';
            } else {
                statusText = 'Поражение';
                statusColor = '#f44336';
            }
        }

        return `
        <div class="card" onclick="showGameDetails(${g.game_id})" style="cursor:pointer; border-left: 4px solid ${resColor};">
            <div class="flex-between" style="margin-bottom: 8px;">
                <span style="font-size: 20px; font-weight: 800; letter-spacing: 1px;">
                    <span style="color:#4caf50">${g.score_a}</span> : <span style="color:#ff9800">${g.score_b}</span>
                </span>
                <div style="text-align:right">
                    <div style="font-size: 10px; font-weight: 800; text-transform: uppercase; color:${statusColor}">${statusText}</div>
                    <span class="subtitle" style="font-weight: 600; font-size:12px;">${new Date(g.date).toLocaleDateString('ru-RU')}</span>
                </div>
            </div>
            <div class="subtitle" style="font-size: 11px; margin-bottom: 12px; display:flex; align-items:center; gap:4px; opacity:0.7">
                <svg style="width:12px;height:12px;fill:currentColor" viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-12-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
                ${g.location}
            </div>
            <div class="flex-between">
                <div class="flex-row" style="gap: 8px;">
                    <div style="width:10px; height:10px; border-radius:50%; background:${teamColor}"></div>
                    <span class="subtitle" style="font-weight:600">${teamLabel}</span>
                </div>
                <span style="color:${resColor}; font-weight: 800; font-size: 16px;">${sign}${g.rating_change} MMR</span>
            </div>
        </div>
        `;
    }).join('');
    
    if(pages.history) pages.history.innerHTML = `<h2>История матчей</h2><p style="padding:0 16px" class="subtitle">Нажмите на карточку для деталей</p>` + listHtml;
}

window.showGameDetails = async function(gameId) {
    loader.style.display = 'flex';
    try {
        const game = await fetchAPI(`/game/${gameId}`);
        
        let html = `
            <div style="text-align:center; margin-bottom:20px;">
                <h2 style="font-size:32px; margin:10px 0;">${game.score_a} : ${game.score_b}</h2>
                <div class="subtitle">${game.location}</div>
                <div class="subtitle">${new Date(game.date).toLocaleString('ru-RU')}</div>
            </div>
            
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
                <div>
                    <h4 style="color:#4caf50; margin-bottom:10px; border-bottom:1px solid rgba(76,175,80,0.2)">Команда А (Зелен)</h4>
                    ${game.team_a.map(p => `
                        <div style="font-size:13px; margin-bottom:4px; display:flex; justify-content:space-between">
                            <span>${p.name}</span>
                            <span style="color:var(--hint-color)">${p.goals > 0 ? `⚽${p.goals}` : ''} ${p.is_mvp ? '🌟' : ''}</span>
                        </div>
                    `).join('')}
                </div>
                <div>
                    <h4 style="color:#ff9800; margin-bottom:10px; border-bottom:1px solid rgba(255,152,0,0.2)">Команда Б (Оранж)</h4>
                    ${game.team_b.map(p => `
                        <div style="font-size:13px; margin-bottom:4px; display:flex; justify-content:space-between">
                            <span>${p.name}</span>
                            <span style="color:var(--hint-color)">${p.goals > 0 ? `⚽${p.goals}` : ''} ${p.is_mvp ? '🌟' : ''}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
            ${game.team_c.length ? `
            <div style="margin-top:20px;">
                <h4 style="color:#3b82f6; margin-bottom:10px; border-bottom:1px solid rgba(59,130,246,0.2)">Команда С (Синие)</h4>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
                    ${game.team_c.map(p => `
                        <div style="font-size:13px; margin-bottom:4px; display:flex; justify-content:space-between">
                            <span>${p.name}</span>
                            <span style="color:var(--hint-color)">${p.goals > 0 ? `⚽${p.goals}` : ''} ${p.is_mvp ? '🌟' : ''}</span>
                        </div>
                    `).join('')}
                </div>
            </div>` : ''}
            <button onclick="closePopup()" class="group-btn" style="margin-top:30px; text-align:center; justify-content:center">Закрыть</button>
        `;
        
        const overlay = document.createElement('div');
        overlay.id = 'details-overlay';
        overlay.style = 'position:fixed; top:0; left:0; right:0; bottom:0; background:var(--bg-color); z-index:2000; padding:24px; overflow-y:auto; animation: fadeIn 0.3s ease;';
        overlay.innerHTML = html;
        document.body.appendChild(overlay);
        
    } catch (e) {
        tg.showAlert('Ошибка: ' + e.message);
    } finally {
        loader.style.display = 'none';
    }
}

window.closePopup = function() {
    const overlay = document.getElementById('details-overlay');
    if(overlay) overlay.remove();
}

// Ads System
async function loadAd() {
    try {
        // If we don't have chat ID yet, pass empty
        let ep = `/ads/random`;
        if (currentChatId) ep += `?chat_id=${currentChatId}`;
        const adRes = await fetchAPI(ep);
        
        if (adRes.status === 'ok') {
            const ad = adRes.ad;
            const adContainer = document.createElement('div');
            adContainer.className = 'card flex-row';
            adContainer.style.background = 'linear-gradient(45deg, rgba(30,30,30,0.8), rgba(60,30,80,0.8))';
            adContainer.style.cursor = 'pointer';
            adContainer.onclick = () => tg.openLink(ad.link);
            
            adContainer.innerHTML = `
                ${ad.image_url ? `<img src="${ad.image_url}" style="width:40px;height:40px;border-radius:8px">` : '📢'}
                <div style="flex:1">
                    <div style="font-size:10px; color:var(--hint-color)">Реклама</div>
                    <div style="font-weight:bold; font-size:14px">${ad.text}</div>
                </div>
            `;
            // Insert at the top of the body (below loader, below group selector)
            document.body.insertBefore(adContainer, document.querySelector('.page-container'));
        }
    } catch (e) {
        console.error("Ad load failed", e);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    init();
    setTimeout(loadAd, 1500); // load ad after UI is stable
});
