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

        const unregBadge = document.getElementById('badge-unregistered-cnt');
        const leftBadge = document.getElementById('badge-left-cnt');
        if (unregBadge) unregBadge.textContent = data.unregistered_count ? `(${data.unregistered_count})` : '';
        if (leftBadge) leftBadge.textContent = data.left_chat_count ? `(${data.left_chat_count})` : '';
        
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

    const unregBar = document.getElementById('unregistered-outreach-bar');
    if (unregBar) {
        if (filterType === 'unregistered') unregBar.classList.remove('hidden');
        else unregBar.classList.add('hidden');
    }

    const sponsorPanel = document.getElementById('sponsor-metrics-panel');
    const playersList = document.getElementById('community-players-list');
    if (filterType === 'sponsors') {
        if (sponsorPanel) sponsorPanel.classList.remove('hidden');
        if (playersList) playersList.classList.add('hidden');
        loadSponsorMetricsPanel();
        return;
    } else {
        if (sponsorPanel) sponsorPanel.classList.add('hidden');
        if (playersList) playersList.classList.remove('hidden');
    }
    
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
    
    // Category filter: keep departed players strictly in the separate 'left' historical tab
    if (currentCommunityFilter === 'left') {
        filtered = filtered.filter(p => p.is_in_chat === false);
    } else if (currentCommunityFilter === 'unregistered') {
        filtered = filtered.filter(p => p.is_in_chat !== false && p.is_registered === false);
    } else if (currentCommunityFilter === 'core') {
        filtered = filtered.filter(p => p.is_in_chat !== false && p.is_core);
    } else if (currentCommunityFilter === 'dormant') {
        filtered = filtered.filter(p => p.is_in_chat !== false && p.is_dormant);
    } else {
        filtered = filtered.filter(p => p.is_in_chat !== false);
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
        const isRegistered = p.is_registered !== false;
        const isInChat = p.is_in_chat !== false;
        const pos = p.position || (isRegistered ? 'CM' : '—');
        let posClass = '';
        if (pos === 'GK') posClass = 'gk';
        else if (['CB', 'LB', 'RB', 'LWB', 'RWB', 'DEF'].includes(pos)) posClass = 'def';
        else if (['ST', 'CF', 'LW', 'RW', 'ATT'].includes(pos)) posClass = 'att';
        
        let tagHtml = '';
        if (!isInChat) {
            if (p.chat_status === 'kicked') {
                tagHtml = `<span class="community-tag-dormant" style="background: rgba(239, 68, 68, 0.22); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4);">⛔ ${getAdminText('tag_kicked', 'Кикнут')}</span>`;
            } else {
                tagHtml = `<span class="community-tag-dormant" style="background: rgba(148, 163, 184, 0.18); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.35);">🚪 ${getAdminText('tag_left', 'Вышел сам')}</span>`;
            }
        } else if (!isRegistered) {
            tagHtml = `<span class="community-tag-dormant" style="background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.35);">👻 ${getAdminText('Unregistered', 'Не в боте')}</span>`;
        } else if (p.is_core) {
            tagHtml = `<span class="community-tag-core">⭐ ${getAdminText('Core', 'Костяк')} • ${p.games_last_4_weeks} ${getAdminText('stat_in_4w')}</span>`;
        } else if (p.is_dormant) {
            const daysText = p.days_since_last_game !== null ? getAdminText('stat_days_ago', { days: p.days_since_last_game }) : getAdminText('stat_never_played');
            tagHtml = `<span class="community-tag-dormant">⏳ ${daysText}</span>`;
        }
        
        const usernameDisplay = p.username ? `<span style="font-size: 0.78rem; color: var(--text-muted); font-weight: 400;">@${p.username}</span>` : '';
        const gamesLabel = getAdminText('modal_stat_games');
        const goalsLabel = getAdminText('modal_stat_goals');
        const profileBtnText = getAdminText('btn_view_profile');
        
        let cardBadge = '';
        if (p.active_card_type === 'RED') {
            cardBadge = `<span title="${getAdminText('card_red_title')}" style="cursor:help; font-size:0.9rem; margin-left:4px;">🟥</span>`;
        } else if (p.active_card_type === 'YELLOW') {
            cardBadge = `<span title="${getAdminText('card_yellow_title')}" style="cursor:help; font-size:0.9rem; margin-left:4px;">🟨</span>`;
        }

        const statsHtml = isRegistered
            ? `<span>${gamesLabel}: <b>${p.total_games}</b></span>
               <span>•</span>
               <span>${goalsLabel}: <b>${p.total_goals}</b></span>
               <span>•</span>
               <span>MVP: <b>${p.total_mvps}</b></span>
               <span>•</span>
               <span style="color: #60a5fa;">ELO: <b>${p.rating}</b></span>`
            : `<span style="color: var(--text-muted); font-size: 0.8rem;">${getAdminText('In Telegram chat, not registered in bot', 'В чате группы, ещё не запустил бота')}</span>`;

        let actionBtnHtml = '';
        if (isRegistered) {
            actionBtnHtml = `<button class="community-profile-btn" onclick="openPlayerModal(${p.user_id})">${profileBtnText}</button>`;
        } else {
            const warnDmText = encodeURIComponent(
                getAdminText(
                    'Hi! Please register in our football bot (press /start), otherwise we will have to remove you from the group during squad cleanup 🙏',
                    'Привет! Зарегистрируйся, пожалуйста, в нашем футбольном боте (нажми /start), иначе нам придётся удалить тебя из группы при чистке состава 🙏'
                )
            );
            const chatUrl = p.username ? `https://t.me/${p.username}?text=${warnDmText}` : `tg://user?id=${p.user_id}`;
            const safeJsName = (p.full_name || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
            const kickBtnHtml = isInChat
                ? `<button class="community-profile-btn" onclick="kickPlayerFromGroup(${p.user_id}, '${safeJsName}')" title="${getAdminText('btn_kick_group', 'Кикнуть из группы')}" style="padding: 6px 9px; background: rgba(239, 68, 68, 0.18); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.38);">👢 ${getAdminText('btn_kick_short', 'Кик')}</button>`
                : '';
            actionBtnHtml = `
                <div style="display:flex; gap:5px; align-items:center; flex-shrink:0; flex-wrap:wrap; justify-content:flex-end;">
                    <button class="community-profile-btn" onclick="openPlayerModal(${p.user_id})" title="${getAdminText('lbl_admin_note', 'Заметка')}" style="padding: 6px 9px;">📝</button>
                    <a href="${chatUrl}" target="_blank" class="community-profile-btn" style="text-decoration:none; display:inline-flex; align-items:center; gap:4px; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.35);">💬 ${getAdminText('Write', 'Написать')}</a>
                    ${kickBtnHtml}
                </div>`;
        }

        const adminNoteHtml = p.admin_note
            ? `<div style="font-size: 0.76rem; color: #fbbf24; margin-top: 4px; display: flex; align-items: flex-start; gap: 4px; line-height: 1.3;"><span>📝</span><span style="word-break: break-word;">${escapeHtml(p.admin_note)}</span></div>`
            : '';
        
        html += `
            <div class="community-player-card">
                <div class="community-player-left">
                    <span class="community-pos-badge ${posClass}">${pos}</span>
                    <div style="min-width: 0;">
                        <div class="community-player-name">
                            <span>${escapeHtml(p.full_name)}</span>
                            ${cardBadge}
                            ${usernameDisplay}
                            ${tagHtml}
                        </div>
                        <div class="community-player-stats">
                            ${statsHtml}
                        </div>
                        ${adminNoteHtml}
                    </div>
                </div>
                ${actionBtnHtml}
            </div>
        `;
    });
    
    listEl.innerHTML = html;
}

