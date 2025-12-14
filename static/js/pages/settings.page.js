window.App = window.App || {};
window.App.pages = window.App.pages || {};

window.App.pages.settings = {
    init: async function () {
        console.log('✅ Settings Page Init');

        // Initialize features
        if (window.App.features && window.App.features.telegramAuth) {
            const auth = window.App.features.telegramAuth;

            // 1. Init event listeners
            auth.init();

            // 2. Load Config
            await auth.loadCurrentConfig();

            // 3. Check Auth Status
            await auth.refreshAuthStatus();
        }

        // Initialize monitoring settings if present (using monitoring.js logic via global init if already handled, 
        // but here we just ensure page specific logic is done)

        // AI Settings are also on this page, strictly they should be moved to a feature too multiple replacements ago, 
        // but for now they remain in script.js or we rely on the specific 'loadAISettings' function which we kept global.
        if (typeof window.loadAISettings === 'function') {
            await window.loadAISettings();
        }
    },

    cleanup: function () {
        console.log('Cleanup Settings Page');
        // Any modal closing or heavy cleanup specific to settings
    }
};
