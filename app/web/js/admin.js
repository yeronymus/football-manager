let initData = "";
let currentGroupId = null;

document.addEventListener('DOMContentLoaded', () => {
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
    document.getElementById('setting-price').value = group.default_price || 155;
    document.getElementById('setting-payment-info').value = group.payment_info || '';
    document.getElementById('setting-location').value = group.default_location || '';
    document.getElementById('setting-max-players').value = group.default_max_players || 26;
    document.getElementById('setting-main-players-count').value = group.default_main_players_count || 22;
    document.getElementById('setting-team-count').value = group.default_team_count || 2;
    document.getElementById('setting-duration').value = (group.default_duration !== undefined && group.default_duration !== null) ? group.default_duration : 2.0;
    document.getElementById('setting-gk-hours').value = (group.default_gk_hours !== undefined && group.default_gk_hours !== null) ? group.default_gk_hours : 0;
    document.getElementById('setting-registration-hours').value = (group.default_registration_hours !== undefined && group.default_registration_hours !== null) ? group.default_registration_hours : 24;
    document.getElementById('setting-signup-limit').value = (group.default_signup_limit !== undefined && group.default_signup_limit !== null) ? group.default_signup_limit : 40;
    
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
            
            let scoreHtml = '';
            if (g.score_a !== null && g.score_b !== null) {
                scoreHtml = `<div style="margin-bottom: 6px; font-size: 1.1rem; display: flex; gap: 6px; align-items: center;">
                    <span class="score-box score-a">${g.score_a}</span> : <span class="score-box score-b">${g.score_b}</span>
                    ${g.team_count > 2 && g.score_c !== null ? ` : <span class="score-box score-c">${g.score_c}</span>` : ''}
                </div>`;
            }
            
            el.innerHTML = `
                <div class="game-info" style="flex: 1;">
                    <h3 style="margin-bottom: 4px; font-size: 1.2rem;">Game #${g.id}</h3>
                    ${scoreHtml}
                    <p style="color: var(--text-main); font-weight: 500; margin-bottom: 2px;">${g.location}</p>
                    <p style="font-size: 0.85rem;">${dateStr} • Players: ${g.players_count}/${g.max_players} • Paid: ${g.paid_count}/${g.players_count}</p>
                </div>
                <div class="badge ${g.status}" style="margin-left: 12px;">${g.status}</div>
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
        document.getElementById('game-title').textContent = `Game #${game.id}`;
        document.getElementById('game-date-location').textContent = `${game.location} • ${dateStr}`;
        
        const badge = document.getElementById('game-status-badge');
        badge.className = `badge ${game.status}`;
        badge.textContent = game.status;
        
        const scoreContainer = document.getElementById('game-score-display');
        if (game.score_a !== null && game.score_b !== null) {
            let scoreHtml = `<span class="score-box score-a">${game.score_a}</span> : <span class="score-box score-b">${game.score_b}</span>`;
            if (game.score_c !== null) {
                scoreHtml += ` : <span class="score-box score-c">${game.score_c}</span>`;
            }
            scoreContainer.innerHTML = scoreHtml;
        } else {
            scoreContainer.innerHTML = '';
        }
        
        const paidCount = game.players.filter(p => p.is_paid).length;
        document.getElementById('roster-paid-info').textContent = `Paid: ${paidCount}/${game.players.length}`;
        
        const listEl = document.getElementById('players-list');
        listEl.innerHTML = '';
        
        // Group players by team
        const teams = {};
        game.players.forEach(p => {
            const t = p.team || 'Unassigned';
            if (!teams[t]) teams[t] = [];
            teams[t].push(p);
        });
        
        // Sort keys (A, B, C, then Unassigned)
        const teamKeys = Object.keys(teams).sort((a,b) => {
            if (a === 'Unassigned') return 1;
            if (b === 'Unassigned') return -1;
            return a.localeCompare(b);
        });
        
        const getTeamConfig = (t) => {
            if (t === 'A') return { name: 'Orange', icon: '🟠', color: 'var(--warning, #fbbf24)', bg: 'rgba(245, 158, 11, 0.2)' };
            if (t === 'B') return { name: 'Green', icon: '🟢', color: 'var(--success, #34d399)', bg: 'rgba(16, 185, 129, 0.2)' };
            if (t === 'C') return { name: 'Blue', icon: '🔵', color: 'var(--primary, #60a5fa)', bg: 'rgba(59, 130, 246, 0.2)' };
            return { name: 'Unassigned / Reserve', icon: '⚪', color: 'var(--text-muted)', bg: 'rgba(255,255,255,0.1)' };
        };

        teamKeys.forEach(t => {
            // Add team header
            const header = document.createElement('div');
            header.className = 'team-header';
            const tc = getTeamConfig(t);
            header.innerHTML = `<span style="margin-right: 6px;">${tc.icon}</span> <span style="color: ${tc.color};">${tc.name.toUpperCase()}</span>`;
            listEl.appendChild(header);
            
            teams[t].forEach(p => {
                const el = document.createElement('div');
                el.className = 'player-item';
                
                const btnClass = p.is_paid ? 'paid' : 'unpaid';
                const btnText = p.is_paid ? 'Paid' : 'Unpaid';
                
                // Construct stats text
                let statsHtml = '';
                if (p.goals > 0) statsHtml += `<span title="Goals">⚽ ${p.goals}</span> `;
                if (p.is_mvp) {
                    statsHtml += `<span title="MVP" style="color: #fbbf24; font-weight: bold; font-size: 0.95rem; margin-left: 6px; padding: 2px 6px; background: rgba(245, 158, 11, 0.15); border-radius: 6px;">MVP 🌟</span>`;
                }
                
                let notifyBtn = '';
                if (!p.is_paid) {
                    notifyBtn = `<button class="action-btn outline" style="padding: 4px 8px; font-size: 0.8rem; margin-right: 6px;" onclick="notifyPayment(${p.user_id}, ${gameId}, this)" title="Уведомить об оплате">🔔</button>`;
                }
                
                el.innerHTML = `
                    <div class="player-info">
                        <span class="player-name">${p.full_name} <div style="font-size:0.8rem; margin-left: 6px;">${statsHtml}</div></span>
                    </div>
                    <div class="player-actions" style="display: flex; align-items: center;">
                        ${notifyBtn}
                        <button class="payment-toggle ${btnClass}" onclick="togglePayment(${p.signup_id}, this, ${gameId})">
                            ${btnText}
                        </button>
                    </div>
                `;
                
                listEl.appendChild(el);
            });
        });
        
        // Setup Tabs
        document.getElementById('tab-roster').className = 'tab-btn active';
        document.getElementById('tab-mvp').className = 'tab-btn';
        document.getElementById('players-list').classList.remove('hidden');
        
        const mvpListEl = document.getElementById('mvp-list');
        mvpListEl.classList.add('hidden');
        mvpListEl.innerHTML = ''; // Clear old votes!
        
    } catch (e) {
        document.getElementById('players-list').innerHTML = `<p style="color:var(--danger)">Failed to load game details.</p>`;
    }
}

