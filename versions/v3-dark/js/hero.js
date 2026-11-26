/*
 * Home page carousel, no dependencies.
 *  - cross-fades slides every data-interval ms, pauses on hover and in a hidden tab
 *  - swipe on touch screens, arrow keys when focused, dots and arrows
 *  - loads each photo just before it is shown (data-src -> src)
 */
(function () {
  'use strict';

  var hero = document.getElementById('hero');
  if (!hero) return;
  var slides = hero.querySelectorAll('.hero-slide');
  var dots = hero.querySelectorAll('.hero-dots button');
  var interval = parseInt(hero.getAttribute('data-interval'), 10) || 5500;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var index = 0;
  var timer = null;
  var hovering = false;

  hero.style.setProperty('--interval', interval + 'ms');

  function load(i) {
    var slide = slides[(i + slides.length) % slides.length];
    var img = slide.querySelector('img[data-src]');
    if (!img) return;
    img.srcset = img.getAttribute('data-srcset');
    img.src = img.getAttribute('data-src');
    img.removeAttribute('data-src');
    img.removeAttribute('data-srcset');
  }

  function go(i) {
    i = (i + slides.length) % slides.length;
    if (i === index) return;
    load(i);
    load(i + 1);
    slides[index].classList.remove('is-active');
    dots[index].classList.remove('is-active');
    dots[index].removeAttribute('aria-current');
    index = i;
    slides[index].classList.add('is-active');
    dots[index].classList.add('is-active');
    dots[index].setAttribute('aria-current', 'true');
    restart();
  }

  function restart() {
    clearTimeout(timer);
    if (reduce || hovering || document.hidden) return;
    timer = setTimeout(function () { go(index + 1); }, interval);
  }

  function pause(on) {
    hero.classList.toggle('is-paused', on);
    if (on) clearTimeout(timer);
    else restart();
  }

  hero.querySelector('.hero-prev').addEventListener('click', function () { go(index - 1); });
  hero.querySelector('.hero-next').addEventListener('click', function () { go(index + 1); });
  dots.forEach(function (dot, i) {
    dot.addEventListener('click', function () { go(i); });
  });

  hero.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowLeft') go(index - 1);
    else if (e.key === 'ArrowRight') go(index + 1);
  });

  // pause while the mouse is over the photo, but only for a real mouse
  if (window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
    hero.addEventListener('mouseenter', function () { hovering = true; pause(true); });
    hero.addEventListener('mouseleave', function () { hovering = false; pause(false); });
  }
  document.addEventListener('visibilitychange', function () { pause(document.hidden); });

  // swipe: a short quick flick is enough, no need to drag far
  var startX = null, startY = 0, startT = 0;
  hero.addEventListener('touchstart', function (e) {
    if (e.touches.length > 1) { startX = null; return; }
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
    startT = Date.now();
  }, { passive: true });
  hero.addEventListener('touchend', function (e) {
    if (startX === null) return;
    var dx = e.changedTouches[0].clientX - startX;
    var dy = e.changedTouches[0].clientY - startY;
    var velocity = Math.abs(dx) / Math.max(1, Date.now() - startT);
    if (Math.abs(dx) > Math.abs(dy) && (Math.abs(dx) > 60 || velocity > 0.3)) go(index + (dx < 0 ? 1 : -1));
    startX = null;
  });

  window.addEventListener('load', function () { load(2); });
  if (reduce) hero.classList.add('is-paused');
  restart();
})();
