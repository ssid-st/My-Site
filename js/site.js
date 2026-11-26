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

  var finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  /* ---- Smoothly follow the mouse (springy lerp, decorative only) ---- */
  function follower(el, ease) {
    var x = 0, y = 0, tx = 0, ty = 0, running = false;
    function frame() {
      x += (tx - x) * ease;
      y += (ty - y) * ease;
      el.style.translate = x.toFixed(1) + 'px ' + y.toFixed(1) + 'px';
      if (Math.abs(tx - x) > 0.3 || Math.abs(ty - y) > 0.3) requestAnimationFrame(frame);
      else running = false;
    }
    return {
      to: function (nx, ny, jump) {
        tx = nx; ty = ny;
        if (jump || reduce) { x = nx; y = ny; }
        if (!running) { running = true; requestAnimationFrame(frame); }
      }
    };
  }

  /* ---- "View" cursor over photos (mouse only) ---- */
  if (finePointer && !reduce) {
    var cursor = document.createElement('div');
    cursor.className = 'cursor';
    cursor.setAttribute('aria-hidden', 'true');
    cursor.textContent = document.body.getAttribute('data-view') || 'View';
    document.body.appendChild(cursor);
    var cf = follower(cursor, 0.22);
    var cursorOn = false;
    document.addEventListener('pointermove', function (e) {
      var over = e.pointerType === 'mouse' && e.target.closest && e.target.closest('.album, .work');
      if (over && !cursorOn) cf.to(e.clientX, e.clientY, true);
      else cf.to(e.clientX, e.clientY);
      if (!!over !== cursorOn) {
        cursorOn = !!over;
        cursor.classList.toggle('is-on', cursorOn);
      }
    }, { passive: true });
    document.addEventListener('pointerdown', function () {
      if (cursorOn) { cursorOn = false; cursor.classList.remove('is-on'); }
    });
  }

  /* ---- Genre list: photo follows the mouse ---- */
  var preview = document.querySelector('.genre-preview');
  if (preview && finePointer) {
    var pimg = preview.querySelector('img');
    var pf = follower(preview, 0.16);
    var visible = false;
    document.querySelectorAll('.genre').forEach(function (g) {
      new Image().src = g.getAttribute('data-img');
      g.addEventListener('pointerenter', function (e) {
        pimg.src = g.getAttribute('data-img');
        pf.to(e.clientX, e.clientY, !visible);
        visible = true;
        preview.classList.add('is-on');
      });
      g.addEventListener('pointermove', function (e) { pf.to(e.clientX, e.clientY); });
    });
    document.querySelector('.genre-list').addEventListener('pointerleave', function () {
      visible = false;
      preview.classList.remove('is-on');
    });
  }

  /* ---- Booking: floating button and dialog ---- */
  var dialog = document.getElementById('booking');
  var floatBtn = document.querySelector('.book-float');
  if (floatBtn) {
    var showFloat = function () {
      var footer = document.querySelector('.site-footer');
      var nearEnd = footer && footer.getBoundingClientRect().top < window.innerHeight;
      floatBtn.classList.toggle('is-shown', window.scrollY > window.innerHeight * 0.6 && !nearEnd);
    };
    window.addEventListener('scroll', showFloat, { passive: true });
    showFloat();
  }
  if (dialog && dialog.showModal) {
    var form = dialog.querySelector('form');
    var status = dialog.querySelector('.booking-status');
    var send = dialog.querySelector('.booking-send');
    var lastOpener = null;
    var closeDialog = function () {
      if (!dialog.open || dialog.classList.contains('is-closing')) return;
      dialog.classList.add('is-closing');
      setTimeout(function () {
        dialog.close();
        dialog.classList.remove('is-closing');
        document.body.classList.remove('menu-lock');
        if (lastOpener) lastOpener.focus();
      }, reduce ? 0 : 260);
    };
    document.querySelectorAll('[data-book]').forEach(function (b) {
      b.addEventListener('click', function () {
        lastOpener = b;
        if (header.classList.contains('menu-open')) setMenu(false);
        dialog.showModal();
        document.body.classList.add('menu-lock');
      });
    });
    dialog.querySelectorAll('[data-close]').forEach(function (b) { b.addEventListener('click', closeDialog); });
    dialog.addEventListener('cancel', function (e) { e.preventDefault(); closeDialog(); });
    dialog.addEventListener('click', function (e) { if (e.target === dialog) closeDialog(); });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (form.elements._honey.value) return;
      var label = send.textContent;
      send.disabled = true;
      send.textContent = form.getAttribute('data-sending');
      status.className = 'booking-status';
      status.textContent = '';
      var data = {};
      new FormData(form).forEach(function (v, k) { data[k] = v; });
      data._url = location.href;
      fetch(form.getAttribute('data-endpoint'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(data)
      }).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      }).then(function (res) {
        if (res && (res.success === false || res.success === 'false')) throw new Error(res.message);
        status.classList.add('is-ok');
        status.textContent = form.getAttribute('data-ok');
        form.reset();
        send.textContent = label;
        send.disabled = false;
      }).catch(function () {
        status.textContent = form.getAttribute('data-err');
        send.textContent = label;
        send.disabled = false;
      });
    });
  }

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
