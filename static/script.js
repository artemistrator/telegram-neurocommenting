// Global variables
let selectedChats = [];
let allChats = [];
let isTelegramConfigSaved = false;

// DOM Elements
const toast = document.getElementById('toast');
const toastMessage = document.getElementById('toast-message');
const authorizeBtn = document.getElementById('authorize-btn');

// Show toast notification
function showToast(message, type = 'success') {
    toastMessage.textContent = message;
    toastMessage.className = `px-4 py-2 rounded shadow-lg text-white ${type === 'success' ? 'bg-green-500' : 'bg-red-500'}`;
    toast.classList.remove('hidden');
    toast.classList.add('flex');

    setTimeout(() => {
        toast.classList.add('hidden');
        toast.classList.remove('flex');
    }, 3000);
}

// Helper: Update UI state based on auth status
function updateAuthUI(isAuthorized) {
    const saveBtn = document.getElementById('save-telegram-settings');
    const authBtn = document.getElementById('authorize-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const inputs = ['api-id', 'api-hash', 'phone', 'session'];

    if (isAuthorized) {
        // Authorized state
        if (saveBtn) saveBtn.classList.add('hidden');
        if (authBtn) authBtn.classList.add('hidden');
        if (logoutBtn) logoutBtn.classList.remove('hidden');
        inputs.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.setAttribute('readonly', 'true');
        });
    } else {
        // Unauthorized state
        if (saveBtn) saveBtn.classList.remove('hidden');
        if (authBtn) authBtn.classList.remove('hidden');
        if (logoutBtn) logoutBtn.classList.add('hidden');
        inputs.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.removeAttribute('readonly');
        });
    }
}

// Helper: Fill empty read-only fields with asterisks
function fillEmptyReadOnlyFields() {
    const inputs = ['api-id', 'api-hash', 'phone', 'session'];
    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el && el.hasAttribute('readonly') && !el.value) {
            el.value = '*****';
        }
    });
}

