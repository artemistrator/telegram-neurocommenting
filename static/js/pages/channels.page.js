window.App = window.App || {};
window.App.pages = window.App.pages || {};
window.App.pages.channels = window.App.pages.channels || {};

window.App.pages.channels.init = function () {
    console.log('✅ Channels Page Init (Modular)');

    const getChatsBtn = document.getElementById('get-chats-btn');
    const chatSearch = document.getElementById('chat-search');
    const saveChatsBtn = document.getElementById('save-chats-btn');

    // Only proceed if critical elements exist
    if (!getChatsBtn && !chatSearch && !saveChatsBtn && !document.getElementById('chats-table-body')) {
        // Not on channels page
        return;
    }

    if (getChatsBtn) {
        getChatsBtn.addEventListener('click', App.pages.channels.loadChannels);
    }

    if (chatSearch) {
        chatSearch.addEventListener('input', function () {
            if (!App.state.allChats) return; // Guard
            const searchTerm = this.value.toLowerCase();
            const filteredChats = App.state.allChats.filter(chat =>
                chat.name.toLowerCase().includes(searchTerm)
            );
            App.pages.channels.renderTable(filteredChats);
        });
    }

    if (saveChatsBtn) {
        saveChatsBtn.addEventListener('click', App.pages.channels.saveSelectedChats);
    }

    // Initial load if table exists
    if (document.getElementById('chats-table-body')) {
        App.pages.channels.loadChannels();
    }
};

window.App.pages.channels.cleanup = function () {
    console.log('Cleanup Channels Page (Modular)');
    // Listeners are on DOM elements that get replaced, so mostly self-cleaning.
};

window.App.pages.channels.loadChannels = async function () {
    const showToast = (msg, type) => window.App.core.toast ? window.App.core.toast.showToast(msg, type) : console.log(msg);

    try {
        const response = await fetch('/api/chats/list');
        if (response.ok) {
            const result = await response.json();
            App.state.allChats = result.chats;
            App.pages.channels.renderTable(App.state.allChats);
            showToast('Список чатов загружен');
        } else {
            const error = await response.json();
            showToast(`Ошибка загрузки чатов: ${error.detail}`, 'error');
        }
    } catch (error) {
        showToast(`Ошибка сети: ${error.message}`, 'error');
    }
};

window.App.pages.channels.renderTable = function (chats) {
    const tbody = document.getElementById('chats-table-body');
    if (!tbody) return;

    tbody.innerHTML = '';

    // Ensure selectedChats is initialized
    const selectedChats = App.state.selectedChats || [];

    chats.forEach(chat => {
        const row = document.createElement('tr');
        const isSelected = selectedChats.includes(chat.id);

        row.innerHTML = `
    <td class="px-6 py-4 whitespace-nowrap">
        <input type="checkbox" class="chat-checkbox" data-id="${chat.id}" ${isSelected ? 'checked' : ''}>
    </td>
    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${chat.id}</td>
    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${chat.name || 'Без названия'}</td>
    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${chat.type || 'unknown'}</td>
`;
        tbody.appendChild(row);
    });

    // Add event listeners to checkboxes
    document.querySelectorAll('.chat-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            const chatId = parseInt(this.dataset.id);
            // Ensure App.state.selectedChats is updated
            if (!App.state.selectedChats) App.state.selectedChats = [];

            if (this.checked) {
                if (!App.state.selectedChats.includes(chatId)) {
                    App.state.selectedChats.push(chatId);
                }
            } else {
                App.state.selectedChats = App.state.selectedChats.filter(id => id !== chatId);
            }
            // Update stats logic could call global updateStats or similar if needed
            // For now, we update local state only
            if (typeof window.updateStats === 'function') {
                window.updateStats();
            }
        });
    });
};

window.App.pages.channels.saveSelectedChats = async function () {
    const showToast = (msg, type) => window.App.core.toast ? window.App.core.toast.showToast(msg, type) : console.log(msg);

    try {
        const response = await fetch('/api/chats/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chats: App.state.selectedChats || [] })
        });

        if (response.ok) {
            showToast('Выбранные чаты сохранены');
            if (typeof window.updateStats === 'function') {
                window.updateStats();
            }
        } else {
            const error = await response.json();
            showToast(`Ошибка сохранения чатов: ${error.detail}`, 'error');
        }
    } catch (error) {
        showToast(`Ошибка сети: ${error.message}`, 'error');
    }
};
