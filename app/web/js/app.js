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
    leaderboard: document.getElementById('page-leaderboard')
};
const groupNameDisplay = document.getElementById('group-name-display');

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
            if(groupNameDisplay) groupNameDisplay.innerText = groupTitle;
        }
        await loadCurrentTab();
        updateNavState(currentTab);
        Object.values(pages).forEach(p => { if(p) p.style.display = 'none'; });
        if(pages[currentTab]) pages[currentTab].style.display = 'block';
    } else {
        await showGroupSelector();
    }
}

function updateNavState(tabId) {
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    const activeNav = document.querySelector(`[onclick="switchTab('${tabId}')"]`);
    if(activeNav) activeNav.classList.add('active');
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
    if(groupNameDisplay) groupNameDisplay.innerText = title;
    
    // Reset pages display
    Object.values(pages).forEach(p => { if(p) p.style.display = 'none'; });
    if(pages[currentTab]) pages[currentTab].style.display = 'block';
    
    updateNavState(currentTab);
    await loadCurrentTab();
}

window.switchTab = async function(tabId) {
    if (currentTab === tabId && pages[tabId].style.display === 'block') return;
    
    // Update UI
    updateNavState(tabId);
    
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
    const userName = data.name || 'Игрок';
    const html = `
        <div class="card flex-row" style="margin-top: 16px; padding: 24px;">
            <div class="avatar">${userName.charAt(0)}</div>
            <div style="flex:1">
                <h3 style="font-size: 20px;">${userName}</h3>
                <div class="flex-between" style="margin-top:4px;">
                    <span class="subtitle">${data.position}</span>
                    <div onclick="editPosition()" style="padding: 8px 12px; margin: -8px -12px; cursor:pointer;">
                        <span style="color:var(--accent-color); font-weight:600; font-size:13px;">Изменить</span>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="flex-row" style="padding: 0 16px; gap: 12px;">
            <div class="card stat-badge" style="margin: 0;">
                <span class="stat-value">${data.rating}</span>
                <span class="subtitle" style="font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">MMR</span>
            </div>
            <div class="card stat-badge" style="margin: 0; cursor:pointer;" onclick="switchTab('history')">
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

    const userPositions = [data.position, ...(data.alt_positions || [])].filter(Boolean);
    const html = `
        <div id="modal-overlay" style="position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.9); backdrop-filter:blur(15px); z-index:3000; display:flex; align-items:center; justify-content:center; animation: fadeIn 0.2s ease;">
            <div class="card" style="width:90%; max-width:400px; padding:24px; max-height:85vh; overflow-y:auto; border:1px solid rgba(255,255,255,0.1)">
                <h3 style="margin-bottom:8px; text-align:center;">Ваши позиции</h3>
                <p class="subtitle" style="text-align:center; margin-bottom:24px; font-size:13px;">Выберите основную и дополнительные</p>
                
                <div style="display:flex; flex-direction:column; gap:20px;">
                    <div>
                        <h4 class="subtitle" style="font-size:11px; text-transform:uppercase; margin-bottom:10px; color:var(--accent-color)">Защита</h4>
                        <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:8px;">
                            ${['LB', 'CB', 'RB', 'LWB', 'RWB'].map(p => `<button onclick="togglePos('${p}')" id="pos-${p}" class="pos-btn ${userPositions.includes(p) ? 'active' : ''}">${p}</button>`).join('')}
                        </div>
                    </div>
                    
                    <div>
                        <h4 class="subtitle" style="font-size:11px; text-transform:uppercase; margin-bottom:10px; color:var(--accent-color)">Полузащита</h4>
                        <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:8px;">
                            ${['CDM', 'CM', 'CAM', 'LM', 'RM'].map(p => `<button onclick="togglePos('${p}')" id="pos-${p}" class="pos-btn ${userPositions.includes(p) ? 'active' : ''}">${p}</button>`).join('')}
                        </div>
                    </div>

                    <div>
                        <h4 class="subtitle" style="font-size:11px; text-transform:uppercase; margin-bottom:10px; color:var(--accent-color)">Нападение</h4>
                        <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:8px;">
                            ${['ST', 'LW', 'RW', 'CF', 'GK'].map(p => `<button onclick="togglePos('${p}')" id="pos-${p}" class="pos-btn ${userPositions.includes(p) ? 'active' : ''}">${p}</button>`).join('')}
                        </div>
                    </div>
                </div>

                <div style="display:flex; gap:12px; margin-top:32px;">
                    <button onclick="closeModal()" class="group-btn" style="flex:1; justify-content:center; background:rgba(255,255,255,0.05); color:var(--hint-color)">Отмена</button>
                    <button onclick="savePositions()" class="group-btn" style="flex:1; justify-content:center; background:var(--accent-color); color:white">Сохранить</button>
                </div>
            </div>
        </div>
    `;
    
    window.selectedPositions = userPositions;
    const div = document.createElement('div');
    div.id = 'modal-container';
    div.innerHTML = html;
    document.body.appendChild(div);
}

window.togglePos = function(pos) {
    const idx = window.selectedPositions.indexOf(pos);
    if (idx > -1) window.selectedPositions.splice(idx, 1);
    else window.selectedPositions.push(pos);
    
    document.getElementById(`pos-${pos}`).classList.toggle('active');
}

window.savePositions = async function() {
    if (window.selectedPositions.length === 0) {
        tg.showAlert('Выберите хотя бы одну позицию');
        return;
    }
    
    const mainPos = window.selectedPositions[0];
    const alts = window.selectedPositions.slice(1);
    
    closeModal();
    loader.style.display = 'flex';
    try {
        await fetchAPI('/users/me/profile', {
            method: 'POST',
            body: JSON.stringify({
                position: mainPos,
                alt_positions: alts
            })
        });
        await renderProfile();
    } catch(e) {
        tg.showAlert('Ошибка: ' + e.message);
    } finally {
        loader.style.display = 'none';
    }
}

window.closeModal = function() {
    const modal = document.getElementById('modal-container');
    if(modal) modal.remove();
}

async function updatePosition(pos) {
    closeModal();
    loader.style.display = 'flex';
    try {
        await fetchAPI('/users/me/profile', {
            method: 'POST',
            body: JSON.stringify({position: pos})
        });
        await renderProfile();
    } catch(e) {
        tg.showAlert('Ошибка: ' + e.message);
    } finally {
        loader.style.display = 'none';
    }
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
            <div style="text-align:center; margin-bottom:30px;">
                <h1 style="font-size:48px; margin:10px 0; font-weight:900; letter-spacing:-1px;">${game.score_a} : ${game.score_b}</h1>
                <div class="subtitle" style="font-size:16px; margin-bottom:4px;">📍 ${game.location}</div>
                <div class="subtitle" style="font-size:14px;">📅 ${new Date(game.date).toLocaleString('ru-RU')}</div>
            </div>
            
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:24px;">
                <div style="background: rgba(76, 175, 80, 0.05); padding: 16px; border-radius: 16px; border: 1px solid rgba(76, 175, 80, 0.1);">
                    <h4 style="color:#4caf50; margin-bottom:12px; border-bottom:1px solid rgba(76,175,80,0.2); padding-bottom:8px; font-weight:800; font-size:14px; text-transform:uppercase;">Зеленые (A)</h4>
                    ${game.team_a.map(p => `
                        <div style="font-size:15px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center">
                            <span style="font-weight:500">${p.name}</span>
                            <span style="display:flex; align-items:center; gap:4px">
                                ${p.goals > 0 ? `<span style="font-size:12px">⚽${p.goals}</span>` : ''} 
                                ${p.is_mvp ? '<span style="font-size:12px">🌟</span>' : ''}
                            </span>
                        </div>
                    `).join('')}
                </div>
                <div style="background: rgba(255, 152, 0, 0.05); padding: 16px; border-radius: 16px; border: 1px solid rgba(255, 152, 0, 0.1);">
                    <h4 style="color:#ff9800; margin-bottom:12px; border-bottom:1px solid rgba(255,152,0,0.2); padding-bottom:8px; font-weight:800; font-size:14px; text-transform:uppercase;">Оранжевые (B)</h4>
                    ${game.team_b.map(p => `
                        <div style="font-size:15px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center">
                            <span style="font-weight:500">${p.name}</span>
                            <span style="display:flex; align-items:center; gap:4px">
                                ${p.goals > 0 ? `<span style="font-size:12px">⚽${p.goals}</span>` : ''} 
                                ${p.is_mvp ? '<span style="font-size:12px">🌟</span>' : ''}
                            </span>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            ${game.team_c && game.team_c.length ? `
            <div style="margin-top:24px; background: rgba(59, 130, 246, 0.05); padding: 16px; border-radius: 16px; border: 1px solid rgba(59, 130, 246, 0.1);">
                <h4 style="color:#3b82f6; margin-bottom:12px; border-bottom:1px solid rgba(59,130,246,0.2); padding-bottom:8px; font-weight:800; font-size:14px; text-transform:uppercase;">Синие (C)</h4>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
                    ${game.team_c.map(p => `
                        <div style="font-size:14px; display:flex; justify-content:space-between">
                            <span>${p.name}</span>
                            <span>${p.goals > 0 ? `⚽${p.goals}` : ''} ${p.is_mvp ? '🌟' : ''}</span>
                        </div>
                    `).join('')}
                </div>
            </div>` : ''}
            
            <button onclick="closePopup()" class="group-btn" style="margin-top:40px; height:56px; font-size:18px; justify-content:center; background:var(--accent-color); color:white;">Закрыть</button>
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
        document.body.style.overflow = 'hidden'; // Prevent background scroll
        
    } catch (e) {
        tg.showAlert('Ошибка: ' + e.message);
    } finally {
        loader.style.display = 'none';
    }
}

window.closePopup = function() {
    const overlay = document.getElementById('details-overlay');
    if(overlay) overlay.remove();
    document.body.style.overflow = '';
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
