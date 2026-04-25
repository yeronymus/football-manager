const tg = window.Telegram.WebApp;
tg.expand();

const API_BASE = '/api';
const initData = tg.initData || ''; 

// State
let currentChatId = null;
let currentTab = 'profile';

// Elements
const loader = document.getElementById('loader');
const groupSelector = document.getElementById('group-selector');
const groupList = document.getElementById('group-list');
const pages = {
    profile: document.getElementById('page-profile'),
    history: document.getElementById('page-history'),
    leaderboard: document.getElementById('page-leaderboard')
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
        await loadCurrentTab();
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
                <button class="group-btn" onclick="selectGroup(${c.id})">${c.title}</button>
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

window.selectGroup = async function(id) {
    currentChatId = id;
    groupSelector.style.display = 'none';
    await loadCurrentTab();
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
        <div class="card flex-row" style="margin-top: 24px; padding: 24px;">
            <div class="avatar">${data.name.charAt(0)}</div>
            <div>
                <h3 style="font-size: 20px;">${data.name}</h3>
                <span class="subtitle">${data.position}</span>
            </div>
        </div>
        
        <div class="flex-row" style="padding: 0 16px; gap: 12px;">
            <div class="card stat-badge" style="margin: 0;">
                <span class="stat-value">${data.rating}</span>
                <span class="subtitle" style="font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">MMR</span>
            </div>
            <div class="card stat-badge" style="margin: 0;">
                <span class="stat-value">${data.games_played}</span>
                <span class="subtitle" style="font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Игр</span>
            </div>
        </div>
        
        <div class="card" style="margin-top: 16px; background: linear-gradient(135deg, rgba(255,215,0,0.1), rgba(255,165,0,0.05)); border-color: rgba(255,215,0,0.2);">
            <div class="flex-between">
                <div>
                    <h4 style="color: gold; font-size: 14px; text-transform: uppercase; margin-bottom: 4px;">🏆 Награды MVP</h4>
                    <span class="subtitle">Лучший игрок матча</span>
                </div>
                <h2 style="color: gold; font-size: 32px; margin:0;">${data.mvp_count}</h2>
            </div>
        </div>
    `;
    if(pages.profile) pages.profile.innerHTML = html;
}

async function renderLeaderboard() {
    const data = await fetchAPI(`/chats/${currentChatId}/leaderboard`);
    
    const listHtml = data.map((p, idx) => `
        <div class="card flex-between">
            <div class="flex-row">
                <div style="font-weight:bold; color:var(--hint-color); width:20px;">${idx+1}</div>
                <div>
                    <div style="font-weight:bold">${p.name}</div>
                    <div class="subtitle">${p.games} игр</div>
                </div>
            </div>
            <div style="font-weight:bold; color:var(--accent-color)">${p.rating}</div>
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
        
        return `
        <div class="card" onclick="showGameDetails(${g.game_id})" style="cursor:pointer; border-left: 4px solid ${resColor};">
            <div class="flex-between" style="margin-bottom: 12px;">
                <span style="font-size: 18px; font-weight: 700; letter-spacing: 1px;">${g.score_a} : ${g.score_b}</span>
                <span class="subtitle" style="font-weight: 600;">${new Date(g.date).toLocaleDateString('ru-RU')}</span>
            </div>
            <div class="flex-between">
                <div class="flex-row" style="gap: 8px;">
                    <span class="subtitle" style="background: rgba(255,255,255,0.05); padding: 2px 8px; border-radius: 6px;">${g.my_team || '-'}</span>
                    <span class="subtitle">Ваша команда</span>
                </div>
                <span style="color:${resColor}; font-weight: 700; font-size: 16px;">${sign}${g.rating_change} MMR</span>
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
        // For MVP, we use Telegram's native popup to show simple details, or we can build an overlay.
        // Let's build a simple alert for now, or you can expand this to a full view.
        let msg = `Счет: ${game.score_a} : ${game.score_b}\n\n`;
        msg += `Команда А:\n` + game.team_a.map(p => `- ${p.name} (Голов: ${p.goals}) ${p.is_mvp ? '🌟' : ''}`).join('\n') + `\n\n`;
        msg += `Команда Б:\n` + game.team_b.map(p => `- ${p.name} (Голов: ${p.goals}) ${p.is_mvp ? '🌟' : ''}`).join('\n');
        
        tg.showAlert(msg);
    } catch (e) {
        tg.showAlert('Ошибка: ' + e.message);
    } finally {
        loader.style.display = 'none';
    }
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
