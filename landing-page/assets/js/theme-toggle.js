/**
 * Theme Toggle - AgentxSuite Landing Page
 * Handles dark/light theme switching
 */

(function() {
    'use strict';

    const THEME_KEY = 'agentxsuite-theme';
    const DARK_THEME = 'dark';
    const LIGHT_THEME = 'light';

    // ===== Get Preferred Theme =====
    function getPreferredTheme() {
        // Check localStorage first
        const storedTheme = localStorage.getItem(THEME_KEY);
        if (storedTheme) {
            return storedTheme;
        }
        
        // Check system preference
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return DARK_THEME;
        }
        
        // Default to dark (as per requirements)
        return DARK_THEME;
    }

    // ===== Apply Theme =====
    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        document.body.setAttribute('data-theme', theme);
        localStorage.setItem(THEME_KEY, theme);
        
        // Update meta theme-color
        updateMetaThemeColor(theme);
    }

    // ===== Update Meta Theme Color =====
    function updateMetaThemeColor(theme) {
        const metaThemeColor = document.querySelector('meta[name="theme-color"]');
        if (metaThemeColor) {
            metaThemeColor.setAttribute('content', theme === DARK_THEME ? '#1a1a2e' : '#ffffff');
        }
    }

    // ===== Toggle Theme =====
    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === DARK_THEME ? LIGHT_THEME : DARK_THEME;
        applyTheme(newTheme);
        
        // Dispatch custom event
        window.dispatchEvent(new CustomEvent('themechange', { 
            detail: { theme: newTheme } 
        }));
    }

    // ===== Initialize Theme Toggle Button =====
    function initToggleButton() {
        const toggleButton = document.querySelector('.theme-toggle');
        if (!toggleButton) return;
        
        toggleButton.addEventListener('click', toggleTheme);
        
        // Keyboard support
        toggleButton.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleTheme();
            }
        });
    }

    // ===== Watch System Theme Changes =====
    function watchSystemTheme() {
        if (!window.matchMedia) return;
        
        const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)');
        
        darkModeQuery.addEventListener('change', (e) => {
            // Only apply system preference if user hasn't set a preference
            if (!localStorage.getItem(THEME_KEY)) {
                applyTheme(e.matches ? DARK_THEME : LIGHT_THEME);
            }
        });
    }

    // ===== Initialize Theme =====
    function init() {
        // Apply theme before page renders (prevent flash)
        const preferredTheme = getPreferredTheme();
        applyTheme(preferredTheme);
        
        // Initialize toggle button
        initToggleButton();
        
        // Watch for system theme changes
        watchSystemTheme();
    }

    // ===== Early Initialization (before DOMContentLoaded) =====
    // This prevents flash of wrong theme
    const preferredTheme = getPreferredTheme();
    applyTheme(preferredTheme);

    // ===== Public API =====
    window.themeToggle = {
        init,
        toggle: toggleTheme,
        setTheme: applyTheme,
        getTheme: () => document.documentElement.getAttribute('data-theme')
    };

    // ===== Full Initialization =====
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();

