window.App = window.App || {};
window.App.core = window.App.core || {};
window.App.core.dom = window.App.core.dom || {};

// Core DOM Utilities
window.App.core.dom.getElement = function (id) {
    return document.getElementById(id);
};

window.App.core.dom.qs = function (selector, parent = document) {
    return parent.querySelector(selector);
};

window.App.core.dom.qsa = function (selector, parent = document) {
    return Array.from(parent.querySelectorAll(selector));
};

window.App.core.dom.safeSetText = function (id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
};

window.App.core.dom.safeSetValue = function (id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value;
};
