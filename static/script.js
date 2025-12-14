window.App = window.App || {};
window.App.pages = window.App.pages || {};
window.App.core = window.App.core || {};
window.App.state = window.App.state || {}; // Initialize state
window.App.api = window.App.api || {};

// Shared state that might be accessed by other modules
// We'll keep these on App.state now but can leave globals for compat if needed, 
// though refactoring suggests moving away from globals. 
// For now, mapping globals to App.state for backward compat
Object.defineProperty(window, 'selectedChats', {
    get: () => window.App.state.selectedChats || [],
    set: (val) => window.App.state.selectedChats = val
});
Object.defineProperty(window, 'allChats', {
    get: () => window.App.state.allChats || [],
    set: (val) => window.App.state.allChats = val
});

let isTelegramConfigSaved = false;

// DOM Elements
const authorizeBtn = document.getElementById('authorize-btn');

// Show toast notification
// Show toast notification
function showToast(message, type = 'success') {
    if (window.App && window.App.core && window.App.core.toast && window.App.core.toast.showToast) {
        return window.App.core.toast.showToast(message, type);
    }
    console.warn('App.core.toast.showToast not found, toast skipped:', message);
}

// Auth UI helpers moved to static/js/features/telegramAuth.js

// Initialize event listeners once DOM is loaded
// Event listeners now handled by App.features.telegramAuth.init() in settings.page.js

// Start app initialization
init();


// renderChatsTable moved to channels.page.js


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

// Monitoring logic moved to static/js/features/monitoring.js

// Wrappers for backward compatibility
window.updateMonitoringStatus = function () {
    if (window.App && window.App.features && window.App.features.monitoring) {
        window.App.features.monitoring.refresh();
    }
};

window.connectSSE = function () {
    if (window.App && window.App.features && window.App.features.monitoring) {
        window.App.features.monitoring.connectSSE();
    }
};

// Initialize Parser Page logic
// Initialize Parser Page logic
function initParserPage() {
    if (window.App && window.App.pages && window.App.pages.parser && window.App.pages.parser.init) {
        return window.App.pages.parser.init();
    }
    console.error('App.pages.parser.init not found');
}

// Expose initParserPage globally for SPA router
window.initParserPage = initParserPage;

// Wrappers for Channels Page (moved to static/js/pages/channels.page.js)
window.initChannelsPage = function () {
    if (window.App && window.App.pages && window.App.pages.channels && window.App.pages.channels.init) {
        window.App.pages.channels.init();
    }
};

window.cleanupChannelsPage = function () {
    if (window.App && window.App.pages && window.App.pages.channels && window.App.pages.channels.cleanup) {
        window.App.pages.channels.cleanup();
    }
};

// Initialize app
async function init() {
    console.log('Current path:', window.location.pathname);

    // --- Routing Logic ---
    if (window.location.pathname === '/parser' || window.location.pathname.endsWith('/parser')) {
        console.log('✅ Calling initParserPage()');
        initParserPage();
        return; // Don't run other init logic on parser page
    }

    if (window.location.pathname === '/channels' || window.location.pathname.endsWith('/channels')) {
        console.log('✅ Calling initChannelsPage()');
        if (typeof initChannelsPage === 'function') {
            initChannelsPage();
        }
        return;
    }
    // --- Other Pages Init Logic ---
    // Only load config if we're on the settings page
    const isSettingsPage = window.location.pathname === '/settings' || window.location.pathname.endsWith('/settings');

    if (isSettingsPage) {
        console.log('✅ Calling App.pages.settings.init()');
        if (window.App && window.App.pages && window.App.pages.settings) {
            await window.App.pages.settings.init();
        }
    }

    // Only initialize monitoring and AI settings if relevant elements exist
    const hasMonitoringElements = document.getElementById('events-log') || document.getElementById('monitoring-status-text');
    const hasAIElements = document.getElementById('ai-enabled') || document.getElementById('openai-api-key');

    if (hasMonitoringElements || hasAIElements) {
        try {
            if (hasMonitoringElements) {
                if (window.App && window.App.features && window.App.features.monitoring) {
                    App.features.monitoring.init();
                    App.features.monitoring.startAuto();
                }
            }

            if (hasAIElements) {
                await loadAISettings(); // This function was inside the block I replaced above, I need to make sure I don't delete it or restore it
            }
        } catch (error) {
            console.error('Init error:', error);
        }
    }
}
