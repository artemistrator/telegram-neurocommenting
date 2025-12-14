// Template Mapper Module
// Handles mapping between template data structure and form data structure

/**
 * Maps a template object from the API to form data structure
 * Handles backward compatibility with existing templates
 * @param {Object} template - Template object from API
 * @returns {Object} Form data structure
 */
export function mapTemplateToFormData(template) {
    // Extract profile config (fallback to direct fields if profile_config doesn't exist)
    const profileConfig = template.profile_config || {};
    const firstName = profileConfig.first_name !== undefined ? profileConfig.first_name : template.first_name;
    const lastName = profileConfig.last_name !== undefined ? profileConfig.last_name : template.last_name;
    const bio = profileConfig.bio !== undefined ? profileConfig.bio : template.bio;
    const avatar = profileConfig.avatar !== undefined ? profileConfig.avatar : template.avatar;
    const channelTitle = profileConfig.channel_title !== undefined ? profileConfig.channel_title : template.channel_title;
    const channelDescription = profileConfig.channel_description !== undefined ? profileConfig.channel_description : template.channel_description;
    const postTextTemplate = profileConfig.post_text_template !== undefined ? profileConfig.post_text_template : template.post_text_template;
    
    // Extract comment config (fallback to direct fields if comment_config doesn't exist)
    const commentConfig = template.comment_config || {};
    const commentingPrompt = commentConfig.commenting_prompt !== undefined ? commentConfig.commenting_prompt : template.commenting_prompt;
    const style = commentConfig.style !== undefined ? commentConfig.style : template.style;
    const tone = commentConfig.tone !== undefined ? commentConfig.tone : template.tone;
    const maxWords = commentConfig.max_words !== undefined ? commentConfig.max_words : template.max_words;
    const filterMode = commentConfig.filter_mode !== undefined ? commentConfig.filter_mode : template.filter_mode;
    const filterKeywords = commentConfig.filter_keywords !== undefined ? commentConfig.filter_keywords : template.filter_keywords;
    const minPostLength = commentConfig.min_post_length !== undefined ? commentConfig.min_post_length : template.min_post_length;
    
    return {
        name: template.name,
        first_name: firstName,
        last_name: lastName,
        bio: bio,
        avatar: avatar,
        channel_title: channelTitle,
        channel_description: channelDescription,
        post_text_template: postTextTemplate,
        commenting_prompt: commentingPrompt,
        style: style,
        tone: tone,
        max_words: maxWords,
        filter_mode: filterMode,
        filter_keywords: filterKeywords,
        min_post_length: minPostLength
    };
}

/**
 * Maps form data to template structure for API submission
 * Creates both the new structured fields and maintains backward compatibility
 * @param {Object} formData - Form data structure
 * @returns {Object} Template data structure for API
 */
export function mapFormDataToTemplate(formData) {
    // Create profile config object
    const profileConfig = {
        first_name: formData.first_name,
        last_name: formData.last_name,
        bio: formData.bio,
        avatar: formData.avatar,
        channel_title: formData.channel_title,
        channel_description: formData.channel_description,
        post_text_template: formData.post_text_template
    };
    
    // Create comment config object
    const commentConfig = {
        commenting_prompt: formData.commenting_prompt,
        style: formData.style,
        tone: formData.tone,
        max_words: formData.max_words,
        filter_mode: formData.filter_mode,
        filter_keywords: formData.filter_keywords,
        min_post_length: formData.min_post_length
    };
    
    // Return template data with both new structured fields and old fields for backward compatibility
    return {
        name: formData.name,
        // Old fields for backward compatibility
        first_name: formData.first_name,
        last_name: formData.last_name,
        bio: formData.bio,
        avatar: formData.avatar,
        channel_title: formData.channel_title,
        channel_description: formData.channel_description,
        post_text_template: formData.post_text_template,
        commenting_prompt: formData.commenting_prompt,
        style: formData.style,
        tone: formData.tone,
        max_words: formData.max_words,
        filter_mode: formData.filter_mode,
        filter_keywords: formData.filter_keywords,
        min_post_length: formData.min_post_length,
        // New structured fields
        profile_config: profileConfig,
        comment_config: commentConfig
    };
}

/**
 * Validates form data before submission
 * @param {Object} formData - Form data to validate
 * @returns {Object} Validation result { isValid: boolean, errors: string[] }
 */
export function validateFormData(formData) {
    const errors = [];
    
    // Validate required fields
    if (!formData.name) {
        errors.push('Название шаблона обязательно');
    }
    
    // Validate comment fields if needed
    if (formData.filter_mode === 'keywords' && !formData.filter_keywords) {
        errors.push('Ключевые слова обязательны при фильтрации по ключам');
    }
    
    // Validate numeric fields
    if (formData.max_words !== null && (isNaN(formData.max_words) || formData.max_words < 0)) {
        errors.push('Максимальное количество слов должно быть положительным числом');
    }
    
    if (formData.min_post_length !== null && (isNaN(formData.min_post_length) || formData.min_post_length < 0)) {
        errors.push('Минимальная длина поста должна быть положительным числом');
    }
    
    return {
        isValid: errors.length === 0,
        errors: errors
    };
}