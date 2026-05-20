const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

let selectedPos = '';
let selectedAlts = [];
const urlParams = new URLSearchParams(window.location.search);
const chatId = urlParams.get('chat_id');
const gameId = urlParams.get('game_id');

function setPos(pos) {
    selectedPos = pos;
    // Highlight primary buttons
    document.querySelectorAll('.position-grid:not(#alt-pos-grid) .pos-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.innerText === pos) btn.classList.add('active');
    });

    // If the new primary position was selected as alternative, remove it
    const altIdx = selectedAlts.indexOf(pos);
    if (altIdx !== -1) {
        selectedAlts.splice(altIdx, 1);
        // Find corresponding alt button and deactivate it
        document.querySelectorAll('#alt-pos-grid .alt-pos-btn').forEach(btn => {
            if (btn.innerText === pos) btn.classList.remove('active');
        });
    }
}

function toggleAltPos(pos, btn) {
    if (pos === selectedPos) {
        tg.showAlert('Эта позиция уже выбрана как основная.');
        return;
    }

    const idx = selectedAlts.indexOf(pos);
    if (idx !== -1) {
        selectedAlts.splice(idx, 1);
        btn.classList.remove('active');
    } else {
        if (selectedAlts.length >= 2) {
            tg.showAlert('Можно выбрать не более двух дополнительных позиций.');
            return;
        }
        selectedAlts.push(pos);
        btn.classList.add('active');
    }
}

document.getElementById('submit-btn').addEventListener('click', async () => {
    const fullName = document.getElementById('full-name').value.trim();
    
    if (!fullName) {
        tg.showAlert('Пожалуйста, введите имя и фамилию.');
        return;
    }
    if (!selectedPos) {
        tg.showAlert('Пожалуйста, выберите позицию.');
        return;
    }

    const loader = document.getElementById('loader');
    loader.style.display = 'flex';

    try {
        const response = await fetch('/api/users/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `tma ${tg.initData}`
            },
            body: JSON.stringify({
                name: fullName,
                position: selectedPos,
                alt_positions: selectedAlts,
                chat_id: chatId
            })
        });

        if (response.ok) {
            tg.HapticFeedback.notificationOccurred('success');
            // Redirect to game or profile depending on context
            let redirectUrl = gameId ? `/web/game.html?game_id=${gameId}` : '/web/profile.html';
            if (chatId && !gameId) redirectUrl += `?chat_id=${chatId}`;
            window.location.href = redirectUrl;
        } else {
            const err = await response.json();
            tg.showAlert(`Ошибка: ${err.detail || 'Не удалось зарегистрироваться'}`);
            loader.style.display = 'none';
        }
    } catch (e) {
        tg.showAlert('Сетевая ошибка при регистрации.');
        loader.style.display = 'none';
    }
});

// Hide loader after initial load
window.addEventListener('load', () => {
    setTimeout(() => {
        document.getElementById('loader').style.display = 'none';
    }, 500);
});
