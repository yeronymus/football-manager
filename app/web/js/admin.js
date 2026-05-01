let initData = "";
let currentGroupId = null;

document.addEventListener('DOMContentLoaded', () => {
    if (window.Telegram && window.Telegram.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        initData = window.Telegram.WebApp.initData;
    }
    
    // For local dev without TG:
    if (!initData) {
        console.warn("No initData found. If in browser, API calls may fail.");
    }

    loadGroups();
});

let currentGameId = null;

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

// API Helper
async function apiCall(endpoint, options = {}) {
    const headers = {
        'Authorization': `tma ${initData}`,
        'Content-Type': 'application/json'
    };
    
    const url = `/api/dashboard${endpoint}`;
    const response = await fetch(url, { ...options, headers });
    
    if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
    }
    
    return response.json();
}

// Load Data
async function loadGroups() {
    const listEl = document.getElementById('groups-list');
    listEl.innerHTML = '<div class="loading-spinner"></div>';
    
    try {
        const groups = await apiCall('/groups');
        listEl.innerHTML = '';
        
        if (groups.length === 0) {
            listEl.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:20px">No groups found.</p>';
            return;
        }

        groups.forEach(g => {
            const el = document.createElement('div');
            el.className = 'group-item';
            el.id = `group-item-${g.chat_id}`;
            el.innerHTML = `
                <h3>${g.title}</h3>
                <p>ID: ${g.chat_id}</p>
            `;
            el.onclick = () => {
                document.querySelectorAll('.group-item').forEach(i => i.classList.remove('active'));
                el.classList.add('active');
                loadGroupGames(g);
            };
            listEl.appendChild(el);
        });

        // Auto-select if only 1 group
        if (groups.length === 1) {
            const firstEl = document.getElementById(`group-item-${groups[0].chat_id}`);
            if (firstEl) firstEl.click();
        }
        
    } catch (e) {
        listEl.innerHTML = `<p style="color:var(--danger)">Failed to load groups.</p>`;
    }
}

