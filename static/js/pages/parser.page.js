window.App = window.App || { pages: {} };

window.App.pages.parser = {
    lastSource: 'search_parser',  // По умолчанию поиск
    
async init() {
console.log('✅ Parser Page Init START');

    try {
        // 1. Загрузить listener аккаунты
        await this.loadListeners();
        
        // 2. Привязать события к кнопкам
        this.bindEvents();
        
        // 3. Добавить секцию ручного ввода
        this.setupManualInput();
        
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
        
        // Создать dropdown если его нет
        let select = document.getElementById('listener-select');
        
        if (!select) {
            // Найти контейнер формы поиска
            const searchForm = document.querySelector('.bg-white.rounded-lg.shadow-md');
            if (!searchForm) return;
            
            // Создать label + select
            const container = document.createElement('div');
            container.className = 'mb-4';
            container.innerHTML = `
                <label class="block text-sm font-medium text-gray-700 mb-1">
                    Listener аккаунт (для парсинга)
                </label>
                <select id="listener-select" 
                    class="w-full p-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="">Выберите listener аккаунт</option>
                </select>
            `;
            
            // Вставить в начало формы
            searchForm.insertBefore(container, searchForm.firstChild);
            select = document.getElementById('listener-select');
        }
        
        // Заполнить options
        select.innerHTML = '<option value="">Выберите listener аккаунт</option>';
        accounts.forEach(acc => {
            const option = document.createElement('option');
            option.value = acc.id;
            option.textContent = `${acc.name} (${acc.phone})`;
            if (acc.is_listener) {
                option.selected = true;
                console.log('Current listener:', acc.phone);
            }
            select.appendChild(option);
        });
        
        // Привязать событие изменения
        select.onchange = async (e) => {
            if (e.target.value) {
                await this.setListener(parseInt(e.target.value));
            }
        };
        
    } catch (err) {
        console.error('Error loading listeners:', err);
        showToast('Ошибка загрузки аккаунтов', 'error');
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
        const commentsIcon = ch.has_comments ? '💬 Да' : '🚫 Нет';
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
            <td class="px-6 py-4 text-gray-500">${commentsIcon}</td>
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
            has_comments: cells[3].textContent.includes('💬'), // ← НОВОЕ
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

setupManualInput() {
    // ПРОВЕРКА: если секция уже существует — не создавать повторно
    if (document.getElementById('manual-input-section')) {
        console.log('[Parser] Manual input section already exists, skipping');
        return;
    }

    const searchForm = document.querySelector('.bg-white.rounded-lg.shadow-md');
    if (!searchForm) return;

    const manualSection = document.createElement('div');
    manualSection.id = 'manual-input-section';  // ← Добавить ID для проверки
    manualSection.className = 'mt-6 pt-6 border-t border-gray-200';
    manualSection.innerHTML = `
        <h3 class="text-lg font-semibold mb-3 text-gray-700">Или добавить вручную</h3>
        <textarea id="manual-urls" rows="3" 
            placeholder="https://t.me/pythonru&#10;@channel_name"
            class="w-full p-2 border rounded-md"></textarea>
        <button id="add-manual-btn" 
            class="mt-2 bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-md font-medium transition">
            ➕ Добавить
        </button>
    `;

    searchForm.appendChild(manualSection);
    
    document.getElementById('add-manual-btn').onclick = () => this.addManualChannels();
},

async addManualChannels() {
    const textarea = document.getElementById('manual-urls');
    const urls = textarea.value.split('\n')
        .map(u => u.trim())
        .filter(u => u.length > 0);
    
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
        textarea.value = '';
        
    } catch (err) {
        console.error('Manual channels error:', err);
        showToast('Ошибка: ' + err.message, 'error');
    } finally {
        loading.classList.add('hidden');
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