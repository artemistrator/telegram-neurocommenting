// ES Module adapter for app.core.js
// This file provides ES module exports that proxy to the global window.app functions

/**
 * Show toast notification with auto DOM creation
 * @param {string} message - Message to display
 * @param {string} type - Type of toast (success, error, warning)
 */
export function showToast(message, type = 'success') {
    if (window.app && typeof window.app.showToast === 'function') {
        return window.app.showToast(message, type);
    } else {
        // Fallback implementation if window.app is not available
        console.warn('window.app.showToast not available, using fallback implementation');
        // Simple fallback implementation
        console.log(`[TOAST] ${type.toUpperCase()}: ${message}`);
    }
}

/**
 * Safe utility to get element by ID with error handling
 * @param {string} id - Element ID to find
 * @returns {Element|null} - Found element or null
 */
export function $id(id) {
    if (window.app && typeof window.app.$id === 'function') {
        return window.app.$id(id);
    } else {
        // Fallback implementation
        console.warn('window.app.$id not available, using fallback implementation');
        const element = document.getElementById(id);
        if (!element) {
            console.warn(`Element with ID '${id}' not found`);
        }
        return element;
    }
}

/**
 * Safe utility to set text content with null check
 * @param {Element} element - Element to set text content on
 * @param {string} text - Text to set
 * @returns {boolean} - True if successful, false if element is null
 */
export function safeSetText(element, text) {
    if (window.app && typeof window.app.safeSetText === 'function') {
        return window.app.safeSetText(element, text);
    } else {
        // Fallback implementation
        console.warn('window.app.safeSetText not available, using fallback implementation');
        if (element) {
            element.textContent = text || '';
            return true;
        } else {
            console.warn('safeSetText: element is null or undefined');
            return false;
        }
    }
}

/**
 * Safe utility to set input value with null check
 * @param {Element} element - Element to set value on
 * @param {string} value - Value to set
 * @returns {boolean} - True if successful, false if element is null
 */
export function safeSetValue(element, value) {
    if (window.app && typeof window.app.safeSetValue === 'function') {
        return window.app.safeSetValue(element, value);
    } else {
        // Fallback implementation
        console.warn('window.app.safeSetValue not available, using fallback implementation');
        if (element) {
            element.value = value || '';
            return true;
        } else {
            console.warn('safeSetValue: element is null or undefined');
            return false;
        }
    }
}