let currentModalUserId = null;

async function openPlayerModal(userId) {
    if (!currentGroupId) return;
    currentModalUserId = userId;
    
    const modal = document.getElementById('player-profile-modal');
    if (!modal) return;
    
    modal.classList.remove('hidden');
    
    document.getElementById('modal-player-name').textContent = getAdminText('loading_dots');
    document.getElementById('modal-player-meta').textContent = '';
    document.getElementById('modal-stat-rating').textContent = '...';
    document.getElementById('modal-stat-games').textContent = '...';
    document.getElementById('modal-stat-goals').textContent = '...';
    document.getElementById('modal-stat-mvp').textContent = '...';
    document.getElementById('modal-matches-list').innerHTML = '<div class="loading-spinner"></div>';
    const noteInput = document.getElementById('modal-admin-note-input');
    const noteStatus = document.getElementById('modal-admin-note-status');
    if (noteInput) noteInput.value = '';
    if (noteStatus) noteStatus.textContent = '';
    
    try {
        const data = await apiCall(`/groups/${currentGroupId}/players/${userId}`);
        
        document.getElementById('modal-player-name').textContent = data.full_name;
        let metaText = `${data.username ? '@' + data.username + ' • ' : ''}${data.position || (data.is_registered === false ? '—' : 'CM')}`;
        if (data.is_in_chat === false) {
            metaText += data.chat_status === 'kicked'
                ? ` • ⛔ ${getAdminText('tag_kicked', 'Кикнут')}`
                : ` • 🚪 ${getAdminText('tag_left', 'Вышел сам')}`;
        } else if (data.is_registered === false) {
            metaText += ` • 👻 ${getAdminText('Unregistered', 'Не в боте')}`;
        }
        document.getElementById('modal-player-meta').textContent = metaText;
        document.getElementById('modal-stat-rating').textContent = data.rating;
        document.getElementById('modal-stat-games').textContent = data.total_games;
        document.getElementById('modal-stat-goals').textContent = data.total_goals;
        document.getElementById('modal-stat-mvp').textContent = data.total_mvps;
        const lateStatEl = document.getElementById('modal-stat-lates');
        if (lateStatEl) {
            const lates = data.total_lates || 0;
            const pct = data.total_games > 0 ? Math.round(data.late_percentage || 0) : 0;
            lateStatEl.textContent = data.total_games > 0 ? `${lates} (${pct}%)` : '0';
        }
        
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
            matchesEl.innerHTML = `<p style="text-align: center; color: var(--text-muted); font-size: 0.8rem; padding: 12px;">${getAdminText('modal_no_matches')}</p>`;
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
        
        if (noteInput) {
            noteInput.value = data.admin_note || '';
        }

        const kickModalBtn = document.getElementById('modal-btn-kick');
        if (kickModalBtn) {
            kickModalBtn.style.display = data.is_in_chat === false ? 'none' : 'inline-flex';
        }

        if (data.is_registered === false) {
            const discSection = document.getElementById('modal-discipline-section');
            if (discSection) discSection.innerHTML = '';
        } else {
            renderModalDiscipline(data.active_card, userId);
        }
    } catch (e) {
        document.getElementById('modal-matches-list').innerHTML = `<p style="color:var(--danger); padding:10px;">${e.message}</p>`;
    }
}

