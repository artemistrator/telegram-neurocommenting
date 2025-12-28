window.App = window.App || {};
window.App.pages = window.App.pages || {};
window.App.pages.channels = window.App.pages.channels || {};

// Avoid redeclaration error if script is loaded multiple times
if (typeof allTemplates === 'undefined') {
    var allTemplates = [];
} else {
    // If it exists (e.g. from previous load), reset or keep it.
    // Using 'var' allows redeclaration in global scope without error, 
    // or we can attach to window.App if we want to be cleaner.
    // User requested specifically stricter control.
    // Let's attach to window to be safe or use 'var'. 
    // User asked: "let allTemplates = []; // объявить ОДИН раз здесь" but that causes error if re-execution context.
    // We will use window.allTemplates or var.
    // The user's specific request was: 
    // "1) В начале файла: ... let allTemplates = []; // объявить ОДИН раз здесь"
    // BUT this fails if the file is imported twice. 
    // I will use `var` which is hoistable and redeclarable, OR better, attach to the page object.
    // Actually, sticking to USER REQUEST strictness: if the file is loaded via <script>, `let` at top level throws if re-run.
    // I will use `var` to allow re-execution or check for existence.
}

// Better approach to match user intent but avoid error:
var allTemplates = allTemplates || [];

// Format relative time for comments
function formatRelativeTime(isoDate) {
    if (!isoDate) return "Никогда";

    const date = new Date(isoDate);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "Только что";
    if (diffMins < 60) return `${diffMins} мин. назад`;
    if (diffHours < 24) return `${diffHours} ч. назад`;
    if (diffDays < 7) return `${diffDays} дн. назад`;

    // Format as date if older than 7 days
    return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
}

// Track selected channels for bulk actions - ensure only declared once
if (typeof selectedChannels === 'undefined') {
    var selectedChannels = new Set();
}

