/**
 * ChefMate-Agent — Theme Manager
 * Handles dark / light mode toggle, persists preference in localStorage.
 */

(function () {
  'use strict';

  const STORAGE_KEY = 'chefmate-theme';

  /** Apply a theme to the document */
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
    updateIcons(theme);
  }

  /** Keep all theme-toggle icons in sync */
  function updateIcons(theme) {
    const isDark = theme === 'dark';

    // Navbar toggle
    const navIcon = document.getElementById('themeIcon');
    if (navIcon) {
      navIcon.className = isDark ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
    }

    // Chat topbar toggle
    const chatIcon = document.getElementById('chatThemeIcon');
    if (chatIcon) {
      chatIcon.className = isDark ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
    }

    // Sidebar toggle switch
    const sidebarSwitch = document.getElementById('sidebarThemeToggle');
    if (sidebarSwitch) {
      sidebarSwitch.classList.toggle('active', isDark);
    }
  }

  /** Toggle between dark and light */
  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    applyTheme(current === 'dark' ? 'light' : 'dark');
  }

  /** Bootstrap: detect saved preference or system preference */
  function initTheme() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      applyTheme(saved);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      applyTheme('dark');
    } else {
      applyTheme('light');
    }
  }

  // Run immediately so there's no flash of wrong theme
  initTheme();

  // Wire up buttons once the DOM is ready
  document.addEventListener('DOMContentLoaded', function () {
    // Navbar toggle
    const navBtn = document.getElementById('themeToggle');
    if (navBtn) navBtn.addEventListener('click', toggleTheme);

    // Chat topbar toggle
    const chatBtn = document.getElementById('chatThemeToggle');
    if (chatBtn) chatBtn.addEventListener('click', toggleTheme);

    // Sidebar toggle switch
    const sidebarSwitch = document.getElementById('sidebarThemeToggle');
    if (sidebarSwitch) sidebarSwitch.addEventListener('click', toggleTheme);

    // Settings nutritionToggle (independent toggle, not theme)
    const nutritionToggle = document.getElementById('nutritionToggle');
    if (nutritionToggle) {
      nutritionToggle.addEventListener('click', function () {
        nutritionToggle.classList.toggle('active');
      });
    }
  });

  // Expose globally for use in other scripts
  window.ChefMateTheme = { toggle: toggleTheme, apply: applyTheme };
})();
