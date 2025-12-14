/**
 * Universal Timer Management with Global Override
 */
window.App = window.App || {};
window.App.core = window.App.core || {};
window.App.state = window.App.state || {};
window.App.state.timers = window.App.state.timers || {
    intervals: new Set(),
    timeouts: new Set()
};

window.App.core.timers = {
    _setInterval: window.setInterval.bind(window),
    _setTimeout: window.setTimeout.bind(window),
    patched: false,

    trackInterval: function (id) {
        window.App.state.timers.intervals.add(id);
        return id;
    },

    trackTimeout: function (id) {
        window.App.state.timers.timeouts.add(id);
        return id;
    },

    clearAll: function () {
        console.log(`[Timers] Clearing ${window.App.state.timers.intervals.size} intervals, ${window.App.state.timers.timeouts.size} timeouts`);

        for (const id of window.App.state.timers.intervals) {
            clearInterval(id);
        }
        window.App.state.timers.intervals.clear();

        for (const id of window.App.state.timers.timeouts) {
            clearTimeout(id);
        }
        window.App.state.timers.timeouts.clear();
    },

    patchTimers: function () {
        if (this.patched) return;

        const self = this;

        window.setInterval = function (fn, ms, ...args) {
            const id = self._setInterval(fn, ms, ...args);
            self.trackInterval(id);
            return id;
        };

        window.setTimeout = function (fn, ms, ...args) {
            const id = self._setTimeout(fn, ms, ...args);
            self.trackTimeout(id);
            return id;
        };

        this.patched = true;
        console.log('[Timers] Global timers patched for tracking');
    }
};

// Auto-patch on load
window.App.core.timers.patchTimers();
