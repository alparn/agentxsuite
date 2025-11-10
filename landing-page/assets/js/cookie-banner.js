/**
 * Cookie Banner - AgentxSuite Landing Page
 * Small, user-friendly cookie consent banner
 */

(function() {
    'use strict';

    const COOKIE_NAME = 'cookie_consent';
    const COOKIE_EXPIRY_DAYS = 365;

    // Initialize cookie banner
    function initCookieBanner() {
        // Check if user has already made a choice
        if (getCookie(COOKIE_NAME)) {
            return; // Don't show banner if consent already given
        }

        // Wait for DOM and i18n to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', createBanner);
        } else {
            // If i18n is available, wait a bit for translations to load
            setTimeout(createBanner, 100);
        }
    }

    function createBanner() {
        // Create banner element
        const banner = document.createElement('div');
        banner.className = 'cookie-banner';
        banner.setAttribute('role', 'dialog');
        banner.setAttribute('aria-label', 'Cookie consent');
        banner.setAttribute('aria-live', 'polite');

        // Determine privacy page path based on current location
        const isDePage = window.location.pathname.includes('/de/');
        const privacyPath = isDePage ? '../legal/datenschutz.html' : 'legal/privacy.html';

        // Fallback translations
        const fallbackTranslations = {
            en: {
                message: "We use essential cookies to ensure the website functions properly. Your privacy is important to us.",
                accept: "Accept",
                decline: "Decline",
                learnMore: "Learn more"
            },
            de: {
                message: "Wir verwenden nur notwendige Cookies, um die Funktionalität der Website sicherzustellen. Ihr Datenschutz ist uns wichtig.",
                accept: "Akzeptieren",
                decline: "Ablehnen",
                learnMore: "Mehr erfahren"
            }
        };

        // Get current language
        const currentLang = document.body.getAttribute('data-lang') || (isDePage ? 'de' : 'en');
        const fallback = fallbackTranslations[currentLang] || fallbackTranslations.en;

        banner.innerHTML = `
            <div class="cookie-banner__content">
                <div class="cookie-banner__text">
                    <p class="cookie-banner__message" data-i18n="cookie.message">
                        ${fallback.message}
                    </p>
                </div>
                <div class="cookie-banner__actions">
                    <a href="${privacyPath}" class="cookie-banner__link" data-i18n="cookie.learnMore">
                        ${fallback.learnMore}
                    </a>
                    <button type="button" class="cookie-banner__btn cookie-banner__btn--decline" data-action="decline" data-i18n="cookie.decline">
                        ${fallback.decline}
                    </button>
                    <button type="button" class="cookie-banner__btn cookie-banner__btn--accept" data-action="accept" data-i18n="cookie.accept">
                        ${fallback.accept}
                    </button>
                </div>
            </div>
        `;

        // Add to page
        document.body.appendChild(banner);

        // Apply i18n if available (wait a bit for i18n to load)
        setTimeout(() => {
            if (window.applyI18n && typeof window.applyI18n === 'function') {
                window.applyI18n(banner);
            } else if (window.i18n && typeof window.i18n.applyTranslations === 'function') {
                window.i18n.applyTranslations();
            }
        }, 200);

        // Animate in
        setTimeout(() => {
            banner.classList.add('cookie-banner--visible');
        }, 100);

        // Handle button clicks
        banner.addEventListener('click', handleBannerClick);
    }

    function handleBannerClick(e) {
        const button = e.target.closest('[data-action]');
        if (!button) return;

        const action = button.getAttribute('data-action');
        
        if (action === 'accept') {
            setCookie(COOKIE_NAME, 'accepted', COOKIE_EXPIRY_DAYS);
        } else if (action === 'decline') {
            setCookie(COOKIE_NAME, 'declined', COOKIE_EXPIRY_DAYS);
        }

        // Hide banner with animation
        const banner = button.closest('.cookie-banner');
        banner.classList.remove('cookie-banner--visible');
        
        setTimeout(() => {
            banner.remove();
        }, 300);
    }

    // Cookie utility functions
    function setCookie(name, value, days) {
        const date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        const expires = `expires=${date.toUTCString()}`;
        document.cookie = `${name}=${value};${expires};path=/;SameSite=Lax`;
    }

    function getCookie(name) {
        const nameEQ = `${name}=`;
        const ca = document.cookie.split(';');
        for (let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    }

    // Initialize on load
    initCookieBanner();

    // Export for external use if needed
    window.cookieBanner = {
        setCookie,
        getCookie,
        init: initCookieBanner
    };
})();

