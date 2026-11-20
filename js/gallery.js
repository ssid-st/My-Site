/*
 * Lightweight album lightbox, no dependencies.
 * Each album button carries:
 *   data-title  — album name
 *   data-photos — JSON array of image URLs
 * Keyboard: ← → Esc. Touch: swipe left/right.
 */
(function () {
  'use strict';

  var albums = document.querySelectorAll('.album[data-photos]');
  if (!albums.length) return;

  var box = document.createElement('div');
  box.className = 'lightbox';
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-modal', 'true');
  box.setAttribute('aria-label', 'Photo viewer');
  box.innerHTML =
    '<button type="button" class="lb-close" aria-label="Close">&times;</button>' +
    '<button type="button" class="lb-prev" aria-label="Previous photo">&#8249;</button>' +
    '<figure><img alt=""><figcaption aria-live="polite"></figcaption></figure>' +
    '<button type="button" class="lb-next" aria-label="Next photo">&#8250;</button>';
  document.body.appendChild(box);

  var img = box.querySelector('img');
  var caption = box.querySelector('figcaption');
  var closeBtn = box.querySelector('.lb-close');
  var photos = [];
  var title = '';
  var index = 0;
  var opener = null;

  function preload(i) {
    if (photos[i]) new Image().src = photos[i];
  }

  function show(i) {
    index = (i + photos.length) % photos.length;
    img.src = photos[index];
    img.alt = title + ' — photo ' + (index + 1);
    caption.textContent = title + '  ' + (index + 1) + ' / ' + photos.length;
    preload((index + 1) % photos.length);
  }

  function open(button) {
    try {
      photos = JSON.parse(button.getAttribute('data-photos'));
    } catch (e) {
      return;
    }
    if (!photos.length) return;
    title = button.getAttribute('data-title') || '';
    opener = button;
    box.classList.add('open');
    document.body.classList.add('lb-open');
    show(0);
    closeBtn.focus();
  }

  function close() {
    box.classList.remove('open');
    document.body.classList.remove('lb-open');
    img.removeAttribute('src');
    if (opener) opener.focus();
  }

  albums.forEach(function (button) {
    button.addEventListener('click', function () { open(button); });
  });

  closeBtn.addEventListener('click', close);
  box.querySelector('.lb-prev').addEventListener('click', function () { show(index - 1); });
  box.querySelector('.lb-next').addEventListener('click', function () { show(index + 1); });

  box.addEventListener('click', function (e) {
    if (e.target === box) close();
  });

  document.addEventListener('keydown', function (e) {
    if (!box.classList.contains('open')) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft') show(index - 1);
    else if (e.key === 'ArrowRight') show(index + 1);
    else if (e.key === 'Tab') {
      // keep focus inside the dialog
      var f = box.querySelectorAll('button');
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { last.focus(); e.preventDefault(); }
      else if (!e.shiftKey && document.activeElement === last) { first.focus(); e.preventDefault(); }
    }
  });

  var startX = null;
  box.addEventListener('touchstart', function (e) {
    startX = e.touches[0].clientX;
  }, { passive: true });
  box.addEventListener('touchend', function (e) {
    if (startX === null) return;
    var dx = e.changedTouches[0].clientX - startX;
    if (Math.abs(dx) > 50) show(index + (dx < 0 ? 1 : -1));
    startX = null;
  });
})();
