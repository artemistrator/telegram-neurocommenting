// Wizard Page JavaScript

// Global wizard state
const wizardState = {
    currentStep: 1,
    totalSteps: 5,
    selectedTemplateId: null,
    // Track proxy availability for Step 1
    proxies: {
        total: 0,
        active: 0,
        dead: 0,
        free: 0
    },
    // Track accounts for Step 2
    accounts: [],
    // Track search results for Step 4
    searchResults: [],
    // Track selected targets for Step 4
    selectedTargets: [],
    // Track matrix assignments for Step 5
    matrixAssignments: [],
    // Track templates for Step 3
    templates: []
};

// Wizard functions
function initWizard() {
    updateStepDisplay();
    attachEventListeners();
    
    // Load proxies on Step 1
    if (wizardState.currentStep === 1) {
        loadProxies();
    }
}

// Update the display for the current step
function updateStepDisplay() {
    const stepContents = document.querySelectorAll('.step-content');
    const stepButtons = document.querySelectorAll('.step-btn');
    const nextStepBtn = document.getElementById('next-step-btn');
    const prevStepBtn = document.getElementById('prev-step-btn');
    const stepProgress = document.querySelectorAll('.step-progress');
    
    // Hide all step contents
    stepContents.forEach(content => {
        content.classList.add('hidden');
    });

    // Show current step content
    const currentStepContent = document.getElementById(`step-${wizardState.currentStep}-${getStepName(wizardState.currentStep)}`);
    if (currentStepContent) {
        currentStepContent.classList.remove('hidden');
    }

    // Update step buttons
    stepButtons.forEach(btn => {
        const stepNum = parseInt(btn.dataset.step);
        if (stepNum === wizardState.currentStep) {
            btn.classList.add('active', 'bg-blue-500');
            btn.classList.remove('bg-gray-300');
        } else {
            btn.classList.remove('active', 'bg-blue-500');
            btn.classList.add('bg-gray-300');
        }
    });

    // Update progress bars
    updateProgressBars();

    // Update navigation buttons
    updateNavigationButtons();
}

// Update progress bars between steps
function updateProgressBars() {
    const stepProgress = document.querySelectorAll('.step-progress');
    
    // Calculate how many progress bars to fill (all before current step)
    const filledBars = wizardState.currentStep - 1;
    
    stepProgress.forEach((progress, index) => {
        if (index < filledBars) {
            progress.style.width = '100%';
        } else {
            progress.style.width = '0%';
        }
    });
}

// Update the visibility of navigation buttons
function updateNavigationButtons() {
    const prevStepBtn = document.getElementById('prev-step-btn');
    const nextStepBtn = document.getElementById('next-step-btn');
    
    // Show/hide prev button
    if (wizardState.currentStep === 1) {
        prevStepBtn.classList.add('hidden');
    } else {
        prevStepBtn.classList.remove('hidden');
    }

    // Update next button text and action
    if (wizardState.currentStep === wizardState.totalSteps) {
        nextStepBtn.textContent = 'Launch Campaign';
    } else {
        nextStepBtn.textContent = 'Next Step →';
    }
    
    // Enable/disable next button based on step requirements
    if (wizardState.currentStep === 1) {
        // Step 1: Only enable Next if there are active proxies
        nextStepBtn.disabled = wizardState.proxies.active <= 0;
        if (wizardState.proxies.active <= 0) {
            nextStepBtn.title = 'You need at least 1 active proxy to proceed';
        } else {
            nextStepBtn.title = '';
        }
    } else if (wizardState.currentStep === 2) {
        // Step 2: Disable Next if no accounts loaded, or if no accounts with proxies
        const totalAccounts = wizardState.accounts.length;
        const accountsWithProxies = wizardState.accounts.filter(a => a.proxy && a.proxy.host).length;
        nextStepBtn.disabled = totalAccounts === 0 || accountsWithProxies <= 0;
        if (totalAccounts === 0) {
            nextStepBtn.title = 'Please load or import accounts first';
        } else if (accountsWithProxies <= 0) {
            nextStepBtn.title = 'You need at least 1 account with a proxy to proceed';
        } else {
            nextStepBtn.title = '';
        }
    } else if (wizardState.currentStep === 3) {
        // Step 3: Only enable Next if at least one template exists
        const totalTemplates = wizardState.templates.length;
        nextStepBtn.disabled = totalTemplates === 0;
        if (totalTemplates === 0) {
            nextStepBtn.title = 'You need to create at least one template to proceed';
        } else {
            nextStepBtn.title = '';
        }
    } else {
        nextStepBtn.disabled = false;
        nextStepBtn.title = '';
    }
}

// Get step name based on step number
function getStepName(step) {
    const stepNames = {
        1: 'proxies',
        2: 'accounts',
        3: 'templates',
        4: 'channels',
        5: 'launch'
    };
    return stepNames[step] || 'unknown';
}

// Go to a specific step
function goToStep(step) {
    if (step >= 1 && step <= wizardState.totalSteps) {
        wizardState.currentStep = step;
        updateStepDisplay();
        
        // Load data for the new step if needed
        if (step === 2) {
            loadAccounts();
        } else if (step === 3) {
            loadTemplates();
        } else if (step === 4) {
            loadChannels();
        } else if (step === 5) {
            renderMatrixTable();
        }
    }
}

// Go to next step
function nextStep() {
    if (wizardState.currentStep < wizardState.totalSteps) {
        // Check requirements for current step before proceeding
        if (wizardState.currentStep === 1) {
            // Step 1: Require active proxies
            if (wizardState.proxies.active <= 0) {
                showToast('You need at least 1 active proxy to proceed to the next step.', 'error');
                return;
            }
        } else if (wizardState.currentStep === 2) {
            // Step 2: Require accounts with proxies
            const accountsWithProxies = wizardState.accounts.filter(a => a.proxy && a.proxy.host).length;
            if (accountsWithProxies <= 0) {
                showToast('You need at least 1 account with a proxy to proceed to the next step.', 'error');
                return;
            }
        } else if (wizardState.currentStep === 3) {
            // Step 3: Require at least one template exists
            if (wizardState.templates.length === 0) {
                showToast('You need to create at least one template to proceed to the next step.', 'error');
                return;
            }
        }
        
        wizardState.currentStep++;
        updateStepDisplay();
        
        // Load data for the new step if needed
        if (wizardState.currentStep === 2) {
            loadAccounts();
        } else if (wizardState.currentStep === 3) {
            loadTemplates();
        } else if (wizardState.currentStep === 4) {
            // Load channels for step 4 if needed
            loadChannels();
        } else if (wizardState.currentStep === 5) {
            // Update summary on step 5
            updateSummary();
        }
    } else if (wizardState.currentStep === wizardState.totalSteps) {
        // On the last step, we can implement launch functionality
        launchCampaign();
    }
}

// Go to previous step
function prevStep() {
    if (wizardState.currentStep > 1) {
        wizardState.currentStep--;
        updateStepDisplay();
    }
}

// Launch campaign function (placeholder)
function launchCampaign() {
    const confirmCheckbox = document.getElementById('confirm-launch');
    if (!confirmCheckbox || confirmCheckbox.checked) {
        alert('Campaign launched successfully!');
        // Here you would implement the actual campaign launch logic
    } else {
        alert('Please confirm that you want to launch the campaign.');
    }
}