function appendAdminNotePreset(i18nKey) {
    const input = document.getElementById('modal-admin-note-input');
    if (!input) return;
    const label = getAdminText(i18nKey).replace(/^[^\p{L}\p{N}]+/u, '').trim();
    const current = (input.value || '').trim();
    if (!current) {
        input.value = label;
    } else if (!current.toLowerCase().includes(label.toLowerCase())) {
        input.value = `${current}; ${label}`;
    }
    input.focus();
}

async function savePlayerAdminNote(overrideVal) {
    if (!currentGroupId || !currentModalUserId) return;
    const input = document.getElementById('modal-admin-note-input');
    const statusEl = document.getElementById('modal-admin-note-status');
    const noteText = overrideVal !== undefined ? overrideVal : (input ? input.value : '');
    if (statusEl) statusEl.textContent = '...';
    try {
        const res = await apiCall(`/groups/${currentGroupId}/players/${currentModalUserId}/note`, 'PUT', { note: noteText });
        if (input) input.value = res.admin_note || '';
        if (statusEl) statusEl.textContent = getAdminText('note_saved', 'Сохранено ✓');
        if (communityData && Array.isArray(communityData.players)) {
            const target = communityData.players.find(p => p.user_id === currentModalUserId);
            if (target) {
                target.admin_note = res.admin_note || null;
                renderCommunityPlayers();
            }
        }
    } catch (e) {
        if (statusEl) statusEl.textContent = '';
        alert(e.message || 'Failed to save note');
    }
}

