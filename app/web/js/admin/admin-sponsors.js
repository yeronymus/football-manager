async function loadSponsorMetricsPanel() {
    const panel = document.getElementById('sponsor-metrics-panel');
    if (!panel || !currentGroupId) return;
    panel.innerHTML = '<div class="loading-spinner"></div>';

    try {
        const lang = localStorage.getItem('webapp_lang') || 'en';
        const data = await apiCall(`/groups/${currentGroupId}/ads/metrics?lang=${encodeURIComponent(lang)}`);
        const banner = (data.banners && data.banners[0]) || {
            title: getAdminText('sponsor_21coffee_title'),
            subtitle: getAdminText('sponsor_21coffee_subtitle'),
            text: getAdminText('sponsor_21coffee_text'),
            cta_text: getAdminText('sponsor_21coffee_cta'),
            link: 'https://www.instagram.com/21coffeecz/',
            image_url: '/web/assets/sponsors/21coffee_logo.jpg',
            hero_image_url: '/web/assets/sponsors/21coffee_hero.webp',
            impressions: data.total_impressions || 0,
            unique_viewers: 0,
            clicks: data.total_clicks || 0,
            unique_clickers: 0,
            ctr_percent: data.overall_ctr_percent || 0,
            placements: {}
        };

        const plEntries = Object.entries(banner.placements || {});
        let plHtml = '';
        if (plEntries.length > 0) {
            plHtml = `<div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:10px;">` +
                plEntries.map(([pl, st]) => `<span style="font-size:0.74rem; padding:4px 9px; border-radius:8px; background:rgba(255,255,255,0.04); border:1px solid var(--border-color);">📍 <b>${escapeHtml(pl)}</b>: ${st.impressions} 👀 / ${st.clicks} 👆</span>`).join('') +
                `</div>`;
        }

        const loyaltyMembers = data.loyalty_members || [];
        let loyaltyHtml = '';
        if (loyaltyMembers.length === 0) {
            loyaltyHtml = `<p style="color:var(--text-muted); font-size:0.82rem; text-align:center; padding:14px;">${getAdminText('No linked loyalty cards yet. When a player wins MVP, the bot sends them the Bondus registration guide and saves their card name here.', 'Пока нет привязанных карт лояльности. Когда игрок выигрывает MVP, бот отправляет ему инструкцию Bondus и сохраняет имя его карты здесь.')}</p>`;
        } else {
            loyaltyHtml = loyaltyMembers.map(m => `
                <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; padding:10px 12px; border-radius:10px; background:rgba(255,255,255,0.03); border:1px solid var(--border-color); margin-bottom:8px;">
                    <div>
                        <div style="font-weight:700; font-size:0.88rem;">
                            ☕ ${escapeHtml(m.full_name)} ${m.username ? `<span style="color:var(--text-muted); font-weight:400;">@${escapeHtml(m.username)}</span>` : ''}
                        </div>
                        <div style="font-size:0.76rem; color:var(--text-muted); margin-top:3px;">
                            ${getAdminText('Bondus Card Name:', 'Имя карты (Bondus):')} <b style="color:#fcd34d;">${escapeHtml(m.loyalty_card_name)}</b>
                        </div>
                    </div>
                    <span style="font-size:0.74rem; color:#34d399; border:1px solid rgba(52,211,153,0.4); padding:2px 8px; border-radius:8px;">✓ Linked</span>
                </div>
            `).join('');
        }

        panel.innerHTML = `
            <div style="position:relative; overflow:hidden; border-radius:16px; padding:16px; margin-bottom:16px; border:1px solid rgba(245,158,11,0.45); background:linear-gradient(125deg, rgba(18,14,11,0.92), rgba(40,28,16,0.86)), url('${banner.hero_image_url || ''}') center/cover no-repeat; display:flex; align-items:center; gap:14px; box-shadow:0 12px 28px rgba(0,0,0,0.45);">
                <img src="${banner.image_url || ''}" style="width:56px; height:56px; border-radius:14px; object-fit:cover; border:2px solid rgba(252,211,77,0.6);">
                <div style="flex:1; min-width:0;">
                    <span style="display:inline-block; padding:2px 8px; border-radius:999px; font-size:0.68rem; font-weight:800; background:rgba(245,158,11,0.22); color:#fcd34d; border:1px solid rgba(245,158,11,0.45);">☕ ACTIVE SPONSOR BANNER</span>
                    <div style="font-weight:800; font-size:1rem; color:#fff; margin-top:4px;">${escapeHtml(banner.title)}</div>
                    <div style="font-size:0.82rem; color:#fde68a; margin-top:2px;">${escapeHtml(banner.text)}</div>
                    <div style="font-size:0.75rem; color:#d6d3d1; margin-top:2px;">${escapeHtml(banner.subtitle || '')}</div>
                </div>
                <a href="${banner.link || 'https://www.instagram.com/21coffeecz/'}" target="_blank" style="text-decoration:none; padding:7px 12px; border-radius:999px; background:linear-gradient(135deg,#f59e0b,#d97706); color:#111; font-weight:800; font-size:0.78rem;">${escapeHtml(banner.cta_text || '@21coffeecz ↗')}</a>
            </div>

            <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:8px; margin-bottom:14px; text-align:center;">
                <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border-color); border-radius:12px; padding:10px 6px;">
                    <div style="font-size:1.25rem; font-weight:800; color:#60a5fa;">${banner.impressions || 0}</div>
                    <div style="font-size:0.68rem; color:var(--text-muted); text-transform:uppercase;">Views</div>
                </div>
                <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border-color); border-radius:12px; padding:10px 6px;">
                    <div style="font-size:1.25rem; font-weight:800; color:#c084fc;">${banner.unique_viewers || 0}</div>
                    <div style="font-size:0.68rem; color:var(--text-muted); text-transform:uppercase;">Unique</div>
                </div>
                <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border-color); border-radius:12px; padding:10px 6px;">
                    <div style="font-size:1.25rem; font-weight:800; color:#34d399;">${banner.clicks || 0}</div>
                    <div style="font-size:0.68rem; color:var(--text-muted); text-transform:uppercase;">Clicks</div>
                </div>
                <div style="background:rgba(255,255,255,0.03); border:1px solid var(--border-color); border-radius:12px; padding:10px 6px;">
                    <div style="font-size:1.25rem; font-weight:800; color:#fbbf24;">${banner.ctr_percent || 0}%</div>
                    <div style="font-size:0.68rem; color:var(--text-muted); text-transform:uppercase;">CTR</div>
                </div>
            </div>
            ${plHtml}

            <div style="margin-top:18px;">
                <h4 style="margin:0 0 10px 0; font-size:0.9rem; color:#fcd34d;">💳 ${getAdminText('Linked Bondus Loyalty Cards', 'Привязанные карты лояльности (Bondus)')}</h4>
                ${loyaltyHtml}
            </div>
        `;
    } catch (e) {
        panel.innerHTML = `<p style="color:var(--danger); text-align:center; padding:20px;">${escapeHtml(e.message)}</p>`;
    }
}