// Load current configuration
async function loadCurrentConfig() {
    try {
        const response = await fetch('/api/config/get');
        if (response.ok) {
            const data = await response.json();

            // Debug: log what we received
            console.log('Loading config...', data);

            // Fill Telegram fields if data exists
            if (data.telegram) {
                if (data.telegram.api_id) document.getElementById('api-id').value = data.telegram.api_id;
                if (data.telegram.api_hash) document.getElementById('api-hash').value = data.telegram.api_hash;
                if (data.telegram.phone) document.getElementById('phone').value = data.telegram.phone;
                if (data.telegram.session) document.getElementById('session').value = data.telegram.session;
            }

            // Fill Webhook
            if (data.webhook_url) {
                document.getElementById('webhook-url').placeholder = data.webhook_url;
            }

            // Update monitored chats count
            const chatsCountEl = document.getElementById('monitored-chats-count');
            if (chatsCountEl) chatsCountEl.textContent = data.monitored_chats_count;

            // Render monitored chats from config immediately
            if (data.monitored_chats && data.monitored_chats.length > 0) {
                const savedChats = data.monitored_chats.map(c => ({
                    id: c.id,
                    name: c.name || 'Saved Chat ' + c.id,
                    type: 'saved'
                }));

                selectedChats = savedChats.map(c => c.id);
                allChats = savedChats;
                renderChatsTable(savedChats);
            }

            // Force check auth status to show/hide Logout button
            fetch('/api/telegram/status')
                .then(r => r.json())
                .then(status => {
                    if (status.authorized) {
                        document.getElementById('logout-btn').classList.remove('hidden');
                        document.getElementById('authorize-btn').classList.add('hidden');
                    }
                });
        }
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

// Enable authorize button if config is saved
function updateAuthorizeButton() {
    const apiId = document.getElementById('api-id').value;
    const apiHash = document.getElementById('api-hash').value;
    const phone = document.getElementById('phone').value;

    if (apiId && apiHash && phone) {
        authorizeBtn.classList.remove('disabled');
    } else {
        authorizeBtn.classList.add('disabled');
    }
}

// Initialize event listeners once DOM is loaded
document.addEventListener('DOMContentLoaded', () => {

    // Save Telegram settings
    const saveTgBtn = document.getElementById('save-telegram-settings');
    if (saveTgBtn) {
        saveTgBtn.addEventListener('click', async () => {
            const data = {
                api_id: document.getElementById('api-id').value,
                api_hash: document.getElementById('api-hash').value,
                phone: document.getElementById('phone').value,
                session: document.getElementById('session').value || 'telegram_session'
            };

            try {
                const response = await fetch('/api/telegram/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (response.ok) {
                    isTelegramConfigSaved = true;
                    updateAuthorizeButton();
                    showToast('Настройки Telegram сохранены');
                } else {
                    const error = await response.json();
                    showToast(`Ошибка сохранения настроек: ${error.detail}`, 'error');
                }
            } catch (error) {
                showToast(`Ошибка сети: ${error.message}`, 'error');
            }
        });
    }

    // Logout button handler
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            if (!confirm('Вы уверены? Это удалит сессию Telegram.')) return;

            try {
                const response = await fetch('/api/telegram/logout', { method: 'POST' });
                if (response.ok) {
                    showToast('Сессия сброшена. Перезагрузите страницу.');
                    // Clear fields
                    document.getElementById('api-id').placeholder = '';
                    document.getElementById('api-hash').placeholder = '';
                    document.getElementById('phone').value = '';
                    // Hide logout button, show authorize
                    logoutBtn.classList.add('hidden');
                    authorizeBtn.classList.remove('hidden');
                } else {
                    const error = await response.json();
                    showToast(`Ошибка: ${error.detail}`, 'error');
                }
            } catch (error) {
                showToast(`Ошибка сети: ${error.message}`, 'error');
            }
        });
    }

    // Start authorization
    if (authorizeBtn) {
        authorizeBtn.addEventListener('click', async () => {
            // 1. First SAVE the settings
            const data = {
                api_id: document.getElementById('api-id').value,
                api_hash: document.getElementById('api-hash').value,
                phone: document.getElementById('phone').value,
                session: document.getElementById('session').value || 'telegram_session'
            };

            try {
                // Save request
                const saveResponse = await fetch('/api/telegram/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                if (!saveResponse.ok) {
                    const error = await saveResponse.json();
                    showToast(`Ошибка сохранения: ${error.detail}`, 'error');
                    return; // Stop if save failed
                }

                // 2. If save successful, start AUTH
                const response = await fetch('/api/telegram/auth/start', { method: 'POST' });
                if (response.ok) {
                    document.getElementById('auth-modal').classList.remove('hidden');
                    document.getElementById('auth-modal').classList.add('flex');
                    showToast('Код отправлен');
                } else {
                    const error = await response.json();
                    if (error.detail && error.detail.includes('ResendCodeRequest')) {
                        document.getElementById('auth-modal').classList.remove('hidden');
                        document.getElementById('auth-modal').classList.add('flex');
                        showToast('Код уже был отправлен, пожалуйста, введите его');
                    } else {
                        showToast(`Ошибка авторизации: ${error.detail}`, 'error');
                    }
                }
            } catch (error) {
                showToast(`Ошибка сети: ${error.message}`, 'error');
            }
        });
    }

    // Cancel Auth
    const cancelAuthBtn = document.getElementById('cancel-auth-btn');
    if (cancelAuthBtn) {
        cancelAuthBtn.addEventListener('click', () => {
            document.getElementById('auth-modal').classList.add('hidden');
            document.getElementById('auth-modal').classList.remove('flex');
        });
    }

    // Submit Code
    const submitCodeBtn = document.getElementById('submit-code-btn');
    if (submitCodeBtn) {
        submitCodeBtn.addEventListener('click', async () => {
            const code = document.getElementById('auth-code').value;
            if (!code) {
                showToast('Введите код', 'error');
                return;
            }

            try {
                const response = await fetch('/api/telegram/auth/code', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: code })
                });

                if (response.ok) {
                    const result = await response.json();

                    if (result.status === 'need_2fa') {
                        // 2FA required
                        document.getElementById('auth-modal').classList.add('hidden');
                        document.getElementById('auth-modal').classList.remove('flex');
                        document.getElementById('password-modal').classList.remove('hidden');
                        document.getElementById('password-modal').classList.add('flex');
                        showToast('Требуется облачный пароль');
                    } else if (result.status === 'success') {
                        // Success
                        document.getElementById('auth-modal').classList.add('hidden');
                        document.getElementById('auth-modal').classList.remove('flex');
                        updateAuthUI(true);
                        fillEmptyReadOnlyFields();
                        showToast('Авторизация успешна');
                    }
                } else {
                    const error = await response.json();
                    showToast(`Ошибка: ${error.detail}`, 'error');
                }
            } catch (error) {
                showToast(`Ошибка сети: ${error.message}`, 'error');
            }
        });
    }

    // Cancel Password
    const cancelPassBtn = document.getElementById('cancel-password-btn');
    if (cancelPassBtn) {
        cancelPassBtn.addEventListener('click', () => {
            document.getElementById('password-modal').classList.add('hidden');
            document.getElementById('password-modal').classList.remove('flex');
        });
    }

    // Submit Password
    const submitPassBtn = document.getElementById('submit-password-btn');
    if (submitPassBtn) {
        submitPassBtn.addEventListener('click', async () => {
            const password = document.getElementById('auth-password').value;
            if (!password) {
                showToast('Введите пароль', 'error');
                return;
            }

            try {
                const response = await fetch('/api/telegram/auth/password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: password })
                });

                if (response.ok) {
                    document.getElementById('password-modal').classList.add('hidden');
                    document.getElementById('password-modal').classList.remove('flex');
                    updateAuthUI(true);
                    fillEmptyReadOnlyFields();
                    showToast('Авторизация успешна');
                } else {
                    const error = await response.json();
                    showToast(`Ошибка: ${error.detail}`, 'error');
                }
            } catch (error) {
                showToast(`Ошибка сети: ${error.message}`, 'error');
            }
        });
    }

    // Get chats list
    const getChatsBtn = document.getElementById('get-chats-btn');
    if (getChatsBtn) {
        getChatsBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/chats/list');
                if (response.ok) {
                    const result = await response.json();
                    allChats = result.chats;
                    renderChatsTable(allChats);
                    showToast('Список чатов загружен');
                } else {
                    const error = await response.json();
                    showToast(`Ошибка загрузки чатов: ${error.detail}`, 'error');
                }
            } catch (error) {
                showToast(`Ошибка сети: ${error.message}`, 'error');
            }
        });
    }

    // Chat search
    const chatSearch = document.getElementById('chat-search');
    if (chatSearch) {
        chatSearch.addEventListener('input', function () {
            const searchTerm = this.value.toLowerCase();
            const filteredChats = allChats.filter(chat =>
                chat.name.toLowerCase().includes(searchTerm)
            );
            renderChatsTable(filteredChats);
        });
    }

    // Save selected chats
    const saveChatsBtn = document.getElementById('save-chats-btn');
    if (saveChatsBtn) {
        saveChatsBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/chats/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ chats: selectedChats })
                });

                if (response.ok) {
                    showToast('Выбранные чаты сохранены');
                    updateStats();
                } else {
                    const error = await response.json();
                    showToast(`Ошибка сохранения чатов: ${error.detail}`, 'error');
                }
            } catch (error) {
                showToast(`Ошибка сети: ${error.message}`, 'error');
            }
        });
    }

    // Save webhook
    const saveWebhookBtn = document.getElementById('save-webhook-btn');
    if (saveWebhookBtn) {
        saveWebhookBtn.addEventListener('click', async () => {
            const url = document.getElementById('webhook-url').value;
            try {
                const response = await fetch('/api/webhook/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });

                if (response.ok) {
                    showToast('Webhook URL сохранен');
                } else {
                    const error = await response.json();
                    showToast(`Ошибка сохранения webhook: ${error.detail}`, 'error');
                }
            } catch (error) {
                showToast(`Ошибка сети: ${error.message}`, 'error');
            }
        });
    }

    // Test webhook
    const testWebhookBtn = document.getElementById('test-webhook-btn');
    if (testWebhookBtn) {
        testWebhookBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/webhook/test', { method: 'POST' });
                if (response.ok) {
                    const result = await response.json();
                    showToast(result.message);
                } else {
                    const error = await response.json();
                    showToast(`Ошибка: ${error.detail}`, 'error');
                }
            } catch (error) {
                showToast(`Ошибка сети: ${error.message}`, 'error');
            }
        });
    }

    // Save AI settings
    const saveAiBtn = document.getElementById('save-ai-settings');
    if (saveAiBtn) {
        saveAiBtn.addEventListener('click', async () => {
            const settings = {
                ai_enabled: document.getElementById('ai-enabled').checked,
                openai_api_key: document.getElementById('openai-api-key').value,
                openai_model: document.getElementById('openai-model').value,
                system_prompt: document.getElementById('openai-prompt').value,
                min_words: parseInt(document.getElementById('min-words').value) || 5,
                use_triggers: document.getElementById('use-triggers').checked,
                trigger_words: document.getElementById('trigger-words').value
                    .split(',')
                    .map(word => word.trim())
                    .filter(word => word.length > 0)
            };

            try {
                const response = await fetch('/api/openai/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });

                if (response.ok) {
                    showToast('Настройки AI сохранены');
                    updateStats();
                } else {
                    let errorMessage = 'Ошибка сохранения настроек AI';
                    try {
                        const errorText = await response.text();
                        errorMessage = errorText || errorMessage;
                    } catch (e) { }
                    showToast(errorMessage, 'error');
                }
            } catch (error) {
                showToast(`Ошибка сети: ${error.message}`, 'error');
            }
        });
    }

    // Start monitoring
    const startBtn = document.getElementById('start-monitoring-btn');
    if (startBtn) {
        startBtn.addEventListener('click', async () => {
            console.log('Start monitoring clicked');
            try {
                const response = await fetch('/api/monitor/start', { method: 'POST' });
                if (response.ok) {
                    showToast('Мониторинг запущен');
                    updateMonitoringStatus();
                } else {
                    const error = await response.json();
                    showToast(`Ошибка запуска: ${error.detail}`, 'error');
                }
            } catch (error) {
                showToast(`Ошибка сети: ${error.message}`, 'error');
            }
        });
    }

    // Stop monitoring
    const stopBtn = document.getElementById('stop-monitoring-btn');
    if (stopBtn) {
        stopBtn.addEventListener('click', async () => {
            console.log('Stop monitoring clicked');
            try {
                const response = await fetch('/api/monitor/stop', { method: 'POST' });
                if (response.ok) {
                    showToast('Мониторинг остановлен');
                    updateMonitoringStatus();
                } else {
                    const error = await response.json();
                    showToast(`Ошибка остановки: ${error.detail}`, 'error');
                }
            } catch (error) {
                showToast(`Ошибка сети: ${error.message}`, 'error');
            }
        });
    }

    // Event listeners for AI settings UI updates
    const aiEnabledCheckbox = document.getElementById('ai-enabled');
    if (aiEnabledCheckbox) {
        aiEnabledCheckbox.addEventListener('change', updateAIUI);
    }
    const useTriggersCheckbox = document.getElementById('use-triggers');
    if (useTriggersCheckbox) {
        useTriggersCheckbox.addEventListener('change', updateAIUI);
    }

    // Initialize input listeners
    const apiIdInput = document.getElementById('api-id');
    if (apiIdInput) apiIdInput.addEventListener('input', updateAuthorizeButton);
    const apiHashInput = document.getElementById('api-hash');
    if (apiHashInput) apiHashInput.addEventListener('input', updateAuthorizeButton);
    const phoneInput = document.getElementById('phone');
    if (phoneInput) phoneInput.addEventListener('input', updateAuthorizeButton);

    // Start app initialization
    init();
});