// Attach event listeners
function attachEventListeners() {
    const stepButtons = document.querySelectorAll('.step-btn');
    const nextStepBtn = document.getElementById('next-step-btn');
    const prevStepBtn = document.getElementById('prev-step-btn');
    
    // Step buttons
    stepButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const step = parseInt(this.dataset.step);
            goToStep(step);
        });
    });

    // Next button
    nextStepBtn.addEventListener('click', nextStep);

    // Previous button
    prevStepBtn.addEventListener('click', prevStep);
    
    // Template modal event listeners
    const profileTab = document.getElementById('profile-tab');
    const commentTab = document.getElementById('comment-tab');
    const submitBtn = document.getElementById('submit-template-btn');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const cancelBtn = document.getElementById('cancel-template-btn');
    
    if (profileTab) {
        profileTab.addEventListener('click', () => switchToTab('profile-tab'));
    }
    if (commentTab) {
        commentTab.addEventListener('click', () => switchToTab('comment-tab'));
    }
    if (submitBtn) {
        submitBtn.addEventListener('click', saveTemplate);
    }
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', closeTemplateModal);
    }
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeTemplateModal);
    }

    // Allow navigation with keyboard (optional)
    document.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowRight') {
            nextStep();
        } else if (e.key === 'ArrowLeft') {
            prevStep();
        }
    });
}

// PROXY FUNCTIONALITY (Step 1) - Copied from proxies.html

// Toast notification function
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const icon = document.getElementById('toast-icon');
    const messageEl = document.getElementById('toast-message');

    const icons = {
        success: '✅',
        error: '❌',
        info: 'ℹ️',
        warning: '⚠️'
    };

    icon.textContent = icons[type] || icons.info;
    messageEl.textContent = message;

    toast.classList.remove('hidden');

    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

// Modal functions
function openImportProxyModal() {
    document.getElementById('importProxyModal').classList.remove('hidden');
    document.getElementById('importProxyModal').classList.add('flex');
    document.getElementById('proxy-list').value = '';
    document.getElementById('import-status').classList.add('hidden');
}

function closeImportProxyModal() {
    document.getElementById('importProxyModal').classList.add('hidden');
    document.getElementById('importProxyModal').classList.remove('flex');
}

// Update proxy
async function updateProxy(proxyId, data) {
    try {
        const response = await fetch(`/api/proxies/${proxyId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            return await response.json();
        } else {
            const error = await response.json();
            throw new Error(error.detail || 'Update failed');
        }
    } catch (error) {
        throw error;
    }
}

// Handle proxy type change
async function handleProxyTypeChange(proxyId, newType) {
    try {
        await updateProxy(proxyId, { type: newType });
        showToast('Тип обновлен. Статус сброшен на "не проверен"', 'success');
        await loadProxies();
    } catch (error) {
        showToast(`Ошибка обновления: ${error.message}`, 'error');
    }
}

// Import proxy list
async function importProxyList() {
    const proxyList = document.getElementById('proxy-list').value.trim();
    const defaultType = document.getElementById('default-proxy-type').value;

    if (!proxyList) {
        alert('Вставьте список прокси');
        return;
    }

    // Create a text file from the textarea content
    const blob = new Blob([proxyList], { type: 'text/plain' });
    const file = new File([blob], 'proxies.txt', { type: 'text/plain' });

    const formData = new FormData();
    formData.append('file', file);

    const statusDiv = document.getElementById('import-status');
    const statusText = document.getElementById('import-status-text');

    statusDiv.classList.remove('hidden');
    statusDiv.querySelector('div').className = 'p-4 rounded-lg bg-blue-50';
    statusText.className = 'text-sm font-medium text-blue-800';
    statusText.textContent = 'Импорт прокси...';

    try {
        const response = await fetch(`/api/proxies/import?default_type=${defaultType}`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            statusDiv.querySelector('div').className = 'p-4 rounded-lg bg-green-50';
            statusText.className = 'text-sm font-medium text-green-800';
            statusText.textContent = `✅ Импортировано: ${data.imported} прокси (тип по умолчанию: ${defaultType.toUpperCase()})`;

            if (data.errors.length > 0) {
                statusText.textContent += `\n⚠️ Ошибок: ${data.errors.length}`;
                console.log('Import errors:', data.errors);
            }

            // Reload proxies after 1 second
            setTimeout(() => {
                closeImportProxyModal();
                loadProxies();
            }, 1500);
        } else {
            statusDiv.querySelector('div').className = 'p-4 rounded-lg bg-red-50';
            statusText.className = 'text-sm font-medium text-red-800';
            statusText.textContent = `❌ Ошибка: ${data.detail}`;
        }
    } catch (error) {
        statusDiv.querySelector('div').className = 'p-4 rounded-lg bg-red-50';
        statusText.className = 'text-sm font-medium text-red-800';
        statusText.textContent = `❌ Ошибка: ${error.message}`;
    }
}

// Load proxies
async function loadProxies() {
    try {
        const response = await fetch('/api/proxies/list');
        const data = await response.json();

        const tbody = document.getElementById('proxies-table');
        tbody.innerHTML = '';

        if (data.proxies.length === 0) {
            tbody.innerHTML = `
            <tr>
                <td colspan="8" class="px-6 py-12 text-center">
                    <div class="text-gray-400">
                        <svg class="mx-auto h-12 w-12 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"/>
                        </svg>
                        <p class="text-lg font-medium text-gray-900 mb-2">Прокси не загружены</p>
                        <p class="text-sm text-gray-500">Нажмите "Импорт списка" чтобы начать</p>
                    </div>
                </td>
            </tr>
        `;
        } else {
            data.proxies.forEach(proxy => {
                const row = document.createElement('tr');
                row.className = 'hover:bg-gray-50';
                row.setAttribute('data-proxy-id', proxy.id);

                // Status badge
                let statusBadge = '';
                if (proxy.status === 'ok' || proxy.status === 'active') {
                    statusBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">Активен</span>';
                } else if (proxy.status === 'failed' || proxy.status === 'dead') {
                    statusBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">Мертв</span>';
                } else {
                    statusBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-800">Не проверен</span>';
                }

                // Auth display
                const authText = proxy.username ? `${proxy.username}:***` : '-';

                // Ping display
                const pingText = proxy.ping_ms ? `${proxy.ping_ms}ms` : '-';

                // Assignment display
                let assignmentText = '<span class="text-green-600 font-medium">Свободен</span>';
                if (proxy.assigned_to) {
                    assignmentText = `<span class="text-gray-600">Аккаунт #${proxy.assigned_to}</span>`;
                }

                // Last check display
                const lastCheck = proxy.last_check ? new Date(proxy.last_check).toLocaleString('ru-RU') : '-';

                // Editable type dropdown
                const typeDropdown = `
                    <select onchange="handleProxyTypeChange(${proxy.id}, this.value)" 
                        class="px-2 py-1 text-xs font-medium rounded bg-blue-100 text-blue-800 border-none cursor-pointer hover:bg-blue-200">
                        <option value="socks5" ${proxy.type === 'socks5' ? 'selected' : ''}>SOCKS5</option>
                        <option value="socks4" ${proxy.type === 'socks4' ? 'selected' : ''}>SOCKS4</option>
                        <option value="http" ${proxy.type === 'http' ? 'selected' : ''}>HTTP</option>
                    </select>
                `;

                row.innerHTML = `
                    <td class="px-6 py-4 whitespace-nowrap font-medium text-gray-900">${proxy.host}:${proxy.port}</td>
                    <td class="px-6 py-4 whitespace-nowrap">${typeDropdown}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-gray-500 text-sm font-mono">${authText}</td>
                    <td class="px-6 py-4 whitespace-nowrap">${statusBadge}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-gray-500 text-sm">${pingText}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm">${assignmentText}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-gray-500 text-sm">${lastCheck}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm">
                        <button onclick="testSingleProxy(${proxy.id})" 
                            class="text-blue-600 hover:text-blue-800 font-medium mr-3"
                            title="Проверить прокси">
                            🔍
                        </button>
                        <button onclick="deleteProxy(${proxy.id})" 
                            class="text-red-600 hover:text-red-800 font-medium"
                            title="Удалить">
                            🗑️
                        </button>
                    </td>
                `;

                tbody.appendChild(row);
            });
        }

        // Update stats
        const totalProxies = data.proxies.length;
        const activeProxies = data.proxies.filter(p => p.status === 'ok' || p.status === 'active').length;
        const deadProxies = data.proxies.filter(p => p.status === 'failed' || p.status === 'dead').length;
        const freeProxies = data.proxies.filter(p => !p.assigned_to).length;
        
        // Update global state
        wizardState.proxies = {
            total: totalProxies,
            active: activeProxies,
            dead: deadProxies,
            free: freeProxies
        };

        document.getElementById('total-proxies').textContent = totalProxies;
        document.getElementById('active-proxies').textContent = activeProxies;
        document.getElementById('dead-proxies').textContent = deadProxies;
        document.getElementById('free-proxies').textContent = freeProxies;
        
        // Update navigation buttons after loading proxies
        updateNavigationButtons();

    } catch (error) {
        console.error('Error loading proxies:', error);
        showToast(`Ошибка загрузки прокси: ${error.message}`, 'error');
    }
}

