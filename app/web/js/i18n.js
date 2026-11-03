// Shared Frontend Internationalization (i18n) Engine for Web Apps
(function (global) {
    const DICTIONARY = {
        en: {
            app_title: "Football Manager",
            match_num: "Match #{num}",
            status_open: "OPEN",
            status_active: "ACTIVE",
            status_finished: "FINISHED",
            loading: "Loading...",
            lbl_format: "Format",
            lbl_price: "Match fee",
            lbl_payment: "Payment info",
            payment_cash: "Cash on site",
            payment_free_corporate: "FREE (Corporate)",
            payment_covered_org: "Covered by organization — no match fee required",
            btn_show_qr: "📱 Show QR Platba",
            btn_hide_qr: "🔼 Hide QR Platba",
            qr_scan_hint: "Scan in your banking app (SPAYD 1.0)",
            qr_iban_label: "IBAN",
            qr_vs_label: "VS",
            btn_copy_iban: "📋 Copy IBAN",
            iban_copied: "IBAN copied!",
            booking_status: "Booking Status",
            sec_achievements: "Personal Achievements",
            ach_veteran_title: "Veteran",
            ach_veteran_legend: "Club Legend",
            ach_veteran_exp: "Experienced",
            ach_veteran_default: "Veteran",
            ach_veteran_desc_0: "Play 1st match",
            ach_veteran_desc_n: "{count} matches played",
            ach_striker_title: "Striker",
            ach_striker_golden: "Golden Boot",
            ach_striker_super: "Super Striker",
            ach_striker_first: "First Touch",
            ach_striker_desc_0: "Score 1st goal",
            ach_striker_desc_n: "{count} goals scored",
            ach_mvp_title: "Match MVP",
            ach_mvp_star: "Superstar",
            ach_mvp_top: "Top Player",
            ach_mvp_desc_0: "Become Match MVP",
            ach_mvp_desc_n: "{count} MVP awards",
            ach_rating_title: "MMR Rank",
            ach_rating_supersonic: "Supersonic",
            ach_rating_authority: "Authority Slayer",
            ach_rating_master: "Master",
            ach_rating_private: "Private",
            ach_rating_desc: "Rating: {rating} MMR",
            ach_rating_desc_default: "Gain strength",
            sec_main_roster: "Main Squad",
            sec_reserve_roster: "Reserve List",
            roster_empty: "Nobody signed up yet. Be the first!",
            player_you: "(You)",
            player_paid: "✅ Paid",
            btn_join_game: "⚽ Sign Up for Game",
            btn_join_reserve: "🧤 Sign Up for Reserve",
            btn_in_active: "✅ You are in Main Squad!",
            btn_in_reserve: "🧤 You are on Reserve List!",
            btn_leave_game: "❌ Leave Match",
            btn_back_to_chat: "🔙 Back to Group Chat",
            btn_match_finished: "Match Finished",
            confirm_leave: "Are you sure you want to leave the match?",
            join_success: "You have signed up successfully!",
            leave_success: "You left the match.",
            gk_priority_notice: "🧤 Attention! For the first {hours} h. ({left} h. left) spots in main squad are reserved for goalkeepers (GK).",
            match_finished_notice: "This match is finished. Final score: {score_a} : {score_b}.",
            profile_default_name: "Player",
            profile_primary_role: "Primary",
            profile_matches: "Matches",
            profile_goals: "Total Goals",
            profile_primary_pos: "Primary Position",
            profile_alt_pos: "Alt Positions",
            profile_edit: "Edit",
            profile_not_set: "Not specified",
            card_yellow: "Yellow Card",
            card_red: "Red Card",
            card_days_left: "{days} d. left",
            card_reason_prefix: "Reason: ",
            card_suspended_warning: "Match registration is suspended.",
            card_tooltip: "{title}: for {weeks} week(s) (until {date}, {days} left){reason}{suspended}",
            btn_change_group: "Change",
            title_select_group: "Select Group",
            select_group_desc: "Select league to view stats",
            nav_profile: "Profile",
            nav_history: "History",
            nav_leaderboard: "Top",
            btn_cancel: "Cancel",
            btn_save: "Save",
            pos_primary_title: "Primary Position",
            pos_primary_desc: "Choose your main role on the pitch",
            pos_alt_title: "Alternative Positions",
            pos_alt_desc: "Choose positions where you can also play",
            history_my_games: "My Games",
            history_all_games: "All Group Games",
            history_no_games: "No games yet.",
            history_game_prefix: "GAME #{num}",
            history_draw: "Draw",
            history_win: "Victory",
            history_defeat: "Defeat",
            history_win_team: "Win for {team}",
            team_green: "Green",
            team_orange: "Orange",
            team_blue: "Blue",
            team_white: "White",
            team_unknown: "Unknown",
            leaderboard_title: "Group Leaderboard",
            leaderboard_games_goals: "{games} games • {goals} goals",
            btn_close_popup: "Close",
            btn_try_again: "Try Again",
            lbl_ad: "Sponsored",
            error_loading_title: "Loading Error",
            error_no_connection: "No connection to server. Check your internet or VPN."
        },
        ru: {
            app_title: "Football Manager",
            match_num: "Матч #{num}",
            status_open: "ОТКРЫТ",
            status_active: "АКТИВЕН",
            status_finished: "ЗАВЕРШЕН",
            loading: "Загрузка...",
            lbl_format: "Формат",
            lbl_price: "Взнос",
            lbl_payment: "Реквизиты",
            payment_cash: "Оплата наличными на месте",
            payment_free_corporate: "БЕСПЛАТНО (Корпоратив)",
            payment_covered_org: "Оплачено организацией — взнос не требуется",
            btn_show_qr: "📱 Показать QR Platba",
            btn_hide_qr: "🔼 Скрыть QR Platba",
            qr_scan_hint: "Отсканируйте в банковском приложении (SPAYD 1.0)",
            qr_iban_label: "IBAN",
            qr_vs_label: "VS",
            btn_copy_iban: "📋 Скопировать IBAN",
            iban_copied: "IBAN скопирован!",
            booking_status: "Статус бронирования",
            sec_achievements: "Личные Достижения",
            ach_veteran_title: "Ветеран",
            ach_veteran_legend: "Легенда Клуба",
            ach_veteran_exp: "Опытный Боец",
            ach_veteran_default: "Ветеран",
            ach_veteran_desc_0: "Сыграй 1-ю игру",
            ach_veteran_desc_n: "{count} игр сыграно",
            ach_striker_title: "Бомбардир",
            ach_striker_golden: "Золотая Бутса",
            ach_striker_super: "Супер-Бомбардир",
            ach_striker_first: "С первого касания",
            ach_striker_desc_0: "Забей первый гол",
            ach_striker_desc_n: "{count} голов забито",
            ach_mvp_title: "MVP Матча",
            ach_mvp_star: "Абсолютная Звезда",
            ach_mvp_top: "Лучший Игрок",
            ach_mvp_desc_0: "Стань MVP матча",
            ach_mvp_desc_n: "{count} наград MVP",
            ach_rating_title: "Ранг MMR",
            ach_rating_supersonic: "Сверхзвуковой",
            ach_rating_authority: "Гроза Авторитетов",
            ach_rating_master: "Мастер",
            ach_rating_private: "Рядовой",
            ach_rating_desc: "Рейтинг: {rating} MMR",
            ach_rating_desc_default: "Набирай силу",
            sec_main_roster: "Основной Состав",
            sec_reserve_roster: "Лист Резерва",
            roster_empty: "Никто еще не записался. Будь первым!",
            player_you: "(Вы)",
            player_paid: "✅ Оплачено",
            btn_join_game: "⚽ Записаться на игру",
            btn_join_reserve: "🧤 Записаться в резерв",
            btn_in_active: "✅ Вы в основном составе!",
            btn_in_reserve: "🧤 Вы записаны в резерв!",
            btn_leave_game: "❌ Выписаться с игры",
            btn_back_to_chat: "🔙 Назад в чат группы",
            btn_match_finished: "Матч завершен",
            confirm_leave: "Вы уверены, что хотите выписаться?",
            join_success: "Вы успешно записались!",
            leave_success: "Вы выписались с игры.",
            gk_priority_notice: "🧤 Внимание! Первые {hours} ч. ({left} ч. осталось) места в основе гарантированы вратарям (GK).",
            match_finished_notice: "Этот матч уже сыгран. Результаты: {score_a} : {score_b}.",
            profile_default_name: "Игрок",
            profile_primary_role: "Основная",
            profile_matches: "Игр",
            profile_goals: "Всего голов",
            profile_primary_pos: "Основная позиция",
            profile_alt_pos: "Доп. позиции",
            profile_edit: "Изменить",
            profile_not_set: "Не указаны",
            card_yellow: "Жёлтая карточка",
            card_red: "Красная карточка",
            card_days_left: "{days} дн.",
            card_reason_prefix: "Причина: ",
            card_suspended_warning: "Запись на игры закрыта.",
            card_tooltip: "{title}: на {weeks} нед. (до {date}, осталось {days}){reason}{suspended}",
            btn_change_group: "Сменить",
            title_select_group: "Выберите группу",
            select_group_desc: "Выберите лигу для просмотра статистики",
            nav_profile: "Профиль",
            nav_history: "История",
            nav_leaderboard: "Топ",
            btn_cancel: "Отмена",
            btn_save: "Сохранить",
            pos_primary_title: "Основная позиция",
            pos_primary_desc: "Выберите вашу главную роль на поле",
            pos_alt_title: "Доп. позиции",
            pos_alt_desc: "Выберите позиции, на которых также играете",
            history_my_games: "Мои игры",
            history_all_games: "Все игры группы",
            history_no_games: "Игр пока нет.",
            history_game_prefix: "ИГРА #{num}",
            history_draw: "Ничья",
            history_win: "Победа",
            history_defeat: "Поражение",
            history_win_team: "Победа {team}",
            team_green: "Зеленые",
            team_orange: "Оранжевые",
            team_blue: "Синие",
            team_white: "Белые",
            team_unknown: "Неизвестно",
            leaderboard_title: "Лидерборд группы",
            leaderboard_games_goals: "{games} игр • {goals} голов",
            btn_close_popup: "Закрыть",
            btn_try_again: "Попробовать снова",
            lbl_ad: "Реклама",
            error_loading_title: "Ошибка загрузки",
            error_no_connection: "Нет связи с сервером. Проверьте интернет или VPN."
        },
        cs: {
            app_title: "Football Manager",
            match_num: "Zápas #{num}",
            status_open: "OTEVŘENO",
            status_active: "AKTIVNÍ",
            status_finished: "ODEHRÁNO",
            loading: "Načítání...",
            lbl_format: "Formát",
            lbl_price: "Startovné",
            lbl_payment: "Platební údaje",
            payment_cash: "Hotově na místě",
            payment_free_corporate: "ZDARMA (Firemní)",
            payment_covered_org: "Hrazeno organizací — startovné se neplatí",
            btn_show_qr: "📱 Zobrazit QR Platbu",
            btn_hide_qr: "🔼 Skrýt QR Platbu",
            qr_scan_hint: "Naskenujte v bankovní aplikaci (SPAYD 1.0)",
            qr_iban_label: "IBAN",
            qr_vs_label: "VS",
            btn_copy_iban: "📋 Kopírovat IBAN",
            iban_copied: "IBAN zkopírován!",
            booking_status: "Stav registrace",
            sec_achievements: "Osobní úspěchy",
            ach_veteran_title: "Veterán",
            ach_veteran_legend: "Klubová legenda",
            ach_veteran_exp: "Zkušený hráč",
            ach_veteran_default: "Veterán",
            ach_veteran_desc_0: "Odehraj 1. zápas",
            ach_veteran_desc_n: "{count} odehraných zápasů",
            ach_striker_title: "Střelec",
            ach_striker_golden: "Zlatá kopačka",
            ach_striker_super: "Super střelec",
            ach_striker_first: "První trefa",
            ach_striker_desc_0: "Vstřel 1. gól",
            ach_striker_desc_n: "{count} vstřelených gólů",
            ach_mvp_title: "MVP zápasu",
            ach_mvp_star: "Superhvězda",
            ach_mvp_top: "Hráč zápasu",
            ach_mvp_desc_0: "Staň se MVP zápasu",
            ach_mvp_desc_n: "{count} ocenění MVP",
            ach_rating_title: "MMR hodnocení",
            ach_rating_supersonic: "Nadzvukový",
            ach_rating_authority: "Postrach favoritů",
            ach_rating_master: "Mistr",
            ach_rating_private: "Nováček",
            ach_rating_desc: "Rating: {rating} MMR",
            ach_rating_desc_default: "Sbírej zkušenosti",
            sec_main_roster: "Hlavní sestava",
            sec_reserve_roster: "Náhradníci",
            roster_empty: "Zatím se nikdo nepřihlásil. Buď první!",
            player_you: "(Ty)",
            player_paid: "✅ Zaplaceno",
            btn_join_game: "⚽ Přihlásit se na zápas",
            btn_join_reserve: "🧤 Přihlásit se mezi náhradníky",
            btn_in_active: "✅ Jsi v hlavní sestavě!",
            btn_in_reserve: "🧤 Jsi na seznamu náhradníků!",
            btn_leave_game: "❌ Odhlásit se ze zápasu",
            btn_back_to_chat: "🔙 Zpět do skupinového chatu",
            btn_match_finished: "Zápas ukončen",
            confirm_leave: "Opravdu se chcete odhlásit ze zápasu?",
            join_success: "Úspěšně jste se přihlásili!",
            leave_success: "Odhlásili jste se ze zápasu.",
            gk_priority_notice: "🧤 Pozor! Prvních {hours} hod. (zbývá {left} hod.) jsou místa v sestavě vyhrazena brankářům (GK).",
            match_finished_notice: "Tento zápas již skončil. Konečné skóre: {score_a} : {score_b}.",
            profile_default_name: "Hráč",
            profile_primary_role: "Hlavní",
            profile_matches: "Zápasy",
            profile_goals: "Celkem gólů",
            profile_primary_pos: "Hlavní pozice",
            profile_alt_pos: "Vedlejší pozice",
            profile_edit: "Upravit",
            profile_not_set: "Neuvedeno",
            card_yellow: "Žlutá karta",
            card_red: "Červená karta",
            card_days_left: "zbývá {days} d.",
            card_reason_prefix: "Důvod: ",
            card_suspended_warning: "Registrace na zápasy je pozastavena.",
            card_tooltip: "{title}: na {weeks} týd. (do {date}, {days}){reason}{suspended}",
            btn_change_group: "Změnit",
            title_select_group: "Vyberte skupinu",
            select_group_desc: "Vyberte ligu pro zobrazení statistik",
            nav_profile: "Profil",
            nav_history: "Historie",
            nav_leaderboard: "Žebříček",
            btn_cancel: "Zrušit",
            btn_save: "Uložit",
            pos_primary_title: "Hlavní pozice",
            pos_primary_desc: "Vyberte svou hlavní roli na hřišti",
            pos_alt_title: "Vedlejší pozice",
            pos_alt_desc: "Vyberte pozice, na kterých také hrajete",
            history_my_games: "Moje zápasy",
            history_all_games: "Všechny zápasy skupiny",
            history_no_games: "Zatím žádné zápasy.",
            history_game_prefix: "ZÁPAS #{num}",
            history_draw: "Remíza",
            history_win: "Výhra",
            history_defeat: "Prohra",
            history_win_team: "Výhra týmu {team}",
            team_green: "Zelení",
            team_orange: "Oranžoví",
            team_blue: "Modří",
            team_white: "Bílí",
            team_unknown: "Neznámý",
            leaderboard_title: "Žebříček skupiny",
            leaderboard_games_goals: "{games} zápasů • {goals} gólů",
            btn_close_popup: "Zavřít",
            btn_try_again: "Zkusit znovu",
            lbl_ad: "Sponzorováno",
            error_loading_title: "Chyba načítání",
            error_no_connection: "Žádné spojení se serverem. Zkontrolujte internet nebo VPN."
        }
    };

    const SUPPORTED_ORDER = ['en', 'ru', 'cs'];
    let availableLocales = [...SUPPORTED_ORDER];
    let currentLang = 'en';
    const listeners = [];
    const loadedRemoteLocales = new Set();

    function normalizeLang(code) {
        if (!code) return 'en';
        const clean = String(code).trim().toLowerCase().split(/[-_]/)[0];
        if (clean === 'cz') return 'cs';
        return clean || 'en';
    }

    function detectLanguage() {
        try {
            const urlParams = new URLSearchParams(window.location.search);
            const rawUrlLang = urlParams.get('lang');
            if (rawUrlLang) {
                const norm = normalizeLang(rawUrlLang);
                localStorage.setItem('webapp_lang', norm);
                return norm;
            }
        } catch (e) {}

        const saved = localStorage.getItem('webapp_lang');
        if (saved) {
            return normalizeLang(saved);
        }

        try {
            const tg = window.Telegram && window.Telegram.WebApp;
            const code = tg?.initDataUnsafe?.user?.language_code;
            if (code) {
                const norm = normalizeLang(code);
                if (DICTIONARY[norm]) return norm;
                return 'en';
            }
        } catch (e) {}

        return 'en';
    }

    async function syncRemoteCatalog(lang) {
        const norm = normalizeLang(lang);
        if (loadedRemoteLocales.has(norm)) return;
        loadedRemoteLocales.add(norm);
        try {
            const res = await fetch(`/api/v1/locales/${encodeURIComponent(norm)}`);
            if (!res.ok) return;
            const payload = await res.json();
            if (payload && payload.messages && typeof payload.messages === 'object') {
                const resolvedCode = normalizeLang(payload.locale || norm);
                if (!DICTIONARY[resolvedCode]) {
                    DICTIONARY[resolvedCode] = {};
                }
                Object.keys(payload.messages).forEach(k => {
                    if (DICTIONARY[resolvedCode][k] === undefined) {
                        DICTIONARY[resolvedCode][k] = payload.messages[k];
                    }
                });
                if (!availableLocales.includes(resolvedCode)) {
                    availableLocales.push(resolvedCode);
                }
                if (currentLang === resolvedCode) {
                    applyDOM();
                }
            }
        } catch (e) {
            // Offline or test environment without backend — built-in DICTIONARY remains active
        }
    }

    async function discoverServerLocales() {
        try {
            const res = await fetch('/api/v1/locales');
            if (!res.ok) return;
            const payload = await res.json();
            if (payload && Array.isArray(payload.locales)) {
                payload.locales.forEach(item => {
                    const code = normalizeLang(item.code);
                    if (code && !availableLocales.includes(code)) {
                        availableLocales.push(code);
                    }
                });
            }
        } catch (e) {}
    }

    function t(key, params) {
        const dict = DICTIONARY[currentLang] || DICTIONARY.en;
        let val = dict[key] !== undefined ? dict[key] : ((DICTIONARY.en && DICTIONARY.en[key]) || key);
        if (params && typeof params === 'object') {
            Object.keys(params).forEach(p => {
                val = val.replaceAll(`{${p}}`, params[p]);
            });
        }
        return val;
    }

    function applyDOM() {
        const dict = DICTIONARY[currentLang] || DICTIONARY.en;

        document.querySelectorAll('[data-i18n]').forEach(el => {
            const k = el.getAttribute('data-i18n');
            const msg = dict[k] !== undefined ? dict[k] : (DICTIONARY.en ? DICTIONARY.en[k] : undefined);
            if (msg !== undefined) {
                el.innerText = msg;
            }
        });

        document.querySelectorAll('[data-i18n-ph]').forEach(el => {
            const k = el.getAttribute('data-i18n-ph');
            const msg = dict[k] !== undefined ? dict[k] : (DICTIONARY.en ? DICTIONARY.en[k] : undefined);
            if (msg !== undefined) {
                el.setAttribute('placeholder', msg);
            }
        });

        const toggleBtn = document.getElementById('lang-toggle-btn') || document.getElementById('lang-globe-btn');
        if (toggleBtn) {
            toggleBtn.innerText = `🌐 ${currentLang.toUpperCase()}`;
        }

        document.documentElement.lang = currentLang;

        listeners.forEach(fn => {
            try { fn(currentLang); } catch (err) { console.error('i18n listener error:', err); }
        });
    }

    function setLanguage(lang) {
        const norm = normalizeLang(lang);
        currentLang = DICTIONARY[norm] ? norm : (availableLocales.includes(norm) ? norm : 'en');
        localStorage.setItem('webapp_lang', currentLang);
        applyDOM();
        syncRemoteCatalog(currentLang);
    }

    function toggleLanguage() {
        const idx = availableLocales.indexOf(currentLang);
        const nextLang = availableLocales[(idx + 1) % availableLocales.length] || 'en';
        setLanguage(nextLang);
    }

    function onLanguageChange(fn) {
        if (typeof fn === 'function') listeners.push(fn);
    }

    // Auto-detect on load (defaulting universally to English per ADR-01)
    currentLang = detectLanguage();
    if (!DICTIONARY[currentLang]) {
        syncRemoteCatalog(currentLang);
    } else {
        syncRemoteCatalog(currentLang);
    }
    discoverServerLocales();

    global.i18n = {
        t,
        normalizeLang,
        get currentLang() { return currentLang; },
        get availableLocales() { return [...availableLocales]; },
        setLanguage,
        toggleLanguage,
        onLanguageChange,
        applyDOM,
        DICTIONARY
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyDOM);
    } else {
        applyDOM();
    }
})(window);