function clearPlayerAdminNote() {
    const input = document.getElementById('modal-admin-note-input');
    if (input) input.value = '';
    savePlayerAdminNote('');
}

async function copyUnregisteredDmTemplate() {
    const text = getAdminText(
        'Hi! Please register in our football bot (press /start), otherwise we will have to remove you from the group during squad cleanup 🙏',
        'Привет! Зарегистрируйся, пожалуйста, в нашем футбольном боте (нажми /start), иначе нам придётся удалить тебя из группы при чистке состава 🙏'
    );
    try {
        await navigator.clipboard.writeText(text);
        showAdminToast(getAdminText('DM text copied!', 'Текст для ЛС скопирован!'));
    } catch (_) {
        prompt(getAdminText('Copy DM text:', 'Скопируйте текст для ЛС:'), text);
    }
}

async function warnAllUnregistered() {
    if (!currentGroupId) return;
    const defaultMsg = getAdminText(
        'Hi! Please register in our football bot (press /start), otherwise we will have to remove you from the group during squad cleanup 🙏',
        'Привет! Зарегистрируйся, пожалуйста, в нашем футбольном боте (нажми /start), иначе нам придётся удалить тебя из группы при чистке состава 🙏'
    );
    const customMsg = prompt(
        getAdminText('Private DM text (sent only to users who already opened the bot; no group chat spam):', 'Текст для отправки в личку (бот напишет тем, у кого уже открыт диалог с ботом; в общий чат ничего не уйдёт):'),
        defaultMsg
    );
    if (customMsg === null) return;

    try {
        const res = await apiCall(`/groups/${currentGroupId}/unregistered/warn`, 'POST', {
            custom_message: customMsg
        });
        alert(
            getAdminText(
                `Sent in DM: ${res.dm_sent_count}. Could not DM (never started bot): ${res.blocked_count}. Use "💬 Write" next to each player to message them from your Telegram.`,
                `Отправлено в личку ботом: ${res.dm_sent_count}.\nНедоступно для бота (не нажимали /start): ${res.blocked_count}.\nДля остальных используй кнопку «💬 Написать» напротив каждого игрока — она сразу откроет ЛС от твоего имени.`
            )
        );
    } catch (e) {
        alert(e.message || 'Failed to send DMs');
    }
}

