/*
 * Shared behaviour for every page, no dependencies:
 *  - light / dark theme switch (remembered in localStorage)
 *  - full-screen menu on phones and tablets
 *  - header hides while scrolling down and comes back on scroll up
 *  - album tiles and images fade in as they load / scroll into view
 */
(function () {
  'use strict';

  var root = document.documentElement;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---- Theme ---- */
  var toggle = document.querySelector('.theme-toggle');
  var themeColor = document.querySelector('meta[name="theme-color"]');
  function applyTheme(theme) {
    root.setAttribute('data-theme', theme);
    if (themeColor) themeColor.setAttribute('content', theme === 'light' ? '#ffffff' : '#141415');
  }
  applyTheme(root.getAttribute('data-theme') || 'dark');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      applyTheme(next);
      try { localStorage.setItem('theme', next); } catch (e) { /* private mode */ }
    });
  }

  /* ---- Menu ---- */
  var header = document.querySelector('.site-header');
  var menuBtn = document.querySelector('.menu-toggle');
  var menuLabel = menuBtn && menuBtn.querySelector('.menu-label');
  function setMenu(open) {
    header.classList.toggle('menu-open', open);
    document.body.classList.toggle('menu-lock', open);
    menuBtn.setAttribute('aria-expanded', String(open));
    menuLabel.textContent = menuBtn.getAttribute(open ? 'data-close' : 'data-open');
  }
  if (menuBtn) {
    menuBtn.addEventListener('click', function () {
      setMenu(!header.classList.contains('menu-open'));
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && header.classList.contains('menu-open')) {
        setMenu(false);
        menuBtn.focus();
      }
    });
    window.matchMedia('(min-width: 1200px)').addEventListener('change', function (m) {
      if (m.matches) setMenu(false);
    });
  }

  /* ---- Header: hide on scroll down, show on scroll up ---- */
  var isHome = document.body.classList.contains('home');
  var hero = document.getElementById('hero');
  var lastY = window.scrollY;
  var ticking = false;
  function onScroll() {
    var y = window.scrollY;
    var menuOpen = header.classList.contains('menu-open');
    if (!menuOpen) {
      if (y > lastY + 4 && y > 120) header.classList.add('is-hidden');
      else if (y < lastY - 4 || y <= 120) header.classList.remove('is-hidden');
    }
    if (isHome && hero) header.classList.toggle('is-solid', y > hero.offsetHeight - header.offsetHeight);
    lastY = y;
    ticking = false;
  }
  window.addEventListener('scroll', function () {
    if (!ticking) { ticking = true; requestAnimationFrame(onScroll); }
  }, { passive: true });
  header.addEventListener('focusin', function () { header.classList.remove('is-hidden'); });
  onScroll();

  /* ---- Images: fade in once decoded ---- */
  document.querySelectorAll('.album img').forEach(function (img) {
    function done() { img.classList.add('is-loaded'); }
    if (img.complete && img.naturalWidth) done();
    else img.addEventListener('load', done, { once: true });
  });

  /* ---- Tiles slide up as they scroll into view ---- */
  var cards = document.querySelectorAll('.reveal');
  if (!('IntersectionObserver' in window) || reduce) {
    cards.forEach(function (c) { c.classList.add('in'); });
    return;
  }
  var observer = new IntersectionObserver(function (entries) {
    var n = 0;
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      // short, slightly uneven stagger: 0, 45, 80, 110, 135 ... ms
      var delay = Math.round(Math.sqrt(n) * 45);
      entry.target.style.setProperty('--delay', Math.min(delay, 260) + 'ms');
      entry.target.classList.add('in');
      // drop the delay afterwards so the press feedback is instant
      setTimeout(function (el) { el.style.removeProperty('--delay'); }, delay + 520, entry.target);
      observer.unobserve(entry.target);
      n++;
    });
  }, { rootMargin: '0px 0px -6% 0px', threshold: 0.08 });
  cards.forEach(function (c) { observer.observe(c); });
})();
