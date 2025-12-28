window.App = window.App || { pages: {} };

function getCheckCircleIcon() {
    return `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 mr-1 inline">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>`;
}

function getXCircleIcon() {
    return `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 mr-1 inline">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>`;
}

function getClockIcon() {
    return `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4 mr-1 inline animate-spin">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>`;
}

window.App.pages.parser = {
    lastSource: 'search_parser',  // По умолчанию поиск
    
async init() {
console.log('✅ Parser Page Init START');

    try {
        // 1. Загрузить listener аккаунты
        await this.loadListeners();
        
        // 2. Привязать события к кнопкам
        this.bindEvents();
        
        console.log('✅ Parser Page Init DONE');
    } catch (err) {
        console.error('❌ Parser Init Error:', err);
    }
},

async loadListeners() {
    try {
        const response = await fetch('/api/parser/available-listeners');
        if (!response.ok) throw new Error('Failed to load listeners');
        
        const accounts = await response.json();
        console.log('Loaded listeners:', accounts);
        
        // Check if there are any listener accounts
        // The API returns accounts with id, phone, name, and is_listener fields
        // is_listener is true if the account's work_mode is 'listener'
        const listeners = accounts.filter(acc => acc.is_listener);
        
        console.log('All accounts:', accounts); // Debug: see all accounts
        console.log('Account structure:', accounts.length > 0 ? accounts[0] : 'No accounts'); // Debug: see account structure
        
        // Use the checkListenerAccounts function to handle filtering and UI updates
        await this.checkListenerAccounts(accounts);
        
        // Filtering and UI updates are now handled in checkListenerAccounts function
        // This block is now redundant and will be removed
        
    } catch (err) {
        console.error('Error loading listeners:', err);
        showToast('Ошибка загрузки аккаунтов', 'error');
    }
},

populateListenerDropdown(listeners) {
    const select = document.getElementById('listener-account');
    if (!select) return;
    
    // Clear existing options except the first one
    select.innerHTML = '<option value="">Выберите listener аккаунт</option>';
    
    listeners.forEach(acc => {
        const option = document.createElement('option');
        option.value = acc.id;
        // Use phone number in the display, fallback to name or id if no phone
        option.textContent = acc.phone || acc.name || acc.id;
        if (acc.is_listener) {
            option.selected = true;
            console.log('Current listener:', acc.phone);
        }
        select.appendChild(option);
    });
    
    // Enable search button if listener is selected
    select.onchange = (e) => {
        const searchBtn = document.getElementById('search-btn');
        searchBtn.disabled = !e.target.value;
    };
},

async checkListenerAccounts(accounts) {
    console.log('All accounts:', accounts); // Debug: see all accounts
    
    const listeners = accounts.filter(acc =>
        acc.is_listener ||
        (acc.work_mode && acc.work_mode.toLowerCase() === 'listener')
    );
    console.log('Filtered listeners:', listeners); // Debug: see filtered results
    
    if (listeners.length === 0) {
        document.getElementById('no-listener-warning').classList.remove('hidden');
        document.getElementById('search-btn').disabled = true;
    } else {
        document.getElementById('no-listener-warning').classList.add('hidden');
        this.populateListenerDropdown(listeners);
    }
},

async setListener(accountId) {
    try {
        const response = await fetch(`/api/parser/${accountId}/set-listener`, {
            method: 'PATCH'
        });
        
        if (!response.ok) throw new Error('Failed to set listener');
        
        showToast('Listener назначен', 'success');
    } catch (err) {
        console.error('Error setting listener:', err);
        showToast('Ошибка назначения listener', 'error');
    }
},

bindEvents() {
    // Кнопка поиска
    const searchBtn = document.getElementById('search-btn');
    if (searchBtn) {
        searchBtn.onclick = () => this.searchChannels();
    }
    
    // Кнопка обновления
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.onclick = () => this.loadListeners();
    }
    
    // Кнопка добавления в мониторинг
    const addBtn = document.getElementById('add-selected-btn');
    if (addBtn) {
        addBtn.onclick = () => this.addToMonitoring();
    }
    
    // Select All checkbox
    const selectAll = document.getElementById('select-all');
    if (selectAll) {
        selectAll.onchange = (e) => {
            document.querySelectorAll('.channel-checkbox').forEach(cb => {
                cb.checked = e.target.checked;
            });
            this.updateAddButton();
        };
    }
    
    // Manual input button
    const addManualBtn = document.getElementById('add-manual-btn');
    if (addManualBtn) {
        addManualBtn.onclick = () => this.validateAndAddChannels();
    }
},