// Render chats table
function renderChatsTable(chats) {
    const tbody = document.getElementById('chats-table-body');
    if (!tbody) return;

    tbody.innerHTML = '';

    chats.forEach(chat => {
        const row = document.createElement('tr');
        const isSelected = selectedChats.includes(chat.id);

        row.innerHTML = `
    <td class="px-6 py-4 whitespace-nowrap">
        <input type="checkbox" class="chat-checkbox" data-id="${chat.id}" ${isSelected ? 'checked' : ''}>
    </td>
    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${chat.id}</td>
    <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${chat.name}</td>
    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${chat.type}</td>
`;

        tbody.appendChild(row);
    });

    // Add event listeners to checkboxes
    document.querySelectorAll('.chat-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            const chatId = parseInt(this.dataset.id);
            if (this.checked) {
                if (!selectedChats.includes(chatId)) {
                    selectedChats.push(chatId);
                }
            } else {
                selectedChats = selectedChats.filter(id => id !== chatId);
            }
        });
    });
}

// Update statistics
function updateStats() {
    const chatsCountEl = document.getElementById('monitored-chats-count');
    if (chatsCountEl) chatsCountEl.textContent = selectedChats.length;

    const triggerWordsInput = document.getElementById('trigger-words');
    if (triggerWordsInput) {
        const triggerWordsText = triggerWordsInput.value;
        const triggerWordsCount = triggerWordsText.split(',')
            .map(word => word.trim())
            .filter(word => word.length > 0)
            .length;
        const keywordsCountEl = document.getElementById('keywords-count');
        if (keywordsCountEl) keywordsCountEl.textContent = triggerWordsCount;
    }
}