async function switchRosterTab(tab) {
    if (tab === 'roster') {
        document.getElementById('tab-roster').className = 'tab-btn active';
        document.getElementById('tab-mvp').className = 'tab-btn';
        document.getElementById('players-list').classList.remove('hidden');
        document.getElementById('mvp-list').classList.add('hidden');
    } else {
        document.getElementById('tab-roster').className = 'tab-btn';
        document.getElementById('tab-mvp').className = 'tab-btn active';
        document.getElementById('players-list').classList.add('hidden');
        document.getElementById('mvp-list').classList.remove('hidden');
        
        // Load votes if not loaded
        const listEl = document.getElementById('mvp-list');
        if (!listEl.innerHTML.includes('player-item')) {
            listEl.innerHTML = '<div class="loading-spinner"></div>';
            try {
                const votes = await apiCall(`/games/${currentGameId}/votes`);
                listEl.innerHTML = '';
                
                if (votes.length === 0) {
                    listEl.innerHTML = '<p style="text-align:center; color:var(--text-muted); padding: 20px;">No votes recorded yet.</p>';
                    return;
                }
                
                // Group votes by Voter Name -> their team and their votes
                const voters = {};
                votes.forEach(v => {
                    if (!voters[v.voter_name]) {
                        voters[v.voter_name] = { team: v.voter_team || 'Unassigned', cast: [] };
                    }
                    voters[v.voter_name].cast.push(v);
                });

                // Group voters by their team
                const votersByTeam = {};
                Object.keys(voters).forEach(name => {
                    const t = voters[name].team;
                    if (!votersByTeam[t]) votersByTeam[t] = {};
                    votersByTeam[t][name] = voters[name].cast;
                });
                
                const getTeamConfig = (t) => {
                    if (t === 'A') return { name: 'Orange', icon: '🟠', color: 'var(--warning, #fbbf24)' };
                    if (t === 'B') return { name: 'Green', icon: '🟢', color: 'var(--success, #34d399)' };
                    if (t === 'C') return { name: 'Blue', icon: '🔵', color: 'var(--primary, #60a5fa)' };
                    return { name: 'Unassigned', icon: '⚪', color: 'var(--text-muted)' };
                };
                
                // We need to count how many votes each voter received to show 🌟
                const receivedVotesCount = {};
                votes.forEach(v => {
                    receivedVotesCount[v.target_name] = (receivedVotesCount[v.target_name] || 0) + 1;
                });
                
                Object.keys(votersByTeam).sort().forEach(t => {
                    const header = document.createElement('div');
                    header.className = 'team-header';
                    const tc = getTeamConfig(t);
                    header.innerHTML = `<span style="margin-right: 6px;">${tc.icon}</span> <span style="color: ${tc.color};">${tc.name.toUpperCase()} VOTERS</span>`;
                    listEl.appendChild(header);
                    
                    Object.keys(votersByTeam[t]).forEach(voterName => {
                        const el = document.createElement('div');
                        el.className = 'player-item';
                        el.style.flexDirection = 'column';
                        el.style.alignItems = 'flex-start';
                        el.style.gap = '6px';
                        
                        const castArr = votersByTeam[t][voterName];
                        
                        let castHtml = '';
                        castArr.forEach(cast => {
                            let badgeClass = 'active';
                            if (cast.vote_team === 'A') badgeClass = 'score-a';
                            if (cast.vote_team === 'B') badgeClass = 'score-b';
                            if (cast.vote_team === 'C') badgeClass = 'score-c';
                            
                            castHtml += `
                                <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; font-size: 0.85rem; padding: 4px 0; border-top: 1px solid rgba(255,255,255,0.05);">
                                    <span>➔ voted for: <strong style="color:var(--text-main); margin-left:2px;">${cast.target_name}</strong></span>
                                    <span class="badge ${badgeClass}" style="color: inherit; font-size: 0.7rem; padding: 2px 6px;">${getTeamConfig(cast.vote_team).name}</span>
                                </div>
                            `;
                        });
                        
                        const rVotes = receivedVotesCount[voterName] || 0;
                        const starHtml = rVotes > 0 ? `<span style="color: #fbbf24; margin-left: 6px;">🌟 ${rVotes}</span>` : '';
                        
                        el.innerHTML = `
                            <div class="player-info" style="width: 100%;">
                                <span class="player-name" style="font-weight: 600;">${voterName} ${starHtml}</span>
                            </div>
                            <div style="width: 100%; padding-left: 8px;">
                                ${castHtml}
                            </div>
                        `;
                        listEl.appendChild(el);
                    });
                });
            } catch (e) {
                listEl.innerHTML = '<p style="color:var(--danger)">Failed to load votes.</p>';
            }
        }
    }
}

