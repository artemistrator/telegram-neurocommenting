window.App = window.App || {};
window.App.pages = window.App.pages || {};

window.App.pages.accounts = {
    // State
    currentAccountsData: [],

    // Config
    toasts: {
        success: '✅',
        error: '❌',
        info: 'ℹ️',
        warning: '⚠️'
    },

    // Core Methods
    init: function () {
        console.log('Accounts Page: Init');
        this.cacheElements();
        this.attachEventListeners();
        this.loadAccounts();
    },

    // Helpers
    directusAssetUrl: function (fileId) {
        const base = (window.App.core.config && window.App.core.config.DIRECTUS_URL) || "http://localhost:18055";
        return `${base}/assets/${fileId}`;
    },

    isUuid: function (s) {
        return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s);
    },

    cleanup: function () {
        console.log('Accounts Page: Cleanup');
        if (this.clickHandler) document.removeEventListener('click', this.clickHandler);
        if (this.changeHandler) document.removeEventListener('change', this.changeHandler);

        // Close all modals
        document.querySelectorAll('.fixed.inset-0').forEach(el => {
            el.classList.add('hidden');
            el.classList.remove('flex');
        });

        this.currentAccountsData = [];
        this.elements = {};
        this.clickHandler = null;
        this.changeHandler = null;
    },

    cacheElements: function () {
        this.elements = {
            totalAccounts: document.getElementById('total-accounts'),
            activeAccounts: document.getElementById('active-accounts'),
            setupCompleted: document.getElementById('setup-completed'),
            withProxy: document.getElementById('with-proxy'),
            bannedAccounts: document.getElementById('banned-accounts'),
            reserveAccounts: document.getElementById('reserve-accounts'),
            accountsTableBody: document.getElementById('accounts-table'),

            // Modals by ID
            importModal: document.getElementById('importModal'),
            accountDetailsModal: document.getElementById('accountDetailsModal'),
            setupAccountModal: document.getElementById('setupAccountModal'),

            // Form Elements
            zipFile: document.getElementById('zip-file'),
            autoAssignProxyZip: document.getElementById('auto-assign-proxy-zip'),
            importStatus: document.getElementById('import-status'),
            importStatusText: document.getElementById('import-status-text'),
            manualPhone: document.getElementById('manual-phone'),
            manualApiId: document.getElementById('manual-api-id'),
            manualApiHash: document.getElementById('manual-api-hash'),
            manualSession: document.getElementById('manual-session'),
            autoAssignProxyManual: document.getElementById('auto-assign-proxy-manual'),
            setupTemplateSelect: document.getElementById('setup-template-select'),
            setupAccountPhone: document.getElementById('setup-account-phone'),
            startSetupBtn: document.getElementById('start-setup-btn'),

            // Toast
            toast: document.getElementById('toast'),
            toastIcon: document.getElementById('toast-icon'),
            toastMessage: document.getElementById('toast-message')
        };
    },

    attachEventListeners: function () {
        this.clickHandler = (e) => {
            const target = e.target;
            const actionBtn = target.closest('[data-action]');
            if (!actionBtn) return;

            const action = actionBtn.dataset.action;
            let id = actionBtn.dataset.id;

            // Generic Modal Close
            if (action === 'close-modal') {
                const modal = actionBtn.closest('.fixed.inset-0');
                if (modal) {
                    modal.classList.add('hidden');
                    modal.classList.remove('flex');
                    // Special cleanup for setup modal
                    if (modal.id === 'setupAccountModal') this.currentSetupAccountId = null;
                }
                return;
            }

            // Tabs
            if (action === 'switchTab') {
                this.switchTab(actionBtn.dataset.tab);
                return;
            }

            // Modal Openers / Actions
            if (action === 'openImportModal') {
                this.openImportModal();
            } else if (action === 'importAccounts') {
                this.importAccounts();
            } else if (action === 'createAccount') {
                this.createAccount();
            } else if (action === 'startAccountSetup') {
                this.startAccountSetup();
            } else if (action === 'openAccountDetails') {
                this.openAccountDetails(parseInt(id));
            } else if (action === 'checkAccountStatus') {
                this.checkAccountStatus(parseInt(id));
            } else if (action === 'runSetup') {
                if (!id) {
                    const m = actionBtn.closest('.fixed.inset-0');
                    if (m && m.dataset.accountId) id = m.dataset.accountId;
                }
                if (id) this.runSetup(parseInt(id));
            } else if (action === 'rerunSetup') {
                if (!id) {
                    const m = actionBtn.closest('.fixed.inset-0');
                    if (m && m.dataset.accountId) id = m.dataset.accountId;
                }
                if (id) this.rerunSetup(parseInt(id));
            } else if (action === 'deleteAccount') {
                this.deleteAccount(parseInt(id));
            } else if (action === 'assignManualProxy') {
                this.assignManualProxy(parseInt(id));
            } else if (action === 'toggleWarmupMode') {
                const current = actionBtn.dataset.current === 'true';
                this.toggleWarmupMode(parseInt(id), current);
            }

            // Refresh Profile
            else if (action === 'refresh-profile') {
                // If clicked from within the modal header, it might not have data-id on the button directly
                // or we want to use the modal's account ID context
                if (!id) {
                    const modal = actionBtn.closest('.fixed.inset-0');
                    if (modal && modal.dataset.accountId) {
                        id = modal.dataset.accountId;
                    }
                }
                if (id) this.refreshAccountProfile(parseInt(id));
            }
            // Swap Proxy
            else if (action === 'swapProxy') {
                this.swapProxy(parseInt(id));
            }
        };
        this.changeHandler = (e) => {
            const target = e.target;
            if (target.dataset.action === 'updateAccountRole') {
                this.updateAccountRole(parseInt(target.dataset.id), target.value);
            }
        };

        document.addEventListener('click', this.clickHandler);
        document.addEventListener('change', this.changeHandler);
    },

    // --- Logic Implementation ---

    showToast: function (message, type = 'success') {
        const { toast, toastIcon, toastMessage } = this.elements;
        if (!toast) return;

        toastIcon.textContent = this.toasts[type] || this.toasts.info;
        toastMessage.textContent = message;
        toast.classList.remove('hidden');

        setTimeout(() => {
            toast.classList.add('hidden');
        }, 3000);
    },

    loadAccounts: async function () {
        try {
            const response = await fetch('/api/accounts/list');
            const data = await response.json();
            const accounts = data.accounts || data.data || [];

            this.currentAccountsData = accounts;
            this.renderAccountsTable(accounts);
            this.updateStats(accounts);
        } catch (error) {
            console.error('Error loading accounts:', error);
            this.showToast(`Ошибка загрузки аккаунтов: ${error.message}`, 'error');
        }
    },

    renderAccountsTable: function (accounts) {
        const tbody = this.elements.accountsTableBody;
        if (!tbody) return;

        tbody.innerHTML = '';

        if (accounts.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="px-6 py-12 text-center">
                        <div class="text-gray-400">
                             <p class="text-lg font-medium text-gray-900 mb-2">Аккаунты не загружены</p>
                             <p class="text-sm text-gray-500">Нажмите "Импорт аккаунтов" чтобы начать</p>
                        </div>
                    </td>
                </tr>`;
            return;
        }



        accounts.forEach(account => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50';
            row.setAttribute('data-account-id', account.id);

            // Helper vars
            const isDisabled = account.status === 'banned';
            const disabledAttr = isDisabled ? 'disabled' : '';
            const warmupActive = account.warmup_mode === true;

            // Profile
            let avatarUrl;
            if (account.avatar_url && this.isUuid(account.avatar_url)) {
                avatarUrl = this.directusAssetUrl(account.avatar_url);
            } else {
                avatarUrl = 'https://ui-avatars.com/api/?name=' + encodeURIComponent(account.phone || 'User');
            }

            const displayName = (account.first_name || account.last_name) ?
                [account.first_name, account.last_name].filter(Boolean).join(' ') : '';

            const profileHtml = `
                <div class="flex items-center">
                    <img src="${avatarUrl}" alt="Avatar" class="w-10 h-10 rounded-full mr-3 object-cover" onerror="this.src='https://ui-avatars.com/api/?name=User'">
                    <div>
                        <div class="font-medium text-gray-900">${account.phone || 'N/A'}</div>
                        ${displayName ? `<div class="text-sm text-gray-500">${displayName}</div>` : ''}
                        ${account.username ? `<div class="text-xs text-blue-500">@${account.username}</div>` : ''}
                    </div>
                </div>`;

            // Role
            const roleHtml = `
                <select 
                    data-action="updateAccountRole" 
                    data-id="${account.id}"
                    class="rounded border-gray-300 text-sm focus:ring-blue-500 focus:border-blue-500 ${isDisabled ? 'bg-gray-100 cursor-not-allowed' : ''}"
                    ${disabledAttr}>
                    <option value="">Не выбрана</option>
                    <option value="commenter" ${account.work_mode === 'commenter' ? 'selected' : ''}>Commenter</option>
                    <option value="listener" ${account.work_mode === 'listener' ? 'selected' : ''}>Listener</option>
                    <option value="reserve" ${account.work_mode === 'reserve' ? 'selected' : ''}>Reserve</option>
                </select>`;

            // Warmup
            const warmupHtml = `
                <button 
                    data-action="toggleWarmupMode" 
                    data-id="${account.id}" 
                    data-current="${warmupActive}"
                    class="focus:outline-none ${isDisabled ? 'cursor-not-allowed opacity-50' : ''}"
                    ${isDisabled ? 'disabled' : ''}>
                    <span class="text-2xl ${warmupActive ? 'text-orange-500' : 'text-gray-400'}">
                        ${warmupActive ? '🔥' : '🧊'}
                    </span>
                </button>`;

            // Status Badge
            let statusBadge = '';
            if (account.status === 'active') statusBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">Active</span>';
            else if (account.status === 'banned') statusBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">Banned</span>';
            else if (account.status === 'reserve' || account.status === 'reserved') statusBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-800">Reserved</span>';
            else statusBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-800">Unknown</span>';

            // Setup Badge
            let setupBadge = '';
            if (account.setup_status === 'completed') {
                const channelLink = account.personal_channel_url || '#';
                setupBadge = `<div><span class="px-2 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800">Done</span>${account.personal_channel_url ? `<br><a href="${channelLink}" target="_blank" class="text-xs text-blue-600 hover:underline mt-1 inline-block">📢</a>` : ''}</div>`;
            } else if (account.setup_status === 'pending') setupBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-800">Pending</span>';
            else if (account.setup_status === 'failed') setupBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">Failed</span>';
            else setupBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-800">Not started</span>';

            // Template
            const setupTemplateName = account.template ? account.template.name : 'Не выбран';
            const templateHtml = `<span class="text-sm text-gray-700">${setupTemplateName}</span>`;

            // Proxy
            let proxyHtml = '';
            if (account.proxy_unavailable === true) {
                // Show unavailable status with swap button
                proxyHtml = `
                    <div class="flex items-center">
                        <span class="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800 mr-2">Proxy unavailable</span>
                        <button data-action="swapProxy" data-id="${account.id}"
                            class="text-blue-500 hover:text-blue-700 text-sm font-medium p-1 rounded hover:bg-blue-50 transition">
                            Swap Proxy
                        </button>
                    </div>`;
            } else if (account.proxy && account.proxy.host) {
                proxyHtml = `
                    <div class="text-sm">
                        <span class="font-mono text-gray-700">${account.proxy.host}:${account.proxy.port}</span>
                        <br><span class="text-xs text-gray-500">${account.proxy.type ? account.proxy.type.toUpperCase() : 'N/A'}</span>
                        <br><span class="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">Proxy OK</span>
                    </div>`;
            } else {
                proxyHtml = `
                    <div class="flex items-center">
                        <span class="text-sm text-red-600 font-medium mr-2">Нет прокси</span>
                        <button data-action="assignManualProxy" data-id="${account.id}"
                            class="text-blue-500 hover:text-blue-700 p-1 rounded hover:bg-blue-50 transition"
                            ${isDisabled ? 'disabled' : ''}>
                            🔗
                        </button>
                    </div>`;
            }
            // Date
            let dateDisplay = 'N/A';
            if (account.date_updated) {
                const date = new Date(account.date_updated);
                const day = String(date.getDate()).padStart(2, '0');
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const hours = String(date.getHours()).padStart(2, '0');
                const minutes = String(date.getMinutes()).padStart(2, '0');
                dateDisplay = `${day}.${month} ${hours}:${minutes}`;
            }

            // Actions
            const actionsHtml = `
                <button data-action="openAccountDetails" data-id="${account.id}" class="text-gray-600 hover:text-gray-800 font-medium mr-2" title="Подробнее">👁️</button>
                <button data-action="refresh-profile" data-id="${account.id}" class="text-blue-600 hover:text-blue-800 font-medium mr-2" title="Обновить профиль">↻</button>
                <button data-action="checkAccountStatus" data-id="${account.id}" class="text-blue-600 hover:text-blue-800 font-medium mr-2" title="Проверить статус">🔍</button>
                <button data-action="runSetup" data-id="${account.id}" class="text-green-600 hover:text-green-800 font-medium mr-2" title="Запустить Setup" ${isDisabled ? 'disabled' : ''}>▶</button>
                <button data-action="rerunSetup" data-id="${account.id}" class="text-orange-600 hover:text-orange-800 font-medium mr-2" title="Перезапустить Setup" ${isDisabled ? 'disabled' : ''}>↻</button>
                <button data-action="deleteAccount" data-id="${account.id}" class="text-red-600 hover:text-red-800 font-medium" title="Удалить">🗑️</button>
            `;

            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap">${profileHtml}</td>
                <td class="px-6 py-4 whitespace-nowrap">${roleHtml}</td>
                <td class="px-6 py-4 whitespace-nowrap text-center">${warmupHtml}</td>
                <td class="px-6 py-4 whitespace-nowrap">${statusBadge}</td>
                <td class="px-6 py-4 whitespace-nowrap">${setupBadge}</td>
                <td class="px-6 py-4 whitespace-nowrap">${templateHtml}</td>
                <td class="px-6 py-4 whitespace-nowrap">${proxyHtml}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${dateDisplay}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">${actionsHtml}</td>
            `;

            tbody.appendChild(row);
        });
    },

    updateStats: function (accounts) {
        if (!this.elements.totalAccounts) return;

        this.elements.totalAccounts.textContent = accounts.length;
        this.elements.activeAccounts.textContent = accounts.filter(a => a.status === 'active').length;
        this.elements.setupCompleted.textContent = accounts.filter(a => a.setup_status === 'completed').length;
        this.elements.withProxy.textContent = accounts.filter(a => a.proxy && a.proxy.host).length;
        this.elements.bannedAccounts.textContent = accounts.filter(a => a.status === 'banned').length;
        this.elements.reserveAccounts.textContent = accounts.filter(a => a.status === 'reserve' || a.status === 'reserved').length;
    },

    // --- Modal Actions ---

    openImportModal: function () {
        if (this.elements.importModal) {
            this.elements.importModal.classList.remove('hidden');
            this.elements.importModal.classList.add('flex');
            this.switchTab('zip');
            if (this.elements.zipFile) this.elements.zipFile.value = '';
            if (this.elements.importStatus) this.elements.importStatus.classList.add('hidden');
        }
    },

    closeImportModal: function () {
        if (this.elements.importModal) {
            this.elements.importModal.classList.add('hidden');
            this.elements.importModal.classList.remove('flex');
        }
    },

    switchTab: function (tab) {
        const tabZip = document.getElementById('tab-zip');
        const tabManual = document.getElementById('tab-manual');
        const contentZip = document.getElementById('content-zip');
        const contentManual = document.getElementById('content-manual');

        if (!tabZip || !tabManual || !contentZip || !contentManual) return;

        if (tab === 'zip') {
            tabZip.className = 'border-blue-500 text-blue-600 w-1/2 py-4 px-1 text-center border-b-2 font-medium text-sm';
            tabManual.className = 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 w-1/2 py-4 px-1 text-center border-b-2 font-medium text-sm cursor-pointer';
            contentZip.classList.remove('hidden');
            contentManual.classList.add('hidden');
        } else {
            tabZip.className = 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 w-1/2 py-4 px-1 text-center border-b-2 font-medium text-sm cursor-pointer';
            tabManual.className = 'border-blue-500 text-blue-600 w-1/2 py-4 px-1 text-center border-b-2 font-medium text-sm';
            contentZip.classList.add('hidden');
            contentManual.classList.remove('hidden');
        }
    },

    // --- Import Logic ---

    importAccounts: async function () {
        if (!this.elements.zipFile || !this.elements.importStatus) return;

        const zipFile = this.elements.zipFile.files[0];
        const autoAssignProxy = this.elements.autoAssignProxyZip ? this.elements.autoAssignProxyZip.checked : false;

        if (!zipFile) {
            this.showToast('Выберите ZIP файл', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('file', zipFile);
        formData.append('auto_assign_proxy', autoAssignProxy);

        const statusDiv = this.elements.importStatus;
        const statusText = this.elements.importStatusText;

        statusDiv.classList.remove('hidden');
        statusDiv.querySelector('div').className = 'p-4 rounded-lg bg-blue-50';
        statusText.className = 'text-sm font-medium text-blue-800';
        statusText.textContent = 'Импорт аккаунтов...';

        try {
            const response = await fetch('/api/accounts/import', { method: 'POST', body: formData });
            const data = await response.json();

            if (response.ok) {
                statusDiv.querySelector('div').className = 'p-4 rounded-lg bg-green-50';
                statusText.className = 'text-sm font-medium text-green-800';

                let message = `✅ Импортировано: ${data.imported} аккаунтов`;
                if (autoAssignProxy && data.proxies_assigned) message += `\n🌐 Назначено прокси: ${data.proxies_assigned}`;
                if (data.errors && data.errors.length > 0) message += `\n⚠️ Ошибок: ${data.errors.length}`;

                statusText.textContent = message;

                setTimeout(() => {
                    this.closeImportModal();
                    this.loadAccounts();
                }, 1500);
            } else {
                throw new Error(data.detail || data.message);
            }
        } catch (error) {
            statusDiv.querySelector('div').className = 'p-4 rounded-lg bg-red-50';
            statusText.className = 'text-sm font-medium text-red-800';
            statusText.textContent = `❌ Ошибка: ${error.message}`;

            // Check for specific proxy error
            if (error.message.includes("NO_PROXY_AVAILABLE")) {
                alert("Ошибка: Нет свободных активных прокси. Добавьте прокси и повторите импорт.");
            }
        }
    },

    createAccount: async function () {
        if (!this.elements.manualPhone) return;

        const phone = this.elements.manualPhone.value;
        const apiId = this.elements.manualApiId.value;
        const apiHash = this.elements.manualApiHash.value;
        const sessionString = this.elements.manualSession.value;
        const autoAssignProxy = this.elements.autoAssignProxyManual ? this.elements.autoAssignProxyManual.checked : false;

        if (!phone || !apiId || !apiHash) {
            this.showToast('Заполните обязательные поля', 'error');
            return;
        }

        const statusDiv = this.elements.importStatus;
        const statusText = this.elements.importStatusText;
        statusDiv.classList.remove('hidden');
        statusDiv.querySelector('div').className = 'p-4 rounded-lg bg-blue-50';
        statusText.className = 'text-sm font-medium text-blue-800';
        statusText.textContent = 'Создание аккаунта...';

        try {
            const response = await fetch('/api/accounts/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    phone: phone,
                    api_id: parseInt(apiId),
                    api_hash: apiHash,
                    session_string: sessionString || null,
                    auto_assign_proxy: autoAssignProxy
                })
            });
            const data = await response.json();

            if (response.ok) {
                statusDiv.querySelector('div').className = 'p-4 rounded-lg bg-green-50';
                statusText.className = 'text-sm font-medium text-green-800';
                let msg = `✅ Аккаунт ${data.account.phone} создан`;
                if (data.proxy) msg += `\n🌐 Прокси: ${data.proxy.host}`;
                statusText.textContent = msg;

                setTimeout(() => {
                    this.closeImportModal();
                    this.loadAccounts();
                }, 1500);
            } else {
                throw new Error(data.detail || data.message);
            }
        } catch (error) {
            statusDiv.querySelector('div').className = 'p-4 rounded-lg bg-red-50';
            statusText.className = 'text-sm font-medium text-red-800';
            statusText.textContent = `❌ Ошибка: ${error.message}`;
        }
    },

    // --- Account Details & Actions ---

    openAccountDetails: function (accountId) {
        const account = this.currentAccountsData.find(a => a.id === accountId);
        if (!account) return;

        const modal = this.elements.accountDetailsModal;
        if (!modal) return;

        // Store ID for delegation context
        modal.dataset.accountId = accountId;

        // Populate fields
        let avatarUrl;
        let isDirectusAvatar = false;

        if (account.avatar_url && this.isUuid(account.avatar_url)) {
            avatarUrl = this.directusAssetUrl(account.avatar_url);
            isDirectusAvatar = true;
        } else {
            avatarUrl = 'https://ui-avatars.com/api/?name=' + encodeURIComponent(account.phone || 'User');
        }
        document.getElementById('modal-avatar').src = avatarUrl;

        // Open Avatar Link (Optional but requested)
        const avatarContainer = document.getElementById('modal-avatar').parentElement;
        let openLink = avatarContainer.querySelector('.avatar-open-link');
        if (isDirectusAvatar) {
            if (!openLink) {
                openLink = document.createElement('a');
                openLink.className = 'avatar-open-link text-xs text-blue-500 hover:underline block text-center mt-1';
                openLink.target = '_blank';
                openLink.textContent = 'Открыть';
                avatarContainer.appendChild(openLink);
            }
            openLink.href = avatarUrl;
            openLink.style.display = 'block';
        } else if (openLink) {
            openLink.style.display = 'none';
        }

        // Name logic
        let displayName = account.phone || 'Unknown';
        if (account.first_name || account.last_name) {
            displayName = [account.first_name, account.last_name].filter(Boolean).join(' ');
        }
        document.getElementById('modal-name').textContent = displayName;

        // Phone & Username
        document.getElementById('modal-phone').textContent = account.phone || '-';
        // Template
        const templateName = account.template ? account.template.name : 'Не выбран';
        document.getElementById('modal-template').textContent = templateName;

        // Set Template Select
        const templateSelect = document.getElementById('account-template-select');
        if (templateSelect) {
            templateSelect.value = account.template ? account.template.id : "";
        }
        document.getElementById('modal-username').textContent = account.username ? `@${account.username}` : '—';

        // Bio logic
        document.getElementById('modal-bio').textContent = account.bio || 'Нет описания';

        // Badges
        const badgesContainer = document.getElementById('modal-badges');
        let statusBadge = '';
        if (account.status === 'active') statusBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">Active</span>';
        else if (account.status === 'banned') statusBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">Banned</span>';
        else if (account.status === 'reserve' || account.status === 'reserved') statusBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-800">Reserved</span>';
        else statusBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-800">Unknown</span>';

        let workModeBadge = '';
        if (account.work_mode) {
            workModeBadge = `<span class="px-2 py-1 text-xs font-semibold rounded-full bg-blue-50 text-blue-600 border border-blue-200">${account.work_mode}</span>`;
        }

        let warmupBadge = '';
        if (account.warmup_mode === true) {
            warmupBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-orange-50 text-orange-600 border border-orange-200">Прогрев 🔥</span>';
        }
        badgesContainer.innerHTML = statusBadge + workModeBadge + warmupBadge;

        // Setup Info
        const setupContainer = document.getElementById('modal-setup');
        if (account.setup_status === 'completed') {
            const link = account.personal_channel_url ? `<a href="${account.personal_channel_url}" target="_blank" class="text-blue-600 hover:underline block mt-1">Перейти в канал</a>` : '';
            setupContainer.innerHTML = `<span class="text-green-600 font-medium">Completed</span>${link}`;
        } else {
            setupContainer.innerHTML = `<span class="px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-800">${account.setup_status || 'Pending'}</span>`;
        }

        // Template Info
        const templateContainer = document.getElementById('modal-template');
        templateContainer.innerHTML = (account.setup_template_id && account.setup_template_id.name)
            ? `<span class="text-gray-700">${account.setup_template_id.name}</span>`
            : `<span class="text-gray-400">Не выбран</span>`;

        // Proxy Info
        const proxyContainer = document.getElementById('modal-proxy');
        if (account.proxy && account.proxy.host) {
            proxyContainer.innerHTML = `
                <div class="font-mono text-sm">${account.proxy.host}:${account.proxy.port}</div>
                <div class="text-xs text-gray-500">${account.proxy.type} | ID: ${account.proxy.id}</div>`;
        } else {
            proxyContainer.innerHTML = `
                <span class="text-red-500">Нет прокси</span>
                <button data-action="assignManualProxy" data-id="${account.id}" class="ml-2 text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded hover:bg-blue-200">Назначить</button>
            `;
        }

        // Inject Refresh Button in Header if not exists
        const header = modal.querySelector('.flex.justify-between.items-center');
        if (header) {
            let existingRefreshBtn = header.querySelector('[data-action="refresh-profile"]');
            if (existingRefreshBtn) {
                existingRefreshBtn.remove();
            }

            const refreshBtn = document.createElement('button');
            refreshBtn.setAttribute('data-action', 'refresh-profile');
            refreshBtn.setAttribute('data-id', account.id);
            refreshBtn.className = 'text-blue-600 hover:text-blue-800 font-medium mr-4';
            refreshBtn.title = 'Обновить профиль';
            refreshBtn.textContent = '↻ Обновить профиль';

            // Insert before close button
            const closeBtn = header.querySelector('[data-action="closeAccountDetails"]');
            if (closeBtn) {
                header.insertBefore(refreshBtn, closeBtn);
            } else {
                header.appendChild(refreshBtn);
            }
        }

        modal.classList.remove('hidden');
        modal.classList.add('flex');
    },

    closeAccountDetails: function () {
        if (this.elements.accountDetailsModal) {
            this.elements.accountDetailsModal.classList.add('hidden');
            this.elements.accountDetailsModal.classList.remove('flex');
        }
    },

    updateAccountRole: async function (accountId, workMode) {
        try {
            const response = await fetch(`/api/accounts/${accountId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ work_mode: workMode })
            });
            const data = await response.json();
            if (response.ok) {
                this.showToast('Роль обновлена', 'success');
                this.loadAccounts();
            } else {
                throw new Error(data.detail || data.message);
            }
        } catch (error) {
            this.showToast(`Ошибка: ${error.message}`, 'error');
        }
    },

    toggleWarmupMode: async function (accountId, currentMode) {
        try {
            const newMode = !currentMode;
            const response = await fetch(`/api/accounts/${accountId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ warmup_mode: newMode })
            });
            const data = await response.json();
            if (response.ok) {
                this.showToast(`Режим прогрева ${newMode ? 'включен' : 'выключен'}`, 'success');
                this.loadAccounts();
            } else {
                throw new Error(data.detail || data.message);
            }
        } catch (error) {
            this.showToast(`Ошибка: ${error.message}`, 'error');
        }
    },

    refreshAccountProfile: async function (accountId) {
        if (!accountId) return;

        // Find all buttons for this action to disable them
        const buttons = document.querySelectorAll(`button[data-action="refresh-profile"][data-id="${accountId}"]`);
        buttons.forEach(btn => {
            btn.disabled = true;
            btn.classList.add('opacity-50', 'cursor-not-allowed');
            if (btn.innerText.includes('↻')) btn.classList.add('animate-spin');
        });

        this.showToast('Обновляю профиль...', 'info');

        try {
            const response = await fetch(`/api/accounts/${accountId}/refresh-profile`, { method: 'POST' });

            if (response.status === 429) {
                const retryAfter = response.headers.get('Retry-After');
                let waitMsg = retryAfter ? `подождите ${retryAfter}с` : 'попробуйте позже';
                const errorData = await response.json().catch(() => ({}));
                if (errorData.detail) waitMsg += ` (${errorData.detail})`;

                this.showToast(`Слишком часто: ${waitMsg}`, 'warning');
            } else if (response.ok) {
                const data = await response.json();
                this.showToast('Профиль обновлен', 'success');
                await this.loadAccounts();

                // If modal is open for this account, refresh it
                const modal = this.elements.accountDetailsModal;
                if (!modal.classList.contains('hidden')) {
                    // Check logic based on dataset.accountId
                    if (modal.dataset.accountId == accountId) {
                        this.openAccountDetails(accountId);
                    }
                }
            } else {
                const data = await response.json();
                throw new Error(data.detail || data.message || 'Unknown error');
            }
        } catch (error) {
            console.error('Refresh profile error:', error);
            this.showToast(`Ошибка: ${error.message}`, 'error');
        } finally {
            // Re-enable buttons
            buttons.forEach(btn => {
                btn.disabled = false;
                btn.classList.remove('opacity-50', 'cursor-not-allowed', 'animate-spin');
            });
        }
    },

    checkAccountStatus: async function (accountId) {
        this.showToast('Проверка статуса аккаунта...', 'info');
        try {
            const response = await fetch(`/api/accounts/${accountId}/check-status`, { method: 'POST' });
            const data = await response.json();
            if (response.ok) {
                this.showToast(`Статус: ${data.status}`, 'success');
                this.loadAccounts();
            } else {
                throw new Error(data.detail || data.message);
            }
        } catch (error) {
            this.showToast(`Ошибка: ${error.message}`, 'error');
        }
    },

    deleteAccount: async function (accountId) {
        if (!confirm('Удалить аккаунт? Это действие нельзя отменить.')) return;
        try {
            const response = await fetch(`/api/accounts/${accountId}`, { method: 'DELETE' });
            if (response.ok) {
                this.showToast('Аккаунт удален', 'success');
                this.loadAccounts();
            } else {
                const data = await response.json();
                throw new Error(data.detail || data.message);
            }
        } catch (error) {
            this.showToast(`Ошибка: ${error.message}`, 'error');
        }
    },

    assignManualProxy: async function (accountId) {
        this.showToast('Ищу свободный прокси...', 'info');
        try {
            const response = await fetch(`/api/accounts/${accountId}/assign-proxy`, { method: 'POST' });
            const data = await response.json();
            if (response.ok) {
                this.showToast(`✅ Прокси назначен: ${data.proxy.host}:${data.proxy.port}`, 'success');
                this.loadAccounts();
                // If inside details modal, close it
                this.closeAccountDetails();
            } else {
                throw new Error(data.detail || data.message);
            }
        } catch (error) {
        }
    },

    swapProxy: async function (accountId) {
        // Find the swap button to disable it and show loading state
        const swapButtons = document.querySelectorAll(`button[data-action="swapProxy"][data-id="${accountId}"]`);
        swapButtons.forEach(btn => {
            btn.disabled = true;
            btn.innerHTML = 'Swapping...';
            btn.classList.add('opacity-50', 'cursor-not-allowed');
        });

        this.showToast('Swapping proxy...', 'info');
        try {
            const response = await fetch(`/api/accounts/${accountId}/swap-proxy`, { method: 'POST' });
            const data = await response.json();
            
            if (response.ok) {
                this.showToast('✅ Proxy swapped successfully!', 'success');
                this.loadAccounts(); // Refresh the accounts list
            } else {
                if (data.error === 'NO_PROXY_AVAILABLE') {
                    this.showToast(`❌ ${data.message || 'No available proxies found'}`, 'error');
                } else {
                    throw new Error(data.detail || data.message || 'Unknown error');
                }
            }
        } catch (error) {
            this.showToast(`❌ Error: ${error.message}`, 'error');
        } finally {
            // Re-enable buttons
            swapButtons.forEach(btn => {
                btn.disabled = false;
                btn.innerHTML = 'Swap Proxy';
                btn.classList.remove('opacity-50', 'cursor-not-allowed');
            });
        }
    },

    // --- Setup Logic ---
    rerunSetup: async function (accountId) {
        if (!accountId) return;
        const account = this.currentAccountsData.find(a => a.id === accountId);
        if (!account) return;
        if (!account.template) {
            this.showToast('Сначала выберите шаблон (нажмите ▶)', 'warning');
            this.runSetup(accountId);
            return;
        }

        this.showToast('Запуск повторной настройки...', 'info');
        try {
            const response = await fetch(`/api/accounts/${accountId}/rerun-setup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                this.showToast('Повторная настройка запущена (Force)', 'success');
                this.loadAccounts();
                // If in modal, maybe close it or update status
            } else {
                const data = await response.json();
                throw new Error(data.detail || data.message);
            }
        } catch (error) {
            this.showToast(`Ошибка: ${error.message}`, 'error');
        }
    },

    runSetup: function (accountId) {
        this.openSetupAccountModal(accountId);
    },

    openSetupAccountModal: async function (accountId) {
        const account = this.currentAccountsData.find(a => a.id === accountId);
        if (!account) return;

        this.currentSetupAccountId = accountId;
        const modal = this.elements.setupAccountModal;

        if (this.elements.setupAccountPhone) {
            this.elements.setupAccountPhone.textContent = account.phone || 'Неизвестный номер';
        }

        await this.loadTemplatesForSelect();

        if (modal) {
            modal.classList.remove('hidden');
            modal.classList.add('flex');
        }
    },

    closeSetupAccountModal: function () {
        if (this.elements.setupAccountModal) {
            this.elements.setupAccountModal.classList.add('hidden');
            this.elements.setupAccountModal.classList.remove('flex');
        }
        this.currentSetupAccountId = null;
    },

    loadTemplatesForSelect: async function () {
        try {
            const response = await fetch('/api/templates/list');
            const data = await response.json();
            const templates = data.templates || [];
            const selectElement = this.elements.setupTemplateSelect;
            if (!selectElement) return;

            selectElement.innerHTML = '';
            if (templates.length === 0) {
                selectElement.innerHTML = '<option value="">Нет доступных шаблонов</option>';
            } else {
                selectElement.innerHTML = '<option value="">Выберите шаблон</option>' +
                    templates.map(t => `<option value="${t.id}">${t.name}</option>`).join('');
            }
        } catch (error) {
            console.error('Error loading templates:', error);
            this.showToast('Ошибка загрузки шаблонов', 'error');
        }
    },

    startAccountSetup: async function () {
        if (!this.currentSetupAccountId) {
            this.showToast('Аккаунт не выбран', 'error');
            return;
        }

        const templateId = this.elements.setupTemplateSelect?.value;
        if (!templateId) {
            this.showToast('Выберите шаблон', 'error');
            return;
        }

        const startBtn = this.elements.startSetupBtn;
        if (startBtn) {
            startBtn.disabled = true;
            startBtn.textContent = 'Запуск...';
        }

        try {
            // First update template
            const patchRes = await fetch(`/api/accounts/${this.currentSetupAccountId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    setup_template_id: parseInt(templateId)
                })
            });

            if (!patchRes.ok) throw new Error("Failed to update template");

            // Then trigger setup via the new endpoint
            const response = await fetch(`/api/accounts/${this.currentSetupAccountId}/run-setup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ force: false })
            });

            const data = await response.json();

            if (response.ok) {
                this.showToast('Setup запущен', 'success');
                this.closeSetupAccountModal();
                this.loadAccounts();
            } else {
                throw new Error(data.detail || data.message);
            }
        } catch (error) {
            this.showToast(`Ошибка: ${error.message}`, 'error');
        } finally {
            if (startBtn) {
                startBtn.disabled = false;
                startBtn.textContent = 'Начать настройку';
            }
        }
    }
};
