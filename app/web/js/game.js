const tg = window.Telegram ? window.Telegram.WebApp : null;
if (tg) {
    tg.expand();
    tg.ready();
}

const urlParams = new URLSearchParams(window.location.search);
const gameId = urlParams.get('game_id');
let chatId = urlParams.get('chat_id');
let currentUserProfile = null;
let currentGame = null;

const loader = document.getElementById('loader');

async function fetchAPI(endpoint, options = {}) {
    const initData = tg ? tg.initData : '';
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `tma ${initData}`
    };
    
    const response = await fetch('/api' + endpoint, {
        ...options,
        headers: { ...headers, ...options.headers }
    });
    
    if (response.status === 404 && endpoint.includes('/users/me/profile')) {
        // Unregistered user - throw specific error to catch and redirect
        throw new Error('USER_NOT_REGISTERED');
    }
    
    if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Ошибка API');
    }
    return await response.json();
}

async function init() {
    if (!gameId) {
        showError('Не указан ID игры. Пожалуйста, откройте Mini App по правильной ссылке.');
        return;
    }

    // Wait for initData
    let retryCount = 0;
    while (tg && !tg.initData && retryCount < 5) {
        await new Promise(r => setTimeout(r, 200));
        retryCount++;
    }

    try {
        // 1. Fetch game details first to get chat_id if not present in URL
        currentGame = await fetchAPI(`/game/${gameId}`);
        if (currentGame && currentGame.chat_id) {
            chatId = currentGame.chat_id;
        }

        // 2. Fetch User Profile to verify registration and load stats
        try {
            currentUserProfile = await fetchAPI(`/users/me/profile?chat_id=${chatId}`);
        } catch (profileError) {
            if (profileError.message === 'USER_NOT_REGISTERED') {
                // Redirect user to register screen
                let registerUrl = `/web/register.html?game_id=${gameId}`;
                if (chatId) registerUrl += `&chat_id=${chatId}`;
                window.location.href = registerUrl;
                return;
            }
            throw profileError;
        }

        // 3. Render everything
        renderGameHeader();
        renderStatusInfo();
        renderAchievements();
        renderRosters();
        setupActionButtons();

        // 4. Load Ads
        await loadAds();

    } catch (e) {
        console.error("Init error:", e);
        showError(e.message === 'Failed to fetch' || e.message === 'Load failed'
            ? "Нет связи с бэкендом. Проверьте сеть."
            : e.message
        );
    } finally {
        if (loader) loader.style.display = 'none';
    }
}

function renderGameHeader() {
    document.getElementById('game-label').innerText = `Матч #${currentGame.id}`;
    
    // Status
    const statusText = currentGame.status === 'open' ? 'ОТКРЫТ' : (currentGame.status === 'active' ? 'АКТИВЕН' : 'ЗАВЕРШЕН');
    const statusBadge = document.getElementById('game-status-badge');
    statusBadge.innerText = statusText;
    if (currentGame.status === 'finished') {
        statusBadge.style.background = 'rgba(244, 67, 54, 0.15)';
        statusBadge.style.color = '#ef4444';
    }

    document.getElementById('game-location').innerText = `📍 ${currentGame.location}`;
    
    // Date & Time
    const dt = new Date(currentGame.date);
    document.getElementById('game-date').innerText = `📅 ${dt.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Prague' })}`;
    
    // Price and Format
    document.getElementById('game-price').innerText = `${currentGame.price} CZK`;
    
    // Main players count for game format
    const formatCount = currentGame.main_players_count ? (currentGame.main_players_count / 2) : 11;
    document.getElementById('game-format').innerText = `${formatCount}х${formatCount}`;

    // Payment details
    document.getElementById('game-payment').innerText = currentGame.payment_info || 'Оплата наличными на месте';
}