validateAndAddChannels() {
    const textarea = document.getElementById('manual-channels');
    const lines = textarea.value.split('\n').filter(line => line.trim());
    
    const validChannels = [];
    const invalidLines = [];
    
    lines.forEach((line, index) => {
        const trimmed = line.trim();
        
        // Valid formats:
        // - https://t.me/channel_name
        // - @channel_name
        // - t.me/channel_name
        
        const regex = /^(?:https?:\/\/)?(?:www\.)?t\.me\/[\w\d_]+$|^@[\w\d_]+$/i;
        
        if (regex.test(trimmed)) {
            validChannels.push(trimmed);
        } else {
            invalidLines.push(`Строка ${index + 1}: "${trimmed}"`);
        }
    });
    
    // Remove duplicates
    const uniqueChannels = [...new Set(validChannels)];
    
    if (invalidLines.length > 0) {
        showToast('error', `Неверный формат:\n${invalidLines.join('\n')}`);
        return;
    }
    
    if (uniqueChannels.length === 0) {
        showToast('error', 'Не найдено валидных каналов');
        return;
    }
    
    // Send to backend
    this.addManualChannels(uniqueChannels);
    showToast('success', `Добавлено каналов: ${uniqueChannels.length}`);
    textarea.value = ''; // Clear textarea
},

async searchChannels() {
    const keywordsInput = document.getElementById('keywords');
    const minSubsInput = document.getElementById('min_subscribers');
    const searchBtn = document.getElementById('search-btn');
    const loading = document.getElementById('table-loading');
    
    const keywords = keywordsInput.value.split('\n').filter(k => k.trim());
    const minSubs = parseInt(minSubsInput.value) || 100;
    
    if (!keywords.length) {
        showToast('Введите хотя бы одно ключевое слово', 'error');
        return;
    }
    
    // Показать loading
    loading.classList.remove('hidden');
    searchBtn.disabled = true;
    
    try {
        const response = await fetch('/api/parser/search-channels', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                keywords,
                min_subscribers: minSubs,
                limit: 50
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Search failed');
        }
        
        const data = await response.json();
        this.lastSource = 'search_parser';  // ← Запомнить источник
        this.displayResults(data.channels || []);
        showToast(`Найдено ${data.channels.length} каналов`, 'success');
        
    } catch (err) {
        console.error('Search error:', err);
        showToast('Ошибка поиска: ' + err.message, 'error');
    } finally {
        loading.classList.add('hidden');
        searchBtn.disabled = false;
    }
},

async addManualChannels(urls) {
    if (!urls.length) {
        showToast('Введите хотя бы одну ссылку', 'error');
        return;
    }
    
    console.log('[Parser] Manual add URLs:', urls);  // DEBUG
    
    const loading = document.getElementById('table-loading');
    loading.classList.remove('hidden');
    
    try {
        const response = await fetch('/api/parser/add-manual-channels', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls: urls })  // ← ПРАВИЛЬНЫЙ ФОРМАТ
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to resolve channels');
        }
        
        const data = await response.json();
        
        if (!data.channels || data.channels.length === 0) {
            showToast('Не удалось резолвить каналы', 'error');
            return;
        }
        
        this.lastSource = 'manual';  // ← Запомнить источник
        this.displayResults(data.channels);
        showToast(`Резолвлено ${data.channels.length} каналов`, 'success');
        
    } catch (err) {
        console.error('Manual channels error:', err);
        showToast('Ошибка: ' + err.message, 'error');
    } finally {
        loading.classList.add('hidden');
    }
},

