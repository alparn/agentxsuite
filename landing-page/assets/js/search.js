/**
 * Search Functionality - AgentxSuite Landing Page
 * Client-side blog post search
 */

(function() {
    'use strict';

    let searchIndex = [];
    let searchInput = null;
    let searchResults = null;

    // ===== Build Search Index =====
    function buildSearchIndex() {
        const posts = document.querySelectorAll('[data-post-title]');
        
        searchIndex = Array.from(posts).map(post => {
            return {
                title: post.getAttribute('data-post-title'),
                description: post.getAttribute('data-post-description') || '',
                tags: (post.getAttribute('data-post-tags') || '').split(',').map(t => t.trim()),
                date: post.getAttribute('data-post-date') || '',
                url: post.getAttribute('data-post-url') || '',
                lang: post.getAttribute('data-post-lang') || 'en'
            };
        });
        
        return searchIndex;
    }

    // ===== Search Posts =====
    function searchPosts(query) {
        if (!query || query.length < 2) {
            return [];
        }
        
        const lowerQuery = query.toLowerCase();
        
        return searchIndex.filter(post => {
            // Search in title
            const titleMatch = post.title.toLowerCase().includes(lowerQuery);
            
            // Search in description
            const descriptionMatch = post.description.toLowerCase().includes(lowerQuery);
            
            // Search in tags
            const tagsMatch = post.tags.some(tag => 
                tag.toLowerCase().includes(lowerQuery)
            );
            
            return titleMatch || descriptionMatch || tagsMatch;
        });
    }

    // ===== Render Search Results =====
    function renderSearchResults(results) {
        if (!searchResults) return;
        
        if (results.length === 0) {
            searchResults.innerHTML = `
                <div class="search-results__empty">
                    <p data-i18n="search.noResults">No results found</p>
                </div>
            `;
            return;
        }
        
        const html = results.map(post => `
            <article class="search-result">
                <h3 class="search-result__title">
                    <a href="${post.url}">${highlightMatch(post.title, searchInput.value)}</a>
                </h3>
                <p class="search-result__description">${highlightMatch(post.description, searchInput.value)}</p>
                <div class="search-result__meta">
                    <span class="search-result__date">${formatDate(post.date)}</span>
                    ${post.tags.length > 0 ? `
                        <div class="search-result__tags">
                            ${post.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
            </article>
        `).join('');
        
        searchResults.innerHTML = html;
    }

    // ===== Highlight Matching Text =====
    function highlightMatch(text, query) {
        if (!query) return text;
        
        const regex = new RegExp(`(${escapeRegex(query)})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }

    // ===== Escape Regex Special Characters =====
    function escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // ===== Format Date =====
    function formatDate(dateString) {
        if (!dateString) return '';
        
        try {
            const date = new Date(dateString);
            const lang = document.documentElement.lang || 'en';
            return date.toLocaleDateString(lang, { 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
            });
        } catch (e) {
            return dateString;
        }
    }

    // ===== Handle Search Input =====
    function handleSearchInput(e) {
        const query = e.target.value.trim();
        
        // Show/hide results container
        if (query.length >= 2) {
            const results = searchPosts(query);
            renderSearchResults(results);
            searchResults.classList.add('is-visible');
        } else {
            searchResults.classList.remove('is-visible');
        }
    }

    // ===== Debounce Function =====
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // ===== Parse URL Search Query =====
    function parseURLSearchQuery() {
        const urlParams = new URLSearchParams(window.location.search);
        const query = urlParams.get('q');
        
        if (query && searchInput) {
            searchInput.value = query;
            handleSearchInput({ target: searchInput });
        }
    }

    // ===== Initialize Search =====
    function init() {
        searchInput = document.querySelector('.search-input');
        searchResults = document.querySelector('.search-results');
        
        // Only initialize if search elements exist
        if (!searchInput || !searchResults) {
            return;
        }
        
        // Build search index
        buildSearchIndex();
        
        // Add event listener with debounce
        const debouncedSearch = debounce(handleSearchInput, 300);
        searchInput.addEventListener('input', debouncedSearch);
        
        // Handle Enter key
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleSearchInput(e);
            }
        });
        
        // Close results when clicking outside
        document.addEventListener('click', (e) => {
            if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                searchResults.classList.remove('is-visible');
            }
        });
        
        // Parse URL query parameter
        parseURLSearchQuery();
    }

    // ===== Public API =====
    window.blogSearch = {
        init,
        search: searchPosts,
        buildIndex: buildSearchIndex
    };

    // ===== Auto-initialize =====
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();

