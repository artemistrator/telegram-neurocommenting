window.App = window.App || {};
window.App.features = window.App.features || {};

window.App.features.telegramAuth = {
    isTelegramConfigSaved: false,

    init: function () {
        console.log('✅ Telegram Auth Feature Init');

        // 1. Listeners for Save Settings
        const saveTgBtn = document.getElementById('save-telegram-settings');
        if (saveTgBtn) {
            saveTgBtn.addEventListener('click', async () => {
                const apiIdEl = document.getElementById('api-id');
                const apiHashEl = document.getElementById('api-hash');
                const phoneEl = document.getElementById('phone');
                const sessionEl = document.getElementById('session');

                const data = {
                    api_id: apiIdEl ? apiIdEl.value : '',
                    api_hash: apiHashEl ? apiHashEl.value : '',
                    phone: phoneEl ? phoneEl.value : '',
                    session: sessionEl ? (sessionEl.value || 'telegram_session') : 'telegram_session'
                };

                try {
                    const response = await fetch('/api/telegram/save', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });

                    if (response.ok) {
                        this.isTelegramConfigSaved = true;
                        this.updateAuthorizeButton();
                        App.core.toast.showToast('Настройки Telegram сохранены');
                    } else {
                        const error = await response.json();
                        App.core.toast.showToast(`Ошибка сохранения настроек: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    App.core.toast.showToast(`Ошибка сети: ${error.message}`, 'error');
                }
            });
        }

        // 2. Logout
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', async () => {
                if (!confirm('Вы уверены? Это удалит сессию Telegram.')) return;

                try {
                    const response = await fetch('/api/telegram/logout', { method: 'POST' });
                    if (response.ok) {
                        App.core.toast.showToast('Сессия сброшена. Перезагрузите страницу.');
                        // Clear fields and update UI
                        const apiIdEl = document.getElementById('api-id');
                        const apiHashEl = document.getElementById('api-hash');
                        const phoneEl = document.getElementById('phone');

                        if (apiIdEl) apiIdEl.placeholder = '';
                        if (apiHashEl) apiHashEl.placeholder = '';
                        if (phoneEl) phoneEl.value = '';

                        this.refreshAuthStatus(); // Update UI state
                    } else {
                        const error = await response.json();
                        App.core.toast.showToast(`Ошибка: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    App.core.toast.showToast(`Ошибка сети: ${error.message}`, 'error');
                }
            });
        }

        // 3. Start Authorization
        const authorizeBtn = document.getElementById('authorize-btn');
        if (authorizeBtn) {
            authorizeBtn.addEventListener('click', async () => {
                // First SAVE 
                const apiIdEl = document.getElementById('api-id');
                const apiHashEl = document.getElementById('api-hash');
                const phoneEl = document.getElementById('phone');
                const sessionEl = document.getElementById('session');

                const data = {
                    api_id: apiIdEl ? apiIdEl.value : '',
                    api_hash: apiHashEl ? apiHashEl.value : '',
                    phone: phoneEl ? phoneEl.value : '',
                    session: sessionEl ? (sessionEl.value || 'telegram_session') : 'telegram_session'
                };

                try {
                    const saveResponse = await fetch('/api/telegram/save', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });

                    if (!saveResponse.ok) {
                        const error = await saveResponse.json();
                        App.core.toast.showToast(`Ошибка сохранения: ${error.detail}`, 'error');
                        return;
                    }

                    // Start Auth
                    const response = await fetch('/api/telegram/auth/start', { method: 'POST' });
                    if (response.ok) {
                        const authModal = document.getElementById('auth-modal');
                        if (authModal) {
                            authModal.classList.remove('hidden');
                            authModal.classList.add('flex');
                        }
                        App.core.toast.showToast('Код отправлен');
                    } else {
                        const error = await response.json();
                        if (error.detail && error.detail.includes('ResendCodeRequest')) {
                            const authModal = document.getElementById('auth-modal');
                            if (authModal) {
                                authModal.classList.remove('hidden');
                                authModal.classList.add('flex');
                            }
                            App.core.toast.showToast('Код уже был отправлен, пожалуйста, введите его');
                        } else {
                            App.core.toast.showToast(`Ошибка авторизации: ${error.detail}`, 'error');
                        }
                    }
                } catch (error) {
                    App.core.toast.showToast(`Ошибка сети: ${error.message}`, 'error');
                }
            });
        }

        // 4. Auth Modals (Code and Password)
        this.initModals();

        // 5. Input listeners for enable/disable auth button
        const inputs = ['api-id', 'api-hash', 'phone'];
        inputs.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('input', () => this.updateAuthorizeButton());
        });

        // 6. Webhook Save
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
                        App.core.toast.showToast('Webhook URL сохранен');
                    } else {
                        const error = await response.json();
                        App.core.toast.showToast(`Ошибка сохранения webhook: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    App.core.toast.showToast(`Ошибка сети: ${error.message}`, 'error');
                }
            });
        }

        // 7. Webhook Test
        const testWebhookBtn = document.getElementById('test-webhook-btn');
        if (testWebhookBtn) {
            testWebhookBtn.addEventListener('click', async () => {
                try {
                    const response = await fetch('/api/webhook/test', { method: 'POST' });
                    if (response.ok) {
                        const result = await response.json();
                        App.core.toast.showToast(result.message);
                    } else {
                        const error = await response.json();
                        App.core.toast.showToast(`Ошибка: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    App.core.toast.showToast(`Ошибка сети: ${error.message}`, 'error');
                }
            });
        }
    },

    initModals: function () {
        // Cancel Auth
        const cancelAuthBtn = document.getElementById('cancel-auth-btn');
        if (cancelAuthBtn) {
            cancelAuthBtn.addEventListener('click', () => {
                const authModal = document.getElementById('auth-modal');
                if (authModal) {
                    authModal.classList.add('hidden');
                    authModal.classList.remove('flex');
                }
            });
        }

        // Submit Code
        const submitCodeBtn = document.getElementById('submit-code-btn');
        if (submitCodeBtn) {
            submitCodeBtn.addEventListener('click', async () => {
                const code = document.getElementById('auth-code').value;
                if (!code) {
                    App.core.toast.showToast('Введите код', 'error');
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
                            const authModal = document.getElementById('auth-modal');
                            const passwordModal = document.getElementById('password-modal');
                            if (authModal) {
                                authModal.classList.add('hidden');
                                authModal.classList.remove('flex');
                            }
                            if (passwordModal) {
                                passwordModal.classList.remove('hidden');
                                passwordModal.classList.add('flex');
                            }
                            App.core.toast.showToast('Требуется облачный пароль');
                        } else if (result.status === 'success') {
                            const authModal = document.getElementById('auth-modal');
                            if (authModal) {
                                authModal.classList.add('hidden');
                                authModal.classList.remove('flex');
                            }
                            App.core.toast.showToast('Авторизация успешна');
                            this.updateAuthUI(true);
                            this.fillEmptyReadOnlyFields();
                        }
                    } else {
                        const error = await response.json();
                        App.core.toast.showToast(`Ошибка: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    App.core.toast.showToast(`Ошибка сети: ${error.message}`, 'error');
                }
            });
        }

        // Cancel Password
        const cancelPassBtn = document.getElementById('cancel-password-btn');
        if (cancelPassBtn) {
            cancelPassBtn.addEventListener('click', () => {
                const passwordModal = document.getElementById('password-modal');
                if (passwordModal) {
                    passwordModal.classList.add('hidden');
                    passwordModal.classList.remove('flex');
                }
            });
        }

        // Submit Password
        const submitPassBtn = document.getElementById('submit-password-btn');
        if (submitPassBtn) {
            submitPassBtn.addEventListener('click', async () => {
                const password = document.getElementById('auth-password').value;
                if (!password) {
                    App.core.toast.showToast('Введите пароль', 'error');
                    return;
                }

                try {
                    const response = await fetch('/api/telegram/auth/password', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ password: password })
                    });

                    if (response.ok) {
                        const passwordModal = document.getElementById('password-modal');
                        if (passwordModal) {
                            passwordModal.classList.add('hidden');
                            passwordModal.classList.remove('flex');
                        }
                        App.core.toast.showToast('Авторизация успешна');
                        this.updateAuthUI(true);
                        this.fillEmptyReadOnlyFields();
                    } else {
                        const error = await response.json();
                        App.core.toast.showToast(`Ошибка: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    App.core.toast.showToast(`Ошибка сети: ${error.message}`, 'error');
                }
            });
        }
    },

    loadCurrentConfig: async function () {
        const apiIdEl = document.getElementById('api-id');
        // Only proceed if we are on a page with settings fields
        if (!apiIdEl) return;

        try {
            const response = await fetch('/api/config/get');
            if (response.ok) {
                const data = await response.json();

                // 1. Telegram Settings
                if (data.telegram) {
                    if (data.telegram.api_id) document.getElementById('api-id').value = data.telegram.api_id;
                    if (data.telegram.api_hash) document.getElementById('api-hash').value = data.telegram.api_hash;
                    if (data.telegram.phone) document.getElementById('phone').value = data.telegram.phone;
                    if (data.telegram.session) document.getElementById('session').value = data.telegram.session;
                }

                // 2. Webhook
                if (data.webhook_url) {
                    const el = document.getElementById('webhook-url');
                    if (el) el.placeholder = data.webhook_url;
                }

                // Note: Other settings like renderChatsTable or updateStats are NOT handled here
                // to respect single responsibility
            }
        } catch (error) {
            console.error('Error loading config:', error);
        }
    },

    refreshAuthStatus: async function () {
        try {
            const response = await fetch('/api/telegram/status');
            const status = await response.json();
            this.updateAuthUI(status.authorized);

            if (status.authorized) {
                this.fillEmptyReadOnlyFields();
            }
        } catch (e) {
            console.log('Auth check failed', e);
        }
    },

    updateAuthUI: function (isAuthorized) {
        const saveBtn = document.getElementById('save-telegram-settings');
        const authBtn = document.getElementById('authorize-btn');
        const logoutBtn = document.getElementById('logout-btn');
        const inputs = ['api-id', 'api-hash', 'phone', 'session'];

        if (isAuthorized) {
            if (saveBtn) saveBtn.classList.add('hidden');
            if (authBtn) authBtn.classList.add('hidden');
            if (logoutBtn) logoutBtn.classList.remove('hidden');
            inputs.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.setAttribute('readonly', 'true');
            });
        } else {
            if (saveBtn) saveBtn.classList.remove('hidden');
            if (authBtn) authBtn.classList.remove('hidden');
            if (logoutBtn) logoutBtn.classList.add('hidden');
            inputs.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.removeAttribute('readonly');
            });
        }
    },

    fillEmptyReadOnlyFields: function () {
        const inputs = ['api-id', 'api-hash', 'phone', 'session'];
        inputs.forEach(id => {
            const el = document.getElementById(id);
            if (el && el.hasAttribute('readonly') && !el.value) {
                el.value = '*****';
            }
        });
    },

    updateAuthorizeButton: function () {
        const apiIdEl = document.getElementById('api-id');
        const apiHashEl = document.getElementById('api-hash');
        const phoneEl = document.getElementById('phone');
        const authorizeBtn = document.getElementById('authorize-btn');

        if (!authorizeBtn) return;

        const apiId = apiIdEl ? apiIdEl.value : '';
        const apiHash = apiHashEl ? apiHashEl.value : '';
        const phone = phoneEl ? phoneEl.value : '';

        if (apiId && apiHash && phone) {
            authorizeBtn.classList.remove('disabled');
        } else {
            authorizeBtn.classList.add('disabled');
        }
    }
};