async function notifyPayment(userId, gameId, btn) {
    if (!confirm('Отправить напоминание об оплате этому игроку в личные сообщения?')) return;
    
    const origText = btn.innerHTML;
    btn.innerHTML = '⏳';
    btn.disabled = true;
    
    try {
        await apiCall(`/games/${gameId}/notify`, 'POST', { user_id: userId });
        btn.innerHTML = '✅';
        setTimeout(() => {
            btn.innerHTML = origText;
            btn.disabled = false;
        }, 2000);
    } catch (e) {
        alert('Ошибка при отправке уведомления. Возможно игрок заблокировал бота.');
        btn.innerHTML = origText;
        btn.disabled = false;
    }
}

// Sub-Apps SPA Iframe Handling
function openApp(appType) {
    const modal = document.getElementById('iframe-modal');
    const iframe = document.getElementById('app-iframe');
    const title = document.getElementById('iframe-title');
    
    const v = Date.now();
    const auth = `&initData=${encodeURIComponent(initData)}&v=${v}`;
    let url = '';
    
    if (appType === 'create') {
        if (!currentGroupId) return;
        url = `/web/index.html?target_chat_id=${currentGroupId}${auth}`;
        title.textContent = 'Create Game';
    } 
    else if (appType === 'draft') {
        if (!currentGameId) return;
        url = `/web/draft.html?game_id=${currentGameId}${auth}`;
        title.textContent = 'Draft & Squads';
    }
    else if (appType === 'edit') {
        if (!currentGameId) return;
        url = `/web/edit_game.html?game_id=${currentGameId}${auth}`;
        title.textContent = 'Edit Game Info';
    }
    else if (appType === 'score') {
        if (!currentGameId) return;
        url = `/web/finish.html?game_id=${currentGameId}${auth}`;
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

window.addEventListener('message', (event) => {
    if (event.data === 'closeIframe') {
        closeApp();
    }
});

// Group Settings
async function updateGroupSetting(key, value) {
    if (!currentGroupId) return;
    
    // Find the input element to show feedback
    const inputId = `setting-${key.replace('default_', '').replaceAll('_', '-')}`;
    const input = document.getElementById(inputId);
    let originalBorder = "";
    if (input) {
        originalBorder = input.style.borderColor;
        input.style.borderColor = "var(--accent-color)";
    }
    
    const data = {};
    data[key] = value;
    
    try {
        await apiCall(`/groups/${currentGroupId}`, {
            method: 'PATCH',
            body: JSON.stringify(data)
        });
        
        // Update local cache
        const gIdx = groups.findIndex(g => g.id == currentGroupId);
        if (gIdx > -1) {
            groups[gIdx] = { ...groups[gIdx], ...data };
        }

        if (input) {
            input.style.borderColor = "#4caf50"; // Success Green
            setTimeout(() => {
                input.style.borderColor = ""; 
            }, 1500);
        }
    } catch (e) {
        console.error("Failed to update setting:", e);
        if (input) input.style.borderColor = "#f44336"; // Error Red
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