// Update AI UI based on settings
function updateAIUI() {
    const aiEnabledCheckbox = document.getElementById('ai-enabled');
    const useTriggersCheckbox = document.getElementById('use-triggers');

    if (!aiEnabledCheckbox || !useTriggersCheckbox) return;

    const aiEnabled = aiEnabledCheckbox.checked;
    const useTriggers = useTriggersCheckbox.checked;

    const aiSettingsContainer = document.getElementById('ai-settings-container');
    if (aiSettingsContainer) aiSettingsContainer.style.display = aiEnabled ? 'block' : 'none';

    const triggerWordsContainer = document.getElementById('trigger-words-container');
    if (triggerWordsContainer) triggerWordsContainer.style.display = (aiEnabled && useTriggers) ? 'block' : 'none';
}

// Helper to generate unique signature for event
function getEventSignature(data) {
    // Create a hash-like string from time, chat, and text
    return `${data.time || ''}-${data.chat_name || ''}-${data.text_preview ? data.text_preview.substring(0, 30) : ''}`.replace(/\s/g, '');
}

// Helper to render a single event
function renderEvent(data, container) {
    if (!container) return;

    const signature = getEventSignature(data);

    // Check if event already exists to avoid duplicates
    // We look for an element with this signature
    const existing = container.querySelector(`[data-signature="${signature}"]`);
    if (existing) return;

    const eventElement = document.createElement('div');
    eventElement.className = 'mb-2 p-2 bg-white rounded shadow event-item border border-gray-100';
    eventElement.setAttribute('data-signature', signature);
    eventElement.innerHTML = `
        <div class="flex justify-between items-start">
            <div class="text-xs text-gray-500">${data.time ? new Date(data.time).toLocaleTimeString() : new Date().toLocaleTimeString()}</div>
            <div class="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">${data.chat_name || 'Unknown'}</div>
        </div>
        <div class="text-sm mt-1 text-gray-800">${data.text_preview || ''}</div>
        ${data.keywords ? `<div class="text-xs text-green-600 mt-1 font-medium">Found: ${data.keywords.join(', ')}</div>` : ''}
    `;

    // Prepend to show newest at top
    container.insertBefore(eventElement, container.firstChild);

    // Limit log size
    while (container.children.length > 50) {
        container.removeChild(container.lastChild);
    }
}