async function kickPlayerFromGroup(targetUserId, fullName) {
    if (!currentGroupId || !targetUserId) return;
    const reason = prompt(
        getAdminText(
            `Remove ${fullName} from the Telegram group? Optional note/reason:`,
            `Удалить «${fullName}» из Telegram-группы?\nУкажи причину для истории (например: не зарегался в боте, не заплатил):`
        ),
        getAdminText('Not registered in bot', 'Не зарегистрировался в боте')
    );
    if (reason === null) return;

    try {
        const res = await apiCall(`/groups/${currentGroupId}/players/${targetUserId}/kick`, 'POST', {
            reason: reason
        });
        if (communityData && Array.isArray(communityData.players)) {
            const p = communityData.players.find(x => x.user_id === targetUserId);
            if (p) {
                p.is_in_chat = false;
                p.chat_status = 'kicked';
                if (res.admin_note) p.admin_note = res.admin_note;
            }
            communityData.unregistered_count = communityData.players.filter(x => x.is_in_chat !== false && x.is_registered === false).length;
            communityData.left_chat_count = communityData.players.filter(x => x.is_in_chat === false).length;
            const unregBadge = document.getElementById('badge-unregistered-cnt');
            const leftBadge = document.getElementById('badge-left-cnt');
            if (unregBadge) unregBadge.textContent = communityData.unregistered_count ? `(${communityData.unregistered_count})` : '';
            if (leftBadge) leftBadge.textContent = communityData.left_chat_count ? `(${communityData.left_chat_count})` : '';
            renderCommunityPlayers();
        }
        closePlayerModalDirect();
    } catch (e) {
        alert(e.message || 'Failed to kick member');
    }
}

function kickPlayerFromModal() {
    if (!currentModalUserId) return;
    const nameEl = document.getElementById('modal-player-name');
    const name = nameEl ? nameEl.textContent : `User ${currentModalUserId}`;
    kickPlayerFromGroup(currentModalUserId, name);
}

async function issueManualCoffeeReward() {
    if (!currentGroupId || !currentModalUserId) return;
    const nameEl = document.getElementById('modal-player-name');
    const name = nameEl ? nameEl.textContent : `User ${currentModalUserId}`;
    if (!confirm(getAdminText(`Send a 21 Coffee MVP voucher to ${name}?`, `Отправить купон на бесплатный кофе 21 Coffee игроку «${name}»?`))) {
        return;
    }
    try {
        const res = await apiCall(`/groups/${currentGroupId}/rewards/issue`, 'POST', {
            target_user_id: currentModalUserId
        });
        alert(
            getAdminText(
                `Voucher ${res.code} issued and sent to player!`,
                `Купон ${res.code} создан и отправлен игроку в личку бота!`
            )
        );
    } catch (e) {
        alert(e.message || 'Failed to issue reward');
    }
}


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
        if (hint) { hint.textContent = getAdminText('hint_yellow_warning'); hint.style.color = 'var(--text-muted)'; }
    } else {
        if (rBtn) { rBtn.style.background = 'rgba(239,68,68,0.2)'; rBtn.style.borderColor = '#f87171'; rBtn.style.color = '#f87171'; }
        if (yBtn) { yBtn.style.background = 'transparent'; yBtn.style.borderColor = 'var(--border-color)'; yBtn.style.color = 'var(--text-muted)'; }
        if (hint) { hint.textContent = '⛔ ' + getAdminText('hint_red_block'); hint.style.color = '#f87171'; }
    }
}

