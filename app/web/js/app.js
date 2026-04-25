
let currentChatId = null;
let currentTab = 'profile';
const tg = window.Telegram.WebApp;
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
    tg.expand();
    tg.ready();
    
    const urlParams = new URLSearchParams(window.location.search);
    const urlChatId = urlParams.get('chat_id');
    
    try {
        const chats = await fetchAPI('/chats');
        const selector = document.getElementById('group-selector');
        
        if (chats.length === 0) {
            document.body.innerHTML = '<div class="card" style="margin:20px;text-align:center">Вы не состоите ни в одной группе бота.</div>';
            return;
        }

        if (urlChatId) {
            currentChatId = urlChatId;
        } else {
            currentChatId = chats[0].id;
        }

        const currentChat = chats.find(c => c.id == currentChatId) || chats[0];
        const groupDisplay = document.getElementById('group-name-display');
        if (groupDisplay) groupDisplay.innerText = currentChat.title;
        
        const header = document.getElementById('group-header');
        if (header) header.style.display = 'flex';
        
        await switchTab(currentTab);
    } catch (e) {
        console.error(e);
        loader.style.display = 'none';
        document.body.innerHTML = `
            <div class="card" style="margin:20px; text-align:center;">
                <h3 style="color:#f44336">Ошибка загрузки</h3>
                <p class="subtitle">${e.message}</p>
                <button onclick="location.reload()" class="group-btn" style="margin-top:20px; background:var(--accent-color); color:white; justify-content:center;">Попробовать снова</button>
            </div>
        `;
    }
}

async function switchTab(tab) {
    currentTab = tab;
    Object.values(pages).forEach(p => p.classList.remove('active'));
    pages[tab].classList.add('active');
    document.querySelectorAll('.nav-item').forEach(t => t.classList.remove('active'));
    const activeNav = document.querySelector(`.nav-item[onclick*="switchTab('${tab}')"]`);
    if (activeNav) activeNav.classList.add('active');
    
    loader.style.display = 'flex';
    if (tab === 'profile') await renderProfile();
    else if (tab === 'leaderboard') await renderLeaderboard();
    else if (tab === 'history') await renderHistory();
    loader.style.display = 'none';
}

async function renderProfile() {
    const data = await fetchAPI(`/users/me/profile?chat_id=${currentChatId}`);
    
    const userName = data.name || 'Игрок';
    const html = `
        <div class="card flex-row" style="margin-top: 16px; padding: 24px;">
            <div class="avatar">${userName.charAt(0)}</div>
            <div style="flex:1">
                <h3 style="font-size: 20px;">${userName}</h3>
                <div class="subtitle" style="margin-top:4px;">
                    Основная: <b style="color:var(--text-color)">${data.position}</b>
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
            <div style="margin-bottom:16px; border-bottom:1px solid var(--border-color); padding-bottom:12px;">
                <h4 class="subtitle" style="text-transform:uppercase; font-weight:700; font-size:11px; margin-bottom:8px; color:var(--accent-color)">Основная позиция</h4>
                <div class="flex-between">
                    <span style="font-weight:600; font-size:17px;">${data.position}</span>
                    <button onclick="editPrimaryPosition()" style="background:var(--accent-color); color:white; border:none; padding:6px 16px; border-radius:8px; font-weight:600; font-size:12px; cursor:pointer;">Изменить</button>
                </div>
            </div>
            
            <div style="margin-bottom:16px; border-bottom:1px solid var(--border-color); padding-bottom:12px;">
                <h4 class="subtitle" style="text-transform:uppercase; font-weight:700; font-size:11px; margin-bottom:8px; color:var(--accent-color)">Доп. позиции</h4>
                <div class="flex-between">
                    <span style="font-weight:600; font-size:15px;">${data.alt_positions && data.alt_positions.length ? data.alt_positions.join(', ') : 'Не указаны'}</span>
                    <button onclick="editAltPositions()" style="background:rgba(255,255,255,0.05); color:var(--text-color); border:1px solid var(--border-color); padding:6px 16px; border-radius:8px; font-weight:600; font-size:12px; cursor:pointer;">Изменить</button>
                </div>
            </div>

            <div class="flex-between">
                <h4 class="subtitle" style="text-transform:uppercase; font-weight:700; font-size:11px;">Всего голов</h4>
                <span style="font-weight:700; font-size:18px; color:var(--accent-color)">${data.total_goals || 0} ⚽</span>
            </div>
        </div>
    `;
    if(pages.profile) pages.profile.innerHTML = html;
}