// Load AI settings from backend
async function loadAISettings() {
    try {
        const response = await fetch('/api/openai/status');
        if (response.ok) {
            const data = await response.json();

            const aiEnabled = document.getElementById('ai-enabled');
            if (aiEnabled) aiEnabled.checked = data.ai_enabled || false;

            const apiKey = document.getElementById('openai-api-key');
            if (apiKey) apiKey.value = data.openai_api_key || '';

            const model = document.getElementById('openai-model');
            if (model) model.value = data.openai_model || 'gpt-5-nano';

            const prompt = document.getElementById('openai-prompt');
            if (prompt) prompt.value = data.system_prompt || 'Ты классификатор сообщений из чатов фрилансеров. Твоя задача — определить, содержит ли сообщение поиск исполнителя, вакансию или предложение работы. Если сообщение — это вопрос новичка, спам, реклама услуг или просто общение — возвращай false. Если это заказ/вакансия — возвращай true. Ответь ТОЛЬКО валидным JSON формата: {"relevant": true} или {"relevant": false}';

            const minWords = document.getElementById('min-words');
            if (minWords) minWords.value = data.min_words || 5;

            const useTriggers = document.getElementById('use-triggers');
            if (useTriggers) useTriggers.checked = data.use_triggers !== undefined ? data.use_triggers : true;

            const triggerWords = document.getElementById('trigger-words');
            if (triggerWords) {
                if (data.trigger_words && Array.isArray(data.trigger_words)) {
                    triggerWords.value = data.trigger_words.join(', ');
                } else {
                    triggerWords.value = 'ищу, нужен, требуется, заказ, сделать, настроить, разработать, кто может, помогите';
                }
            }

            updateAIUI();
            updateStats();
        }
    } catch (error) {
        console.error('Error loading AI settings:', error);
    }
}