displayResults(channels) {
    const tbody = document.getElementById('results-table');
    const noResults = document.getElementById('no-results');
    const resultsCount = document.getElementById('results-count');
    
    tbody.innerHTML = '';
    
    if (!channels.length) {
        noResults.classList.remove('hidden');
        resultsCount.textContent = '0';
        return;
    }
    
    noResults.classList.add('hidden');
    resultsCount.textContent = channels.length;
    
    channels.forEach(ch => {
        const tr = document.createElement('tr');
        
        // Update comments display based on has_comments field
        let commentsDisplay = `<span class="text-gray-500 flex items-center">${getClockIcon()} Проверяется...</span>`;
        if (ch.has_comments === true) {
            commentsDisplay = `<span class="text-green-600 flex items-center">${getCheckCircleIcon()} Открыты</span>`;
        } else if (ch.has_comments === false) {
            commentsDisplay = `<span class="text-red-600 flex items-center">${getXCircleIcon()} Закрыты</span>`;
        }
        
        const url = ch.url || `https://t.me/${ch.username || ''}`;
        
        tr.innerHTML = `
            <td class="px-6 py-4">
                <input type="checkbox" value="${ch.channel_id}" 
                    data-username="${ch.username || ''}" 
                    data-url="${url}"
                    class="channel-checkbox h-4 w-4 text-blue-600 rounded">
            </td>
            <td class="px-6 py-4 font-medium text-gray-900">${ch.title}</td>
            <td class="px-6 py-4 text-gray-500">${(ch.subscribers || 0).toLocaleString()}</td>
            <td class="px-6 py-4 text-gray-500">${commentsDisplay}</td>
            <td class="px-6 py-4 text-gray-500"><a href="${url}" target="_blank" class="text-blue-600 hover:underline">${url}</a></td>
        `;
        tbody.appendChild(tr);
        
        // Привязать событие к checkbox
        tr.querySelector('.channel-checkbox').onchange = () => this.updateAddButton();
    });
},

updateAddButton() {
    const addBtn = document.getElementById('add-selected-btn');
    const selected = document.querySelectorAll('.channel-checkbox:checked');
    addBtn.disabled = selected.length === 0;
},

async addToMonitoring() {
    const selected = [];
    document.querySelectorAll('.channel-checkbox:checked').forEach(cb => {
        const row = cb.closest('tr');
        const cells = row.querySelectorAll('td');
        selected.push({
            channel_id: parseInt(cb.value),
            title: cells[1].textContent,
            subscribers: parseInt(cells[2].textContent.replace(/\D/g, '')) || 0,
            has_comments: cells[3].innerHTML.includes('✅ Открыты'), // ← Updated to use has_comments field
            url: `https://t.me/${cb.dataset.username || ''}`
        });
    });
    
    if (!selected.length) {
        showToast('Выберите хотя бы один канал', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/parser/add-to-monitoring', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                channels: selected,
                source: this.lastSource  // ← Передать источник
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add channels');
        }
        
        const data = await response.json();
        if (data.errors && data.errors.length > 0) {
            showToast(`Добавлено ${data.added} каналов. Ошибок: ${data.errors.length}`, 'warning');
        } else {
            showToast(`Добавлено ${data.added} каналов`, 'success');
        }
        
        // Очистить выделение
        document.querySelectorAll('.channel-checkbox:checked').forEach(cb => cb.checked = false);
        this.updateAddButton();
        
    } catch (err) {
        console.error('Error adding channels:', err);
        showToast('Ошибка добавления каналов: ' + err.message, 'error');
    }
},



cleanup() {
    console.log('Parser Page: Cleanup');
    // Очистка при выходе со страницы
}
};

// Экпорт для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
module.exports = window.App.pages.parser;
}