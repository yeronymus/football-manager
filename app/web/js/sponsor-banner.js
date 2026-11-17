/**
 * Shared animated sponsor banner component.
 * Reads config-driven ad payload from /api/ads/random (backed by sponsors.json + locales)
 * and tracks impressions/clicks while redirecting to the sponsor's Instagram.
 */
(function (global) {
    function ensureSponsorStyles() {
        if (document.getElementById('sponsor-banner-styles')) return;
        const st = document.createElement('style');
        st.id = 'sponsor-banner-styles';
        st.textContent = `
            @keyframes sponsorShine {
                0% { transform: translateX(-120%) skewX(-18deg); }
                35%, 100% { transform: translateX(220%) skewX(-18deg); }
            }
            @keyframes sponsorFloat {
                0%, 100% { transform: translateY(0px); }
                50% { transform: translateY(-2px); }
            }
            .sponsor-banner-card {
                position: relative;
                overflow: hidden;
                border-radius: 16px;
                padding: 14px;
                cursor: pointer;
                border: 1px solid rgba(245, 158, 11, 0.42);
                box-shadow: 0 10px 26px rgba(0, 0, 0, 0.42), 0 0 18px rgba(245, 158, 11, 0.14);
                background-size: cover;
                background-position: center;
                transition: transform 0.18s ease, box-shadow 0.18s ease;
            }
            .sponsor-banner-card:active {
                transform: scale(0.985);
            }
            .sponsor-banner-card::before {
                content: '';
                position: absolute;
                inset: 0;
                background: linear-gradient(125deg, rgba(18, 14, 11, 0.92) 0%, rgba(28, 21, 16, 0.84) 55%, rgba(45, 29, 14, 0.88) 100%);
                z-index: 1;
            }
            .sponsor-banner-card::after {
                content: '';
                position: absolute;
                top: 0; left: 0; width: 45%; height: 100%;
                background: linear-gradient(90deg, transparent, rgba(252, 211, 77, 0.14), transparent);
                animation: sponsorShine 5.5s infinite ease-in-out;
                z-index: 2;
                pointer-events: none;
            }
            .sponsor-inner {
                position: relative;
                z-index: 3;
                display: flex;
                align-items: center;
                gap: 12px;
            }
            .sponsor-logo-wrap {
                flex-shrink: 0;
                width: 50px;
                height: 50px;
                border-radius: 13px;
                overflow: hidden;
                border: 2px solid rgba(252, 211, 77, 0.55);
                box-shadow: 0 4px 12px rgba(0,0,0,0.45);
                animation: sponsorFloat 3.4s infinite ease-in-out;
            }
            .sponsor-logo-wrap img {
                width: 100%;
                height: 100%;
                object-fit: cover;
                display: block;
            }
            .sponsor-badge-pill {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 2px 8px;
                border-radius: 999px;
                font-size: 9.5px;
                font-weight: 800;
                letter-spacing: 0.5px;
                text-transform: uppercase;
                background: rgba(245, 158, 11, 0.22);
                color: #fcd34d;
                border: 1px solid rgba(245, 158, 11, 0.45);
            }
            .sponsor-cta-pill {
                flex-shrink: 0;
                padding: 6px 10px;
                border-radius: 999px;
                background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                color: #111;
                font-weight: 800;
                font-size: 11px;
                box-shadow: 0 4px 10px rgba(245, 158, 11, 0.3);
            }
        `;
        document.head.appendChild(st);
    }

    function escapeAttr(raw) {
        return String(raw || '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function openSponsorInstagram(url, bannerId, chatId, placement) {
        const tg = global.Telegram && global.Telegram.WebApp;
        if (bannerId) {
            const headers = { 'Content-Type': 'application/json' };
            if (tg && tg.initData) headers['Authorization'] = `tma ${tg.initData}`;
            fetch(`/api/ads/${bannerId}/click`, {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    chat_id: chatId ? parseInt(chatId, 10) : null,
                    placement: placement || 'default',
                }),
            }).catch(() => {});
        }
        if (tg && tg.openLink) {
            tg.openLink(url);
        } else {
            global.open(url, '_blank');
        }
    }

    function renderSponsorBannerInto(el, ad, chatId, placement) {
        if (!el || !ad) return;
        ensureSponsorStyles();
        const heroBg = escapeAttr(ad.hero_image_url || '');
        const logoUrl = escapeAttr(ad.image_url || '');
        const badge = escapeAttr(ad.badge_text || '');
        const title = escapeAttr(ad.title || '');
        const text = escapeAttr(ad.text || '');
        const subtitle = escapeAttr(ad.subtitle || '');
        const cta = escapeAttr(ad.cta_text || '↗');
        const link = ad.link || 'https://www.instagram.com/21coffeecz/';

        el.innerHTML = `
            <div class="sponsor-banner-card" style="background-image: url('${heroBg}');">
                <div class="sponsor-inner">
                    ${logoUrl ? `<div class="sponsor-logo-wrap"><img src="${logoUrl}" alt="${title}"></div>` : ''}
                    <div style="flex:1; min-width:0;">
                        ${badge ? `<span class="sponsor-badge-pill">${badge}</span>` : ''}
                        <div style="font-weight:800; font-size:13.5px; color:#fff; margin-top:4px; line-height:1.25;">${title}</div>
                        <div style="font-size:11.5px; color:#fde68a; font-weight:600; margin-top:2px; line-height:1.25;">${text}</div>
                        ${subtitle ? `<div style="font-size:10.5px; color:#d6d3d1; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${subtitle}</div>` : ''}
                    </div>
                    <div class="sponsor-cta-pill">${cta}</div>
                </div>
            </div>
        `;
        const card = el.querySelector('.sponsor-banner-card');
        if (card) {
            card.addEventListener('click', () => openSponsorInstagram(link, ad.id, chatId, placement));
        }
        el.style.display = 'block';
    }

    async function loadAndRenderSponsorBanner(targets, options) {
        const opts = options || {};
        const chatId = opts.chatId || null;
        const placement = opts.placement || 'default';
        const lang = opts.lang || localStorage.getItem('webapp_lang') || 'en';
        const tg = global.Telegram && global.Telegram.WebApp;
        const headers = {};
        if (tg && tg.initData) headers['Authorization'] = `tma ${tg.initData}`;

        let url = `/api/ads/random?placement=${encodeURIComponent(placement)}&lang=${encodeURIComponent(lang)}`;
        if (chatId) url += `&chat_id=${encodeURIComponent(chatId)}`;

        try {
            const res = await fetch(url, { headers });
            if (!res.ok) return;
            const data = await res.json();
            if (data.status !== 'ok' || !data.ad) return;
            targets.forEach((t) => {
                const el = typeof t.el === 'string' ? document.querySelector(t.el) : t.el;
                if (el) renderSponsorBannerInto(el, data.ad, chatId, t.placement || placement);
            });
        } catch (e) {
            console.warn('Sponsor banner load failed:', e);
        }
    }

    global.SponsorBanner = {
        render: renderSponsorBannerInto,
        loadAndRender: loadAndRenderSponsorBanner,
        openLink: openSponsorInstagram,
    };
})(window);
