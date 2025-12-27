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
        } catch (err) {
            console.error('Error loading templates:', err);
        }
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
        } catch (err) {
            console.error('Error loading channels:', err);
            if (typeof showToast === 'function') {
                showToast('Ошибка загрузки каналов: ' + err.message, 'error');
            }
        } finally {
            if (spinner) spinner.classList.add('hidden');
        }
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

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-6 py-4 font-medium text-gray-900 break-all max-w-[200px]">
                    ${title}
                </td>
                <td class="px-6 py-4 text-gray-700">
                    ${subs.toLocaleString()}
                </td>
                <td class="px-6 py-4">
                    <span class="px-2 py-1 rounded text-xs ${ch.status === 'active'
                    ? 'bg-green-100 text-green-800'
                    : 'bg-gray-100 text-gray-800'
                }">
                        ${ch.status || '—'}
                    </span>
                </td>
                <td class="px-6 py-4">
                     <select class="border rounded px-2 py-1 text-sm template-select w-full" data-channel-id="${ch.id}">
                        ${generateOptions(currentTemplateId)}
                     </select>
                </td>
                <td class="px-6 py-4 text-gray-500">
                    ${ch.source || '—'}
                </td>
                <td class="px-6 py-4">
                    <a href="${ch.url || '#'}" target="_blank" class="text-blue-600 hover:underline">
                        Открыть
                    </a>
                </td>
            `;
            tbody.appendChild(tr);
        });

        // Save old values for optimistic rollback
        const selects = tbody.querySelectorAll('.template-select');
        selects.forEach(sel => {
            sel.dataset.oldValue = sel.value;
        });

        console.log(`[Channels] Displayed ${channels.length} channels`);
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