window.App = window.App || {};
window.App.pages = window.App.pages || {};
window.App.pages.parser = window.App.pages.parser || {};

window.App.pages.parser.init = function () {
    console.log('✅ Parser Page Init START (Modular)');

    // We need to access App.core.toast.showToast. 
    // The original code used 'app.showToast'. 
    // If 'app' is global, it might still work, but let's use the new robust way if possible.
    // However, for minimal changes, I will define a local helper or use the global 'showToast' if available.
    // Since 'initParserPage' was global, it had access to global 'showToast'.
    // BUT the original code used 'app.showToast'. This suggests 'app' exists globally.
    // I will try to use 'App.core.toast.showToast' instead of 'app.showToast' where I can.

    // For now, let's assume 'app' is global OR we can just use our new toast.
    const showToast = (msg, type) => {
        if (window.App && window.App.core && window.App.core.toast) {
            window.App.core.toast.showToast(msg, type);
        } else if (typeof window.showToast === 'function') {
            window.showToast(msg, type); // Fallback to global proxy
        } else if (window.app && window.app.showToast) {
            window.app.showToast(msg, type);
        } else {
            console.log('Toast:', msg);
        }
    };

    // Also need 'app.showToast' to work if the code calls it as method.
    // The copied code below uses 'app.showToast'. 
    // I'll leave 'app.showToast' calls but ensure 'app' exists locally or I replace it.
    // Replacing 'app.showToast' with 'showToast' (local wrapper) in the code below is safer.

    const searchBtn = document.getElementById('search-btn');
    const refreshBtn = document.getElementById('refresh-btn');
    const addSelectedBtn = document.getElementById('add-selected-btn');
    const resultsTable = document.getElementById('results-table');
    const resultsCount = document.getElementById('results-count');
    const selectAllCheckbox = document.getElementById('select-all');
    const noResults = document.getElementById('no-results');
    const tableLoading = document.getElementById('table-loading');

    // Key elements check - if main elements are missing, we might be on a partial load or wrong state
    if (!searchBtn || !resultsTable) {
        console.warn('Parser page: Required elements not found, skipping init events.');
        return;
    }

    // Optional elements checks can be silent
    // if (!refreshBtn) ...

    let currentResults = [];

    // --- API Interactions ---

    async function startSearch() {
        const keywordsInput = document.getElementById('keywords');
        if (!keywordsInput) return;

        const keywordsText = keywordsInput.value.trim();
        if (!keywordsText) {
            showToast('Введите ключевые слова', 'error');
            return;
        }

        const keywords = keywordsText.split('\n').map(k => k.trim()).filter(k => k);
        const minSubscribersInput = document.getElementById('min_subscribers');
        const minSubscribers = minSubscribersInput ? (parseInt(minSubscribersInput.value) || 100) : 100;

        // UI State: Loading
        if (searchBtn) {
            searchBtn.disabled = true;
            const btnText = searchBtn.querySelector('.btn-text');
            if (btnText) btnText.textContent = 'Запуск...';
            const loadingIcon = searchBtn.querySelector('.loading');
            if (loadingIcon) loadingIcon.classList.remove('hidden');
        }

        try {
            const response = await fetch('/api/parser/start-search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    keywords: keywords,
                    min_subscribers: minSubscribers
                })
            });

            const data = await response.json();

            if (response.ok) {
                showToast(`Поиск запущен для ${data.count} ключевых слов`);
                if (keywordsInput) keywordsInput.value = ''; // Clear input
            } else {
                throw new Error(data.detail || 'Ошибка запуска поиска');
            }
        } catch (error) {
            console.error(error);
            showToast(error.message, 'error');
        } finally {
            // UI State: Reset
            if (searchBtn) {
                searchBtn.disabled = false;
                const btnText = searchBtn.querySelector('.btn-text');
                if (btnText) btnText.textContent = 'Начать поиск';
                const loadingIcon = searchBtn.querySelector('.loading');
                if (loadingIcon) loadingIcon.classList.add('hidden');
            }
        }
    }

    async function loadResults() {
        // UI State: Table Loading
        if (tableLoading) tableLoading.classList.remove('hidden');

        try {
            const response = await fetch('/api/parser/results');
            const data = await response.json();

            if (response.ok) {
                currentResults = data.results || [];
                renderResults(currentResults);
            } else {
                throw new Error(data.detail || 'Ошибка загрузки результатов');
            }
        } catch (error) {
            console.error(error);
            showToast('Не удалось загрузить результаты', 'error');
        } finally {
            if (tableLoading) tableLoading.classList.add('hidden');
        }
    }

    async function addToMonitoring() {
        // Correctly collect selected IDs using specific selector
        const selectedCheckboxes = document.querySelectorAll('input[type="checkbox"][name="channel_select"]:checked');
        const selectedIds = Array.from(selectedCheckboxes).map(cb => parseInt(cb.value));

        console.log('addToMonitoring payload:', selectedIds);

        if (selectedIds.length === 0) {
            showToast('Выберите каналы для добавления', 'error');
            return;
        }

        if (addSelectedBtn) {
            addSelectedBtn.disabled = true;
            addSelectedBtn.innerHTML = '<span class="mr-1">⏳</span> Добавление...';
        }

        try {
            const response = await fetch('/api/parser/add-to-monitoring', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ channel_ids: selectedIds })
            });

            const data = await response.json();

            if (response.ok) {
                showToast(`Добавлено ${data.added} каналов в мониторинг`);
                await loadResults(); // Reload table
                // Reset Checkbox state
                if (selectAllCheckbox) selectAllCheckbox.checked = false;
            } else {
                throw new Error(data.detail || 'Ошибка добавления');
            }
        } catch (error) {
            console.error(error);
            showToast(error.message, 'error');
        } finally {
            if (addSelectedBtn) {
                addSelectedBtn.disabled = false;
                addSelectedBtn.innerHTML = '<span class="mr-1">➕</span> Добавить выбранные в мониторинг';
            }
            updateAddButtonState();
        }
    }

    // --- UI Helper Functions ---

    function renderResults(results) {
        if (!resultsTable) return;
        resultsTable.innerHTML = '';
        if (resultsCount) resultsCount.textContent = results.length;
        if (selectAllCheckbox) selectAllCheckbox.checked = false;
        updateAddButtonState();

        if (results.length === 0) {
            if (noResults) noResults.classList.remove('hidden');
            return;
        } else {
            if (noResults) noResults.classList.add('hidden');
        }

        results.forEach(channel => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50 transition-colors';

            // Priority formatting
            let priorityClass = 'bg-gray-100 text-gray-800';
            if (channel.priority >= 7) priorityClass = 'bg-green-100 text-green-800';
            else if (channel.priority >= 4) priorityClass = 'bg-yellow-100 text-yellow-800';

            row.innerHTML = `
                <td class="px-6 py-4 whitespace-nowrap">
                    <input type="checkbox" value="${channel.id}" name="channel_select"
                        class="channel-checkbox h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500 cursor-pointer">
                </td>
                <td class="px-6 py-4">
                    <div class="flex items-center">
                        <div class="ml-0">
                            <div class="text-sm font-medium text-gray-900 line-clamp-1" title="${channel.title || 'Без названия'}">
                                <a href="${channel.url}" target="_blank" class="hover:text-blue-600 hover:underline">
                                    ${channel.title || 'Без названия'}
                                </a>
                            </div>
                            <div class="text-sm text-gray-500">${channel.username ? '@' + channel.username : ''}</div>
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${channel.subscribers ? channel.subscribers.toLocaleString() : '0'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${priorityClass}">
                        ${channel.priority || 0}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${channel.posts_count || 0}
                </td>
            `;
            resultsTable.appendChild(row);
        });

        // Add event listeners to new checkboxes
        document.querySelectorAll('.channel-checkbox').forEach(cb => {
            cb.addEventListener('change', updateAddButtonState);
        });
    }

    function updateAddButtonState() {
        const checkedCount = document.querySelectorAll('input[name="channel_select"]:checked').length;
        if (addSelectedBtn) {
            addSelectedBtn.disabled = checkedCount === 0;
            if (checkedCount > 0) {
                addSelectedBtn.innerHTML = `<span class="mr-1">➕</span> Добавить (${checkedCount})`;
            } else {
                addSelectedBtn.innerHTML = '<span class="mr-1">➕</span> Добавить выбранные в мониторинг';
            }
        }
    }

    // --- Event Listeners ---

    if (searchBtn) {
        searchBtn.addEventListener('click', startSearch);
        console.log('✅ Added event listener to searchBtn');
    }

    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            // Simple rotation animation for feedback
            const icon = refreshBtn.querySelector('svg');
            if (icon) {
                icon.classList.add('animate-spin');
                setTimeout(() => icon.classList.remove('animate-spin'), 1000);
            }

            loadResults();
        });
        console.log('✅ Added event listener to refreshBtn');
    }

    if (addSelectedBtn) {
        addSelectedBtn.addEventListener('click', addToMonitoring);
        console.log('✅ Added event listener to addSelectedBtn');
    }

    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            document.querySelectorAll('.channel-checkbox').forEach(cb => {
                cb.checked = isChecked;
            });
            updateAddButtonState();
        });
        console.log('✅ Added event listener to selectAllCheckbox');
    }

    // Initial Load
    loadResults();

    console.log('✅ Parser Page Init END (Modular)');
};

// Cleanup function
window.App.pages.parser.cleanup = function () {
    console.log('Cleanup Parser Page (Modular)');
    // Remove event listeners if needed, mostly redundant as DOM is replaced
};