function renderStatusInfo() {
    const statusCard = document.getElementById('status-info-card');
    const descText = document.getElementById('status-info-desc');
    
    // GK Reservation countdown warning
    const now = new Date();
    const created = currentGame.created_at ? new Date(currentGame.created_at) : null;
    let gkReserved = false;

    if (created && currentGame.gk_hours > 0) {
        const hoursPassed = (now - created) / (3600 * 1000);
        if (hoursPassed < currentGame.gk_hours) {
            gkReserved = true;
            const hoursLeft = Math.ceil(currentGame.gk_hours - hoursPassed);
            descText.innerText = `🧤 Внимание! Первые ${currentGame.gk_hours} ч. (${hoursLeft} ч. осталось) места в основе гарантированы вратарям (GK).`;
            statusCard.style.display = 'block';
        }
    }
    
    // Match closed status
    if (currentGame.status === 'finished') {
        descText.innerText = `Этот матч уже сыгран. Результаты: ${currentGame.score_a || 0} : ${currentGame.score_b || 0}.`;
        statusCard.style.display = 'block';
        statusCard.style.background = 'rgba(244,67,54,0.05)';
        statusCard.style.borderColor = 'rgba(244,67,54,0.2)';
        document.getElementById('status-info-title').style.color = '#ef4444';
        document.getElementById('status-info-title').innerText = 'Матч завершен';
    }
}

function renderAchievements() {
    // 1. Veteran
    const games = currentUserProfile.games_played || 0;
    const vetCard = document.getElementById('ach-veteran');
    const vetIcon = document.getElementById('ach-veteran-icon');
    const vetTitle = document.getElementById('ach-veteran-title');
    const vetDesc = document.getElementById('ach-veteran-desc');
    
    if (games >= 50) {
        vetCard.classList.add('unlocked');
        vetIcon.innerText = '👑';
        vetTitle.innerText = 'Легенда Клуба';
        vetDesc.innerText = `${games} игр сыграно`;
    } else if (games >= 10) {
        vetCard.classList.add('unlocked');
        vetIcon.innerText = '🏆';
        vetTitle.innerText = 'Опытный Боец';
        vetDesc.innerText = `${games} игр сыграно`;
    } else if (games >= 1) {
        vetCard.classList.add('unlocked');
        vetIcon.innerText = '⚔️';
        vetTitle.innerText = 'Ветеран';
        vetDesc.innerText = `${games} игр сыграно`;
    } else {
        vetDesc.innerText = 'Сыграй 1-ю игру';
    }

    // 2. Goleador
    const goals = currentUserProfile.total_goals || 0;
    const golCard = document.getElementById('ach-goleador');
    const golIcon = document.getElementById('ach-goleador-icon');
    const golTitle = document.getElementById('ach-goleador-title');
    const golDesc = document.getElementById('ach-goleador-desc');
    
    if (goals >= 50) {
        golCard.classList.add('unlocked');
        golIcon.innerText = '👑';
        golTitle.innerText = 'Золотая Бутса';
        golDesc.innerText = `${goals} голов забито`;
    } else if (goals >= 10) {
        golCard.classList.add('unlocked');
        golIcon.innerText = '🏆';
        golTitle.innerText = 'Супер-Бомбардир';
        golDesc.innerText = `${goals} голов забито`;
    } else if (goals >= 1) {
        golCard.classList.add('unlocked');
        golIcon.innerText = '🥅';
        golTitle.innerText = 'С первого касания';
        golDesc.innerText = `${goals} голов забито`;
    } else {
        golDesc.innerText = 'Забей первый гол';
    }

    // 3. MVP
    const mvps = currentUserProfile.mvp_count || 0;
    const mvpCard = document.getElementById('ach-mvp');
    const mvpIcon = document.getElementById('ach-mvp-icon');
    const mvpTitle = document.getElementById('ach-mvp-title');
    const mvpDesc = document.getElementById('ach-mvp-desc');
    
    if (mvps >= 5) {
        mvpCard.classList.add('unlocked');
        mvpIcon.innerText = '👑';
        mvpTitle.innerText = 'Абсолютная Звезда';
        mvpDesc.innerText = `${mvps} наград MVP`;
    } else if (mvps >= 1) {
        mvpCard.classList.add('unlocked');
        mvpIcon.innerText = '🌟';
        mvpTitle.innerText = 'Лучший Игрок';
        mvpDesc.innerText = `${mvps} наград MVP`;
    } else {
        mvpDesc.innerText = 'Стань MVP матча';
    }

    // 4. Rating (MMR)
    const rating = currentUserProfile.rating || 100;
    const ratCard = document.getElementById('ach-rating');
    const ratIcon = document.getElementById('ach-rating-icon');
    const ratTitle = document.getElementById('ach-rating-title');
    const ratDesc = document.getElementById('ach-rating-desc');
    
    if (rating >= 200) {
        ratCard.classList.add('unlocked');
        ratIcon.innerText = '⚡';
        ratTitle.innerText = 'Сверхзвуковой';
        ratDesc.innerText = `Рейтинг: ${rating} MMR`;
    } else if (rating >= 150) {
        ratCard.classList.add('unlocked');
        ratIcon.innerText = '🔥';
        ratTitle.innerText = 'Гроза Авторитетов';
        ratDesc.innerText = `Рейтинг: ${rating} MMR`;
    } else if (rating >= 120) {
        ratCard.classList.add('unlocked');
        ratIcon.innerText = '🦾';
        ratTitle.innerText = 'Мастер';
        ratDesc.innerText = `Рейтинг: ${rating} MMR`;
    } else {
        ratCard.classList.add('unlocked');
        ratIcon.innerText = '⚽';
        ratTitle.innerText = 'Рядовой';
        ratDesc.innerText = `Рейтинг: ${rating} MMR`;
    }
}