async function loadGroupGames(group) {
    currentGroupId = group.chat_id;
    currentGroupId = group.chat_id;
    switchView('view-group');
    
    document.getElementById('group-title').textContent = group.title;
    
    // Setup Settings
    document.getElementById('group-settings-container').classList.remove('hidden');
    document.getElementById('setting-lang').value = group.language || 'ru';
    document.getElementById('setting-price').value = group.payment_info || '';
    
    const listEl = document.getElementById('games-list');
    listEl.innerHTML = '<div class="loading-spinner"></div>';
    
    try {
        const games = await apiCall(`/groups/${currentGroupId}/games`);
        listEl.innerHTML = '';
        
        if (games.length === 0) {
            listEl.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:40px">No games found for this group.</p>';
            return;
        }
        
        games.forEach(g => {
            const el = document.createElement('div');
            el.className = 'game-card';
            
            const dateStr = new Date(g.date_time).toLocaleString('en-GB', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'});
            
            el.innerHTML = `
                <div class="game-info">
                    <h3>${g.location}</h3>
                    <p>${dateStr} • Players: ${g.players_count}/${g.max_players}</p>
                </div>
                <div class="badge ${g.status}">${g.status}</div>
            `;
            
            el.onclick = () => loadGameDetails(g.id);
            listEl.appendChild(el);
        });
        
    } catch (e) {
        listEl.innerHTML = `<p style="color:var(--danger)">Failed to load games.</p>`;
    }
}

async function loadGameDetails(gameId) {
    currentGameId = gameId;
    switchView('view-game');
    document.getElementById('players-list').innerHTML = '<div class="loading-spinner"></div>';
    
    try {
        const game = await apiCall(`/games/${gameId}`);
        
        const dateStr = new Date(game.date_time).toLocaleString('en-GB', {day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'});
        document.getElementById('game-title').textContent = `${game.location} (${dateStr})`;
        
        const badge = document.getElementById('game-status-badge');
        badge.className = `badge ${game.status}`;
        badge.textContent = game.status;
        
        document.getElementById('game-stat-players').textContent = `${game.players.length}`;
        document.getElementById('game-stat-price').textContent = game.price;
        
        const paidCount = game.players.filter(p => p.is_paid).length;
        document.getElementById('game-stat-paid').textContent = `${paidCount}/${game.players.length}`;
        
        const listEl = document.getElementById('players-list');
        listEl.innerHTML = '';
        
        game.players.forEach(p => {
            const el = document.createElement('div');
            el.className = 'player-item';
            
            const btnClass = p.is_paid ? 'paid' : 'unpaid';
            const btnText = p.is_paid ? 'Paid' : 'Unpaid';
            
            el.innerHTML = `
                <div class="player-info">
                    <span class="player-name">${p.full_name}</span>
                    <span class="player-meta">${p.position || 'CM'}</span>
                </div>
                <div class="player-actions">
                    <span style="font-size: 0.85rem; color: var(--text-muted); margin-right: 8px;">${p.status}</span>
                    <button class="payment-toggle ${btnClass}" onclick="togglePayment(${p.signup_id}, this, ${gameId})">
                        ${btnText}
                    </button>
                </div>
            `;
            
            listEl.appendChild(el);
        });
        
    } catch (e) {
        document.getElementById('players-list').innerHTML = `<p style="color:var(--danger)">Failed to load game details.</p>`;
    }
}

// Sub-Apps SPA Iframe Handling
function openApp(appType) {
    const modal = document.getElementById('iframe-modal');
    const iframe = document.getElementById('app-iframe');
    const title = document.getElementById('iframe-title');
    
    let url = '';
    
    if (appType === 'create') {
        if (!currentGroupId) return;
        url = `/web/index.html?target_chat_id=${currentGroupId}`;
        title.textContent = 'Create Game';
    } 
    else if (appType === 'draft') {
        if (!currentGameId) return;
        url = `/web/draft.html?game_id=${currentGameId}`;
        title.textContent = 'Draft & Squads';
    }
    else if (appType === 'edit') {
        if (!currentGameId) return;
        url = `/web/edit_game.html?game_id=${currentGameId}`;
        title.textContent = 'Edit Game Info';
    }
    else if (appType === 'score') {
        if (!currentGameId) return;
        url = `/web/finish.html?game_id=${currentGameId}`;
        title.textContent = 'Enter Score & Stats';
    }

    if (url) {
        // Appending timestamp to bust iframe cache slightly if needed, but usually query params are enough
        iframe.src = url;
        modal.classList.add('show');
    }
}

function closeApp() {
    const modal = document.getElementById('iframe-modal');
    const iframe = document.getElementById('app-iframe');
    modal.classList.remove('show');
    
    // Clear iframe src after transition
    setTimeout(() => {
        iframe.src = 'about:blank';
        // Refresh underlying data just in case the app changed it
        if (currentGameId) loadGameDetails(currentGameId);
        else if (currentGroupId) {
            // Need to reload group games without losing context
            // We can just call it via active group
            document.querySelector('.group-item.active').click();
        }
    }, 300);
}

// Group Settings
async function updateGroupSetting(key, value) {
    if (!currentGroupId) return;
    
    const data = {};
    data[key] = value;
    
    try {
        await apiCall(`/groups/${currentGroupId}`, {
            method: 'PATCH',
            body: JSON.stringify(data)
        });
    } catch (e) {
        alert("Failed to update setting");
    }
}

// No showGroupGames function needed since we have showGroupsView now

async function togglePayment(signupId, btnEl, gameId) {
    btnEl.disabled = true;
    const originalText = btnEl.textContent;
    btnEl.textContent = "...";
    
    try {
        const res = await apiCall(`/signups/${signupId}/toggle_pay`, { method: 'POST' });
        
        if (res.is_paid) {
            btnEl.className = 'payment-toggle paid';
            btnEl.textContent = 'Paid';
        } else {
            btnEl.className = 'payment-toggle unpaid';
            btnEl.textContent = 'Unpaid';
        }
        
        // Update total counter logic implicitly by reloading details or just string manipulation
        // For premium feel, we just let the button change, and optionally refresh game details
        // loadGameDetails(gameId); // Uncomment if we want full refresh
    } catch (e) {
        btnEl.textContent = originalText;
        alert("Failed to toggle payment");
    } finally {
        btnEl.disabled = false;
    }
}
