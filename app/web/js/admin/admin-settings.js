function resolveSettingInputElement(key, explicitEl) {
    if (explicitEl) return explicitEl;
    if (key === 'language') return document.getElementById('setting-lang');
    const inputId = `setting-${key.replace('default_', '').replaceAll('_', '-')}`;
    return document.getElementById(inputId);
}

function onBillingModeSettingChange(selectEl) {
    const mode = selectEl.value;
    applyBillingModeSettingsUI(mode);
    updateGroupSetting('billing_mode', mode, selectEl);
}

function onCurrencySettingChange(selectEl) {
    const curr = selectEl.value;
    applyBillingModeSettingsUI(
        (document.getElementById('setting-billing-mode') && document.getElementById('setting-billing-mode').value) || 'manual',
        curr
    );
    updateGroupSetting('currency', curr, selectEl);
}

async function onSportPresetSettingChange(selectEl) {
    const sportCode = selectEl.value;
    await updateGroupSetting('sport_type', sportCode, selectEl);
    const updatedGroup = groupsCache.find(g => String(g.chat_id) === String(currentGroupId));
    if (updatedGroup && typeof applyGroupPresetUI === 'function') {
        applyGroupPresetUI(updatedGroup);
    }
}

async function updatePolicySetting(policyKey, policyValue, inputEl) {
    if (!currentGroupId) return;
    const cached = groupsCache.find(g => String(g.chat_id) === String(currentGroupId));
    const mergedPolicy = { ...((cached && cached.policy) || {}), [policyKey]: policyValue };
    return updateGroupSetting('policy', mergedPolicy, inputEl);
}

async function updateGroupSetting(key, value, explicitInputEl) {
    if (!currentGroupId) return;
    
    const input = resolveSettingInputElement(key, explicitInputEl);
    if (input) {
        input.style.borderColor = "var(--accent-color)";
    }
    
    const data = {};
    data[key] = value;

    const saveTask = (async () => {
        try {
            const res = await apiCall(`/groups/${currentGroupId}`, {
                method: 'PATCH',
                body: JSON.stringify(data)
            });
            
            // Update local cache using chat_id (fixes ReferenceError: groups is not defined & g.id mismatch)
            const gIdx = groupsCache.findIndex(g => String(g.chat_id) === String(currentGroupId));
            if (gIdx > -1) {
                groupsCache[gIdx] = (res && res.group) ? res.group : { ...groupsCache[gIdx], ...data };
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
    })();

    pendingSettingSaves.push(saveTask);
    try {
        await saveTask;
    } finally {
        pendingSettingSaves = pendingSettingSaves.filter(p => p !== saveTask);
    }
}

// No showGroupGames function needed since we have showGroupsView now


async function updateEventModuleToggle(moduleKey, isChecked) {
    if (!currentGroupId) return;
    try {
        const group = groupsCache.find(g => String(g.chat_id) === String(currentGroupId)) || {};
        const policy = Object.assign({}, group.policy || {});
        const enabledModules = Object.assign({}, policy.enabled_modules || {});
        enabledModules[moduleKey] = Boolean(isChecked);
        policy.enabled_modules = enabledModules;
        await apiCall(`/groups/${currentGroupId}`, 'PATCH', { policy });
        group.policy = policy;
        const gIdx = groupsCache.findIndex(g => String(g.chat_id) === String(currentGroupId));
        if (gIdx > -1) {
            groupsCache[gIdx].modules = { ...(groupsCache[gIdx].modules || {}), [moduleKey]: Boolean(isChecked) };
            if (typeof applyGroupPresetUI === 'function') {
                applyGroupPresetUI(groupsCache[gIdx]);
            }
        }
        showAdminToast('🧩 Модуль обновлён!');
    } catch (err) {
        showAdminToast('Failed to update module: ' + err.message);
    }
}

