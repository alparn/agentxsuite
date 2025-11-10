/**
 * Main JavaScript - AgentxSuite Landing Page
 * Core functionality and initialization
 */

(function() {
    'use strict';

    // ===== Mobile Navigation =====
    function initMobileNav() {
        const toggle = document.querySelector('.header__mobile-toggle');
        const nav = document.querySelector('.nav');
        
        if (!toggle || !nav) return;
        
        toggle.addEventListener('click', function() {
            const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
            toggle.setAttribute('aria-expanded', !isExpanded);
            nav.classList.toggle('is-open');
            
            // Animate hamburger icon
            toggle.classList.toggle('is-active');
        });
        
        // Close mobile nav when clicking outside
        document.addEventListener('click', function(e) {
            if (!nav.contains(e.target) && !toggle.contains(e.target)) {
                nav.classList.remove('is-open');
                toggle.setAttribute('aria-expanded', 'false');
                toggle.classList.remove('is-active');
            }
        });
        
        // Close mobile nav when clicking on a link
        nav.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', function() {
                nav.classList.remove('is-open');
                toggle.setAttribute('aria-expanded', 'false');
                toggle.classList.remove('is-active');
            });
        });
    }

    // ===== Smooth Scroll =====
    function initSmoothScroll() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function(e) {
                const href = this.getAttribute('href');
                
                // Skip if it's just "#"
                if (href === '#') {
                    e.preventDefault();
                    return;
                }
                
                const target = document.querySelector(href);
                if (target) {
                    e.preventDefault();
                    const headerOffset = 80;
                    const elementPosition = target.getBoundingClientRect().top;
                    const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
                    
                    window.scrollTo({
                        top: offsetPosition,
                        behavior: 'smooth'
                    });
                }
            });
        });
    }

    // ===== Stats Counter Animation =====
    function initStatsCounter() {
        const stats = document.querySelectorAll('.stats__value');
        
        if (stats.length === 0) return;
        
        const animateCounter = (element) => {
            const target = parseInt(element.getAttribute('data-count'));
            const duration = 2000; // 2 seconds
            const start = 0;
            const increment = target / (duration / 16); // 60 FPS
            let current = start;
            
            const timer = setInterval(() => {
                current += increment;
                if (current >= target) {
                    element.textContent = target.toLocaleString();
                    clearInterval(timer);
                } else {
                    element.textContent = Math.floor(current).toLocaleString();
                }
            }, 16);
        };
        
        // Intersection Observer for triggering animation
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && entry.target.textContent === '0') {
                    animateCounter(entry.target);
                }
            });
        }, { threshold: 0.5 });
        
        stats.forEach(stat => observer.observe(stat));
    }

    // ===== Header Scroll Effect =====
    function initHeaderScroll() {
        const header = document.querySelector('.header');
        if (!header) return;
        
        let lastScrollTop = 0;
        
        window.addEventListener('scroll', () => {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            
            if (scrollTop > 100) {
                header.classList.add('is-scrolled');
            } else {
                header.classList.remove('is-scrolled');
            }
            
            lastScrollTop = scrollTop;
        });
    }

    // ===== Set Current Year in Footer =====
    function setCurrentYear() {
        const yearElement = document.getElementById('current-year');
        if (yearElement) {
            yearElement.textContent = new Date().getFullYear();
        }
    }

    // ===== Lazy Loading Images =====
    function initLazyLoading() {
        const images = document.querySelectorAll('img[loading="lazy"]');
        
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                            img.removeAttribute('data-src');
                        }
                        imageObserver.unobserve(img);
                    }
                });
            });
            
            images.forEach(img => imageObserver.observe(img));
        } else {
            // Fallback for browsers without IntersectionObserver
            images.forEach(img => {
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                }
            });
        }
    }

    // ===== Fade-in Animation on Scroll =====
    function initScrollAnimations() {
        const elements = document.querySelectorAll('.feature-card, .step, .content-block__text p');
        
        if (elements.length === 0) return;
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate-slide-up');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });
        
        elements.forEach(el => observer.observe(el));
    }

    // ===== Prefers Reduced Motion =====
    function respectReducedMotion() {
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
        
        if (prefersReducedMotion.matches) {
            document.body.style.scrollBehavior = 'auto';
            
            // Disable animations
            const style = document.createElement('style');
            style.innerHTML = `
                *, *::before, *::after {
                    animation-duration: 0.01ms !important;
                    animation-iteration-count: 1 !important;
                    transition-duration: 0.01ms !important;
                }
            `;
            document.head.appendChild(style);
        }
    }

    // ===== Initialize Language Switcher Behavior =====
    function initLanguageSwitcher() {
        const switcher = document.querySelector('.lang-switcher');
        if (!switcher) return;
        
        const toggle = switcher.querySelector('.lang-switcher__toggle');
        const menu = switcher.querySelector('.lang-switcher__menu');
        const links = switcher.querySelectorAll('.lang-switcher__link');
        
        if (!toggle || !menu) return;
        
        // Keyboard accessibility
        toggle.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                menu.style.opacity = menu.style.opacity === '1' ? '0' : '1';
                menu.style.visibility = menu.style.visibility === 'visible' ? 'hidden' : 'visible';
            }
        });
        
        // Handle language selection - use href attribute directly for navigation
        links.forEach(link => {
            link.addEventListener('click', (e) => {
                const href = link.getAttribute('href');
                const lang = link.getAttribute('data-lang');
                
                // Store language preference
                if (lang) {
                    localStorage.setItem('preferred-language', lang);
                }
                
                // Let the browser handle navigation naturally
                // The href attribute already contains the correct relative path
                // No need to preventDefault - let normal navigation happen
            });
        });
    }

    // ===== Error Handling for Missing Elements =====
    function handleMissingElements() {
        // Gracefully handle missing elements without breaking the page
        console.log('Landing page initialized successfully');
    }

    // ===== Performance Monitoring =====
    function logPerformanceMetrics() {
        if ('performance' in window && 'timing' in window.performance) {
            window.addEventListener('load', () => {
                setTimeout(() => {
                    const perfData = window.performance.timing;
                    const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;
                    const domContentLoadedTime = perfData.domContentLoadedEventEnd - perfData.navigationStart;
                    
                    console.log('Page Load Time:', pageLoadTime + 'ms');
                    console.log('DOM Content Loaded:', domContentLoadedTime + 'ms');
                    
                    // Log Web Vitals if available
                    if ('PerformanceObserver' in window) {
                        try {
                            const observer = new PerformanceObserver((list) => {
                                for (const entry of list.getEntries()) {
                                    console.log(`${entry.name}:`, entry.value);
                                }
                            });
                            
                            observer.observe({ entryTypes: ['largest-contentful-paint', 'first-input'] });
                        } catch (e) {
                            // PerformanceObserver not fully supported
                        }
                    }
                }, 0);
            });
        }
    }

    // ===== Main Initialization =====
    function init() {
        // Respect user's motion preferences first
        respectReducedMotion();
        
        // Initialize all features
        initMobileNav();
        initSmoothScroll();
        initStatsCounter();
        initHeaderScroll();
        setCurrentYear();
        initLazyLoading();
        initScrollAnimations();
        initLanguageSwitcher();
        handleMissingElements();
        
        // Performance monitoring (only in development)
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            logPerformanceMetrics();
        }
        
        // Add loaded class to body
        document.body.classList.add('is-loaded');
    }

    // ===== Run Initialization =====
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();

