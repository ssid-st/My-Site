/*
 * Home page hero carousel helpers:
 *  - loads slide photos just before they are shown (data-src -> src)
 *  - sizes the hero to fill the screen below the header and menu
 */
(function () {
  'use strict';

  var hero = document.getElementById('hero');
  if (!hero) return;
  var slides = hero.querySelectorAll('.carousel-item');

  function load(i) {
    var slide = slides[(i + slides.length) % slides.length];
    if (!slide) return;
    slide.querySelectorAll('img[data-src]').forEach(function (img) {
      img.src = img.getAttribute('data-src');
      img.removeAttribute('data-src');
    });
  }

  hero.addEventListener('slide.bs.carousel', function (e) {
    load(e.to);
    load(e.to + 1);
  });
  window.addEventListener('load', function () { load(2); });

  function fit() {
    var used = 0;
    ['.site-header', '.site-nav'].forEach(function (sel) {
      var el = document.querySelector(sel);
      if (el) used += el.offsetHeight;
    });
    document.documentElement.style.setProperty('--chrome', used + 'px');
  }
  fit();
  window.addEventListener('resize', fit);
  document.addEventListener('shown.bs.collapse', fit);
  document.addEventListener('hidden.bs.collapse', fit);
})();
