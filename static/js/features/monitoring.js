window.App = window.App || {};
window.App.features = window.App.features || {};

window.App.features.monitoring = {
    eventSource: null,
    autoRefreshInterval: null,

    init: function () {
        console.log('✅ Monitoring Feature Init');

        // Start monitoring
        const startBtn = document.getElementById('start-monitoring-btn');
        if (startBtn) {
            startBtn.addEventListener('click', async () => {
                console.log('Start monitoring clicked');
                const showToast = window.App.core.toast ? window.App.core.toast.showToast : console.log;
                try {
                    const response = await fetch('/api/monitor/start', { method: 'POST' });
                    if (response.ok) {
                        showToast('Мониторинг запущен');
                        App.features.monitoring.refresh();
                        App.features.monitoring.startAuto();
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
                const showToast = window.App.core.toast ? window.App.core.toast.showToast : console.log;
                try {
                    const response = await fetch('/api/monitor/stop', { method: 'POST' });
                    if (response.ok) {
                        showToast('Мониторинг остановлен');
                        App.features.monitoring.refresh();
                        // We don't necessarily stop auto-refresh here, as we might want to see the status change to "Stopped"
                    } else {
                        const error = await response.json();
                        showToast(`Ошибка остановки: ${error.detail}`, 'error');
                    }
                } catch (error) {
                    showToast(`Ошибка сети: ${error.message}`, 'error');
                }
            });
        }
    },

    cleanup: function () {
        console.log('Cleanup Monitoring Feature');
        if (this.eventSource) {
            console.log('Closing SSE connection');
            this.eventSource.close();
            this.eventSource = null;
        }
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
    },

    startAuto: function () {
        // If already running, don't start another
        if (this.autoRefreshInterval) return;

        // Initial check
        this.refresh();
        this.connectSSE();

        // Use standard setInterval - it should be patched by timers.js to be tracked
        this.autoRefreshInterval = setInterval(() => {
            this.refresh();
        }, 5000);
    },

    stopAuto: function () {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    },

    refresh: async function () {
        // Guard: Check if monitoring elements exist
        const statusIndicator = document.getElementById('monitoring-status-indicator');
        const statusText = document.getElementById('monitoring-status-text');
        const eventsLog = document.getElementById('events-log');

        if (!statusIndicator && !statusText && !eventsLog) {
            return;
        }

        try {
            const response = await fetch('/api/monitor/status');
            if (response.ok) {
                const data = await response.json();

                if (statusIndicator) {
                    statusIndicator.className = data.active ? 'status-indicator status-active' : 'status-indicator status-inactive';
                }

                if (statusText) {
                    statusText.textContent = data.active ? 'Запущен' : 'Остановлен';
                }

                const chatsCount = document.getElementById('monitored-chats-count');
                if (chatsCount) chatsCount.textContent = data.chats_count || 0;

                // Populate event log from history
                if (data.events && Array.isArray(data.events)) {
                    if (eventsLog) {
                        // Reverse iterate or just add them. implementation in script.js was:
                        // data.events.forEach(event => renderEvent(event, eventsLog));
                        // renderEvent prepends, so order in array matters.
                        // Assuming data.events is [oldest, ..., newest], forEach prepending means newest ends up at top.
                        data.events.forEach(event => {
                            App.features.monitoring.renderEvent(event, eventsLog);
                        });
                    }
                }

                // Update stats if function exists globally (legacy) or we can move it too later
                if (typeof window.updateStats === 'function') {
                    window.updateStats();
                }
            }
        } catch (error) {
            console.error('Error updating monitoring status:', error);
        }
    },

    connectSSE: function () {
        if (this.eventSource) return; // Already connected

        const eventsLog = document.getElementById('events-log');
        if (!eventsLog) return;

        console.log('Connecting SSE...');
        this.eventSource = new EventSource('/api/monitor/logs');

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                App.features.monitoring.renderEvent(data, eventsLog);
            } catch (e) {
                console.error('Error parsing SSE event:', e);
            }
        };

        this.eventSource.onerror = (error) => {
            console.error('SSE error:', error);
            // Optional: close and retry logic, but for now simple logging
        };
    },

    getEventSignature: function (data) {
        return `${data.time || ''}-${data.chat_name || ''}-${data.text_preview ? data.text_preview.substring(0, 30) : ''}`.replace(/\s/g, '');
    },

    renderEvent: function (data, container) {
        if (!container) return;

        const signature = this.getEventSignature(data);

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

        container.insertBefore(eventElement, container.firstChild);

        while (container.children.length > 50) {
            container.removeChild(container.lastChild);
        }
    }
};
