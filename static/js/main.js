/**
 * ChefMate-Agent — Main JS
 * Handles: navbar scroll effect, intersection observer animations,
 *          button ripple effects, ingredient chip clicks,
 *          navbar scroll shrink, and query-string prefill.
 */

(function () {
  'use strict';

  /* ── Navbar scroll effect ─────────────────────────────────── */
  function initNavbarScroll() {
    const navbar = document.getElementById('mainNavbar');
    if (!navbar) return;
    window.addEventListener('scroll', function () {
      navbar.classList.toggle('scrolled', window.scrollY > 20);
    }, { passive: true });
  }

  /* ── Intersection Observer for fade-in animations ─────────── */
  function initScrollAnimations() {
    const els = document.querySelectorAll('.fade-in-up, .fade-in-right');
    if (!els.length) return;

    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

    els.forEach(function (el) { observer.observe(el); });
  }

  /* ── Button ripple effect ─────────────────────────────────── */
  function initRipple() {
    document.addEventListener('click', function (e) {
      const btn = e.target.closest('.cm-btn-primary');
      if (!btn) return;

      const rect = btn.getBoundingClientRect();
      const ripple = document.createElement('span');
      const size = Math.max(rect.width, rect.height);
      ripple.className = 'cm-ripple';
      ripple.style.cssText = [
        'width:' + size + 'px',
        'height:' + size + 'px',
        'left:' + (e.clientX - rect.left - size / 2) + 'px',
        'top:' + (e.clientY - rect.top - size / 2) + 'px',
      ].join(';');

      btn.appendChild(ripple);
      ripple.addEventListener('animationend', function () { ripple.remove(); });
    });
  }

  /* ── Smooth scroll for anchor links ──────────────────────── */
  function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
      anchor.addEventListener('click', function (e) {
        const id = this.getAttribute('href').slice(1);
        const target = document.getElementById(id);
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    });
  }

  /* ── Auto-redirect "Ask ChefMate" links with ?q= param ───── */
  function initQueryPrefill() {
    const params = new URLSearchParams(window.location.search);
    const q = params.get('q');
    if (q) {
      // Store for chat.js to pick up
      sessionStorage.setItem('chefmate-prefill', decodeURIComponent(q));
    }
  }

  /* ── DOM ready ────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    initNavbarScroll();
    initScrollAnimations();
    initRipple();
    initSmoothScroll();
    initQueryPrefill();
  });
})();
