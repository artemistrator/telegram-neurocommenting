// Templates Page Module
// Handles initialization, rendering, and page-level interactions for the templates page

import { showToast } from '../app.core.esm.js';
import { openCreateTemplateModal, openEditTemplateModal, closeTemplateModal, cleanupTemplateModal } from './template.modal.js';

let currentTemplateId = null;

// Initialize templates page
export async function initTemplatesPage() {
    console.log('Initializing templates page');
    await loadTemplates();
    
    // Add event listeners
    document.getElementById('refresh-templates-btn')?.addEventListener('click', loadTemplates);
    document.getElementById('create-template-btn')?.addEventListener('click', openCreateTemplateModal);
    
    console.log('Templates page initialized');
}

// Make cleanup function available globally
window.cleanupTemplatesPage = cleanupTemplatesPage;

// Cleanup function when leaving the page
export function cleanupTemplatesPage() {
    console.log('Cleaning up templates page');
    // Remove event listeners to prevent duplicates on repeated visits
    const refreshBtn = document.getElementById('refresh-templates-btn');
    const createBtn = document.getElementById('create-template-btn');
    const createFirstBtn = document.getElementById('create-first-template-btn');
    
    if (refreshBtn) {
        refreshBtn.removeEventListener('click', loadTemplates);
    }
    
    if (createBtn) {
        createBtn.removeEventListener('click', openCreateTemplateModal);
    }
    
    if (createFirstBtn) {
        createFirstBtn.removeEventListener('click', openCreateTemplateModal);
    }
    
    // Cleanup modal event listeners
    cleanupTemplateModal();
}

// Load templates from API
export async function loadTemplates() {
    console.log('Loading templates from API');
    try {
        showLoadingIndicator(true);
        
        const response = await fetch('/api/templates/list?_t=' + new Date().getTime());
        
        if (!response.ok) {
            let errorMessage = 'Failed to load templates';
            try {
                const errorText = await response.text();
                try {
                    const errorData = JSON.parse(errorText);
                    errorMessage = errorData.detail || errorText || errorMessage;
                } catch (parseError) {
                    errorMessage = errorText || errorMessage;
                }
            } catch (textError) {
                console.log('Could not read error response:', textError);
            }
            throw new Error(errorMessage);
        }

        const data = await response.json();
        console.log('Templates data received:', data);
        renderTemplates(data.templates);
    } catch (error) {
        console.error('Error loading templates:', error);
        showToast('Ошибка загрузки шаблонов: ' + error.message, 'error');
    } finally {
        showLoadingIndicator(false);
    }
}

// Render templates in the grid
function renderTemplates(templates) {
    const container = document.getElementById('templates-container');
    
    if (!container) {
        console.error('Templates container not found');
        return;
    }

    if (templates.length === 0) {
        container.innerHTML = `
            <div class="col-span-full text-center py-12">
                <p class="text-gray-500">Нет созданных шаблонов</p>
                <button id="create-first-template-btn" 
                    class="mt-4 bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg font-medium transition">
                    Создать первый шаблон
                </button>
            </div>
        `;
        
        // Add event listener to the create button
        document.getElementById('create-first-template-btn')?.addEventListener('click', openCreateTemplateModal);
        return;
    }

    container.innerHTML = templates.map(template => `
        <div class="bg-white rounded-lg shadow-md overflow-hidden border border-gray-200 hover:shadow-lg transition">
            <div class="p-5">
                <div class="flex justify-between items-start">
                    <h3 class="text-lg font-bold text-gray-800">${escapeHtml(template.name)}</h3>
                    <div class="flex gap-2">
                        <button onclick="window.editTemplate(${template.id})" 
                            class="text-blue-500 hover:text-blue-700">
                            ✏️
                        </button>
                        <button onclick="window.deleteTemplate(${template.id})" 
                            class="text-red-500 hover:text-red-700">
                            🗑️
                        </button>
                    </div>
                </div>
                
                <!-- Profile Summary -->
                ${getProfileSummary(template)}
                
                <!-- Comment Policy Summary -->
                ${getCommentPolicySummary(template)}
            </div>
        </div>
    `).join('');
    
    // Make editTemplate and deleteTemplate globally available
    window.editTemplate = openEditTemplateModal;
    window.deleteTemplate = deleteTemplate;
}