function renderRosters() {
    // 1. Collect all active players (A, B, C and unassigned but status == active)
    let activePlayers = [];
    
    if (currentGame.team_a) activePlayers = activePlayers.concat(currentGame.team_a);
    if (currentGame.team_b) activePlayers = activePlayers.concat(currentGame.team_b);
    if (currentGame.team_c) activePlayers = activePlayers.concat(currentGame.team_c);
    if (currentGame.unassigned) activePlayers = activePlayers.concat(currentGame.unassigned);
    
    // Remove duplicates just in case
    const activeMap = new Map();
    activePlayers.forEach(p => activeMap.set(p.id, p));
    activePlayers = Array.from(activeMap.values());

    // 2. Sort active players by rating descending
    activePlayers.sort((a, b) => b.rating - a.rating);

    // 3. Sort reserve players by rating descending
    let reservePlayers = currentGame.reserve || [];
    reservePlayers.sort((a, b) => b.rating - a.rating);

    // 4. Render Active Players list
    const activeList = document.getElementById('roster-active');
    activeList.innerHTML = '';
    
    if (activePlayers.length === 0) {
        activeList.innerHTML = '<div style="text-align:center; padding: 20px; color:var(--hint-color); font-size:14px;">Никто еще не записался. Будь первым!</div>';
    } else {
        activePlayers.forEach((p, idx) => {
            const isMe = p.id === currentUserProfile.user_id;
            activeList.innerHTML += `
                <div class="player-row flex-between ${isMe ? 'current-user' : ''}">
                    <div class="flex-row" style="gap:10px;">
                        <span class="player-rank">${idx + 1}</span>
                        <div>
                            <span style="font-weight:600; font-size:15px;">${p.name} ${isMe ? '<b style="color:var(--accent-color)">(Вы)</b>' : ''}</span>
                            <div style="margin-top:2px; display:flex; gap:6px; align-items:center;">
                                <span class="player-pos-badge">${p.position}</span>
                                ${p.is_paid ? '<span style="font-size:10px; color:#4caf50">✅ Оплачено</span>' : ''}
                            </div>
                        </div>
                    </div>
                    <span class="player-rating">${p.rating}</span>
                </div>
            `;
        });
    }

    // 5. Update counts
    document.getElementById('active-count').innerText = `${activePlayers.length} / ${currentGame.max_players}`;

    // 6. Render Reserve list
    const reserveList = document.getElementById('roster-reserve');
    const reserveHeader = document.getElementById('reserve-header');
    reserveList.innerHTML = '';

    if (reservePlayers.length > 0) {
        reserveHeader.style.display = 'flex';
        reservePlayers.forEach((p, idx) => {
            const isMe = p.id === currentUserProfile.user_id;
            reserveList.innerHTML += `
                <div class="player-row flex-between ${isMe ? 'current-user' : ''}" style="background: rgba(255,152,0,0.03);">
                    <div class="flex-row" style="gap:10px;">
                        <span class="player-rank" style="color:#ff9800">${idx + 1}</span>
                        <div>
                            <span style="font-weight:600; font-size:15px;">${p.name} ${isMe ? '<b style="color:var(--accent-color)">(Вы)</b>' : ''}</span>
                            <div style="margin-top:2px;"><span class="player-pos-badge">${p.position}</span></div>
                        </div>
                    </div>
                    <span class="player-rating" style="color:#ff9800">${p.rating}</span>
                </div>
            `;
        });
        document.getElementById('reserve-count').innerText = reservePlayers.length;
    } else {
        reserveHeader.style.display = 'none';
    }
}