window.editPrimaryPosition = function() {
    const positions = ['GK', 'LB', 'CB', 'RB', 'LWB', 'RWB', 'CDM', 'CM', 'CAM', 'LM', 'RM', 'LW', 'RW', 'ST', 'CF'];
    const html = `
        <div id="modal-overlay" style="position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.9); backdrop-filter:blur(15px); z-index:3000; display:flex; align-items:center; justify-content:center; animation: fadeIn 0.2s ease;">
            <div class="card" style="width:90%; max-width:400px; padding:24px; max-height:85vh; overflow-y:auto; border:1px solid rgba(255,255,255,0.1)">
                <h3 style="margin-bottom:8px; text-align:center;">Основная позиция</h3>
                <p class="subtitle" style="text-align:center; margin-bottom:24px; font-size:13px;">Выберите вашу главную роль на поле</p>
                <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px;">
                    ${positions.map(p => `<button onclick="savePrimary('${p}')" class="pos-btn">${p}</button>`).join('')}
                </div>
                <button onclick="closeModal()" style="margin-top:24px; width:100%; color:var(--hint-color); background:none; border:none; cursor:pointer; font-weight:600;">Отмена</button>
            </div>
        </div>
    `;
    renderModal(html);
}

window.editAltPositions = async function() {
    loader.style.display = 'flex';
    const data = await fetchAPI(`/users/me/profile?chat_id=${currentChatId}`);
    loader.style.display = 'none';
    
    const currentAlts = data.alt_positions || [];
    const positions = ['GK', 'LB', 'CB', 'RB', 'LWB', 'RWB', 'CDM', 'CM', 'CAM', 'LM', 'RM', 'LW', 'RW', 'ST', 'CF'];
    
    const html = `
        <div id="modal-overlay" style="position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.9); backdrop-filter:blur(15px); z-index:3000; display:flex; align-items:center; justify-content:center; animation: fadeIn 0.2s ease;">
            <div class="card" style="width:90%; max-width:400px; padding:24px; max-height:85vh; overflow-y:auto; border:1px solid rgba(255,255,255,0.1)">
                <h3 style="margin-bottom:8px; text-align:center;">Доп. позиции</h3>
                <p class="subtitle" style="text-align:center; margin-bottom:24px; font-size:13px;">Выберите позиции, на которых также играете</p>
                <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px;">
                    ${positions.map(p => `<button onclick="toggleAlt('${p}')" id="alt-${p}" class="pos-btn ${currentAlts.includes(p) ? 'active' : ''}">${p}</button>`).join('')}
                </div>
                <div style="display:flex; gap:12px; margin-top:32px;">
                    <button onclick="closeModal()" class="group-btn" style="flex:1; justify-content:center; background:rgba(255,255,255,0.05); color:var(--hint-color); border:1px solid var(--border-color)">Отмена</button>
                    <button onclick="saveAlts()" class="group-btn" style="flex:1; justify-content:center; background:var(--accent-color); color:white">Сохранить</button>
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
        await renderProfile();
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
        const profile = await fetchAPI(`/users/me/profile?chat_id=${currentChatId}`);
        await fetchAPI('/users/me/profile', {
            method: 'POST',
            body: JSON.stringify({ 
                position: profile.position,
                alt_positions: alts 
            })
        });
        await renderProfile();
    } catch(e) { tg.showAlert(e.message); }
    finally { loader.style.display = 'none'; }
}

window.closeModal = function() {
    const modal = document.getElementById('modal-container');
    if(modal) modal.remove();
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

        const isOtherGroup = !g.is_current_group;

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
            ${isOtherGroup ? `<div style="font-size:10px; color:var(--accent-color); margin-bottom:8px; font-weight:700">📌 ГРУППА: ${g.group_title}</div>` : ''}
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
    
    if(pages.history) pages.history.innerHTML = `<h2>История матчей</h2><p style="padding:0 16px" class="subtitle">Ниже показаны все ваши игры в системе</p>` + listHtml;
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
        document.body.style.overflow = 'hidden'; 
        
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

async function loadAd() {
    try {
        let ep = `/ads/random`;
        if (currentChatId) ep += `?chat_id=${currentChatId}`;
        const adRes = await fetchAPI(ep);
        
        if (adRes.status === 'ok') {
            const ad = adRes.ad;
            const adContainer = document.createElement('div');
            adContainer.className = 'card flex-row';
            adContainer.style.background = 'linear-gradient(45deg, rgba(30,30,30,0.8), rgba(60,30,80,0.8))';
            adContainer.style.cursor = 'pointer';
            adContainer.style.margin = '16px';
            adContainer.onclick = () => tg.openLink(ad.link);
            
            adContainer.innerHTML = `
                ${ad.image_url ? `<img src="${ad.image_url}" style="width:40px;height:40px;border-radius:8px">` : '📢'}
                <div style="flex:1">
                    <div style="font-size:10px; color:var(--hint-color)">Реклама</div>
                    <div style="font-weight:bold; font-size:14px">${ad.text}</div>
                </div>
            `;
            document.body.insertBefore(adContainer, document.querySelector('.page-container'));
        }
    } catch (e) {
        console.error("Ad load failed", e);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    init();
    setTimeout(loadAd, 1500);
});
