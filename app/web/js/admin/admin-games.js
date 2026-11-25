async function loadGroups() {
    const listEl = document.getElementById('groups-list');
    listEl.innerHTML = '<div class="loading-spinner"></div>';
    
    // Wait for initData if missing
    let retryCount = 0;
    while (window.Telegram && window.Telegram.WebApp && !window.Telegram.WebApp.initData && retryCount < 5) {
        console.warn(`initData missing, retry ${retryCount}...`);
        await new Promise(r => setTimeout(r, 200));
        retryCount++;
    }
    initData = (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) || initData;

    try {
        const groups = await apiCall('/groups');
        groupsCache = Array.isArray(groups) ? groups : [];
        listEl.innerHTML = '';
        
        if (groupsCache.length === 0) {
            listEl.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:20px">No groups found.</p>';
            return;
        }

        groupsCache.forEach(g => {
            const el = document.createElement('div');
            el.className = 'group-item';
            el.id = `group-item-${g.chat_id}`;
            el.innerHTML = `
                <h3>${escapeHtml(g.title)}</h3>
                <p>ID: ${g.chat_id}</p>
            `;
            el.onclick = () => {
                document.querySelectorAll('.group-item').forEach(i => i.classList.remove('active'));
                el.classList.add('active');
                const latestGroup = groupsCache.find(item => String(item.chat_id) === String(g.chat_id)) || g;
                loadGroupGames(latestGroup);
            };
            listEl.appendChild(el);
        });

        // Auto-select if only 1 group
        if (groupsCache.length === 1) {
            const firstEl = document.getElementById(`group-item-${groupsCache[0].chat_id}`);
            if (firstEl) firstEl.click();
        }
        
    } catch (e) {
        listEl.innerHTML = `
            <p style="color:var(--danger)">Failed to load groups: ${escapeHtml(e.message)}</p>
            <button class="btn" style="margin-top:10px" onclick="loadGroups()">Retry</button>
        `;
    }
}

function resolveGroupPresetModules(group) {
    const sportType = (group && group.sport_type) || 'football';
    if (group && group.modules) return group.modules;
    const isNonScorePreset = ['trip', 'book_club', 'board_games', 'generic'].includes(sportType);
    const modOverrides = (group && group.policy && group.policy.enabled_modules) || {};
    return {
        roles_enabled: modOverrides.roles_enabled !== undefined ? Boolean(modOverrides.roles_enabled) : !['book_club', 'board_games', 'padel'].includes(sportType),
        team_draft_enabled: modOverrides.team_draft_enabled !== undefined ? Boolean(modOverrides.team_draft_enabled) : (sportType !== 'book_club'),
        score_tracking_enabled: modOverrides.score_tracking_enabled !== undefined ? Boolean(modOverrides.score_tracking_enabled) : !isNonScorePreset,
        mvp_voting_enabled: modOverrides.mvp_voting_enabled !== undefined ? Boolean(modOverrides.mvp_voting_enabled) : !['trip', 'book_club', 'padel'].includes(sportType),
    };
}

function applyGroupPresetUI(group) {
    if (!group) return;
    const mods = resolveGroupPresetModules(group);
    const modRolesEl = document.getElementById('mod-roles');
    if (modRolesEl) modRolesEl.checked = Boolean(mods.roles_enabled);
    const modDraftEl = document.getElementById('mod-draft');
    if (modDraftEl) modDraftEl.checked = Boolean(mods.team_draft_enabled);
    const modScoreEl = document.getElementById('mod-score');
    if (modScoreEl) modScoreEl.checked = Boolean(mods.score_tracking_enabled);
    const modVotingEl = document.getElementById('mod-voting');
    if (modVotingEl) modVotingEl.checked = Boolean(mods.mvp_voting_enabled);

    const gamesTabBtn = document.getElementById('tab-group-games');
    const icon = group.preset_icon || '⚽';
    if (gamesTabBtn) {
        const span = gamesTabBtn.querySelector('span');
        const evNoun = group.terminology && group.terminology.event_noun;
        gamesTabBtn.childNodes.forEach(n => {
            if (n.nodeType === Node.TEXT_NODE && n.textContent.trim()) {
                n.textContent = `${icon} `;
            }
        });
        if (span && evNoun && group.sport_type && group.sport_type !== 'football') {
            span.textContent = evNoun;
        }
    }

    const enterScoreBtn = document.getElementById('btn-enter-score');
    if (enterScoreBtn) enterScoreBtn.style.display = mods.score_tracking_enabled ? '' : 'none';
    const settleBtn = document.getElementById('btn-settle-event');
    if (settleBtn) settleBtn.style.display = mods.score_tracking_enabled ? 'none' : '';
    const draftBtn = document.getElementById('btn-manage-draft');
    if (draftBtn) draftBtn.style.display = mods.team_draft_enabled ? '' : 'none';
    const voteBtn = document.getElementById('btn-trigger-voting');
    if (voteBtn) voteBtn.style.display = mods.mvp_voting_enabled ? '' : 'none';
    const mvpTab = document.getElementById('tab-mvp');
    if (mvpTab) mvpTab.style.display = mods.mvp_voting_enabled ? '' : 'none';
}