function setupActionButtons() {
    const actionBtn = document.getElementById('action-btn');
    const leaveBtn = document.getElementById('leave-btn');

    // Check if game is open/active
    const isFinished = currentGame.status === 'finished';
    if (isFinished) {
        actionBtn.disabled = true;
        actionBtn.style.opacity = 0.5;
        actionBtn.innerHTML = '<span>Матч завершен</span>';
        leaveBtn.style.display = 'none';
        return;
    }

    // Check if current user is signed up
    let isSignedUp = false;
    let isReserve = false;

    // Check active
    if (currentGame.team_a && currentGame.team_a.some(p => p.id === currentUserProfile.user_id)) isSignedUp = true;
    if (currentGame.team_b && currentGame.team_b.some(p => p.id === currentUserProfile.user_id)) isSignedUp = true;
    if (currentGame.team_c && currentGame.team_c.some(p => p.id === currentUserProfile.user_id)) isSignedUp = true;
    if (currentGame.unassigned && currentGame.unassigned.some(p => p.id === currentUserProfile.user_id)) isSignedUp = true;
    
    // Check reserve
    if (currentGame.reserve && currentGame.reserve.some(p => p.id === currentUserProfile.user_id)) {
        isSignedUp = true;
        isReserve = true;
    }

    if (isSignedUp) {
        actionBtn.style.background = '#4caf50';
        actionBtn.style.boxShadow = '0 8px 20px rgba(76,175,80,0.3)';
        actionBtn.disabled = true;
        actionBtn.innerHTML = isReserve 
            ? '<span>🧤 Вы записаны в резерв!</span>' 
            : '<span>✅ Вы в основном составе!</span>';
        
        leaveBtn.style.display = 'flex';
        leaveBtn.onclick = handleLeave;
    } else {
        // Determine whether user will join active or reserve
        let activeCount = 0;
        if (currentGame.team_a) activeCount += currentGame.team_a.length;
        if (currentGame.team_b) activeCount += currentGame.team_b.length;
        if (currentGame.team_c) activeCount += currentGame.team_c.length;
        if (currentGame.unassigned) activeCount += currentGame.unassigned.length;
        
        const willBeReserve = activeCount >= currentGame.max_players;

        actionBtn.disabled = false;
        actionBtn.style.background = willBeReserve ? '#ff9800' : 'var(--accent-color)';
        actionBtn.style.boxShadow = willBeReserve ? '0 8px 20px rgba(255,152,0,0.3)' : '0 8px 20px rgba(56,189,248,0.3)';
        actionBtn.innerHTML = willBeReserve
            ? '<span>🧤 Записаться в резерв</span>'
            : '<span>⚽ Записаться на игру</span>';
        actionBtn.onclick = handleJoin;
        
        leaveBtn.style.display = 'none';
    }
}

