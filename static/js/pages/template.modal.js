// Template Modal Module
// Handles the create/edit template modal with tabbed interface

import { showToast } from '../app.core.esm.js';
import { mapTemplateToFormData, mapFormDataToTemplate } from './template.mapper.js';

let currentTemplateId = null;

// Open create template modal
export function openCreateTemplateModal() {
    currentTemplateId = null;
    document.getElementById('modal-title').textContent = 'Создать шаблон';
    document.getElementById('template-form').reset();
    document.getElementById('template-id').value = '';
    
    // Reset tabs
    switchToTab('profile-tab');
    
    showTemplateModal();
}

// Open edit template modal
export async function openEditTemplateModal(id) {
    try {
        console.log(`Loading template with ID: ${id}`);
        const response = await fetch('/api/templates/list');
        console.log('Templates list response:', response);

        if (!response.ok) {
            let errorMessage = 'Failed to load templates';
            try {
                const errorText = await response.text();
                console.log('Error response text:', errorText);
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
        console.log('Templates data:', data);
        const template = data.templates.find(t => t.id === id);

        if (!template) {
            throw new Error('Template not found');
        }

        // Fill form with template data
        currentTemplateId = template.id;
        document.getElementById('modal-title').textContent = 'Редактировать шаблон';
        document.getElementById('template-id').value = template.id;
        
        // Map template data to form fields
        const formData = mapTemplateToFormData(template);
        fillFormFields(formData);

        // Reset tabs
        switchToTab('profile-tab');
        
        showTemplateModal();
    } catch (error) {
        console.error('Error loading template:', error);
        showToast('Ошибка загрузки шаблона: ' + error.message, 'error');
    }
}

// Close template modal
export function closeTemplateModal() {
    hideTemplateModal();
}

// Show template modal
function showTemplateModal() {
    const modal = document.getElementById('templateModal');
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
}

// Hide template modal
function hideTemplateModal() {
    const modal = document.getElementById('templateModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

// Switch to a specific tab
export function switchToTab(tabId) {
    // Hide all tab panels
    document.querySelectorAll('[role="tabpanel"]').forEach(panel => {
        panel.classList.add('hidden');
    });
    
    // Remove active class from all tabs
    document.querySelectorAll('[role="tab"]').forEach(tab => {
        tab.setAttribute('aria-selected', 'false');
        tab.classList.remove('border-blue-500', 'text-blue-600');
        tab.classList.add('border-transparent', 'text-gray-500');
    });
    
    // Show the selected tab panel
    const panelId = tabId.replace('-tab', '-panel');
    const panel = document.getElementById(panelId);
    if (panel) {
        panel.classList.remove('hidden');
    }
    
    // Activate the selected tab
    const tab = document.getElementById(tabId);
    if (tab) {
        tab.setAttribute('aria-selected', 'true');
        tab.classList.remove('border-transparent', 'text-gray-500');
        tab.classList.add('border-blue-500', 'text-blue-600');
    }
}

// Fill form fields with data
function fillFormFields(data) {
    // Basic fields
    document.getElementById('template-name').value = data.name || '';
    
    // Profile fields
    document.getElementById('template-first-name').value = data.first_name || '';
    document.getElementById('template-last-name').value = data.last_name || '';
    document.getElementById('template-bio').value = data.bio || '';
    document.getElementById('template-avatar').value = data.avatar || '';
    document.getElementById('template-channel-title').value = data.channel_title || '';
    document.getElementById('template-channel-description').value = data.channel_description || '';
    document.getElementById('template-post-text-template').value = data.post_text_template || '';
    
    // Comment fields
    document.getElementById('template-commenting-prompt').value = data.commenting_prompt || '';
    document.getElementById('template-style').value = data.style || '';
    document.getElementById('template-tone').value = data.tone || '';
    document.getElementById('template-max-words').value = data.max_words || '';
    document.getElementById('template-min-post-length').value = data.min_post_length || '';
    document.getElementById('template-filter-mode').value = data.filter_mode || 'none';
    document.getElementById('template-filter-keywords').value = data.filter_keywords || '';
}

// Collect form data
function collectFormData() {
    return {
        name: document.getElementById('template-name').value.trim(),
        first_name: document.getElementById('template-first-name').value.trim() || null,
        last_name: document.getElementById('template-last-name').value.trim() || null,
        bio: document.getElementById('template-bio').value.trim() || null,
        avatar: document.getElementById('template-avatar').value.trim() || null,
        channel_title: document.getElementById('template-channel-title').value.trim() || null,
        channel_description: document.getElementById('template-channel-description').value.trim() || null,
        post_text_template: document.getElementById('template-post-text-template').value.trim() || null,
        commenting_prompt: document.getElementById('template-commenting-prompt').value.trim() || null,
        style: document.getElementById('template-style').value.trim() || null,
        tone: document.getElementById('template-tone').value.trim() || null,
        max_words: document.getElementById('template-max-words').value ? parseInt(document.getElementById('template-max-words').value) : null,
        min_post_length: document.getElementById('template-min-post-length').value ? parseInt(document.getElementById('template-min-post-length').value) : null,
        filter_mode: document.getElementById('template-filter-mode').value || 'none',
        filter_keywords: document.getElementById('template-filter-keywords').value.trim() || null
    };
}

// Handle form submission
export async function submitForm() {
    try {
        console.log('Form submission started');

        // Collect form data
        const formData = collectFormData();
        console.log('Form data collected:', formData);

        // Validate required fields
        if (!formData.name) {
            console.log('Validation failed: name is required');
            showToast('Название шаблона обязательно', 'warning');
            return;
        }

        // Validate comment fields if needed
        if (formData.filter_mode === 'keywords' && !formData.filter_keywords) {
            console.log('Validation failed: keywords required for keyword filter mode');
            showToast('Ключевые слова обязательны при фильтрации по ключам', 'warning');
            return;
        }

        // Map form data to template structure
        const templateData = mapFormDataToTemplate(formData);
        console.log('Mapped template data:', templateData);

        console.log('Current template ID:', currentTemplateId);

        let response;
        if (currentTemplateId) {
            // Update existing template
            console.log(`Making PATCH request to /api/templates/${currentTemplateId}`);
            response = await fetch(`/api/templates/${currentTemplateId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(templateData)
            });
        } else {
            // Create new template
            console.log('Making POST request to /api/templates/create');
            response = await fetch('/api/templates/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(templateData)
            });
        }

        console.log('Response received:', response);

        if (!response.ok) {
            console.log('Response not ok, status:', response.status);
            let errorMessage = 'Failed to save template';
            try {
                const errorText = await response.text();
                console.log('Error response text:', errorText);
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

        // Success
        console.log('Template saved successfully');
        closeTemplateModal();
        
        // Reload templates list
        if (window.loadTemplates) {
            await window.loadTemplates();
        }
        
        showToast(currentTemplateId ? 'Шаблон обновлен' : 'Шаблон создан', 'success');

    } catch (error) {
        console.error('Error saving template:', error);
        showToast(`Ошибка: ${error.message}`, 'error');
    }
}

// Store event listeners for cleanup
let profileTabListener, commentTabListener, submitListener, closeModalListener, cancelListener;

// Initialize modal event listeners
export function initTemplateModal() {
    // Tab switching
    profileTabListener = () => switchToTab('profile-tab');
    commentTabListener = () => switchToTab('comment-tab');
    document.getElementById('profile-tab')?.addEventListener('click', profileTabListener);
    document.getElementById('comment-tab')?.addEventListener('click', commentTabListener);
    
    // Form submission
    submitListener = submitForm;
    document.getElementById('submit-template-btn')?.addEventListener('click', submitListener);
    
    // Close modal
    closeModalListener = closeTemplateModal;
    cancelListener = closeTemplateModal;
    document.getElementById('close-modal-btn')?.addEventListener('click', closeModalListener);
    document.getElementById('cancel-template-btn')?.addEventListener('click', cancelListener);
}

// Cleanup modal event listeners
export function cleanupTemplateModal() {
    // Tab switching
    document.getElementById('profile-tab')?.removeEventListener('click', profileTabListener);
    document.getElementById('comment-tab')?.removeEventListener('click', commentTabListener);
    
    // Form submission
    document.getElementById('submit-template-btn')?.removeEventListener('click', submitListener);
    
    // Close modal
    document.getElementById('close-modal-btn')?.removeEventListener('click', closeModalListener);
    document.getElementById('cancel-template-btn')?.removeEventListener('click', cancelListener);
}
