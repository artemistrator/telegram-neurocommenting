window.onerror = function(msg, url, line) {
    console.error("Global JS Error: " + msg + "\nLine: " + line);
};
console.log("Dashboard JS loaded");

window.App = window.App || { pages: {} };

window.App.pages.dashboard = {
    // State
    charts: {
        activity: null,
        health: null
    },
    autoRefreshInterval: null,

    // Init
    async init() {
        try {
            console.log('Dashboard Page: Init');
            this.bindEvents();
            await this.loadAllData();
            // Removed auto-refresh functionality - only manual refresh allowed
        } catch (error) {
            console.error("Error in init: " + error.message);
        }
    },

    cleanup() {
        console.log('Dashboard Page: Cleanup');
        this.stopAutoRefresh();
        this.destroyCharts();
    },

    // Event Handlers
    bindEvents() {
        try {
            const refreshBtn = document.getElementById('refresh-btn');
            if (refreshBtn) {
                refreshBtn.onclick = () => this.loadAllData();
            }
        } catch (error) {
            console.error("Error binding events: " + error.message);
        }
    },

    // Data Loading
    async loadAllData() {
        try {
            await Promise.all([
                this.loadStats(),
                this.loadCharts(),
                this.loadRecent()
            ]);
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showToast('Ошибка загрузки данных', 'error');
        }
    },

    async loadStats() {
        try {
            const response = await fetch('/api/dashboard/stats');
            if (!response.ok) throw new Error('Failed to load stats: ' + response.status + ' ' + response.statusText);
            const data = await response.json();
            this.renderStats(data);
        } catch (error) {
            console.error("Error loading stats: " + error.message);
            throw error;
        }
    },

    async loadCharts() {
        try {
            const response = await fetch('/api/dashboard/charts?days=30');
            if (!response.ok) throw new Error('Failed to load charts: ' + response.status + ' ' + response.statusText);
            const data = await response.json();
            this.renderCharts(data);
        } catch (error) {
            console.error("Error loading charts: " + error.message);
            throw error;
        }
    },

    async loadRecent() {
        try {
            const response = await fetch('/api/dashboard/recent');
            if (!response.ok) throw new Error('Failed to load recent activity: ' + response.status + ' ' + response.statusText);
            const data = await response.json();
            this.renderRecentTables(data);
        } catch (error) {
            console.error("Error loading recent: " + error.message);
            throw error;
        }
    },

    // Rendering
    renderStats(data) {
        try {
            // Update DOM elements by ID
            const elements = {
                'stat-accounts-total': data.accounts.total,
                'stat-accounts-active': data.accounts.active,
                'stat-accounts-banned': data.accounts.banned,
                'stat-accounts-in-setup': data.accounts.in_setup,
                'stat-proxies-total': data.proxies.total,
                'stat-proxies-alive': data.proxies.alive,
                'stat-proxies-dead': data.proxies.dead,
                'stat-proxies-free': data.proxies.free,
                'stat-tasks-pending': data.queue_health.pending_tasks,
                'stat-tasks-failed': data.queue_health.failed_tasks,
                'stat-comments-pending': data.queue_health.pending_comments
            };

            for (const [id, value] of Object.entries(elements)) {
                const el = document.getElementById(id);
                if (el) {
                    el.textContent = value;
                } else {
                    console.warn("Missing DOM element: " + id);
                }
            }
        } catch (error) {
            console.error("Error rendering stats: " + error.message);
        }
    },

    renderCharts(data) {
        try {
            this.destroyCharts(); // Clear old charts

            // Activity Chart (Line)
            const activityCtx = document.getElementById('activity-chart');
            if (activityCtx) {
                // Ensure labels are proper strings and not complex objects
                const labels = data.daily_activity.comments.map(d => this.formatDate(d.date));
                const commentsData = data.daily_activity.comments.map(d => d.count);
                const subscriptionsData = data.daily_activity.subscriptions.map(d => d.count);
                const postsFoundData = data.daily_activity.posts_found.map(d => d.count);

                this.charts.activity = new Chart(activityCtx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: 'Comments',
                                data: commentsData,
                                borderColor: 'rgb(59, 130, 246)',
                                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                                tension: 0.4,
                                fill: true
                            },
                            {
                                label: 'Subscriptions',
                                data: subscriptionsData,
                                borderColor: 'rgb(16, 185, 129)',
                                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                tension: 0.4,
                                fill: true
                            },
                            {
                                label: 'Posts Found',
                                data: postsFoundData,
                                borderColor: 'rgb(245, 158, 11)',
                                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                                tension: 0.4,
                                fill: true
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false, // Чтобы не растягивался бесконечно
                        plugins: {
                            legend: { 
                                position: 'top',
                                labels: {
                                    boxWidth: 12,
                                    font: { size: 11 }
                                }
                            }
                        },
                        scales: {
                            y: { 
                                beginAtZero: true 
                            },
                            x: {
                                type: 'category', // Важно! Чтобы даты были просто подписями
                                ticks: { 
                                    autoSkip: true, 
                                    maxTicksLimit: 10 
                                }
                            }
                        }
                    }
                });
            }

            // Health Chart (Bar)
            const healthCtx = document.getElementById('health-chart');
            if (healthCtx) {
                // Ensure labels are proper strings and not complex objects
                const healthLabels = data.system_health.errors.map(d => this.formatDate(d.date));
                const healthData = data.system_health.errors.map(d => d.count);

                this.charts.health = new Chart(healthCtx, {
                    type: 'bar',
                    data: {
                        labels: healthLabels,
                        datasets: [{
                            label: 'Errors',
                            data: healthData,
                            backgroundColor: 'rgba(239, 68, 68, 0.5)',  // Red color as requested
                            borderColor: 'rgb(239, 68, 68)',  // Red color as requested
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            y: { 
                                beginAtZero: true,
                                ticks: {
                                    precision: 0
                                }
                            },
                            x: {
                                type: 'category', // Важно! Чтобы даты были просто подписями
                                ticks: { 
                                    autoSkip: true, 
                                    maxTicksLimit: 10 
                                }
                            }
                        }
                    }
                });
            }
        } catch (error) {
            console.error("Error rendering charts: " + error.message);
        }
    },

    renderRecentTables(data) {
        try {
            // Recent Comments
            const commentsContainer = document.getElementById('recent-comments');
            if (commentsContainer && data.recent_comments) {
                if (data.recent_comments.length === 0) {
                    commentsContainer.innerHTML = '<p class="text-gray-400 text-sm">No recent comments</p>';
                } else {
                    commentsContainer.innerHTML = data.recent_comments.map(c => `
                        <div class="border-b pb-2 last:border-b-0">
                            <div class="flex items-center justify-between">
                                <div class="flex-1 min-w-0">
                                    <p class="text-sm font-medium text-gray-900 truncate">${this.escapeHtml(c.account_phone || 'Unknown')}</p>
                                    <p class="text-xs text-gray-500 truncate">${this.escapeHtml(c.channel_title)}</p>
                                    <p class="text-sm text-gray-700 mt-1">${this.escapeHtml(c.text)}</p>
                                </div>
                                <div class="text-xs text-gray-500 whitespace-nowrap ml-2">
                                    ${this.formatDateTime(c.posted_at)}
                                </div>
                            </div>
                        </div>
                    `).join('');
                }
            }

            // Recent Errors
            const errorsContainer = document.getElementById('recent-errors');
            if (errorsContainer && data.recent_errors) {
                if (data.recent_errors.length === 0) {
                    errorsContainer.innerHTML = '<p class="text-gray-400 text-sm">No recent errors</p>';
                } else {
                    errorsContainer.innerHTML = data.recent_errors.map(e => `
                        <div class="border-b pb-2 last:border-b-0">
                            <div class="flex items-center justify-between">
                                <div class="flex-1 min-w-0">
                                    <div class="flex items-center">
                                        <span class="px-2 py-1 text-xs rounded-full ${
                                            e.level === 'error' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'
                                        }">${e.level}</span>
                                        <p class="text-xs text-gray-500 ml-2">${this.formatDateTime(e.created_at)}</p>
                                    </div>
                                    <p class="text-sm text-gray-700 mt-1">${this.escapeHtml(e.message)}</p>
                                </div>
                            </div>
                        </div>
                    `).join('');
                }
            }
        } catch (error) {
            console.error("Error rendering recent tables: " + error.message);
        }
    },

    // Utils
    formatDate(dateStr) {
        // YYYY-MM-DD → DD.MM
        const [year, month, day] = dateStr.split('-');
        return `${day}.${month}`;
    },

    formatDateTime(isoStr) {
        if (!isoStr) return 'N/A';
        try {
            const date = new Date(isoStr);
            return date.toLocaleString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return 'Invalid date';
        }
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    destroyCharts() {
        if (this.charts.activity) {
            this.charts.activity.destroy();
            this.charts.activity = null;
        }
        if (this.charts.health) {
            this.charts.health.destroy();
            this.charts.health = null;
        }
    },

    startAutoRefresh() {
        this.autoRefreshInterval = setInterval(() => {
            console.log('Dashboard: Auto-refresh triggered');
            this.loadAllData();
        }, 30000); // 30 seconds
    },

    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
    },

    showToast(message, type = 'info') {
        // Simple toast implementation
        console.log(`[${type.toUpperCase()}] ${message}`);
        
        // If window.App.core.toast exists, use it
        if (window.App.core && window.App.core.toast) {
            window.App.core.toast.show(message, type);
        }
    }
};

// Universal starter
function startDashboard() {
    console.log("Starting dashboard...");
    if (typeof window.App.pages.dashboard.init === 'function') {
        window.App.pages.dashboard.init();
    } else {
        console.error("Init function missing");
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startDashboard);
} else {
    // DOM уже готов — запускаем сразу!
    startDashboard();
}