async function handleJoin() {
    loader.style.display = 'flex';
    try {
        const res = await fetchAPI(`/game/${gameId}/join`, { method: 'POST' });
        
        if (tg) {
            tg.HapticFeedback.notificationOccurred('success');
            tg.showConfirm(res.message || "Вы успешно записались!");
        } else {
            alert(res.message || "Вы успешно записались!");
        }
        
        // Refresh
        currentGame = await fetchAPI(`/game/${gameId}`);
        renderRosters();
        setupActionButtons();
    } catch(e) {
        if (tg) tg.showAlert(e.message);
        else alert(e.message);
    } finally {
        loader.style.display = 'none';
    }
}

async function handleLeave() {
    if (tg) {
        tg.showConfirm("Вы уверены, что хотите выписаться?", async (confirmed) => {
            if (confirmed) {
                await executeLeave();
            }
        });
    } else {
        if (confirm("Вы уверены, что хотите выписаться?")) {
            await executeLeave();
        }
    }
}

async function executeLeave() {
    loader.style.display = 'flex';
    try {
        const res = await fetchAPI(`/game/${gameId}/leave`, { method: 'POST' });
        
        if (tg) {
            tg.HapticFeedback.notificationOccurred('success');
            tg.showConfirm(res.message || "Вы выписались с игры.");
        } else {
            alert(res.message || "Вы выписались с игры.");
        }
        
        // Refresh
        currentGame = await fetchAPI(`/game/${gameId}`);
        renderRosters();
        setupActionButtons();
    } catch(e) {
        if (tg) tg.showAlert(e.message);
        else alert(e.message);
    } finally {
        loader.style.display = 'none';
    }
}

async function loadAds() {
    const topAd = document.getElementById('ad-banner-top');
    const bottomAd = document.getElementById('ad-banner-bottom');
    
    try {
        let endpoint = `/ads/random`;
        if (chatId) endpoint += `?chat_id=${chatId}`;
        
        const adRes = await fetchAPI(endpoint);
        
        if (adRes.status === 'ok' && adRes.ad) {
            const ad = adRes.ad;
            
            const html = `
                <div class="card flex-row" style="margin: 0; padding: 12px; background: linear-gradient(135deg, rgba(30,30,40,0.8), rgba(60,30,80,0.8)); cursor:pointer;" onclick="openAdLink('${ad.link}')">
                    ${ad.image_url ? `<img src="${ad.image_url}" style="width:40px;height:40px;border-radius:8px;object-fit:cover;margin-right:12px;">` : '<span style="font-size:24px;margin-right:12px;">📢</span>'}
                    <div style="flex:1">
                        <div style="font-size:9px; color:var(--hint-color); text-transform:uppercase; letter-spacing:0.5px;">Спонсорская Реклама</div>
                        <div style="font-weight:bold; font-size:13px; color:var(--text-color); margin-top:2px;">${ad.text}</div>
                    </div>
                </div>
            `;
            
            // Show at the top and bottom
            topAd.innerHTML = html;
            topAd.style.display = 'block';
            
            bottomAd.innerHTML = html;
            bottomAd.style.display = 'block';
        }
    } catch(e) {
        console.warn("Sponsor ads load failed:", e);
    }
}

window.openAdLink = function(url) {
    if (tg) {
        tg.openLink(url);
    } else {
        window.open(url, '_blank');
    }
}

function showError(msg) {
    document.body.innerHTML = `
        <div class="card" style="margin:20px; text-align:center;">
            <h3 style="color:#ef4444">Ошибка</h3>
            <p class="subtitle" style="margin-top:8px;">${msg}</p>
            <button onclick="location.reload()" class="btn-join" style="margin-top:20px; background:var(--accent-color); color:white; justify-content:center;">Попробовать снова</button>
            <button onclick="window.Telegram.WebApp.close()" class="pos-btn" style="width:100%; margin-top:10px; background:transparent; border:none; color:var(--hint-color); font-weight:600; font-size:12px;">Закрыть</button>
        </div>
    `;
}

document.addEventListener("DOMContentLoaded", init);
