const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

let selectedPos = '';
const urlParams = new URLSearchParams(window.location.search);
const chatId = urlParams.get('chat_id');
const gameId = urlParams.get('game_id');

function setPos(pos) {
    selectedPos = pos;
    document.querySelectorAll('.pos-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.innerText === pos) btn.classList.add('active');
    });
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
                chat_id: chatId
            })
        });

        if (response.ok) {
            tg.HapticFeedback.notificationOccurred('success');
            // Redirect to profile with current chat context if available
            let profileUrl = '/web/profile.html';
            if (chatId) profileUrl += `?chat_id=${chatId}`;
            window.location.href = profileUrl;
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
