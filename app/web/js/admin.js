function getAdminText(enText, ruText) {
    const lang = localStorage.getItem('webapp_lang') || 'en';
    return lang === 'ru' ? ruText : enText;
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
let initData = "";
let currentGroupId = null;

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

// API Helper
async function apiCall(endpoint, options = {}) {
    const headers = {
        'Authorization': `tma ${initData}`,
        'Content-Type': 'application/json'
    };
    
    const url = `/api/dashboard${endpoint}`;
    try {
        const response = await fetch(url, { ...options, headers });
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

// Load Data
async function loadGroups() {
    const listEl = document.getElementById('groups-list');
    listEl.innerHTML = '<div class="loading-spinner"></div>';
    
    // Wait for initData if missing
    let retryCount = 0;
    while (!window.Telegram.WebApp.initData && retryCount < 5) {
        console.warn(`initData missing, retry ${retryCount}...`);
        await new Promise(r => setTimeout(r, 200));
        retryCount++;
    }
    initData = window.Telegram.WebApp.initData || initData;

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
        listEl.innerHTML = `
            <p style="color:var(--danger)">Failed to load groups: ${e.message}</p>
            <button class="btn" style="margin-top:10px" onclick="loadGroups()">Retry</button>
        `;
    }
}

async function loadGroupGames(group) {
    currentGroupId = group.chat_id;
    switchView('view-group');
    
    document.getElementById('group-title').textContent = group.title;
    switchGroupTab('games');
    
    // Setup Settings
    document.getElementById('setting-lang').value = group.language || 'ru';
    document.getElementById('setting-price').value = (group.default_price !== undefined && group.default_price !== null) ? group.default_price : 100;
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
            
            const dateStr = new Date(g.date_time).toLocaleString('en-GB', {day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Prague'});
            
            let scoreHtml = '';
            if (g.score_a !== null && g.score_b !== null) {
                scoreHtml = `<div style="margin-bottom: 6px; font-size: 1.1rem; display: flex; gap: 6px; align-items: center;">
                    <span class="score-box score-a">${g.score_a}</span> : <span class="score-box score-b">${g.score_b}</span>
                    ${g.team_count > 2 && g.score_c !== null ? ` : <span class="score-box score-c">${g.score_c}</span>` : ''}
                </div>`;
            }
            
            el.innerHTML = `
                <div class="game-info" style="flex: 1;">
                    <h3 style="margin-bottom: 4px; font-size: 1.2rem;">Game #${g.game_number || g.id}</h3>
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
        
        const dateStr = new Date(game.date_time).toLocaleString('en-GB', {day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Prague'});
        document.getElementById('game-title').textContent = `Game #${game.game_number || game.id}`;
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
        
        currentGameData = game;

        const paidCount = game.players.filter(p => p.is_paid).length;
        document.getElementById('roster-paid-info').textContent = `Paid: ${paidCount}/${game.players.length}`;
        
        const activeUnpaidCount = game.players.filter(p => p.status === 'active' && !p.is_paid).length;
        const allPmNotifyBtn = document.getElementById('btn-notify-all-pm');
        if (allPmNotifyBtn) {
            allPmNotifyBtn.style.display = activeUnpaidCount > 0 ? 'inline-flex' : 'none';
        }
        const groupNotifyBtn = document.getElementById('btn-notify-group');
        if (groupNotifyBtn) {
            groupNotifyBtn.style.display = activeUnpaidCount > 0 ? 'inline-flex' : 'none';
        }
        
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

                // Delivery badge (feedback / backlog)
                let notifyBadgeHtml = '';
                if (p.notify_status === 'delivered') {
                    notifyBadgeHtml = `<span class="notify-badge delivered" title="Delivered in Telegram DM">✅ ${getAdminText('DM Sent', 'В ЛС')} ${p.notified_at || ''}</span>`;
                } else if (p.notify_status === 'blocked') {
                    notifyBadgeHtml = `<span class="notify-badge blocked" title="Bot blocked by user">⚠️ ${getAdminText('Bot blocked', 'Бот заблокирован')} ${p.notified_at || ''}</span>`;
                } else if (p.notify_status === 'guest') {
                    notifyBadgeHtml = `<span class="notify-badge guest" title="Guest player without Telegram account">👤 ${getAdminText('Guest (no DM)', 'Гость (нет ЛС)')}</span>`;
                } else if (p.notify_status === 'error') {
                    notifyBadgeHtml = `<span class="notify-badge error" title="Delivery failed">❌ ${getAdminText('Failed', 'Ошибка')} ${p.notified_at || ''}</span>`;
                }
                
                let notifyBtn = '';
                if (!p.is_paid) {
                    const safeName = (p.full_name || '').replace(/'/g, "\\'");
                    notifyBtn = `<button class="action-btn outline" style="padding: 4px 8px; font-size: 0.8rem; margin-right: 6px;" onclick="notifyPayment(${p.user_id}, ${gameId}, this, '${safeName}')" title="${getAdminText('Notify payment in DM', 'Напомнить об оплате в ЛС')}">🔔</button>`;
                }
                
                let removeBtn = `<button class="action-btn outline" style="padding: 4px 8px; font-size: 0.8rem; margin-left: 6px; border-color: rgba(239, 68, 68, 0.3); color: var(--danger);" onclick="kickPlayer(${p.signup_id}, ${gameId}, this)" title="${getAdminText('Remove player', 'Убрать игрока')}">❌</button>`;
                
                el.innerHTML = `
                    <div class="player-info">
                        <span class="player-name">${p.full_name} <div style="font-size:0.8rem; margin-left: 6px;">${statsHtml}</div></span>
                        <div class="player-meta" id="notify-meta-${p.user_id}">${notifyBadgeHtml}</div>
                    </div>
                    <div class="player-actions" style="display: flex; align-items: center;">
                        ${notifyBtn}
                        <button class="payment-toggle ${btnClass}" onclick="togglePayment(${p.signup_id}, this, ${gameId})">
                            ${btnText}
                        </button>
                        ${removeBtn}
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

async function notifyPayment(userId, gameId, btn, playerName) {
    const confirmMsg = getAdminText(
        `🔔 Send payment reminder to ${playerName || 'player'} in Telegram DM?`,
        `🔔 Отправить напоминание об оплате игроку ${playerName || ''} в личные сообщения Telegram?`
    );
    if (!confirm(confirmMsg)) return;
    
    const origText = btn.innerHTML;
    btn.innerHTML = '⏳';
    btn.disabled = true;
    
    try {
        const res = await apiCall(`/games/${gameId}/notify`, {
            method: 'POST',
            body: JSON.stringify({ user_id: userId })
        });

        const metaEl = document.getElementById(`notify-meta-${userId}`);
        const timeStr = res.time || '';
        
        if (res.delivery === 'delivered') {
            btn.innerHTML = '✅';
            if (metaEl) {
                metaEl.innerHTML = `<span class="notify-badge delivered">✅ ${getAdminText('DM Sent', 'В ЛС')} ${timeStr}</span>`;
            }
        } else if (res.delivery === 'blocked') {
            btn.innerHTML = '⚠️';
            if (metaEl) {
                metaEl.innerHTML = `<span class="notify-badge blocked">⚠️ ${getAdminText('Bot blocked', 'Бот заблокирован')} ${timeStr}</span>`;
            }
            alert(getAdminText('The player has blocked the bot or has not started a chat with it.', 'Игрок заблокировал бота или ни разу не запускал его в ЛС.'));
        } else if (res.delivery === 'guest') {
            btn.innerHTML = '👤';
            if (metaEl) {
                metaEl.innerHTML = `<span class="notify-badge guest">👤 ${getAdminText('Guest (no DM)', 'Гость (нет ЛС)')}</span>`;
            }
            alert(getAdminText('This player is a guest without a Telegram account.', 'Этот игрок — гость и не имеет Telegram-аккаунта.'));
        } else {
            btn.innerHTML = '❌';
            if (metaEl) {
                metaEl.innerHTML = `<span class="notify-badge error">❌ ${getAdminText('Failed', 'Ошибка')} ${timeStr}</span>`;
            }
            alert(res.detail || 'Failed to send notification.');
        }

        setTimeout(() => {
            btn.innerHTML = origText;
            btn.disabled = false;
        }, 2000);
    } catch (e) {
        alert(getAdminText('Failed to send notification: ' + e.message, 'Ошибка при отправке: ' + e.message));
        btn.innerHTML = origText;
        btn.disabled = false;
    }
}

async function notifyAllDmClick() {
    if (!currentGameData) return;
    
    const unpaidPlayers = (currentGameData.players || []).filter(p => p.status === 'active' && !p.is_paid);
    if (unpaidPlayers.length === 0) {
        promptAlert(getAdminText('All active players have already paid! 🎉', 'Все активные игроки уже оплатили! 🎉'));
        return;
    }
    
    const confirmMsg = getAdminText(
        `✉️ Send personal payment reminder in DM to all ${unpaidPlayers.length} unpaid player(s)?\n\nThe bot will contact each player directly in private chat.`,
        `✉️ Отправить напоминание об оплате в ЛС всем неоплатившим игрокам (${unpaidPlayers.length} чел.)?\n\nБот напишет каждому игроку в личные сообщения.`
    );
    const confirmed = await promptConfirm(confirmMsg);
    if (!confirmed) return;
    
    const btn = document.getElementById('btn-notify-all-pm');
    const origHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.innerHTML = '⏳ ' + getAdminText('Sending...', 'Отправка...');
        btn.disabled = true;
    }
    
    try {
        const res = await apiCall(`/games/${currentGameId}/notify_all_pm`, {
            method: 'POST'
        });
        
        // Update badges for each player on screen
        if (res.results) {
            Object.keys(res.results).forEach(uid => {
                const info = res.results[uid];
                const metaEl = document.getElementById(`notify-meta-${uid}`);
                if (metaEl) {
                    const timeStr = info.time || '';
                    if (info.status === 'delivered') {
                        metaEl.innerHTML = `<span class="notify-badge delivered">✅ ${getAdminText('DM Sent', 'В ЛС')} ${timeStr}</span>`;
                    } else if (info.status === 'blocked') {
                        metaEl.innerHTML = `<span class="notify-badge blocked">⚠️ ${getAdminText('Bot blocked', 'Бот заблокирован')} ${timeStr}</span>`;
                    } else if (info.status === 'guest') {
                        metaEl.innerHTML = `<span class="notify-badge guest">👤 ${getAdminText('Guest (no DM)', 'Гость (нет ЛС)')}</span>`;
                    } else {
                        metaEl.innerHTML = `<span class="notify-badge error">❌ ${getAdminText('Failed', 'Ошибка')} ${timeStr}</span>`;
                    }
                }
            });
        }
        
        promptAlert(getAdminText(
            `✅ Reminders sent:\n• Delivered in DM: ${res.delivered}\n• Bot blocked: ${res.blocked}\n• Guests: ${res.guests}`,
            `✅ Напоминания отправлены:\n• Доставлено в ЛС: ${res.delivered}\n• Бот заблокирован: ${res.blocked}\n• Гостей: ${res.guests}`
        ));
    } catch (e) {
        promptAlert(getAdminText('Failed to send reminders: ' + e.message, 'Ошибка при отправке напоминаний: ' + e.message));
    } finally {
        if (btn) {
            btn.innerHTML = origHtml;
            btn.disabled = false;
        }
    }
}

async function notifyGroupDebtClick() {
    if (!currentGameData) return;
    
    const unpaidPlayers = (currentGameData.players || []).filter(p => p.status === 'active' && !p.is_paid);
    if (unpaidPlayers.length === 0) {
        promptAlert(getAdminText('All active players have already paid! 🎉', 'Все активные игроки уже оплатили! 🎉'));
        return;
    }
    
    const confirmMsg = getAdminText(
        `📢 Post list of ${unpaidPlayers.length} unpaid player(s) to the group chat?\n\nThe bot will tag them with payment details.`,
        `📢 Опубликовать список ${unpaidPlayers.length} неоплативших игроков в группе?\n\nБот отметит их и прикрепит реквизиты для оплаты.`
    );
    const confirmed = await promptConfirm(confirmMsg);
    if (!confirmed) return;
    
    const btn = document.getElementById('btn-notify-group');
    const origHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.innerHTML = '⏳ ' + getAdminText('Sending...', 'Отправка...');
        btn.disabled = true;
    }
    
    try {
        const res = await apiCall(`/games/${currentGameId}/notify_group`, {
            method: 'POST'
        });
        
        promptAlert(getAdminText(
            `✅ Successfully posted payment reminder for ${res.unpaid_count} player(s) to the group chat!`,
            `✅ Список ${res.unpaid_count} должников успешно опубликован в группе!`
        ));
    } catch (e) {
        promptAlert(getAdminText('Failed to post to group: ' + e.message, 'Ошибка при отправке в группу: ' + e.message));
    } finally {
        if (btn) {
            btn.innerHTML = origHtml;
            btn.disabled = false;
        }
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
    const inputId = key === 'language' ? 'setting-lang' : `setting-${key.replace('default_', '').replaceAll('_', '-')}`;
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
        
        // Refresh details so Paid count and Tag Debtors button update seamlessly
        await loadGameDetails(gameId);
    } catch (e) {
        btnEl.textContent = originalText;
        alert("Failed to toggle payment");
    } finally {
        btnEl.disabled = false;
    }
}

async function kickPlayer(signupId, gameId, btn) {
    if (!confirm(getAdminText('Remove this player from the match?', 'Убрать этого игрока из игры?'))) return;
    
    btn.disabled = true;
    const origText = btn.innerHTML;
    btn.innerHTML = '⏳';
    
    try {
        await apiCall(`/signups/${signupId}`, { method: 'DELETE' });
        loadGameDetails(gameId);
    } catch (e) {
        alert(getAdminText('Failed to remove player: ', 'Ошибка при удалении игрока: ') + e.message);
        btn.disabled = false;
        btn.innerHTML = origText;
    }
}

async function deleteGameClick() {
    if (!currentGameId) return;
    if (!confirm(getAdminText('⚠️ Are you sure you want to permanently delete this game? This action cannot be undone.', '⚠️ Вы уверены, что хотите полностью удалить эту игру? Это действие необратимо.'))) return;
    
    try {
        await apiCall(`/games/${currentGameId}`, { method: 'DELETE' });
        // Go back to group games list
        if (currentGroupId) {
            // Click active group again to reload its list
            const activeGrp = document.querySelector('.group-item.active');
            if (activeGrp) {
                activeGrp.click();
            } else {
                showGroupsView();
            }
        } else {
            showGroupsView();
        }
    } catch (e) {
        alert(getAdminText('Failed to delete game: ', 'Ошибка при удалении игры: ') + e.message);
    }
}

async function triggerVotingClick() {
    if (!currentGameId) return;
    
    const confirmMsg = getAdminText(
        '🏆 Are you sure you want to open MVP voting for this match in the Telegram group?',
        '🏆 Вы уверены, что хотите открыть голосование за MVP этого матча в группе Telegram?'
    );
    const confirmed = await promptConfirm(confirmMsg);
    if (!confirmed) return;
    
    try {
        await apiCall(`/games/${currentGameId}/trigger_voting`, { method: 'POST' });
        promptAlert(getAdminText('✅ MVP voting opened in the group!', '✅ Голосование за MVP успешно открыто в группе!'));
        loadGameDetails(currentGameId);
    } catch (e) {
        promptAlert(getAdminText('Failed to open voting: ', 'Не удалось открыть голосование: ') + (e.message || e));
    }
}

// --- Group View Navigation Tabs & Community Analytics ---
let currentGroupViewTab = 'games';
let communityData = null;
let currentCommunityFilter = 'all';

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
    
    if (gamesEl) gamesEl.classList.toggle('hidden', tab !== 'games');
    if (commEl) commEl.classList.toggle('hidden', tab !== 'community');
    if (settEl) settEl.classList.toggle('hidden', tab !== 'settings');
    
    if (tab === 'community' && currentGroupId) {
        loadGroupCommunity(currentGroupId);
    }
}

async function loadGroupCommunity(chatId) {
    const listEl = document.getElementById('community-players-list');
    if (listEl) listEl.innerHTML = '<div class="loading-spinner"></div>';
    
    try {
        const data = await apiCall(`/groups/${chatId}/analytics`);
        communityData = data;
        
        // Update KPI values
        const totalVal = document.getElementById('kpi-total-val');
        const coreVal = document.getElementById('kpi-core-val');
        const dormantVal = document.getElementById('kpi-dormant-val');
        
        if (totalVal) totalVal.textContent = data.total_players || 0;
        if (coreVal) coreVal.textContent = data.core_count || 0;
        if (dormantVal) dormantVal.textContent = data.dormant_count || 0;
        
        renderCommunityPlayers();
    } catch (e) {
        if (listEl) {
            listEl.innerHTML = `<p style="text-align:center;color:var(--danger);padding:30px">${getAdminText('Failed to load community analytics: ', 'Ошибка загрузки аналитики состава: ') + e.message}</p>`;
        }
    }
}

function filterCommunity(filterType) {
    currentCommunityFilter = filterType;
    
    // Update KPI card selection
    document.querySelectorAll('.kpi-card').forEach(c => c.classList.remove('active'));
    const kpiEl = document.getElementById(`kpi-card-${filterType}`);
    if (kpiEl) kpiEl.classList.add('active');
    
    // Update chips selection
    document.querySelectorAll('.community-chip').forEach(c => c.classList.remove('active'));
    const chipEl = document.getElementById(`chip-${filterType}`);
    if (chipEl) chipEl.classList.add('active');
    
    renderCommunityPlayers();
}

function onCommunitySearchInput() {
    renderCommunityPlayers();
}

function renderCommunityPlayers() {
    if (!communityData || !communityData.players) return;
    
    const listEl = document.getElementById('community-players-list');
    if (!listEl) return;
    
    const searchInput = document.getElementById('community-search-input');
    const query = searchInput ? (searchInput.value || '').trim().toLowerCase() : '';
    
    let filtered = communityData.players;
    
    // Category filter
    if (currentCommunityFilter === 'core') {
        filtered = filtered.filter(p => p.is_core);
    } else if (currentCommunityFilter === 'dormant') {
        filtered = filtered.filter(p => p.is_dormant);
    }
    
    // Search filter
    if (query) {
        filtered = filtered.filter(p => {
            const name = (p.full_name || '').toLowerCase();
            const uname = (p.username || '').toLowerCase();
            return name.includes(query) || uname.includes(query);
        });
    }
    
    if (filtered.length === 0) {
        listEl.innerHTML = `<p style="text-align:center;color:var(--text-muted);padding:30px">${getAdminText('No players found.', 'Игроки не найдены.')}</p>`;
        return;
    }
    
    let html = '';
    filtered.forEach(p => {
        const pos = p.position || 'CM';
        let posClass = '';
        if (pos === 'GK') posClass = 'gk';
        else if (['CB', 'LB', 'RB', 'LWB', 'RWB', 'DEF'].includes(pos)) posClass = 'def';
        else if (['ST', 'CF', 'LW', 'RW', 'ATT'].includes(pos)) posClass = 'att';
        
        let tagHtml = '';
        if (p.is_core) {
            tagHtml = `<span class="community-tag-core">⭐ ${getAdminText('Core', 'Костяк')} • ${p.games_last_4_weeks} ${getAdminText('in 4w', 'за месяц')}</span>`;
        } else if (p.is_dormant) {
            const daysText = p.days_since_last_game !== null ? `${p.days_since_last_game} ${getAdminText('days ago', 'дн. назад')}` : getAdminText('Never played', 'Не играл');
            tagHtml = `<span class="community-tag-dormant">⏳ ${daysText}</span>`;
        }
        
        const usernameDisplay = p.username ? `<span style="font-size: 0.78rem; color: var(--text-muted); font-weight: 400;">@${p.username}</span>` : '';
        const gamesLabel = getAdminText('Games', 'Игр');
        const goalsLabel = getAdminText('Goals', 'Голы');
        const profileBtnText = getAdminText('Profile ›', 'Профиль ›');
        
        let cardBadge = '';
        if (p.active_card_type === 'RED') {
            cardBadge = `<span title="${getAdminText('Red Card (Suspended)', 'Красная карточка (дисквалификация)')}" style="cursor:help; font-size:0.9rem; margin-left:4px;">🟥</span>`;
        } else if (p.active_card_type === 'YELLOW') {
            cardBadge = `<span title="${getAdminText('Yellow Card', 'Жёлтая карточка')}" style="cursor:help; font-size:0.9rem; margin-left:4px;">🟨</span>`;
        }
        
        html += `
            <div class="community-player-card">
                <div class="community-player-left">
                    <span class="community-pos-badge ${posClass}">${pos}</span>
                    <div style="min-width: 0;">
                        <div class="community-player-name">
                            <span>${p.full_name}</span>
                            ${cardBadge}
                            ${usernameDisplay}
                            ${tagHtml}
                        </div>
                        <div class="community-player-stats">
                            <span>${gamesLabel}: <b>${p.total_games}</b></span>
                            <span>•</span>
                            <span>${goalsLabel}: <b>${p.total_goals}</b></span>
                            <span>•</span>
                            <span>MVP: <b>${p.total_mvps}</b></span>
                            <span>•</span>
                            <span style="color: #60a5fa;">ELO: <b>${p.rating}</b></span>
                        </div>
                    </div>
                </div>
                <button class="community-profile-btn" onclick="openPlayerModal(${p.user_id})">
                    ${profileBtnText}
                </button>
            </div>
        `;
    });
    
    listEl.innerHTML = html;
}

async function openPlayerModal(userId) {
    if (!currentGroupId) return;
    
    const modal = document.getElementById('player-profile-modal');
    if (!modal) return;
    
    modal.classList.remove('hidden');
    
    document.getElementById('modal-player-name').textContent = getAdminText('Loading...', 'Загрузка...');
    document.getElementById('modal-player-meta').textContent = '';
    document.getElementById('modal-stat-rating').textContent = '...';
    document.getElementById('modal-stat-games').textContent = '...';
    document.getElementById('modal-stat-goals').textContent = '...';
    document.getElementById('modal-stat-mvp').textContent = '...';
    document.getElementById('modal-matches-list').innerHTML = '<div class="loading-spinner"></div>';
    
    try {
        const data = await apiCall(`/groups/${currentGroupId}/players/${userId}`);
        
        document.getElementById('modal-player-name').textContent = data.full_name;
        document.getElementById('modal-player-meta').textContent = `${data.username ? '@' + data.username + ' • ' : ''}${data.position || 'CM'}`;
        document.getElementById('modal-stat-rating').textContent = data.rating;
        document.getElementById('modal-stat-games').textContent = data.total_games;
        document.getElementById('modal-stat-goals').textContent = data.total_goals;
        document.getElementById('modal-stat-mvp').textContent = data.total_mvps;
        
        const tgLink = document.getElementById('modal-tg-link');
        if (tgLink) {
            if (data.username) {
                tgLink.href = `https://t.me/${data.username}`;
                tgLink.style.display = 'inline-flex';
            } else {
                tgLink.href = `tg://user?id=${data.user_id}`;
                tgLink.style.display = 'inline-flex';
            }
        }
        
        const matchesEl = document.getElementById('modal-matches-list');
        if (!data.recent_matches || data.recent_matches.length === 0) {
            matchesEl.innerHTML = `<p style="text-align: center; color: var(--text-muted); font-size: 0.8rem; padding: 12px;">${getAdminText('No match history in this group.', 'Нет сыгранных матчей в этой группе.')}</p>`;
        } else {
            let mHtml = '';
            data.recent_matches.forEach(m => {
                const mvpBadge = m.is_mvp ? '<span style="color:#fbbf24; font-size:0.75rem;">⭐ MVP</span>' : '';
                const goalsBadge = m.goals > 0 ? `<span style="font-size:0.75rem;">⚽ ${m.goals}</span>` : '';
                mHtml += `
                    <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); padding:8px 10px; border-radius:8px; border:1px solid var(--border-color); font-size:0.8rem;">
                        <div>
                            <span style="font-weight:600; color:var(--text-main);">#${m.game_number || m.game_id}</span>
                            <span style="color:var(--text-muted); margin-left:6px;">${m.date}</span>
                            <div style="font-size:0.72rem; color:var(--text-muted); margin-top:2px;">${m.location}</div>
                        </div>
                        <div style="display:flex; align-items:center; gap:6px;">
                            ${goalsBadge}
                            ${mvpBadge}
                        </div>
                    </div>
                `;
            });
            matchesEl.innerHTML = mHtml;
        }
        
        renderModalDiscipline(data.active_card, userId);
    } catch (e) {
        document.getElementById('modal-matches-list').innerHTML = `<p style="color:var(--danger); padding:10px;">${e.message}</p>`;
    }
}

let selectedCardType = 'YELLOW';

function toggleCardForm() {
    const f = document.getElementById('card-issue-form');
    if (!f) return;
    f.classList.toggle('hidden');
}

function selectCardType(type) {
    selectedCardType = type;
    const yBtn = document.getElementById('btn-card-yellow');
    const rBtn = document.getElementById('btn-card-red');
    const hint = document.getElementById('card-type-hint');
    if (type === 'YELLOW') {
        if (yBtn) { yBtn.style.background = 'rgba(234,179,8,0.2)'; yBtn.style.borderColor = '#facc15'; yBtn.style.color = '#facc15'; }
        if (rBtn) { rBtn.style.background = 'transparent'; rBtn.style.borderColor = 'var(--border-color)'; rBtn.style.color = 'var(--text-muted)'; }
        if (hint) { hint.textContent = getAdminText('Yellow is an official warning.', 'Жёлтая — предупреждение.'); hint.style.color = 'var(--text-muted)'; }
    } else {
        if (rBtn) { rBtn.style.background = 'rgba(239,68,68,0.2)'; rBtn.style.borderColor = '#f87171'; rBtn.style.color = '#f87171'; }
        if (yBtn) { yBtn.style.background = 'transparent'; yBtn.style.borderColor = 'var(--border-color)'; yBtn.style.color = 'var(--text-muted)'; }
        if (hint) { hint.textContent = getAdminText('⛔ Red blocks match signups!', '⛔ Красная блокирует запись на игры!'); hint.style.color = '#f87171'; }
    }
}

function renderModalDiscipline(card, targetUserId) {
    const section = document.getElementById('modal-discipline-section');
    if (!section) return;

    if (card) {
        const isRed = (card.card_type === 'RED');
        const cardTitle = isRed ? getAdminText('Red Card (Suspended)', 'Красная карточка (дисквалификация)') : getAdminText('Yellow Card', 'Жёлтая карточка');
        const cardEmoji = isRed ? '🟥' : '🟨';
        const expDate = card.expires_at ? new Date(card.expires_at).toLocaleDateString() : '';
        const bg = isRed ? 'rgba(239, 68, 68, 0.12)' : 'rgba(234, 179, 8, 0.12)';
        const border = isRed ? 'rgba(239, 68, 68, 0.35)' : 'rgba(234, 179, 8, 0.35)';
        const titleColor = isRed ? '#f87171' : '#facc15';

        section.innerHTML = `
            <div style="background:${bg}; border:1px solid ${border}; border-radius:10px; padding:12px; margin-top:12px;">
                <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div>
                        <div style="font-weight:700; font-size:0.95rem; color:${titleColor}; display:flex; align-items:center; gap:6px;">
                            <span>${cardEmoji}</span> <span>${cardTitle}</span>
                        </div>
                        <div style="font-size:0.8rem; color:var(--text-muted); margin-top:3px;">
                            ${getAdminText('Duration:', 'Срок:')} <b>${card.weeks} ${getAdminText('weeks', 'нед.')}</b> (${getAdminText('until', 'до')} ${expDate}, <b>${card.days_left} ${getAdminText('days left', 'дн. осталось')}</b>)
                        </div>
                        ${card.reason ? `<div style="font-size:0.8rem; color:var(--text-main); margin-top:4px;"><b>${getAdminText('Reason:', 'Причина:')}</b> ${escapeHtml(card.reason)}</div>` : ''}
                        ${isRed ? `<div style="font-size:0.75rem; color:#f87171; margin-top:4px;">⛔ ${getAdminText('Match signups are blocked for this player in this group.', 'Запись на игры в этой группе заблокирована.')}</div>` : ''}
                    </div>
                    <button class="action-btn outline" onclick="revokePlayerCard(${targetUserId})" style="padding:4px 10px; font-size:0.75rem; border-color:${border}; color:var(--text-main);">
                        ${getAdminText('Revoke', 'Снять')}
                    </button>
                </div>
            </div>
        `;
    } else {
        selectedCardType = 'YELLOW';
        section.innerHTML = `
            <div style="background:rgba(255,255,255,0.02); border:1px solid var(--border-color); border-radius:10px; padding:12px; margin-top:12px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:0.82rem; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; color:var(--text-muted);">
                        ${getAdminText('Discipline & Sanctions', 'Дисциплина')}
                    </span>
                    <button id="btn-toggle-card-form" class="action-btn outline" onclick="toggleCardForm()" style="padding:4px 8px; font-size:0.75rem;">
                        + ${getAdminText('Issue Card', 'Выдать карточку')}
                    </button>
                </div>
                <div id="card-issue-form" class="hidden" style="margin-top:10px; border-top:1px dashed var(--border-color); padding-top:10px;">
                    <div style="display:flex; gap:8px; margin-bottom:10px;">
                        <button type="button" id="btn-card-yellow" class="action-btn" onclick="selectCardType('YELLOW')" style="flex:1; font-size:0.82rem; padding:7px; background:rgba(234,179,8,0.2); border:1px solid #facc15; color:#facc15;">
                            🟨 ${getAdminText('Yellow', 'Жёлтая')}
                        </button>
                        <button type="button" id="btn-card-red" class="action-btn outline" onclick="selectCardType('RED')" style="flex:1; font-size:0.82rem; padding:7px; border:1px solid var(--border-color); color:var(--text-muted);">
                            🟥 ${getAdminText('Red (Ban)', 'Красная')}
                        </button>
                    </div>
                    <div style="display:flex; gap:8px; align-items:center; margin-bottom:10px;">
                        <span style="font-size:0.8rem; color:var(--text-muted);">${getAdminText('Duration:', 'Срок:')}</span>
                        <select id="card-weeks-select" style="flex:1; background:rgba(255,255,255,0.05); border:1px solid var(--border-color); color:var(--text-main); border-radius:6px; padding:6px 8px; font-size:0.82rem;">
                            <option value="1">1 ${getAdminText('week', 'неделя')}</option>
                            <option value="2">2 ${getAdminText('weeks', 'недели')}</option>
                            <option value="4" selected>4 ${getAdminText('weeks', 'недели (1 мес.)')}</option>
                            <option value="8">8 ${getAdminText('weeks', 'недель (2 мес.)')}</option>
                            <option value="12">12 ${getAdminText('weeks', 'недель (3 мес.)')}</option>
                        </select>
                    </div>
                    <input type="text" id="card-reason-input" placeholder="${getAdminText('Reason (e.g. no-show, unsportsmanlike behavior)...', 'Причина (например, неявка, грубость)...')}" style="width:100%; box-sizing:border-box; background:rgba(255,255,255,0.05); border:1px solid var(--border-color); color:var(--text-main); border-radius:6px; padding:6px 10px; font-size:0.82rem; margin-bottom:10px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span id="card-type-hint" style="font-size:0.72rem; color:var(--text-muted);">
                            ${getAdminText('Yellow is an official warning.', 'Жёлтая — предупреждение.')}
                        </span>
                        <button type="button" class="action-btn" onclick="submitIssueCard(${targetUserId})" style="padding:6px 14px; font-size:0.82rem;">
                            ${getAdminText('Confirm & Send DM', 'Выдать и уведомить')}
                        </button>
                    </div>
                </div>
            </div>
        `;
    }
}

async function submitIssueCard(userId) {
    if (!currentGroupId) return;
    const weeks = parseInt(document.getElementById('card-weeks-select').value, 10) || 4;
    const reason = (document.getElementById('card-reason-input').value || '').trim();
    
    const confirmMsg = getAdminText(
        `Issue ${selectedCardType === 'RED' ? 'RED' : 'YELLOW'} card for ${weeks} week(s)? The player will receive a Telegram DM notice.`,
        `Выдать ${selectedCardType === 'RED' ? 'КРАСНУЮ' : 'ЖЁЛТУЮ'} карточку на ${weeks} нед.? Игроку придёт уведомление в ЛС.`
    );
    if (!confirm(confirmMsg)) return;

    try {
        await apiCall(`/groups/${currentGroupId}/players/${userId}/card`, 'POST', {
            card_type: selectedCardType,
            weeks: weeks,
            reason: reason || null
        });
        showAdminToast(getAdminText('Card issued successfully!', 'Карточка успешно выдана!'));
        await openPlayerModal(userId);
        if (currentGroupAnalytics) {
            loadGroupAnalytics(currentGroupId);
        }
    } catch (e) {
        alert(e.message || 'Error issuing card');
    }
}

async function revokePlayerCard(userId) {
    if (!currentGroupId) return;
    const confirmMsg = getAdminText(
        'Revoke disciplinary card? The sanction will be lifted immediately.',
        'Досрочно снять карточку? Санкция будет отменена сразу же.'
    );
    if (!confirm(confirmMsg)) return;

    try {
        await apiCall(`/groups/${currentGroupId}/players/${userId}/card`, 'DELETE');
        showAdminToast(getAdminText('Card revoked successfully!', 'Карточка снята!'));
        await openPlayerModal(userId);
        if (currentGroupAnalytics) {
            loadGroupAnalytics(currentGroupId);
        }
    } catch (e) {
        alert(e.message || 'Error revoking card');
    }
}

function closePlayerModalDirect() {
    const modal = document.getElementById('player-profile-modal');
    if (modal) modal.classList.add('hidden');
}

function closePlayerModal(e) {
    if (e.target && e.target.id === 'player-profile-modal') {
        closePlayerModalDirect();
    }
}