async function loadGroupGames(group) {
    currentGroupId = group.chat_id;
    switchView('view-group');
    
    document.getElementById('group-title').textContent = group.title;
    const urlTab = (new URLSearchParams(window.location.search)).get('tab');
    if (urlTab === 'inventory') {
        switchGroupTab('inventory');
    } else {
        switchGroupTab('games');
    }
    
    // Normalize language ('cz' -> 'cs', universal default 'en')
    const rawLang = String(group.language || 'en').toLowerCase();
    const normLang = rawLang === 'cz' ? 'cs' : (['en', 'ru', 'cs'].includes(rawLang) ? rawLang : 'en');
    const currency = group.currency || 'CZK';
    const billingMode = group.billing_mode || 'manual';
    const sportType = group.sport_type || 'football';
    const cancelHours = (group.policy && group.policy.free_cancellation_hours !== undefined && group.policy.free_cancellation_hours !== null)
        ? group.policy.free_cancellation_hours
        : 24;

    // Setup Settings
    document.getElementById('setting-lang').value = normLang;
    const sportEl = document.getElementById('setting-sport-type');
    if (sportEl) sportEl.value = sportType;
    const billEl = document.getElementById('setting-billing-mode');
    if (billEl) billEl.value = billingMode;
    const currEl = document.getElementById('setting-currency');
    if (currEl) currEl.value = currency;
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
    const cancelEl = document.getElementById('setting-cancel-hours');
    if (cancelEl) cancelEl.value = cancelHours;
    const ratingSysEl = document.getElementById('setting-rating-system');
    if (ratingSysEl) ratingSysEl.value = (group.policy && group.policy.rating_system) || 'simple_points';
    const subEl = document.getElementById('setting-employer-subsidy');
    if (subEl) subEl.value = (group.policy && group.policy.employer_subsidy_pct !== undefined) ? group.policy.employer_subsidy_pct : 0;
    const msEl = document.getElementById('setting-multisport-discount');
    if (msEl) msEl.value = (group.policy && group.policy.multisport_discount_amount !== undefined) ? group.policy.multisport_discount_amount : 150;

    applyGroupPresetUI(group);

    applyBillingModeSettingsUI(billingMode, currency);
    
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
            
            const groupTz = (typeof currentGroupData !== 'undefined' && currentGroupData && currentGroupData.timezone) || 'Europe/Prague';
            const dateStr = new Date(g.date_time).toLocaleString('en-GB', {day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: groupTz});
            
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
                    <p style="color: var(--text-main); font-weight: 500; margin-bottom: 2px;">${escapeHtml(g.location)}</p>
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
        
        const gameTz = game.timezone || (typeof currentGroupData !== 'undefined' && currentGroupData && currentGroupData.timezone) || 'Europe/Prague';
        const dateStr = new Date(game.date_time).toLocaleString('en-GB', {day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: gameTz});
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

        const activeGroupObj = groupsCache.find(g => String(g.chat_id) === String(currentGroupId));
        if (activeGroupObj) {
            applyGroupPresetUI(activeGroupObj);
        }
        const isFreeCorporate = (activeGroupObj && activeGroupObj.billing_mode === 'free_corporate') || (game.price === 0 && !game.payment_info && activeGroupObj?.billing_mode === 'free_corporate');

        const paidCount = game.players.filter(p => p.is_paid).length;
        document.getElementById('roster-paid-info').textContent = isFreeCorporate
            ? `✨ ${getAdminText('free_corporate_paid_label')}`
            : `Paid: ${paidCount}/${game.players.length}`;
        
        const activeUnpaidCount = isFreeCorporate ? 0 : game.players.filter(p => p.status === 'active' && !p.is_paid).length;
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
                if (!p.is_paid && !isFreeCorporate) {
                    const safeName = (p.full_name || '').replace(/'/g, "\\'");
                    notifyBtn = `<button class="action-btn outline" style="padding: 4px 8px; font-size: 0.8rem; margin-right: 6px;" onclick="notifyPayment(${p.user_id}, ${gameId}, this, '${safeName}')" title="${getAdminText('Notify payment in DM', 'Напомнить об оплате в ЛС')}">🔔</button>`;
                }
                
                let removeBtn = `<button class="action-btn outline" style="padding: 4px 8px; font-size: 0.8rem; margin-left: 6px; border-color: rgba(239, 68, 68, 0.3); color: var(--danger);" onclick="kickPlayer(${p.signup_id}, ${gameId}, this)" title="${getAdminText('Remove player', 'Убрать игрока')}">❌</button>`;
                const payToggleBtn = isFreeCorporate
                    ? ''
                    : `<button class="payment-toggle ${btnClass}" onclick="togglePayment(${p.signup_id}, this, ${gameId})">${btnText}</button>`;

                const isLate = !!p.is_late;
                const lateBtnClass = isLate ? 'late-active' : 'late-inactive';
                const lateBtnText = isLate ? getAdminText('late_toggle_late', 'Опоздал') : getAdminText('late_toggle_ontime', 'Вовремя');
                const lateToggleBtn = `<button class="action-btn outline late-btn ${lateBtnClass}" onclick="toggleLate(${p.signup_id}, this, ${gameId})" title="${getAdminText('late_toggle_label', 'Отметить опоздание')}">⏱️ <span>${lateBtnText}</span></button>`;

                el.innerHTML = `
                    <div class="player-info">
                        <span class="player-name">${escapeHtml(p.full_name)} <div style="font-size:0.8rem; margin-left: 6px;">${statsHtml}</div></span>
                        <div class="player-meta" id="notify-meta-${p.user_id}">${notifyBadgeHtml}</div>
                    </div>
                    <div class="player-actions" style="display: flex; align-items: center; gap: 4px;">
                        ${lateToggleBtn}
                        ${notifyBtn}
                        ${payToggleBtn}
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
async function openApp(appType) {
    // Ensure any focused input triggers onblur and finishes saving before opening sub-app
    if (document.activeElement && typeof document.activeElement.blur === 'function') {
        document.activeElement.blur();
    }
    if (pendingSettingSaves.length > 0) {
        await Promise.allSettled([...pendingSettingSaves]);
    }

    const modal = document.getElementById('iframe-modal');
    const iframe = document.getElementById('app-iframe');
    const title = document.getElementById('iframe-title');
    
    const v = Date.now();
    try { sessionStorage.setItem('tma_init_data', initData); } catch (e) {}
    const auth = `&v=${v}`;
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
        if (currentGameId) loadGameDetails(currentGameId);
        else if (currentGroupId) {
            const activeItem = document.querySelector('.group-item.active');
            if (activeItem) activeItem.click();
        }
    }, 300);
}

window.addEventListener('message', (event) => {
    if (event.data === 'closeIframe') {
        closeApp();
    }
});

// Group Settings

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


async function toggleLate(signupId, btnEl, gameId) {
    try {
        btnEl.disabled = true;
        const res = await apiCall(`/signups/${signupId}/toggle_late`, 'POST');
        const isLate = !!res.is_late;
        btnEl.classList.toggle('late-active', isLate);
        btnEl.classList.toggle('late-inactive', !isLate);
        const span = btnEl.querySelector('span');
        if (span) {
            span.textContent = isLate ? getAdminText('late_toggle_late', 'Опоздал') : getAdminText('late_toggle_ontime', 'Вовремя');
        }
    } catch (err) {
        showAdminToast('Failed to toggle late status: ' + err.message);
    } finally {
        btnEl.disabled = false;
    }
}

// -------------------------------------------------------------
// Inventory & Equipment Management
// -------------------------------------------------------------
let currentInventoryItems = [];
let currentInventoryCategory = 'ALL';
let currentInventoryStatusFilter = 'ALL';
let cachedGroupAdmins = [];


async function exportAttendanceCsv() {
    if (!currentGroupId) return;
    try {
        const headers = {};
        if (initData) {
            headers['Authorization'] = `tma ${initData}`;
        }
        const inTelegramWebView = Boolean(window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData);
        if (inTelegramWebView) {
            const res = await fetch(`/api/dashboard/groups/${currentGroupId}/attendance.csv?send_dm=true`, { headers });
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            showAdminToast('📥 CSV-отчёт отправлен вам в личку бота!');
            return;
        }
        const res = await fetch(`/api/dashboard/groups/${currentGroupId}/attendance.csv`, { headers });
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `attendance_group_${currentGroupId}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        showAdminToast('CSV exported!');
    } catch (err) {
        showAdminToast('CSV export failed: ' + err.message);
    }
}


async function settleEventWithoutScoreClick() {
    if (!currentGroupId || !currentGameId) return;
    const confirmed = await promptConfirm('Завершить событие без ввода счёта и зафиксировать посещаемость участников?');
    if (!confirmed) return;
    try {
        const res = await apiCall(`/groups/${currentGroupId}/events/${currentGameId}/settle`, 'POST', {});
        showAdminToast(`✅ Событие завершено! Участников: ${res.participants_count || 0}`);
        await loadGameDetails(currentGameId);
    } catch (err) {
        showAdminToast('Ошибка завершения события: ' + err.message);
    }
}
