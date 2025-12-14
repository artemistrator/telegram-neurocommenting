window.App = window.App || {};
window.App.core = window.App.core || {};
window.App.core.toast = window.App.core.toast || {};

/**
 * Show a toast notification
 * @param {string} message - Message to display
 * @param {string} type - 'success' or 'error'
 */
window.App.core.toast.showToast = function (message, type = 'success') {
    // Find or create toast container
    let toast = document.getElementById('toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast';
        toast.className = 'fixed bottom-5 right-5 bg-gray-800 text-white px-6 py-3 rounded-lg shadow-lg transform translate-y-20 opacity-0 transition-all duration-300 z-50';
        document.body.appendChild(toast);
    }

    // Find or create toast message element
    let toastMessage = document.getElementById('toast-message');
    if (!toastMessage) {
        toastMessage = document.createElement('span');
        toastMessage.id = 'toast-message';
        toast.appendChild(toastMessage);
    }

    // Set message and type
    toastMessage.textContent = message;
    toastMessage.className = `px-4 py-2 rounded shadow-lg text-white ${type === 'success' ? 'bg-green-500' : 'bg-red-500'}`;

    // Show toast
    toast.classList.remove('hidden', 'translate-y-20', 'opacity-0');
    toast.classList.add('flex');

    // Hide toast after 3 seconds
    setTimeout(() => {
        toast.classList.add('translate-y-20', 'opacity-0');
        setTimeout(() => {
            toast.classList.add('hidden');
            toast.classList.remove('flex');
        }, 300);
    }, 3000);
};