// Test single proxy
async function testSingleProxy(proxyId) {
    const row = document.querySelector(`tr[data-proxy-id="${proxyId}"]`);
    if (!row) return;

    // Show loading state
    const statusCell = row.cells[3];
    const originalStatus = statusCell.innerHTML;
    statusCell.innerHTML = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-800">Проверка...</span>';

    try {
        const response = await fetch(`/api/proxies/test/${proxyId}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (response.ok) {
            if (data.status === 'ok') {
                showToast(`Прокси работает! Пинг: ${data.ping_ms}ms`, 'success');
            } else {
                showToast('Прокси не работает', 'error');
            }
            // Reload proxies to get updated data
            await loadProxies();
        } else {
            statusCell.innerHTML = originalStatus;
            showToast(`Ошибка проверки: ${data.detail}`, 'error');
        }
    } catch (error) {
        statusCell.innerHTML = originalStatus;
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

// Test all proxies
async function testAllProxies() {
    const tbody = document.getElementById('proxies-table');
    const rows = tbody.querySelectorAll('tr[data-proxy-id]');

    if (rows.length === 0) {
        alert('Нет прокси для проверки');
        return;
    }

    if (!confirm(`Проверить все ${rows.length} прокси? Это может занять некоторое время.`)) {
        return;
    }

    let completed = 0;
    const total = rows.length;

    for (const row of rows) {
        const proxyId = row.getAttribute('data-proxy-id');

        try {
            await testSingleProxy(proxyId);
            completed++;

            // Update progress in console
            console.log(`Проверено ${completed}/${total} прокси`);

            // Small delay between tests to avoid overwhelming the server
            await new Promise(resolve => setTimeout(resolve, 500));
        } catch (error) {
            console.error(`Ошибка проверки прокси ${proxyId}:`, error);
        }
    }

    showToast(`Проверка завершена! Проверено ${completed}/${total} прокси.`, 'success');
    await loadProxies();
}

// Delete proxy
async function deleteProxy(proxyId) {
    if (!confirm('Удалить прокси? Это действие нельзя отменить.')) {
        return;
    }

    try {
        const response = await fetch(`/api/proxies/${proxyId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showToast('Прокси удален', 'success');
            await loadProxies();
        } else {
            const data = await response.json();
            showToast(`Ошибка: ${data.detail}`, 'error');
        }
    } catch (error) {
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

// ACCOUNT FUNCTIONALITY (Step 2) - Adapted from accounts.page.js

// Load accounts
async function loadAccounts() {
    try {
        const response = await fetch('/api/accounts/list');
        const data = await response.json();
        const accounts = data.accounts || data.data || [];

        wizardState.accounts = accounts;
        renderAccountsTable(accounts);
        updateAccountStats(accounts);
        
        // Update navigation buttons after loading accounts
        updateNavigationButtons();
    } catch (error) {
        console.error('Error loading accounts:', error);
        showToast(`Ошибка загрузки аккаунтов: ${error.message}`, 'error');
        // Still update navigation buttons even on error
        updateNavigationButtons();
    }
}

// Render accounts table
function renderAccountsTable(accounts) {
    const tbody = document.getElementById('accounts-table');
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
        let avatarUrl = 'https://ui-avatars.com/api/?name=' + encodeURIComponent(account.phone || 'User');
        if (account.avatar_url) {
            avatarUrl = account.avatar_url;
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
                onchange="updateAccountRole(${account.id}, this.value)" 
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
                onclick="toggleWarmupMode(${account.id}, ${warmupActive})" 
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

        // Proxy - Updated to show proxy status
        let proxyHtml = '';
        if (account.proxy && account.proxy.host) {
            proxyHtml = `
                <div class="text-sm">
                    <span class="font-mono text-gray-700">${account.proxy.host}:${account.proxy.port}</span>
                    <br><span class="text-xs text-gray-500">${account.proxy.type ? account.proxy.type.toUpperCase() : 'N/A'}</span>
                    <br><span class="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">Proxy OK</span>
                </div>`;
        } else {
            proxyHtml = `<span class="text-sm text-red-600 font-medium">No Proxy</span>`;
        }

        // Status column for wizard - shows if proxy is assigned
        let statusColumn = 'No Proxy';
        if (account.proxy && account.proxy.host) {
            statusColumn = `Ready (Proxy Assigned: ${account.proxy.host})`;
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
            <button onclick="openAccountDetails(${account.id})" class="text-gray-600 hover:text-gray-800 font-medium mr-2" title="Подробнее">👁️</button>
            <button onclick="checkAccountStatus(${account.id})" class="text-blue-600 hover:text-blue-800 font-medium mr-2" title="Проверить статус">🔍</button>
            <button onclick="runSetup(${account.id})" class="text-green-600 hover:text-green-800 font-medium mr-2" title="Запустить Setup" ${isDisabled ? 'disabled' : ''}>▶</button>
            <button onclick="deleteAccount(${account.id})" class="text-red-600 hover:text-red-800 font-medium" title="Удалить">🗑️</button>
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
}

// Update account stats
function updateAccountStats(accounts) {
    document.getElementById('total-accounts').textContent = accounts.length;
    document.getElementById('active-accounts').textContent = accounts.filter(a => a.status === 'active').length;
    document.getElementById('setup-completed').textContent = accounts.filter(a => a.setup_status === 'completed').length;
    document.getElementById('with-proxy').textContent = accounts.filter(a => a.proxy && a.proxy.host).length;
    document.getElementById('banned-accounts').textContent = accounts.filter(a => a.status === 'banned').length;
    document.getElementById('reserve-accounts').textContent = accounts.filter(a => a.status === 'reserve' || a.status === 'reserved').length;
}

// Import accounts with auto-proxy assignment
async function importAccountsAutoProxy() {
    // First get available active proxies
    const availableProxies = await getAvailableProxies();
    
    if (availableProxies.length === 0) {
        showToast('No available active proxies to assign', 'error');
        return;
    }
    
    // Create a FormData with auto_assign_proxy = true
    const formData = new FormData();
    formData.append('auto_assign_proxy', true);
    
    // Use the same import API as the accounts page
    try {
        const response = await fetch('/api/accounts/import', { 
            method: 'POST', 
            body: formData 
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(`✅ Импортировано: ${data.imported} аккаунтов`, 'success');
            // Reload accounts after import
            await loadAccounts();
        } else {
            throw new Error(data.detail || data.message);
        }
    } catch (error) {
        showToast(`❌ Ошибка: ${error.message}`, 'error');
    }
}

// Get available active proxies for auto-assignment
async function getAvailableProxies() {
    try {
        const response = await fetch('/api/proxies/list');
        const data = await response.json();
        
        // Return only active proxies that are not assigned
        return data.proxies.filter(proxy => 
            (proxy.status === 'ok' || proxy.status === 'active') && !proxy.assigned_to
        );
    } catch (error) {
        console.error('Error getting available proxies:', error);
        return [];
    }
}

// Update account role
async function updateAccountRole(accountId, workMode) {
    try {
        const response = await fetch(`/api/accounts/${accountId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ work_mode: workMode })
        });
        const data = await response.json();
        if (response.ok) {
            showToast('Роль обновлена', 'success');
            loadAccounts();
        } else {
            throw new Error(data.detail || data.message);
        }
    } catch (error) {
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

// Toggle warmup mode
async function toggleWarmupMode(accountId, currentMode) {
    try {
        const newMode = !currentMode;
        const response = await fetch(`/api/accounts/${accountId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ warmup_mode: newMode })
        });
        const data = await response.json();
        if (response.ok) {
            showToast(`Режим прогрева ${newMode ? 'включен' : 'выключен'}`, 'success');
            loadAccounts();
        } else {
            throw new Error(data.detail || data.message);
        }
    } catch (error) {
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

// Check account status
async function checkAccountStatus(accountId) {
    showToast('Проверка статуса аккаунта...', 'info');
    try {
        const response = await fetch(`/api/accounts/${accountId}/check-status`, { method: 'POST' });
        const data = await response.json();
        if (response.ok) {
            showToast(`Статус: ${data.status}`, 'success');
            loadAccounts();
        } else {
            throw new Error(data.detail || data.message);
        }
    } catch (error) {
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

// Delete account
async function deleteAccount(accountId) {
    if (!confirm('Удалить аккаунт? Это действие нельзя отменить.')) return;
    try {
        const response = await fetch(`/api/accounts/${accountId}`, { method: 'DELETE' });
        if (response.ok) {
            showToast('Аккаунт удален', 'success');
            loadAccounts();
        } else {
            const data = await response.json();
            throw new Error(data.detail || data.message);
        }
    } catch (error) {
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

// Run setup
function runSetup(accountId) {
    // Placeholder for setup functionality
    showToast('Setup functionality coming soon', 'info');
}

// TEMPLATE FUNCTIONALITY (Step 3)

// Load templates
async function loadTemplates() {
    try {
        const response = await fetch('/api/templates/list');
        const data = await response.json();
        wizardState.templates = data.templates || [];
        renderTemplates(wizardState.templates);
        // Update navigation buttons after loading templates
        updateNavigationButtons();
    } catch (error) {
        console.error('Error loading templates:', error);
        showToast(`Ошибка загрузки шаблонов: ${error.message}`, 'error');
        wizardState.templates = [];
        // Still update navigation buttons even on error
        updateNavigationButtons();
    }
}

// Render templates as cards
function renderTemplates(templates) {
    const container = document.getElementById('templates-container');
    
    if (!container) {
        console.error('Templates container not found');
        return;
    }

    if (templates.length === 0) {
        container.innerHTML = `
            <div class="col-span-full text-center py-12">
                <p class="text-gray-500">Нет созданных шаблонов</p>
            </div>
        `;
        return;
    }

    container.innerHTML = templates.map(template => `
        <div class="bg-white rounded-lg shadow-md overflow-hidden border border-gray-200 hover:shadow-lg transition">
            <div class="p-5">
                <div class="flex justify-between items-start">
                    <h3 class="text-lg font-bold text-gray-800">${escapeHtml(template.name)}</h3>
                    <div class="flex gap-2">
                        <button onclick="editTemplate(${template.id})" 
                            class="text-blue-500 hover:text-blue-700">
                            ✏️
                        </button>
                        <button onclick="deleteTemplate(${template.id})" 
                            class="text-red-500 hover:text-red-700">
                            🗑️
                        </button>
                    </div>
                </div>
                
                <!-- Profile Summary -->
                ${getProfileSummary(template)}
                
                <!-- Comment Policy Summary -->
                ${getCommentPolicySummary(template)}
            </div>
        </div>
    `).join('');
}

// Get profile summary for template card
function getProfileSummary(template) {
    // Extract profile data from either profile_config or fallback to direct fields
    const profileData = template.profile_config || {};
    const firstName = profileData.first_name || template.first_name || '';
    const lastName = profileData.last_name || template.last_name || '';
    const bio = profileData.bio || template.bio || '';
    
    const fullName = `${firstName} ${lastName}`.trim();
    
    return `
        <div class="mt-3">
            ${fullName ? `<p class="text-sm text-gray-600">${escapeHtml(fullName)}</p>` : ''}
            ${bio ? `<p class="text-sm text-gray-600 line-clamp-2 mt-1">${escapeHtml(bio)}</p>` : ''}
        </div>
    `;
}

// Get comment policy summary for template card
function getCommentPolicySummary(template) {
    // Extract comment data from either comment_config or fallback to direct fields
    const commentData = template.comment_config || {};
    const filterMode = commentData.filter_mode || template.filter_mode || 'none';
    const filterKeywords = commentData.filter_keywords || template.filter_keywords || '';
    
    let filterText = '';
    switch(filterMode) {
        case 'keywords':
            filterText = 'По ключам';
            break;
        case 'none':
        default:
            filterText = 'Без фильтра';
            break;
    }
    
    // Get first few keywords for display
    let keywordsPreview = '';
    if (filterKeywords) {
        const keywords = filterKeywords.split(',').map(k => k.trim()).filter(k => k);
        keywordsPreview = keywords.slice(0, 2).join(', ');
        if (keywords.length > 2) {
            keywordsPreview += '...';
        }
    }
    
    return `
        <div class="mt-3 flex items-center gap-1">
            <span class="text-xs bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full border border-purple-200">
                ${filterText}${keywordsPreview ? `: ${keywordsPreview}` : ''}
            </span>
        </div>
    `;
}

// Template modal state
let currentTemplateId = null;

// Open create template modal
function openCreateTemplateModal() {
    currentTemplateId = null;
    document.getElementById('modal-title').textContent = 'Создать шаблон';
    document.getElementById('template-form').reset();
    document.getElementById('template-id').value = '';
    
    // Reset tabs
    switchToTab('profile-tab');
    
    showTemplateModal();
}

// Open edit template modal
async function editTemplate(id) {
    try {
        const response = await fetch('/api/templates/list');
        
        if (!response.ok) {
            throw new Error('Failed to load templates');
        }
        
        const data = await response.json();
        const template = data.templates.find(t => t.id === id);
        
        if (!template) {
            throw new Error('Template not found');
        }
        
        // Fill form with template data
        currentTemplateId = template.id;
        document.getElementById('modal-title').textContent = 'Редактировать шаблон';
        document.getElementById('template-id').value = template.id;
        
        // Map template data to form fields
        fillFormFields(template);
        
        // Reset tabs
        switchToTab('profile-tab');
        
        showTemplateModal();
    } catch (error) {
        console.error('Error loading template:', error);
        showToast('Ошибка загрузки шаблона: ' + error.message, 'error');
    }
}

// Close template modal
function closeTemplateModal() {
    hideTemplateModal();
}

// Show template modal
function showTemplateModal() {
    const modal = document.getElementById('templateModal');
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
}

// Hide template modal
function hideTemplateModal() {
    const modal = document.getElementById('templateModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

// Switch to a specific tab
function switchToTab(tabId) {
    // Hide all tab panels
    document.querySelectorAll('[role="tabpanel"]').forEach(panel => {
        panel.classList.add('hidden');
    });
    
    // Remove active class from all tabs
    document.querySelectorAll('[role="tab"]').forEach(tab => {
        tab.setAttribute('aria-selected', 'false');
        tab.classList.remove('border-blue-500', 'text-blue-600');
        tab.classList.add('border-transparent', 'text-gray-500');
    });
    
    // Show the selected tab panel
    const panelId = tabId.replace('-tab', '-panel');
    const panel = document.getElementById(panelId);
    if (panel) {
        panel.classList.remove('hidden');
    }
    
    // Activate the selected tab
    const tab = document.getElementById(tabId);
    if (tab) {
        tab.setAttribute('aria-selected', 'true');
        tab.classList.remove('border-transparent', 'text-gray-500');
        tab.classList.add('border-blue-500', 'text-blue-600');
    }
}

// Fill form fields with template data
function fillFormFields(template) {
    // Extract profile config (fallback to direct fields)
    const profileConfig = template.profile_config || {};
    const commentConfig = template.comment_config || {};
    
    // Basic fields
    document.getElementById('template-name').value = template.name || '';
    
    // Profile fields
    document.getElementById('template-first-name').value = profileConfig.first_name || template.first_name || '';
    document.getElementById('template-last-name').value = profileConfig.last_name || template.last_name || '';
    document.getElementById('template-avatar').value = profileConfig.avatar || template.avatar || '';
    document.getElementById('template-channel-title').value = profileConfig.channel_title || template.channel_title || '';
    document.getElementById('template-channel-description').value = profileConfig.channel_description || template.channel_description || '';
    document.getElementById('template-post-text-template').value = profileConfig.post_text_template || template.post_text_template || '';
    
    // Comment fields
    document.getElementById('template-commenting-prompt').value = commentConfig.commenting_prompt || template.commenting_prompt || '';
    document.getElementById('template-style').value = commentConfig.style || template.style || '';
    document.getElementById('template-tone').value = commentConfig.tone || template.tone || '';
    document.getElementById('template-max-words').value = commentConfig.max_words || template.max_words || '';
    document.getElementById('template-min-post-length').value = commentConfig.min_post_length || template.min_post_length || '';
    document.getElementById('template-filter-mode').value = commentConfig.filter_mode || template.filter_mode || 'none';
    document.getElementById('template-filter-keywords').value = commentConfig.filter_keywords || template.filter_keywords || '';
}

// Collect form data
function collectFormData() {
    return {
        name: document.getElementById('template-name').value.trim(),
        first_name: document.getElementById('template-first-name').value.trim() || null,
        last_name: document.getElementById('template-last-name').value.trim() || null,
        avatar: document.getElementById('template-avatar').value.trim() || null,
        channel_title: document.getElementById('template-channel-title').value.trim() || null,
        channel_description: document.getElementById('template-channel-description').value.trim() || null,
        post_text_template: document.getElementById('template-post-text-template').value.trim() || null,
        commenting_prompt: document.getElementById('template-commenting-prompt').value.trim() || null,
        style: document.getElementById('template-style').value.trim() || null,
        tone: document.getElementById('template-tone').value.trim() || null,
        max_words: document.getElementById('template-max-words').value ? parseInt(document.getElementById('template-max-words').value) : null,
        min_post_length: document.getElementById('template-min-post-length').value ? parseInt(document.getElementById('template-min-post-length').value) : null,
        filter_mode: document.getElementById('template-filter-mode').value || 'none',
        filter_keywords: document.getElementById('template-filter-keywords').value.trim() || null
    };
}

// Map form data to template structure
function mapFormDataToTemplate(formData) {
    // Create profile config object
    const profileConfig = {
        first_name: formData.first_name,
        last_name: formData.last_name,
        avatar: formData.avatar,
        channel_title: formData.channel_title,
        channel_description: formData.channel_description,
        post_text_template: formData.post_text_template
    };
    
    // Create comment config object
    const commentConfig = {
        commenting_prompt: formData.commenting_prompt,
        style: formData.style,
        tone: formData.tone,
        max_words: formData.max_words,
        filter_mode: formData.filter_mode,
        filter_keywords: formData.filter_keywords,
        min_post_length: formData.min_post_length
    };
    
    // Return template data with both new structured fields and old fields for backward compatibility
    return {
        name: formData.name,
        // Old fields for backward compatibility
        first_name: formData.first_name,
        last_name: formData.last_name,
        avatar: formData.avatar,
        channel_title: formData.channel_title,
        channel_description: formData.channel_description,
        post_text_template: formData.post_text_template,
        commenting_prompt: formData.commenting_prompt,
        style: formData.style,
        tone: formData.tone,
        max_words: formData.max_words,
        filter_mode: formData.filter_mode,
        filter_keywords: formData.filter_keywords,
        min_post_length: formData.min_post_length,
        // New structured fields
        profile_config: profileConfig,
        comment_config: commentConfig
    };
}

// Save template (create or update)
async function saveTemplate() {
    try {
        // Collect form data
        const formData = collectFormData();
        
        // Validate required fields
        if (!formData.name) {
            showToast('Название шаблона обязательно', 'warning');
            return;
        }
        
        // Validate comment fields if needed
        if (formData.filter_mode === 'keywords' && !formData.filter_keywords) {
            showToast('Ключевые слова обязательны при фильтрации по ключам', 'warning');
            return;
        }
        
        // Map form data to template structure
        const templateData = mapFormDataToTemplate(formData);
        
        let response;
        if (currentTemplateId) {
            // Update existing template
            response = await fetch(`/api/templates/${currentTemplateId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(templateData)
            });
        } else {
            // Create new template
            response = await fetch('/api/templates/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(templateData)
            });
        }
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Failed to save template' }));
            throw new Error(errorData.detail || 'Failed to save template');
        }
        
        // Success
        closeTemplateModal();
        
        // Reload templates list
        await loadTemplates();
        
        showToast(currentTemplateId ? 'Шаблон обновлен' : 'Шаблон создан', 'success');
        
    } catch (error) {
        console.error('Error saving template:', error);
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

// Delete template
async function deleteTemplate(id) {
    if (!confirm('Вы уверены, что хотите удалить этот шаблон?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/templates/${id}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: 'Failed to delete template' }));
            throw new Error(errorData.detail || 'Failed to delete template');
        }
        
        // Success
        await loadTemplates();
        showToast('Шаблон удален', 'success');
        
    } catch (error) {
        console.error('Error deleting template:', error);
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.toString().replace(/[&<>"]+/g, m => map[m]);
}

// Load channels for Step 4
async function loadChannels() {
    try {
        const response = await fetch('/api/channels/list');
        const data = await response.json();
        renderChannelsTable(data.channels || []);
    } catch (error) {
        console.error('Error loading channels:', error);
        showToast(`Ошибка загрузки каналов: ${error.message}`, 'error');
    }
}

// Render channels table
function renderChannelsTable(channels) {
    const tbody = document.getElementById('channels-table-body');
    if (!tbody) return;

    tbody.innerHTML = '';

    if (channels.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="px-6 py-12 text-center">
                    <p class="text-gray-500">Нет каналов в мониторинге.</p>
                </td>
            </tr>`;
        return;
    }

    channels.forEach(channel => {
        const row = document.createElement('tr');
        
        // Status badge
        let statusBadge = '';
        if (channel.status === 'active') {
            statusBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">Активен</span>';
        } else {
            statusBadge = '<span class="px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-800">Не активен</span>';
        }
        
        // Template name
        const templateName = channel.template ? channel.template.name : 'Не выбран';
        
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${channel.title || channel.name || 'N/A'}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${channel.subscribers || 'N/A'}</td>
            <td class="px-6 py-4 whitespace-nowrap">${statusBadge}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${templateName}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${channel.mode || 'Monitoring'}</td>
        `;
        
        tbody.appendChild(row);
    });
}

// Update summary on Step 5
function updateSummary() {
    // Update proxy summary
    document.getElementById('summary-proxies').textContent = `${wizardState.proxies.active} active`;
    
    // Update accounts summary
    const accountsWithProxies = wizardState.accounts.filter(a => a.proxy && a.proxy.host).length;
    document.getElementById('summary-accounts').textContent = `${accountsWithProxies} accounts`;
    
    // Update template summary
    const templateElement = document.querySelector(`[data-template-id="${wizardState.selectedTemplateId}"] h3`);
    const templateName = templateElement ? templateElement.textContent : 'Not selected';
    document.getElementById('summary-template').textContent = templateName;
    
    // Update channels summary (count from the channels table)
    const channelRows = document.querySelectorAll('#channels-table-body tr');
    document.getElementById('summary-channels').textContent = `${channelRows.length} channels`;
}

// Search and Targets functionality (Step 4)

// Start search
async function startSearch() {
    const keywords = document.getElementById('keywords').value.trim();
    const minSubscribers = document.getElementById('min_subscribers').value;
    
    if (!keywords) {
        showToast('Please enter at least one keyword', 'error');
        return;
    }
    
    // Show loading state
    const searchBtn = document.getElementById('search-btn');
    const btnText = searchBtn.querySelector('.btn-text');
    const loadingSpinner = searchBtn.querySelector('.loading');
    
    btnText.textContent = 'Searching...';
    loadingSpinner.classList.remove('hidden');
    
    try {
        const keywordsList = keywords.split('\n').filter(k => k.trim() !== '');
        
        const response = await fetch('/api/parser/search-channels', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                keywords: keywordsList, 
                min_subscribers: parseInt(minSubscribers),
                limit: 50
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Search failed');
        }
        
        const data = await response.json();
        const results = data.channels || [];
        
        // Add unique IDs for wizard state management
        results.forEach((result, index) => {
            result.id = result.channel_id || (Date.now() + index);
        });
        
        wizardState.searchResults = results;
        renderSearchResults(results);
        
        showToast(`Found ${results.length} channels`, 'success');
    } catch (error) {
        console.error('Search error:', error);
        showToast(`Search error: ${error.message}`, 'error');
    } finally {
        // Restore button state
        btnText.textContent = 'Начать поиск';
        loadingSpinner.classList.add('hidden');
    }
}

// Render search results
function renderSearchResults(results) {
    const tbody = document.getElementById('results-table');
    const noResults = document.getElementById('no-results');
    const resultsCount = document.getElementById('results-count');
    
    if (!tbody || !noResults || !resultsCount) return;
    
    tbody.innerHTML = '';
    
    if (results.length === 0) {
        noResults.classList.remove('hidden');
        resultsCount.textContent = '0';
        return;
    }
    
    noResults.classList.add('hidden');
    resultsCount.textContent = results.length;
    
    results.forEach(result => {
        const row = document.createElement('tr');
        row.id = `result-${result.id}`;
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap">
                <input type="checkbox" class="result-checkbox h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500" 
                    data-id="${result.id}" onclick="updateAddSelectedButton()">
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${result.title || result.name}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${result.subscribers}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${result.comments || 0}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-blue-600">
                <a href="${result.url}" target="_blank" class="hover:underline">${result.url}</a>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Toggle select all checkboxes
function toggleSelectAll() {
    const selectAllCheckbox = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('.result-checkbox');
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
    });
    
    updateAddSelectedButton();
}

// Update the state of the 'Add Selected' button
function updateAddSelectedButton() {
    const checkboxes = document.querySelectorAll('.result-checkbox:checked');
    const addSelectedBtn = document.getElementById('add-selected-btn');
    
    if (addSelectedBtn) {
        addSelectedBtn.disabled = checkboxes.length === 0;
    }
}

// Add selected results to targets
function addSelectedToTargets() {
    const checkboxes = document.querySelectorAll('.result-checkbox:checked');
    
    if (checkboxes.length === 0) return;
    
    const selectedResults = [];
    
    checkboxes.forEach(checkbox => {
        const id = parseInt(checkbox.dataset.id);
        const result = wizardState.searchResults.find(r => r.id === id);
        
        if (result && !wizardState.selectedTargets.some(t => t.id === result.id)) {
            wizardState.selectedTargets.push({...result});
        }
    });
    
    renderSelectedTargets();
    
    // Uncheck all checkboxes and update button
    document.querySelectorAll('.result-checkbox').forEach(cb => cb.checked = false);
    document.getElementById('select-all').checked = false;
    updateAddSelectedButton();
    
    showToast(`Added ${checkboxes.length} targets`, 'success');
}

// Render selected targets
function renderSelectedTargets() {
    const tbody = document.getElementById('selected-targets-table');
    const noSelectedTargets = document.getElementById('no-selected-targets');
    const selectedTargetsCount = document.getElementById('selected-targets-count');
    
    if (!tbody || !noSelectedTargets || !selectedTargetsCount) return;
    
    tbody.innerHTML = '';
    
    if (wizardState.selectedTargets.length === 0) {
        noSelectedTargets.classList.remove('hidden');
        selectedTargetsCount.textContent = '0';
        return;
    }
    
    noSelectedTargets.classList.add('hidden');
    selectedTargetsCount.textContent = wizardState.selectedTargets.length;
    
    wizardState.selectedTargets.forEach(target => {
        const row = document.createElement('tr');
        row.id = `selected-target-${target.id}`;
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${target.title || target.name}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${target.subscribers}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-blue-600">
                <a href="${target.url}" target="_blank" class="hover:underline">${target.url}</a>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
                <button onclick="removeSelectedTarget(${target.id})" 
                    class="text-red-600 hover:text-red-800 font-medium">
                    Удалить
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Remove a selected target
function removeSelectedTarget(targetId) {
    wizardState.selectedTargets = wizardState.selectedTargets.filter(t => t.id !== targetId);
    renderSelectedTargets();
    
    // Also uncheck the corresponding result in the search results table
    const checkbox = document.querySelector(`.result-checkbox[data-id="${targetId}"]`);
    if (checkbox) {
        checkbox.checked = false;
        updateAddSelectedButton();
    }
}

// Clear all selected targets
function clearSelectedTargets() {
    wizardState.selectedTargets = [];
    renderSelectedTargets();
    
    // Uncheck all checkboxes in search results
    document.querySelectorAll('.result-checkbox').forEach(cb => cb.checked = false);
    document.getElementById('select-all').checked = false;
    updateAddSelectedButton();
    
    showToast('Cleared all selected targets', 'info');
}

// Refresh search results
async function refreshSearchResults() {
    try {
        // Get current search parameters
        const keywords = document.getElementById('keywords').value.trim();
        const minSubscribers = document.getElementById('min_subscribers').value;
        
        if (!keywords) {
            renderSearchResults(wizardState.searchResults);
            return;
        }
        
        // Re-run the search with current parameters
        const keywordsList = keywords.split('\n').filter(k => k.trim() !== '');
        
        const response = await fetch('/api/parser/search-channels', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                keywords: keywordsList, 
                min_subscribers: parseInt(minSubscribers),
                limit: 50
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Search failed');
        }
        
        const data = await response.json();
        const results = data.channels || [];
        
        // Add unique IDs for wizard state management
        results.forEach((result, index) => {
            result.id = result.channel_id || (Date.now() + index);
        });
        
        wizardState.searchResults = results;
        renderSearchResults(results);
        
        showToast(`Refreshed results: ${results.length} channels`, 'success');
    } catch (error) {
        console.error('Refresh error:', error);
        showToast(`Refresh error: ${error.message}`, 'error');
        // Fallback to rendering existing results
        renderSearchResults(wizardState.searchResults);
    }
}

// Add manual channels
async function addManualChannels() {
    const textarea = document.getElementById('manual-urls');
    const urls = textarea.value.split('\n')
        .map(u => u.trim())
        .filter(u => u.length > 0);
    
    if (!urls.length) {
        showToast('Введите хотя бы одну ссылку', 'error');
        return;
    }
    
    const loading = document.getElementById('table-loading');
    loading.classList.remove('hidden');
    
    try {
        const response = await fetch('/api/parser/add-manual-channels', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls: urls })
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
        
        // Add unique IDs for wizard state management
        const results = data.channels;
        results.forEach((result, index) => {
            result.id = result.channel_id || (Date.now() + index);
        });
        
        // Add to search results
        wizardState.searchResults = [...wizardState.searchResults, ...results];
        renderSearchResults(wizardState.searchResults);
        
        showToast(`Резолвлено ${results.length} каналов`, 'success');
        textarea.value = '';
        
    } catch (error) {
        console.error('Manual channels error:', error);
        showToast('Ошибка: ' + error.message, 'error');
    } finally {
        loading.classList.add('hidden');
    }
}
// Matrix functionality (Step 5)

// Render matrix table
function renderMatrixTable() {
    const tbody = document.getElementById('matrix-table');
    const noMatrixRows = document.getElementById('no-matrix-rows');
    
    if (!tbody || !noMatrixRows) return;
    
    tbody.innerHTML = '';
    
    if (wizardState.selectedTargets.length === 0) {
        noMatrixRows.classList.remove('hidden');
        return;
    }
    
    noMatrixRows.classList.add('hidden');
    
    // Create matrix assignments if they don't exist
    if (wizardState.matrixAssignments.length === 0) {
        wizardState.selectedTargets.forEach(target => {
            wizardState.matrixAssignments.push({
                targetId: target.id,
                target: target,
                accountId: null,
                templateId: null
            });
        });
    }
    
    wizardState.matrixAssignments.forEach(assignment => {
        const row = document.createElement('tr');
        row.id = `matrix-row-${assignment.targetId}`;
        
        // Create account dropdown
        let accountOptions = '<option value=>Select Account</option>';
        wizardState.accounts.forEach(account => {
            const selected = assignment.accountId === account.id ? 'selected' : '';
            const proxyStatus = account.proxy && account.proxy.host ? ` (Proxy: ${account.proxy.host})` : ' (No Proxy)';
            accountOptions += `<option value="${account.id}" ${selected}>${account.phone || account.id}${proxyStatus}</option>`;
        });
        
        // Create template dropdown
        let templateOptions = '<option value=>Select Template</option>';
        // Get all available templates (including the selected one from step 3)
        const allTemplates = [];
        
        // Add the template selected in step 3 if it exists
        if (wizardState.selectedTemplateId) {
            const selectedTemplate = wizardState.accounts
                .flatMap(acc => acc.template)
                .find(t => t && t.id === wizardState.selectedTemplateId);
            
            if (selectedTemplate && !allTemplates.some(t => t.id === selectedTemplate.id)) {
                allTemplates.push(selectedTemplate);
            }
        }
        
        // Add templates from accounts
        wizardState.accounts.forEach(account => {
            if (account.template && !allTemplates.some(t => t.id === account.template.id)) {
                allTemplates.push(account.template);
            }
        });
        
        allTemplates.forEach(template => {
            if (template) {  // Make sure template exists
                const selected = assignment.templateId === template.id ? 'selected' : '';
                templateOptions += `<option value="${template.id}" ${selected}>${template.name}</option>`;
            }
        });
        
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${assignment.target.title || assignment.target.name}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
                <select class="account-select w-full p-2 border border-gray-300 rounded-md" 
                    onchange="updateMatrixAssignment(${assignment.targetId}, 'account', this.value)" 
                    data-target-id="${assignment.targetId}">
                    ${accountOptions}
                </select>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
                <select class="template-select w-full p-2 border border-gray-300 rounded-md" 
                    onchange="updateMatrixAssignment(${assignment.targetId}, 'template', this.value)" 
                    data-target-id="${assignment.targetId}">
                    ${templateOptions}
                </select>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Update matrix assignment
function updateMatrixAssignment(targetId, type, value) {
    const assignment = wizardState.matrixAssignments.find(a => a.targetId === targetId);
    if (assignment) {
        if (type === 'account') {
            assignment.accountId = value ? parseInt(value) : null;
        } else if (type === 'template') {
            assignment.templateId = value ? parseInt(value) : null;
        }
    }
}

// Auto-distribute accounts and templates
function autoDistribute() {
    if (wizardState.selectedTargets.length === 0) {
        showToast('No targets selected', 'error');
        return;
    }
    
    if (wizardState.accounts.length === 0) {
        showToast('No accounts available', 'error');
        return;
    }
    
    if (!wizardState.selectedTemplateId) {
        showToast('No template selected', 'error');
        return;
    }
    
    // Find accounts that have proxies assigned
    const accountsWithProxies = wizardState.accounts.filter(a => a.proxy && a.proxy.host);
    
    if (accountsWithProxies.length === 0) {
        showToast('No accounts with proxies available', 'error');
        return;
    }
    
    // Find the selected template from the accounts
    const selectedTemplate = wizardState.accounts
        .flatMap(acc => acc.template)
        .find(t => t && t.id === wizardState.selectedTemplateId);
    
    if (!selectedTemplate) {
        showToast('Selected template not found', 'error');
        return;
    }
    
    // Distribute accounts and templates to targets
    wizardState.selectedTargets.forEach((target, index) => {
        const accountId = accountsWithProxies[index % accountsWithProxies.length].id;
        const templateId = wizardState.selectedTemplateId;
        
        // Find or create assignment
        let assignment = wizardState.matrixAssignments.find(a => a.targetId === target.id);
        if (!assignment) {
            assignment = {
                targetId: target.id,
                target: target,
                accountId: null,
                templateId: null
            };
            wizardState.matrixAssignments.push(assignment);
        }
        
        assignment.accountId = accountId;
        assignment.templateId = templateId;
    });
    
    // Re-render the matrix table to reflect changes
    renderMatrixTable();
    
    showToast(`Auto-distributed to ${wizardState.selectedTargets.length} targets`, 'success');
}

// Finish campaign - send payload
async function finishCampaign() {
    // Validate that all targets have assignments
    const incompleteAssignments = wizardState.matrixAssignments.filter(a => !a.accountId || !a.templateId);
    
    if (incompleteAssignments.length > 0) {
        showToast(`Please assign accounts and templates to all ${incompleteAssignments.length} targets`, 'error');
        return;
    }
    
    // Create payload
    const payload = {
        targets: wizardState.matrixAssignments.map(assignment => ({
            channel_url: assignment.target.url,
            account_id: assignment.accountId,
            template_id: assignment.templateId
        }))
    };
    
    console.log('Campaign payload:', payload);
    
    try {
        const response = await fetch('/api/campaign/launch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            showToast('Campaign launched successfully!', 'success');
            // Optionally reset wizard state or redirect to campaign dashboard
        } else {
            const error = await response.json();
            throw new Error(error.detail || 'Launch failed');
        }
    } catch (error) {
        console.error('Launch error:', error);
        showToast(`Launch error: ${error.message}`, 'error');
    }
}

// Note: goToStep function is defined earlier in the file

// Update the nextStep function to handle navigation to step 5
async function nextStep() {
    if (wizardState.currentStep < wizardState.totalSteps) {
        // Check requirements for current step before proceeding
        if (wizardState.currentStep === 1) {
            // Step 1: Require active proxies
            if (wizardState.proxies.active <= 0) {
                showToast('You need at least 1 active proxy to proceed to the next step.', 'error');
                return;
            }
        } else if (wizardState.currentStep === 2) {
            // Step 2: Require accounts with proxies
            const accountsWithProxies = wizardState.accounts.filter(a => a.proxy && a.proxy.host).length;
            if (accountsWithProxies <= 0) {
                showToast('You need at least 1 account with a proxy to proceed to the next step.', 'error');
                return;
            }
        } else if (wizardState.currentStep === 3) {
            // Step 3: Require at least one template exists
            if (wizardState.templates.length === 0) {
                showToast('You need to create at least one template to proceed to the next step.', 'error');
                return;
            }
        } else if (wizardState.currentStep === 4) {
            // Step 4: Require selected targets
            if (wizardState.selectedTargets.length === 0) {
                showToast('You need to select at least one target to proceed to the next step.', 'error');
                return;
            }
        }
        
        wizardState.currentStep++;
        updateStepDisplay();
        
        // Load data for the new step if needed
        if (wizardState.currentStep === 2) {
            loadAccounts();
        } else if (wizardState.currentStep === 3) {
            loadTemplates();
        } else if (wizardState.currentStep === 4) {
            // Data already available
        } else if (wizardState.currentStep === 5) {
            renderMatrixTable();
        }
    } else if (wizardState.currentStep === wizardState.totalSteps) {
        // On the last step, we can implement launch functionality
        await finishCampaign();
    }
}

// Update updateStepDisplay to handle the new step IDs
function updateStepDisplay() {
    const stepContents = document.querySelectorAll('.step-content');
    const stepButtons = document.querySelectorAll('.step-btn');
    const nextStepBtn = document.getElementById('next-step-btn');
    const prevStepBtn = document.getElementById('prev-step-btn');
    const stepProgress = document.querySelectorAll('.step-progress');
    
    // Hide all step contents
    stepContents.forEach(content => {
        content.classList.add('hidden');
    });

    // Show current step content
    let currentStepContentId;
    switch (wizardState.currentStep) {
        case 1:
            currentStepContentId = 'step-1-proxies';
            break;
        case 2:
            currentStepContentId = 'step-2-accounts';
            break;
        case 3:
            currentStepContentId = 'step-3-templates';
            break;
        case 4:
            currentStepContentId = 'step-4-targets';
            break;
        case 5:
            currentStepContentId = 'step-5-matrix';
            break;
    }
    
    if (currentStepContentId) {
        const currentStepContent = document.getElementById(currentStepContentId);
        if (currentStepContent) {
            currentStepContent.classList.remove('hidden');
        }
    }

    // Update step buttons
    stepButtons.forEach(btn => {
        const stepNum = parseInt(btn.dataset.step);
        if (stepNum === wizardState.currentStep) {
            btn.classList.add('active', 'bg-blue-500');
            btn.classList.remove('bg-gray-300');
        } else {
            btn.classList.remove('active', 'bg-blue-500');
            btn.classList.add('bg-gray-300');
        }
    });

    // Update progress bars
    updateProgressBars();

    // Update navigation buttons
    updateNavigationButtons();
}

// Update updateNavigationButtons to handle step 5
function updateNavigationButtons() {
    const prevStepBtn = document.getElementById('prev-step-btn');
    const nextStepBtn = document.getElementById('next-step-btn');
    
    // Show/hide prev button
    if (wizardState.currentStep === 1) {
        prevStepBtn.classList.add('hidden');
    } else {
        prevStepBtn.classList.remove('hidden');
    }

    // Update next button text and action
    if (wizardState.currentStep === wizardState.totalSteps) {
        nextStepBtn.textContent = 'Finish Campaign';
        nextStepBtn.onclick = async () => await finishCampaign();
    } else {
        nextStepBtn.textContent = 'Next Step →';
        nextStepBtn.onclick = async () => await nextStep();
    }
    
    // Enable/disable next button based on step requirements
    if (wizardState.currentStep === 1) {
        // Step 1: Only enable Next if there are active proxies
        nextStepBtn.disabled = wizardState.proxies.active <= 0;
        if (wizardState.proxies.active <= 0) {
            nextStepBtn.title = 'You need at least 1 active proxy to proceed';
        } else {
            nextStepBtn.title = '';
        }
    } else if (wizardState.currentStep === 2) {
        // Step 2: Only enable Next if there are accounts with proxies
        const accountsWithProxies = wizardState.accounts.filter(a => a.proxy && a.proxy.host).length;
        nextStepBtn.disabled = accountsWithProxies <= 0;
        if (accountsWithProxies <= 0) {
            nextStepBtn.title = 'You need at least 1 account with a proxy to proceed';
        } else {
            nextStepBtn.title = '';
        }
    } else if (wizardState.currentStep === 3) {
        // Step 3: Only enable Next if at least one template exists
        const totalTemplates = wizardState.templates.length;
        nextStepBtn.disabled = totalTemplates === 0;
        if (totalTemplates === 0) {
            nextStepBtn.title = 'You need to create at least one template to proceed';
        } else {
            nextStepBtn.title = '';
        }
    } else if (wizardState.currentStep === 4) {
        // Step 4: Only enable Next if there are selected targets
        nextStepBtn.disabled = wizardState.selectedTargets.length <= 0;
        if (wizardState.selectedTargets.length <= 0) {
            nextStepBtn.title = 'You need to select at least one target to proceed';
        } else {
            nextStepBtn.title = '';
        }
    } else {
        nextStepBtn.disabled = false;
        nextStepBtn.title = '';
    }
}

// Initialize the wizard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initWizard();
});

// Expose functions to window for potential external use
window.initWizardPage = initWizard;
window.goToStep = goToStep;
window.nextStep = nextStep;
window.prevStep = prevStep;
window.loadProxies = loadProxies;
window.testAllProxies = testAllProxies;
window.openImportProxyModal = openImportProxyModal;
window.closeImportProxyModal = closeImportProxyModal;
window.importProxyList = importProxyList;
window.loadTemplates = loadTemplates;
window.openCreateTemplateModal = openCreateTemplateModal;
window.closeTemplateModal = closeTemplateModal;
window.saveTemplate = saveTemplate;
window.editTemplate = editTemplate;
window.deleteTemplate = deleteTemplate;