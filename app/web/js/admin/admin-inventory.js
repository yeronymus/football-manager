function getCategoryIcon(cat) {
    switch (cat) {
        case 'BIBS': return '🎽';
        case 'BALLS': return '⚽';
        case 'MEDICAL': return '🩹';
        case 'EQUIPMENT': return '🎒';
        default: return '📦';
    }
}

function formatAdminDate(isoStr) {
    if (!isoStr) return '';
    try {
        const d = new Date(isoStr);
        const localeMap = { ru: 'ru-RU', cs: 'cs-CZ', en: 'en-GB' };
        return d.toLocaleDateString(localeMap[adminCurrentLang] || 'ru-RU', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    } catch (e) {
        return isoStr.split('T')[0];
    }
}

async function loadGroupInventory(chatId) {
    const listEl = document.getElementById('inventory-items-list');
    if (listEl) listEl.innerHTML = '<div class="loading-spinner"></div>';
    
    try {
        const [data, admins] = await Promise.all([
            apiCall(`/groups/${chatId}/inventory`),
            apiCall(`/groups/${chatId}/inventory/admins`).catch(() => [])
        ]);
        currentInventoryItems = (data && data.items) || [];
        cachedGroupAdmins = admins || [];
        
        // Update KPI cards
        const totalEl = document.getElementById('kpi-inv-total-val');
        const soonEl = document.getElementById('kpi-inv-soon-val');
        const urgentEl = document.getElementById('kpi-inv-urgent-val');
        if (totalEl) totalEl.textContent = data.total_count || 0;
        if (soonEl) soonEl.textContent = data.warning_count || 0;
        if (urgentEl) urgentEl.textContent = data.urgent_count || 0;
        
        renderInventoryItems();
    } catch (e) {
        if (listEl) {
            listEl.innerHTML = `<p style="text-align:center;color:var(--danger);padding:30px">Failed to load inventory: ${escapeHtml(e.message)}</p>`;
        }
    }
}

function filterInventoryCategory(cat) {
    currentInventoryCategory = cat;
    document.querySelectorAll('#inventory-category-chips .community-chip').forEach(c => c.classList.remove('active'));
    const chip = document.getElementById(`chip-inv-${cat}`);
    if (chip) chip.classList.add('active');
    renderInventoryItems();
}

function filterInventoryStatus(status) {
    currentInventoryStatusFilter = (currentInventoryStatusFilter === status && status !== 'ALL') ? 'ALL' : status;
    document.querySelectorAll('#group-inventory-container .kpi-card').forEach(c => c.classList.remove('active'));
    if (currentInventoryStatusFilter === 'REPLACE_SOON') {
        const c = document.getElementById('kpi-inv-soon');
        if (c) c.classList.add('active');
    } else if (currentInventoryStatusFilter === 'URGENT_PURCHASE') {
        const c = document.getElementById('kpi-inv-urgent');
        if (c) c.classList.add('active');
    } else {
        const c = document.getElementById('kpi-inv-all');
        if (c) c.classList.add('active');
    }
    renderInventoryItems();
}

function renderInventoryItems() {
    const listEl = document.getElementById('inventory-items-list');
    if (!listEl) return;
    
    let items = [...currentInventoryItems];
    
    if (currentInventoryCategory !== 'ALL') {
        items = items.filter(it => it.category === currentInventoryCategory);
    }
    if (currentInventoryStatusFilter !== 'ALL') {
        items = items.filter(it => it.status === currentInventoryStatusFilter);
    }
    
    if (items.length === 0) {
        listEl.innerHTML = `<p style="text-align:center;color:var(--text-muted);padding:30px" data-i18n="no_inventory_items">${getAdminText('no_inventory_items')}</p>`;
        return;
    }
    
    let html = '';
    items.forEach(it => {
        const catIcon = getCategoryIcon(it.category);
        const catLabel = getAdminText(`cat_${it.category.toLowerCase()}`, it.category);
        
        let statusClass = 'inv-status-in-stock';
        let statusText = getAdminText('status_in_stock', 'В наличии');
        if (it.status === 'REPLACE_SOON') {
            statusClass = 'inv-status-replace-soon';
            statusText = getAdminText('status_replace_soon', 'Скоро обновить');
        } else if (it.status === 'URGENT_PURCHASE') {
            statusClass = 'inv-status-urgent-purchase';
            statusText = getAdminText('status_urgent_purchase', 'Срочно купить');
        }
        
        // Lifespan & progress bar
        let progressHtml = '';
        if (it.lifespan_days) {
            const pct = Math.min(100, Math.max(0, Math.round(it.percent_used || 0)));
            let barColor = 'green';
            if (pct >= 100) barColor = 'red';
            else if (pct >= 75) barColor = 'yellow';
            
            let wearLabel = '';
            if (it.days_left !== null && it.days_left < 0) {
                wearLabel = getAdminText('lbl_expired', { days: Math.abs(it.days_left) });
            } else if (it.days_left !== null) {
                wearLabel = `${it.days_left} ${getAdminText('lbl_days_left', 'дн. осталось')}`;
            }
            const usageText = getAdminText('lbl_days_used', { used: it.days_used || 0, total: it.lifespan_days });
            
            progressHtml = `
                <div style="margin-top: 4px;">
                    <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:var(--text-muted);">
                        <span>${usageText}</span>
                        <span style="font-weight:600; color:${barColor === 'red' ? '#f87171' : (barColor === 'yellow' ? '#facc15' : '#34d399')};">${wearLabel}</span>
                    </div>
                    <div class="inv-progress-track">
                        <div class="inv-progress-fill ${barColor}" style="width: ${pct}%;"></div>
                    </div>
                </div>
            `;
        } else {
            progressHtml = `<div style="font-size:0.75rem; color:var(--text-muted); margin-top:4px;">⏳ ${getAdminText('lbl_no_lifespan', 'Без ограничения срока')}</div>`;
        }
        
        // Purchase Date
        const pDateStr = it.purchase_date ? formatAdminDate(it.purchase_date) : '';
        const pDateHtml = pDateStr ? `<span>📅 ${getAdminText('lbl_purchased_date', 'Куплено')}: <b>${pDateStr}</b></span>` : '';
        
        // Notes / Recipient Display
        let metaExtra = '';
        if (it.notes) {
            metaExtra += `<span style="display:inline-block; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(it.notes)}">📝 ${escapeHtml(it.notes)}</span>`;
        }
        
        let recipientDisplay = '';
        if (it.alert_recipient_user_id) {
            const foundAdmin = cachedGroupAdmins.find(a => a.user_id === it.alert_recipient_user_id);
            if (foundAdmin) {
                recipientDisplay = `👤 ${escapeHtml(foundAdmin.full_name)}${foundAdmin.username ? ' (@' + escapeHtml(foundAdmin.username) + ')' : ''}`;
            } else {
                recipientDisplay = `👤 ID: <code>${it.alert_recipient_user_id}</code>`;
            }
        } else {
            recipientDisplay = `👥 ${getAdminText('recipient_all_admins', 'Все админы группы')}`;
        }
        metaExtra += `<span title="${escapeHtml(recipientDisplay)}" style="display:inline-block; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${recipientDisplay}</span>`;
        
        html += `
            <div class="inv-item-card" id="inv-item-${it.id}">
                <div class="inv-header-row">
                    <div class="inv-title-area">
                        <span style="font-size: 1.15rem;">${catIcon}</span>
                        <span class="inv-name">${escapeHtml(it.name)}</span>
                        <span class="inv-qty-badge">x${it.quantity}</span>
                        <span style="font-size:0.75rem; color:var(--text-muted);">${catLabel}</span>
                    </div>
                    <span class="inv-status-badge ${statusClass}">${statusText}</span>
                </div>
                ${progressHtml}
                <div class="inv-meta-row">
                    ${pDateHtml}
                    ${metaExtra}
                </div>
                <div class="inv-actions-row">
                    <button class="action-btn outline" onclick="sendSingleItemAlert(${it.id})" style="padding: 4px 10px; font-size: 0.78rem; border-color: rgba(245, 158, 11, 0.4); color: #fbbf24;" title="${getAdminText('btn_send_alert', 'Отправить алерт')}">
                        🔔 ${getAdminText('btn_send_alert', 'Алерт')}
                    </button>
                    <button class="action-btn outline" onclick="markInventoryPurchased(${it.id})" style="padding: 4px 10px; font-size: 0.78rem; border-color: rgba(16, 185, 129, 0.4); color: #34d399;" title="Renew / mark purchased today">
                        🛒 ${getAdminText('btn_mark_purchased', 'Куплено / Обновить')}
                    </button>
                    <button class="action-btn outline" onclick="openEditInventoryModal(${it.id})" style="padding: 4px 10px; font-size: 0.78rem;">
                        ✏️ ${getAdminText('btn_edit_item', 'Изменить')}
                    </button>
                    <button class="action-btn outline" onclick="deleteInventoryItem(${it.id})" style="padding: 4px 8px; font-size: 0.78rem; border-color: rgba(239, 68, 68, 0.3); color: var(--danger);" title="Delete item">
                        🗑️
                    </button>
                </div>
            </div>
        `;
    });
    
    listEl.innerHTML = html;
}

function populateRecipientDropdown(selectedUserId) {
    const sel = document.getElementById('inv-item-recipient-select');
    const customInp = document.getElementById('inv-item-recipient-custom');
    if (!sel) return;
    
    let optionsHtml = `<option value="">👥 ${getAdminText('opt_all_admins', 'Все админы группы')}</option>`;
    
    let isMatched = (selectedUserId === null || selectedUserId === undefined || selectedUserId === '');
    
    cachedGroupAdmins.forEach(admin => {
        const uLabel = admin.username ? ` (@${escapeHtml(admin.username)})` : '';
        const isSel = String(admin.user_id) === String(selectedUserId);
        if (isSel) isMatched = true;
        optionsHtml += `<option value="${admin.user_id}" ${isSel ? 'selected' : ''}>👤 ${escapeHtml(admin.full_name)}${uLabel}</option>`;
    });
    
    optionsHtml += `<option value="__custom__" ${!isMatched && selectedUserId ? 'selected' : ''}>✏️ ${getAdminText('opt_custom_recipient', 'Другой Telegram ID...')}</option>`;
    sel.innerHTML = optionsHtml;
    
    if (!isMatched && selectedUserId) {
        if (customInp) {
            customInp.value = selectedUserId;
            customInp.classList.remove('hidden');
        }
    } else {
        if (customInp) {
            customInp.value = '';
            customInp.classList.add('hidden');
        }
    }
}

function onRecipientSelectChange(selectEl) {
    const customInp = document.getElementById('inv-item-recipient-custom');
    if (!customInp) return;
    if (selectEl.value === '__custom__') {
        customInp.classList.remove('hidden');
        customInp.focus();
    } else {
        customInp.classList.add('hidden');
        customInp.value = '';
    }
}

function openAddInventoryModal() {
    const modal = document.getElementById('inventory-modal');
    if (!modal) return;
    document.getElementById('inv-edit-id').value = '';
    document.getElementById('inv-modal-title').textContent = getAdminText('modal_add_item_title', 'Новый предмет инвентаря');
    document.getElementById('inv-item-name').value = '';
    document.getElementById('inv-item-category').value = 'BIBS';
    document.getElementById('inv-item-quantity').value = 1;
    document.getElementById('inv-item-purchase-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('inv-item-lifespan').value = 180;
    document.getElementById('inv-item-notes').value = '';
    populateRecipientDropdown(null);
    modal.classList.remove('hidden');
}

function openEditInventoryModal(itemId) {
    const item = currentInventoryItems.find(it => it.id === itemId);
    if (!item) return;
    const modal = document.getElementById('inventory-modal');
    if (!modal) return;
    document.getElementById('inv-edit-id').value = item.id;
    document.getElementById('inv-modal-title').textContent = getAdminText('modal_edit_item_title', 'Редактировать предмет');
    document.getElementById('inv-item-name').value = item.name || '';
    document.getElementById('inv-item-category').value = item.category || 'OTHER';
    document.getElementById('inv-item-quantity').value = item.quantity || 1;
    document.getElementById('inv-item-purchase-date').value = item.purchase_date ? item.purchase_date.split('T')[0] : '';
    document.getElementById('inv-item-lifespan').value = item.lifespan_days || '';
    document.getElementById('inv-item-notes').value = item.notes || '';
    populateRecipientDropdown(item.alert_recipient_user_id);
    modal.classList.remove('hidden');
}

function closeInventoryModalDirect() {
    const modal = document.getElementById('inventory-modal');
    if (modal) modal.classList.add('hidden');
}

function closeInventoryModal(event) {
    if (event && event.target && event.target.id === 'inventory-modal') {
        closeInventoryModalDirect();
    }
}

function setLifespanPreset(days) {
    const el = document.getElementById('inv-item-lifespan');
    if (el) el.value = days !== null ? days : '';
}

async function submitInventoryForm(e) {
    e.preventDefault();
    if (!currentGroupId) return;
    
    const editId = document.getElementById('inv-edit-id').value;
    const name = document.getElementById('inv-item-name').value.trim();
    const category = document.getElementById('inv-item-category').value;
    const quantity = parseInt(document.getElementById('inv-item-quantity').value, 10) || 1;
    const pDate = document.getElementById('inv-item-purchase-date').value;
    const lifespan = document.getElementById('inv-item-lifespan').value ? parseInt(document.getElementById('inv-item-lifespan').value, 10) : null;
    const notes = document.getElementById('inv-item-notes').value.trim();
    
    const recipientSel = document.getElementById('inv-item-recipient-select');
    let recipient = null;
    if (recipientSel) {
        if (recipientSel.value === '__custom__') {
            const customVal = document.getElementById('inv-item-recipient-custom').value.trim();
            recipient = customVal ? parseInt(customVal, 10) : null;
        } else if (recipientSel.value) {
            recipient = parseInt(recipientSel.value, 10);
        }
    }
    
    const payload = {
        name,
        category,
        quantity,
        purchase_date: pDate ? new Date(pDate).toISOString() : null,
        lifespan_days: lifespan,
        notes: notes || null,
        alert_recipient_user_id: recipient,
    };
    
    const saveBtn = document.getElementById('btn-save-inventory');
    if (saveBtn) saveBtn.disabled = true;
    
    try {
        if (editId) {
            await apiCall(`/groups/${currentGroupId}/inventory/${editId}`, 'PUT', payload);
        } else {
            await apiCall(`/groups/${currentGroupId}/inventory`, 'POST', payload);
        }
        closeInventoryModalDirect();
        showAdminToast(getAdminText('toast_item_saved', 'Предмет сохранен!'));
        await loadGroupInventory(currentGroupId);
    } catch (err) {
        showAdminToast('Error: ' + err.message);
    } finally {
        if (saveBtn) saveBtn.disabled = false;
    }
}

async function sendSingleItemAlert(itemId) {
    if (!currentGroupId) return;
    try {
        const res = await apiCall(`/groups/${currentGroupId}/inventory/${itemId}/send_alert`, 'POST');
        const count = (res && res.delivered_to) || 0;
        showAdminToast(getAdminText('toast_single_alert_sent', { count }));
    } catch (err) {
        showAdminToast('Error: ' + err.message);
    }
}

async function markInventoryPurchased(itemId) {
    const item = currentInventoryItems.find(it => it.id === itemId);
    const name = item ? item.name : 'this item';
    const confirmed = await promptConfirm(getAdminText('confirm_mark_purchased', { name }));
    if (!confirmed) return;
    
    try {
        await apiCall(`/groups/${currentGroupId}/inventory/${itemId}/purchased`, 'POST');
        showAdminToast(getAdminText('toast_item_purchased', 'Срок службы обновлен!'));
        await loadGroupInventory(currentGroupId);
    } catch (err) {
        showAdminToast('Error: ' + err.message);
    }
}

async function deleteInventoryItem(itemId) {
    const item = currentInventoryItems.find(it => it.id === itemId);
    const name = item ? item.name : 'this item';
    const confirmed = await promptConfirm(getAdminText('confirm_delete_item', { name }));
    if (!confirmed) return;
    
    try {
        await apiCall(`/groups/${currentGroupId}/inventory/${itemId}`, 'DELETE');
        showAdminToast(getAdminText('toast_item_deleted', 'Предмет удален!'));
        await loadGroupInventory(currentGroupId);
    } catch (err) {
        showAdminToast('Error: ' + err.message);
    }
}

async function triggerInventoryAlerts() {
    if (!currentGroupId) return;
    try {
        const res = await apiCall(`/groups/${currentGroupId}/inventory/trigger_alerts`, 'POST');
        const count = (res && res.alerts_sent) || 0;
        showAdminToast(getAdminText('toast_alerts_sent', { count }));
    } catch (err) {
        showAdminToast('Error checking alerts: ' + err.message);
    }
}