function renderModalDiscipline(card, targetUserId) {
    const section = document.getElementById('modal-discipline-section');
    if (!section) return;

    if (card) {
        const isRed = (card.card_type === 'RED');
        const cardTitle = isRed ? getAdminText('card_red_title') : getAdminText('card_yellow_title');
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
                            ${getAdminText('lbl_duration')} <b>${card.weeks} ${getAdminText('lbl_weeks')}</b> (${getAdminText('lbl_until')} ${expDate}, <b>${card.days_left} ${getAdminText('lbl_days_left')}</b>)
                        </div>
                        ${card.reason ? `<div style="font-size:0.8rem; color:var(--text-main); margin-top:4px;"><b>${getAdminText('lbl_reason')}</b> ${escapeHtml(card.reason)}</div>` : ''}
                        ${isRed ? `<div style="font-size:0.75rem; color:#f87171; margin-top:4px;">⛔ ${getAdminText('msg_red_blocked')}</div>` : ''}
                    </div>
                    <button class="action-btn outline" onclick="revokePlayerCard(${targetUserId})" style="padding:4px 10px; font-size:0.75rem; border-color:${border}; color:var(--text-main);">
                        ${getAdminText('btn_revoke_card')}
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
                        ${getAdminText('discipline_title')}
                    </span>
                    <button id="btn-toggle-card-form" class="action-btn outline" onclick="toggleCardForm()" style="padding:4px 8px; font-size:0.75rem;">
                        + ${getAdminText('btn_issue_card')}
                    </button>
                </div>
                <div id="card-issue-form" class="hidden" style="margin-top:10px; border-top:1px dashed var(--border-color); padding-top:10px;">
                    <div style="display:flex; gap:8px; margin-bottom:10px;">
                        <button type="button" id="btn-card-yellow" class="action-btn" onclick="selectCardType('YELLOW')" style="flex:1; font-size:0.82rem; padding:7px; background:rgba(234,179,8,0.2); border:1px solid #facc15; color:#facc15;">
                            🟨 ${getAdminText('card_yellow_short')}
                        </button>
                        <button type="button" id="btn-card-red" class="action-btn outline" onclick="selectCardType('RED')" style="flex:1; font-size:0.82rem; padding:7px; border:1px solid var(--border-color); color:var(--text-muted);">
                            🟥 ${getAdminText('card_red_short')}
                        </button>
                    </div>
                    <div style="display:flex; gap:8px; align-items:center; margin-bottom:10px;">
                        <span style="font-size:0.8rem; color:var(--text-muted);">${getAdminText('lbl_duration')}</span>
                        <select id="card-weeks-select" style="flex:1; background:rgba(255,255,255,0.05); border:1px solid var(--border-color); color:var(--text-main); border-radius:6px; padding:6px 8px; font-size:0.82rem;">
                            <option value="1">${getAdminText('opt_1_week')}</option>
                            <option value="2">${getAdminText('opt_2_weeks')}</option>
                            <option value="4" selected>${getAdminText('opt_4_weeks')}</option>
                            <option value="8">${getAdminText('opt_8_weeks')}</option>
                            <option value="12">${getAdminText('opt_12_weeks')}</option>
                        </select>
                    </div>
                    <input type="text" id="card-reason-input" placeholder="${getAdminText('ph_card_reason')}" style="width:100%; box-sizing:border-box; background:rgba(255,255,255,0.05); border:1px solid var(--border-color); color:var(--text-main); border-radius:6px; padding:6px 10px; font-size:0.82rem; margin-bottom:10px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span id="card-type-hint" style="font-size:0.72rem; color:var(--text-muted);">
                            ${getAdminText('hint_yellow_warning')}
                        </span>
                        <button type="button" class="action-btn" onclick="submitIssueCard(${targetUserId})" style="padding:6px 14px; font-size:0.82rem;">
                            ${getAdminText('btn_confirm_issue_dm')}
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
    
    const typeLabel = selectedCardType === 'RED' ? getAdminText('card_red_short') : getAdminText('card_yellow_short');
    const playerName = document.getElementById('modal-player-name')?.textContent || '';
    const confirmMsg = getAdminText('confirm_issue_prompt', { type: typeLabel, name: playerName, weeks: weeks });
    if (!confirm(confirmMsg)) return;

    try {
        await apiCall(`/groups/${currentGroupId}/players/${userId}/card`, 'POST', {
            card_type: selectedCardType,
            weeks: weeks,
            reason: reason || null
        });
        showAdminToast(getAdminText('toast_card_issued'));
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
    const playerName = document.getElementById('modal-player-name')?.textContent || '';
    const confirmMsg = getAdminText('confirm_revoke_prompt', { name: playerName });
    if (!confirm(confirmMsg)) return;

    try {
        await apiCall(`/groups/${currentGroupId}/players/${userId}/card`, 'DELETE');
        showAdminToast(getAdminText('toast_card_revoked'));
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

// -------------------------------------------------------------
// Late Arrival Tracking
// -------------------------------------------------------------