// Get profile summary for template card
function getProfileSummary(template) {
    // Extract profile data from either profile_config or fallback to direct fields
    const profileData = template.profile_config || {};
    const firstName = profileData.first_name || template.first_name || '';
    const lastName = profileData.last_name || template.last_name || '';
    const bio = profileData.bio || template.bio || '';
    
    const fullName = `${firstName} ${lastName}`.trim();
    
    return `
        <div class="mt-3">
            ${fullName ? `<p class="text-sm text-gray-600">${escapeHtml(fullName)}</p>` : ''}
            ${bio ? `<p class="text-sm text-gray-600 line-clamp-2 mt-1">${escapeHtml(bio)}</p>` : ''}
        </div>
    `;
}

// Get comment policy summary for template card
function getCommentPolicySummary(template) {
    // Extract comment data from either comment_config or fallback to direct fields
    const commentData = template.comment_config || {};
    const filterMode = commentData.filter_mode || template.filter_mode || 'none';
    const filterKeywords = commentData.filter_keywords || template.filter_keywords || '';
    
    let filterText = '';
    switch(filterMode) {
        case 'keywords':
            filterText = 'По ключам';
            break;
        case 'none':
        default:
            filterText = 'Без фильтра';
            break;
    }
    
    // Get first few keywords for display
    let keywordsPreview = '';
    if (filterKeywords) {
        const keywords = filterKeywords.split(',').map(k => k.trim()).filter(k => k);
        keywordsPreview = keywords.slice(0, 2).join(', ');
        if (keywords.length > 2) {
            keywordsPreview += '...';
        }
    }
    
    return `
        <div class="mt-3 flex items-center gap-1">
            <span class="text-xs bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full border border-purple-200">
                ${filterText}${keywordsPreview ? `: ${keywordsPreview}` : ''}
            </span>
        </div>
    `;
}

// Delete template
async function deleteTemplate(id) {
    if (!confirm('Вы уверены, что хотите удалить этот шаблон?')) {
        return;
    }

    try {
        console.log(`Making DELETE request to /api/templates/${id}`);
        const response = await fetch(`/api/templates/${id}`, {
            method: 'DELETE'
        });

        console.log('Delete response received:', response);

        if (!response.ok) {
            console.log('Delete response not ok, status:', response.status);
            let errorMessage = 'Failed to delete template';
            try {
                const errorText = await response.text();
                console.log('Delete error response text:', errorText);
                try {
                    const errorData = JSON.parse(errorText);
                    errorMessage = errorData.detail || errorText || errorMessage;
                } catch (parseError) {
                    errorMessage = errorText || errorMessage;
                }
            } catch (textError) {
                console.log('Could not read delete error response:', textError);
            }
            throw new Error(errorMessage);
        }

        // Success
        console.log('Template deleted successfully');
        await loadTemplates();
        showToast('Шаблон удален', 'success');

    } catch (error) {
        console.error('Error deleting template:', error);
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

// Show/hide loading indicator
function showLoadingIndicator(show) {
    const refreshBtn = document.getElementById('refresh-templates-btn');
    if (refreshBtn) {
        const icon = refreshBtn.querySelector('svg');
        if (icon) {
            if (show) {
                icon.classList.add('animate-spin');
            } else {
                icon.classList.remove('animate-spin');
            }
        }
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.toString().replace(/[&<>"']/g, m => map[m]);
}

// Global init function for compatibility with layout.html
window.init = function() {
    // This function is called by layout.html, but we handle initialization in the module script
    console.log('Global init called for templates page');
};

// Global cleanup function for compatibility with layout.html
window.cleanup = function() {
    // This function is called by layout.html for cleanup
    console.log('Global cleanup called for templates page');
    if (typeof window.cleanupTemplatesPage === 'function') {
        window.cleanupTemplatesPage();
    }
};
