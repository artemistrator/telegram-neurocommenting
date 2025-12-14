// Core utility functions for the application

// Show toast notification with auto DOM creation
function showToast(message, type = 'success') {
    // Ensure toast container exists
    let toast = document.getElementById('toast');
    let toastMessage = document.getElementById('toast-message');
    
    if (!toast) {
        // Create toast container if it doesn't exist
        toast = document.createElement('div');
        toast.id = 'toast';
        toast.className = 'fixed bottom-5 right-5 bg-gray-800 text-white px-6 py-3 rounded-lg shadow-lg transform translate-y-20 opacity-0 transition-all duration-300 z-50';
        document.body.appendChild(toast);
    }
    
    if (!toastMessage) {
        // Create message element if it doesn't exist
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
}

// Safe utility to get element by ID with error handling
function $id(id) {
    const element = document.getElementById(id);
    if (!element) {
        console.warn(`Element with ID '${id}' not found`);
    }
    return element;
}

// Safe utility to set text content with null check
function safeSetText(element, text) {
    if (element) {
        element.textContent = text || '';
        return true;
    } else {
        console.warn('safeSetText: element is null or undefined');
        return false;
    }
}

// Safe utility to set input value with null check
function safeSetValue(element, value) {
    if (element) {
        element.value = value || '';
        return true;
    } else {
        console.warn('safeSetValue: element is null or undefined');
        return false;
    }
}

// Export utilities for global access
window.app = {
    showToast,
    $id,
    safeSetText,
    safeSetValue
};

// Also make showToast available globally for backward compatibility
window.showToast = showToast;