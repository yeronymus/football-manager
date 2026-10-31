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
            lbl_ad: "Реклама",
            error_loading_title: "Ошибка загрузки",
            error_no_connection: "Нет связи с сервером. Проверьте интернет или VPN."
        }
    };

    let currentLang = 'en';
    const listeners = [];

    function detectLanguage() {
        try {
            const urlParams = new URLSearchParams(window.location.search);
            const urlLang = urlParams.get('lang');
            if (urlLang && (urlLang === 'en' || urlLang === 'ru')) {
                localStorage.setItem('webapp_lang', urlLang);
                return urlLang;
            }
        } catch (e) {}

        const saved = localStorage.getItem('webapp_lang');
        if (saved && (saved === 'en' || saved === 'ru')) return saved;

        try {
            const tg = window.Telegram && window.Telegram.WebApp;
            const code = tg?.initDataUnsafe?.user?.language_code;
            if (code) {
                if (code.toLowerCase().startsWith('ru')) return 'ru';
                return 'en';
            }
        } catch (e) {}

        return 'en';
    }

    function t(key, params) {
        const dict = DICTIONARY[currentLang] || DICTIONARY.en;
        let val = dict[key] || (DICTIONARY.en && DICTIONARY.en[key]) || key;
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
            if (dict[k] !== undefined) {
                el.innerText = dict[k];
            }
        });

        document.querySelectorAll('[data-i18n-ph]').forEach(el => {
            const k = el.getAttribute('data-i18n-ph');
            if (dict[k] !== undefined) {
                el.setAttribute('placeholder', dict[k]);
            }
        });

        const toggleBtn = document.getElementById('lang-toggle-btn') || document.getElementById('lang-globe-btn');
        if (toggleBtn) {
            toggleBtn.innerText = currentLang === 'en' ? '🌐 EN' : '🌐 RU';
        }

        listeners.forEach(fn => {
            try { fn(currentLang); } catch (err) { console.error('i18n listener error:', err); }
        });
    }

    function setLanguage(lang) {
        if (lang !== 'en' && lang !== 'ru') lang = 'en';
        currentLang = lang;
        localStorage.setItem('webapp_lang', lang);
        applyDOM();
    }

    function toggleLanguage() {
        setLanguage(currentLang === 'en' ? 'ru' : 'en');
    }

    function onLanguageChange(fn) {
        if (typeof fn === 'function') listeners.push(fn);
    }

    // Auto-detect on load
    currentLang = detectLanguage();

    global.i18n = {
        t,
        get currentLang() { return currentLang; },
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