// Update monitoring status
async function updateMonitoringStatus() {
    try {
        const response = await fetch('/api/monitor/status');
        if (response.ok) {
            const data = await response.json();

            const statusIndicator = document.getElementById('monitoring-status-indicator');
            const statusText = document.getElementById('monitoring-status-text');

            if (statusIndicator && statusText) {
                if (data.active) {
                    statusIndicator.className = 'status-indicator status-active';
                    statusText.textContent = 'Запущен';
                } else {
                    statusIndicator.className = 'status-indicator status-inactive';
                    statusText.textContent = 'Остановлен';
                }
            }

            const chatsCount = document.getElementById('monitored-chats-count');
            if (chatsCount) chatsCount.textContent = data.chats_count || 0;

            // Populate event log from history
            if (data.events && Array.isArray(data.events)) {
                const eventsLog = document.getElementById('events-log');
                if (eventsLog) {
                    // data.events is likely [oldest, ..., newest]
                    // We iterate and prepend. 
                    // If we prepend Old then New, New ends up on top. Correct.
                    data.events.forEach(event => {
                        renderEvent(event, eventsLog);
                    });
                }
            }

            // Sync keywords count from input if possible
            updateStats();
        }
    } catch (error) {
        console.error('Error updating monitoring status:', error);
    }
}

// Connect to SSE for real-time logs
function connectSSE() {
    const eventSource = new EventSource('/api/monitor/logs');
    const eventsLog = document.getElementById('events-log');

    if (!eventsLog) return;

    eventSource.onmessage = function (event) {
        try {
            const data = JSON.parse(event.data);
            renderEvent(data, eventsLog);
        } catch (e) {
            console.error('Error parsing SSE event:', e);
        }
    };

    eventSource.onerror = function (error) {
        console.error('SSE error:', error);
    };
}

// Initialize app
async function init() {
    // Load current configuration
    await loadCurrentConfig();

    // Check auth status
    try {
        const response = await fetch('/api/telegram/status');
        const data = await response.json();
        updateAuthUI(data.authorized);
    } catch (e) {
        console.log('Auth check failed', e);
    }

    try {
        await updateMonitoringStatus();
        await loadAISettings();

        // Poll status every 5s
        setInterval(updateMonitoringStatus, 5000);

        // Start SSE
        connectSSE();
    } catch (error) {
        console.error('Init error:', error);
    }
}