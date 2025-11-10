/**
 * Internationalization (i18n) - AgentxSuite Landing Page
 * Handles language switching and text translations
 */

(function() {
    'use strict';

    // Translation cache
    let translations = {};
    let currentLang = 'en';

    // ===== Language Detection =====
    function detectLanguage() {
        const bodyLang = document.body.getAttribute('data-lang');
        const pathLang = window.location.pathname.startsWith('/de/') ? 'de' : 'en';
        const storedLang = localStorage.getItem('preferred-language');
        
        return bodyLang || pathLang || storedLang || 'en';
    }

    // ===== Load Translations =====
    async function loadTranslations(lang) {
        try {
            // Support both absolute and relative paths
            const basePath = window.location.pathname.includes('/de/') ? '../' : './';
            const i18nPath = window.location.protocol === 'file:' 
                ? `${basePath}assets/i18n/${lang}.json`
                : `/assets/i18n/${lang}.json`;
            const response = await fetch(i18nPath);
            if (!response.ok) {
                throw new Error(`Failed to load translations for ${lang}`);
            }
            translations = await response.json();
            return translations;
        } catch (error) {
            console.error('Error loading translations:', error);
            // Fallback to English if loading fails
            if (lang !== 'en') {
                return loadTranslations('en');
            }
            return {};
        }
    }

    // ===== Apply Translations =====
    function applyTranslations() {
        const elements = document.querySelectorAll('[data-i18n]');
        
        elements.forEach(element => {
            const key = element.getAttribute('data-i18n');
            const translation = getNestedTranslation(translations, key);
            
            if (translation) {
                // Handle different element types
                if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                    element.placeholder = translation;
                } else if (element.hasAttribute('aria-label')) {
                    element.setAttribute('aria-label', translation);
                } else {
                    element.textContent = translation;
                }
            }
        });
    }

    // ===== Get Nested Translation =====
    function getNestedTranslation(obj, path) {
        return path.split('.').reduce((prev, curr) => {
            return prev ? prev[curr] : null;
        }, obj);
    }

    // ===== Update Language Switcher UI =====
    function updateLanguageSwitcherUI() {
        const currentLangElement = document.querySelector('.lang-switcher__current');
        if (currentLangElement) {
            currentLangElement.textContent = currentLang.toUpperCase();
        }
        
        // Update active state in menu
        const links = document.querySelectorAll('.lang-switcher__link');
        links.forEach(link => {
            const linkLang = link.getAttribute('data-lang');
            if (linkLang === currentLang) {
                link.classList.add('is-active');
            } else {
                link.classList.remove('is-active');
            }
        });
    }

    // ===== Change Language =====
    async function changeLanguage(newLang) {
        if (newLang === currentLang) return;
        
        currentLang = newLang;
        localStorage.setItem('preferred-language', newLang);
        
        // Load and apply new translations
        await loadTranslations(newLang);
        applyTranslations();
        updateLanguageSwitcherUI();
        
        // Update document language
        document.documentElement.lang = newLang;
        document.body.setAttribute('data-lang', newLang);
    }

    // ===== Initialize i18n =====
    async function init() {
        currentLang = detectLanguage();
        
        // Load translations for current language
        await loadTranslations(currentLang);
        
        // Apply translations
        applyTranslations();
        
        // Update UI
        updateLanguageSwitcherUI();
        
        // Set document language
        document.documentElement.lang = currentLang;
    }

    // ===== Public API =====
    window.i18n = {
        init,
        changeLanguage,
        getCurrentLanguage: () => currentLang,
        translate: (key) => getNestedTranslation(translations, key)
    };

    // ===== Auto-initialize =====
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();

