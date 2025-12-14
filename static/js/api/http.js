window.App = window.App || {};
window.App.api = window.App.api || {};

/**
 * Wrapper for fetch API
 * @param {string} method - HTTP method (GET, POST, etc.)
 * @param {string} url - Request URL
 * @param {object|null} body - Request body (optional)
 * @returns {Promise<Response>} Fetch response
 */
window.App.api.request = async function (method, url, body = null) {
    const options = {
        method: method,
        headers: { 'Content-Type': 'application/json' }
    };

    if (body) {
        options.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(url, options);
        return response;
    } catch (error) {
        console.error(`API Request failed (${method} ${url}):`, error);
        throw error;
    }
};