Object.assign(window.App.pages.channels, {
    async init() {
        console.log('✅ Channels Page Init START');

        // Setup event delegation for template changes
        const tbody = document.getElementById('channels-table-body');
        if (tbody) {
            tbody.addEventListener('change', (e) => {
                if (e.target && e.target.classList.contains('template-select')) {
                    const channelId = e.target.dataset.channelId;
                    const val = e.target.value;
                    const templateId = val ? Number(val) : null;
                    this.onTemplateChange(channelId, templateId, e.target);
                }
            });
        }

        // Add refresh button handler
        const refreshBtn = document.getElementById('refresh-channels-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadChannels();
            });
        }

        // Add event listeners for search and filter
        document.getElementById('channel-search')?.addEventListener('input', () => {
            this.applyFilters();
        });
        
        document.getElementById('template-filter')?.addEventListener('change', () => {
            this.applyFilters();
        });

        // Add event listener for select-all checkbox
        document.getElementById('select-all')?.addEventListener('change', (e) => {
            this.handleSelectAll(e.target.checked);
        });

        try {
            await this.loadTemplates();
        } catch (e) {
            console.error("Failed to load templates", e);
        }

        await this.loadChannels();
        console.log('✅ Channels Page Init END');
    },

    async loadTemplates() {
        try {
            const resp = await fetch('/api/channels/setup-templates');
            if (!resp.ok) {
                console.error('Failed to load templates', resp.status);
                return;
            }
            const data = await resp.json();
            allTemplates = data.templates || [];
            console.log(`[Channels] Loaded ${allTemplates.length} templates`);
            
            // Populate template filter dropdown
            this.populateTemplateFilter();
        } catch (err) {
            console.error('Error loading templates:', err);
        }
    },

    populateTemplateFilter() {
        const filterSelect = document.getElementById('template-filter');
        if (!filterSelect) return;

        // Clear existing options except the first one
        filterSelect.innerHTML = '<option value="">Все шаблоны</option>';
        
        allTemplates.forEach(t => {
            const option = document.createElement('option');
            option.value = t.id;
            option.textContent = t.name;
            filterSelect.appendChild(option);
        });
    },

    async loadChannels() {
        // Show loading state if spinner exists
        const spinner = document.getElementById('channels-loading');
        if (spinner) spinner.classList.remove('hidden');

        try {
            const resp = await fetch('/api/channels/list');
            if (!resp.ok) {
                const body = await resp.text();
                throw new Error(body || `HTTP ${resp.status}`);
            }
            const data = await resp.json();
            this.displayChannels(data.channels || []);
            // Use stats from backend if available, otherwise calculate from channels
            if (data.stats) {
                this.updateStatsFromBackend(data.stats);
            } else {
                this.updateStats(data.channels || []);
            }
        } catch (err) {
            console.error('Error loading channels:', err);
            if (typeof showToast === 'function') {
                showToast('Ошибка загрузки каналов: ' + err.message, 'error');
            }
        } finally {
            if (spinner) spinner.classList.add('hidden');
        }
    },

    // Format subscriber count (1.2K, 1.5M, "Нет данных")
    formatSubscribers(count) {
        if (!count || count === 0) {
            return '<span class="text-gray-400">Нет данных</span>';
        }
        
        if (count >= 1000000) {
            return `<span class="font-medium">${(count / 1000000).toFixed(1)}M</span>`;
        }
        
        if (count >= 1000) {
            return `<span class="font-medium">${(count / 1000).toFixed(1)}K</span>`;
        }
        
        return `<span class="font-medium">${count}</span>`;
    },

    updateStats(channels) {
        // Update stats cards
        const totalChannels = channels.length;
        const activeChannels = channels.filter(ch => ch.status === 'active').length;
        const totalComments = channels.reduce((sum, ch) => sum + (ch.comments_count || 0), 0);
        const commentsToday = channels.filter(ch => {
            // Check if last comment was today
            const lastComment = ch.last_comment_date;
            if (!lastComment) return false;
            const today = new Date();
            const commentDate = new Date(lastComment);
            return commentDate.toDateString() === today.toDateString();
        }).length;

        document.getElementById('total-channels').textContent = totalChannels;
        document.getElementById('active-channels').textContent = activeChannels;
        document.getElementById('total-comments').textContent = totalComments;
        document.getElementById('comments-today').textContent = commentsToday;
    },

    updateStatsFromBackend(stats) {
        // Update stats cards from backend data
        document.getElementById('total-channels').textContent = stats.total || 0;
        document.getElementById('active-channels').textContent = stats.active || 0;
        document.getElementById('total-comments').textContent = stats.total_comments || 0;
        document.getElementById('comments-today').textContent = stats.comments_today || 0;
    },

    applyFilters() {
        const searchTerm = document.getElementById('channel-search').value.toLowerCase();
        const templateFilter = document.getElementById('template-filter').value;
        
        const tbody = document.getElementById('channels-table-body');
        const rows = tbody.querySelectorAll('tr');
        
        rows.forEach(row => {
            const titleCell = row.querySelector('.channel-title');
            const name = titleCell ? titleCell.textContent.toLowerCase() : '';
            const url = titleCell ? titleCell.getAttribute('data-url').toLowerCase() : '';
            const templateSelect = row.querySelector('.template-select');
            const templateId = templateSelect ? templateSelect.value : '';
            
            const matchesSearch = name.includes(searchTerm) || url.includes(searchTerm);
            const matchesTemplate = !templateFilter || templateId === templateFilter;
            
            if (matchesSearch && matchesTemplate) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    },

    displayChannels(channels) {
        const tbody = document.getElementById('channels-table-body');
        const noData = document.getElementById('no-channels');

        if (!tbody) return;

        tbody.innerHTML = '';

        if (!channels.length) {
            if (noData) noData.classList.remove('hidden');
            return;
        } else {
            if (noData) noData.classList.add('hidden');
        }

        // Helper to generate options
        const generateOptions = (currentTemplateId) => {
            let html = '<option value="">Выбрать...</option>';
            allTemplates.forEach(t => {
                const isSelected = currentTemplateId === t.id;
                // Format: "Name (Phone)" if phone exists
                let label = t.name;
                if (t.account_phone) {
                    label += ` (${t.account_phone})`;
                }
                html += `<option value="${t.id}" ${isSelected ? 'selected' : ''}>${label}</option>`;
            });
            return html;
        };

        channels.forEach((ch) => {
            const title = ch.title || ch.url || 'Без названия';
            const subs = ch.subscribers_count || 0;

            const currentTemplateId = ch.template ? ch.template.id : null;
            const commentsCount = ch.comments_count || 0;
            const lastCommentFormatted = formatRelativeTime(ch.last_comment_date);

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-6 py-4 text-gray-500">
                    <input type="checkbox" class="channel-checkbox h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500" data-id="${ch.id}">
                </td>
                <td class="px-6 py-4 font-medium text-gray-900 break-all max-w-[200px]">
                    <a href="${ch.url || '#'}" target="_blank" class="text-blue-600 hover:underline channel-title" data-url="${ch.url}">
                        ${title}
                    </a>
                </td>
                <td class="px-6 py-4 text-gray-700">
                    ${this.formatSubscribers(subs)}
                </td>
                <td class="px-6 py-4">
                    <span class="px-2 py-1 rounded text-xs ${ch.status === 'active'
                    ? 'bg-green-100 text-green-800'
                    : 'bg-gray-100 text-gray-800'
                }">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="inline w-4 h-4 mr-1">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        ${ch.status || '—'}
                    </span>
                </td>
                <td class="px-6 py-4">
                     <select class="border rounded px-2 py-1 text-sm template-select w-full" data-channel-id="${ch.id}">
                        ${generateOptions(currentTemplateId)}
                     </select>
                </td>
                <td class="px-6 py-4 text-gray-700">
                    <span class="px-2 py-1 bg-purple-50 text-purple-700 rounded text-sm font-medium">
                        ${commentsCount}
                    </span>
                </td>
                <td class="px-6 py-4 text-gray-700">
                    <div class="flex items-center gap-1 text-sm">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-4 h-4">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span>${lastCommentFormatted}</span>
                    </div>
                </td>
                <td class="px-6 py-4 text-gray-500">
                    <span>${ch.date_created ? new Date(ch.date_created).toLocaleString('ru-RU', {
                        day: '2-digit',
                        month: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit'
                    }) : '—'}</span>
                </td>
                <td class="px-6 py-4 text-gray-500">
                    ${ch.source || 'manual'}
                </td>
                <td class="px-6 py-4">
                    <button class="icon-btn-danger p-1.5 rounded-md hover:bg-red-50 text-red-600" onclick="window.App.pages.channels.deleteChannel(${ch.id})">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                        </svg>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        // Save old values for optimistic rollback
        const selects = tbody.querySelectorAll('.template-select');
        selects.forEach(sel => {
            sel.dataset.oldValue = sel.value;
        });

        // Add event listeners for checkboxes
        this.addCheckboxEventListeners();
        
        console.log(`[Channels] Displayed ${channels.length} channels`);
    },

    addCheckboxEventListeners() {
        // Remove previous listeners to avoid duplicates
        document.removeEventListener('change', this.handleCheckboxChange);
        
        // Add event listener for checkboxes using event delegation
        document.addEventListener('change', this.handleCheckboxChange.bind(this));
    },

    handleCheckboxChange(e) {
        if (e.target.classList.contains('channel-checkbox')) {
            const channelId = parseInt(e.target.dataset.id);
            
            if (e.target.checked) {
                selectedChannels.add(channelId);
            } else {
                selectedChannels.delete(channelId);
            }
            
            this.updateBulkActionsBar();
            this.updateSelectAllCheckbox();
        }
    },

    handleSelectAll(checked) {
        const checkboxes = document.querySelectorAll('.channel-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = checked;
            const channelId = parseInt(checkbox.dataset.id);
            
            if (checked) {
                selectedChannels.add(channelId);
            } else {
                selectedChannels.delete(channelId);
            }
        });
        
        this.updateBulkActionsBar();
    },

    updateSelectAllCheckbox() {
        const checkboxes = document.querySelectorAll('.channel-checkbox');
        const selectAllCheckbox = document.getElementById('select-all');
        
        if (!selectAllCheckbox || checkboxes.length === 0) return;
        
        const checkedCount = document.querySelectorAll('.channel-checkbox:checked').length;
        selectAllCheckbox.checked = checkboxes.length > 0 && checkedCount === checkboxes.length;
    },

    updateBulkActionsBar() {
        const bar = document.getElementById('bulk-actions-bar');
        const count = document.getElementById('selected-count');
        
        count.textContent = selectedChannels.size;
        bar.style.display = selectedChannels.size > 0 ? 'flex' : 'none';
    },

    async deleteChannel(channelId) {
        if (!confirm('Удалить канал из мониторинга?')) {
            return;
        }

        try {
            const resp = await fetch(`/api/channels/${channelId}`, {
                method: 'DELETE',
            });

            if (!resp.ok) {
                const body = await resp.text();
                throw new Error(body || `HTTP ${resp.status}`);
            }

            if (typeof showToast === 'function') {
                showToast('Канал удален', 'success');
            }

            await this.loadChannels();
        } catch (err) {
            console.error('Error deleting channel:', err);
            if (typeof showToast === 'function') {
                showToast('Ошибка удаления канала: ' + err.message, 'error');
            }
        }
    },

    async deleteSelected() {
        if (selectedChannels.size === 0) return;
        
        const confirmed = confirm(`Удалить ${selectedChannels.size} каналов из мониторинга?`);
        if (!confirmed) return;
        
        try {
            const response = await fetch('/api/channels/bulk-delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ channel_ids: Array.from(selectedChannels) })
            });
            
            if (response.ok) {
                if (typeof showToast === 'function') {
                    showToast(`Удалено каналов: ${selectedChannels.size}`, 'success');
                }
                selectedChannels.clear();
                this.updateBulkActionsBar();
                this.updateSelectAllCheckbox();
                await this.loadChannels(); // Refresh the list
            } else {
                const errorText = await response.text();
                throw new Error(errorText);
            }
        } catch (error) {
            console.error('Error bulk deleting channels:', error);
            if (typeof showToast === 'function') {
                showToast('Ошибка при удалении каналов', 'error');
            }
        }
    },

    async onTemplateChange(channelId, templateId, selectEl) {
        // Optimistic UI handled by not disabling (or disabling appropriately)
        // Store current value as old value before request?
        // Actually, change event already fired. The select value IS the new value.
        // We stored the PREVIOUS value in dataset.oldValue during render (or previous change).
        const oldValue = selectEl.dataset.oldValue;

        try {
            selectEl.disabled = true;

            const resp = await fetch(`/api/channels/${channelId}/set-template`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ template_id: templateId }),
            });

            if (!resp.ok) {
                const body = await resp.text();
                throw new Error(body || `HTTP ${resp.status}`);
            }

            const updatedChannel = await resp.json();

            // Update successful
            if (typeof showToast === 'function') {
                const tmplName = updatedChannel.template ? updatedChannel.template.name : 'отвязан';
                showToast(`Шаблон ${updatedChannel.template ? 'обновлен' : 'отвязан'}`, 'success');
            }

            // Update old value to new value
            selectEl.dataset.oldValue = selectEl.value;

        } catch (err) {
            console.error('Failed to update channel template', err);
            // Revert
            if (oldValue !== undefined) {
                selectEl.value = oldValue;
            }
            if (typeof showToast === 'function') {
                showToast('Не удалось обновить шаблон: ' + err.message, 'error');
            }
        } finally {
            selectEl.disabled = false;
        }
    },

    cleanup() {
        console.log('Cleanup Channels Page');
        // Remove event listeners? The element replaces on page change usually, 
        // but explicit cleanup is good practice if spa uses same container.
        // However, `displayChannels` overwrites innerHTML, so element listeners are gone.
        // The `document.addEventListener` in the plan was replaced by `tbody.addEventListener` which is safer for SPA.
        // But `tbody` is inside the page content which gets replaced.
        // If `init` runs on every page view, we are good.
    },
});