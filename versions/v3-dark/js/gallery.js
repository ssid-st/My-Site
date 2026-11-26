/*
 * Album viewer (lightbox), no dependencies.
 *
 * Each album tile (.album) carries:
 *   data-title  — album name
 *   data-photos — JSON [[base, width, height, tinyPreview], ...]
 *                 the photo is base + '-800.webp' or base + '-1600.webp'
 *
 *  - the first photo grows out of the tile that was pressed, and shrinks back into it on close
 *  - photos change with a short slide and blur, or follow the finger when swiped
 *  - a quick flick is enough; swipe down closes
 *  - keyboard: ← → Esc, focus stays inside the viewer
 */
(function () {
  'use strict';

  var grid = document.querySelector('.album-grid');
  var albums = document.querySelectorAll('.album[data-photos]');
  if (!grid || !albums.length) return;

  var L = {};
  try { L = JSON.parse(grid.getAttribute('data-labels')) || {}; } catch (e) { /* defaults below */ }
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var EASE_OUT = 'cubic-bezier(0.23, 1, 0.32, 1)';
  var EASE_DRAWER = 'cubic-bezier(0.32, 0.72, 0, 1)';

  var ICON = {
    close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5l14 14M19 5L5 19"/></svg>',
    prev: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 4l-8 8 8 8"/></svg>',
    next: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4l8 8-8 8"/></svg>'
  };

  /* ---- Build the viewer once ---- */
  var box = document.createElement('div');
  box.className = 'lightbox';
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-modal', 'true');
  box.setAttribute('aria-label', L.viewer || 'Photo viewer');
  box.innerHTML =
    '<div class="lb-backdrop"></div>' +
    '<div class="lb-stage"></div>' +
    '<button type="button" class="lb-btn lb-close lb-ui" aria-label="' + (L.close || 'Close') + '">' + ICON.close + '</button>' +
    '<button type="button" class="lb-btn lb-prev lb-ui" aria-label="' + (L.prev_photo || 'Previous photo') + '">' + ICON.prev + '</button>' +
    '<button type="button" class="lb-btn lb-next lb-ui" aria-label="' + (L.next_photo || 'Next photo') + '">' + ICON.next + '</button>' +
    '<p class="lb-caption lb-ui" aria-live="polite"></p>';
  document.body.appendChild(box);

  var backdrop = box.querySelector('.lb-backdrop');
  var stage = box.querySelector('.lb-stage');
  var caption = box.querySelector('.lb-caption');
  var closeBtn = box.querySelector('.lb-close');

  var photos = [];
  var title = '';
  var index = 0;
  var opener = null;
  var frame = null;     // the element showing the current photo
  var busy = false;     // true while opening / closing

  /* ---- Helpers ---- */
  function viewport() {
    return { w: window.innerWidth, h: window.innerHeight };
  }

  // where a photo of w × h sits when fitted on screen
  function fitRect(w, h) {
    var v = viewport();
    var coarse = window.matchMedia('(pointer: coarse)').matches;
    var padX = coarse || v.w < 700 ? 0 : 72;
    var padTop = v.w < 700 ? 56 : 48;
    var padBottom = 48;
    var maxW = v.w - padX * 2;
    var maxH = v.h - padTop - padBottom;
    var s = Math.min(maxW / w, maxH / h);
    var fw = Math.round(w * s), fh = Math.round(h * s);
    return { x: Math.round((v.w - fw) / 2), y: Math.round(padTop + (maxH - fh) / 2), w: fw, h: fh };
  }

  function srcFor(p, rect) {
    var need = Math.max(rect.w, rect.h) * (window.devicePixelRatio || 1);
    return p[0] + (need > 900 ? '-1600.webp' : '-800.webp');
  }

  function preload(i) {
    var p = photos[(i + photos.length) % photos.length];
    if (p) new Image().src = srcFor(p, fitRect(p[1], p[2]));
  }

  function makeFrame(i) {
    var p = photos[i];
    var r = fitRect(p[1], p[2]);
    var el = document.createElement('div');
    el.className = 'lb-frame';
    el.style.cssText = 'left:' + r.x + 'px;top:' + r.y + 'px;width:' + r.w + 'px;height:' + r.h + 'px;' +
      '--lqip:url(' + p[3] + ')';
    var img = document.createElement('img');
    img.alt = title + ' — ' + (L.photo || 'photo') + ' ' + (i + 1);
    img.draggable = false;
    img.decoding = 'async';
    img.addEventListener('load', function () { img.classList.add('is-loaded'); }, { once: true });
    img.src = srcFor(p, r);
    if (img.complete && img.naturalWidth) img.classList.add('is-loaded');
    el.appendChild(img);
    el._rect = r;
    return el;
  }

  // run a Web Animation and leave the element in its end state
  function animate(el, from, to, duration, easing) {
    if (reduce && from.transform) {
      // reduced motion: no movement, only a quick fade
      from = { opacity: from.opacity != null ? from.opacity : 0 };
      to = { opacity: to.opacity != null ? to.opacity : 1 };
      duration = 180;
    }
    var a = el.animate([from, to], { duration: duration, easing: easing || EASE_OUT, fill: 'forwards' });
    return a.finished.then(function () {
      Object.keys(to).forEach(function (k) {
        var prop = k === 'clipPath' ? 'clip-path' : k;
        el.style.setProperty(prop, to[k]);
      });
      a.cancel();
    }, function () {});
  }

  // transform + clip that make a full-size frame look exactly like the album tile
  function tileState(el, tile) {
    var r = el._rect;
    var t = tile.getBoundingClientRect();
    var s = Math.max(t.width / r.w, t.height / r.h);
    var dx = t.left + t.width / 2 - (r.x + r.w / 2);
    var dy = t.top + t.height / 2 - (r.y + r.h / 2);
    var ix = Math.max(0, (r.w - t.width / s) / 2);
    var iy = Math.max(0, (r.h - t.height / s) / 2);
    return {
      transform: 'translate(' + dx + 'px,' + dy + 'px) scale(' + s + ')',
      clipPath: 'inset(' + iy + 'px ' + ix + 'px)',
      visible: t.bottom > 0 && t.top < window.innerHeight
    };
  }

  function updateCaption() {
    caption.innerHTML = '';
    caption.appendChild(document.createTextNode(title));
    var n = document.createElement('span');
    n.textContent = (index + 1) + ' / ' + photos.length;
    caption.appendChild(n);
  }

  /* ---- Open / close ---- */
  function open(tile) {
    if (busy) return;
    try { photos = JSON.parse(tile.getAttribute('data-photos')); } catch (e) { return; }
    if (!photos.length) return;
    title = tile.getAttribute('data-title') || '';
    opener = tile;
    index = 0;
    busy = true;

    box.classList.add('is-open');
    document.body.classList.add('lb-lock');
    stage.innerHTML = '';
    frame = makeFrame(0);
    stage.appendChild(frame);
    updateCaption();

    var from = tileState(frame, tile);
    tile.style.visibility = 'hidden';
    animate(backdrop, { opacity: 0 }, { opacity: 1 }, 300, 'ease');
    animate(frame,
      { transform: from.transform, clipPath: from.clipPath },
      { transform: 'none', clipPath: 'inset(0px 0px)' },
      420, EASE_DRAWER).then(function () {
      busy = false;
      box.classList.add('ui-on');
    });
    closeBtn.focus({ preventScroll: true });
    preload(1);
    preload(-1);
  }

  function close() {
    if (busy || !box.classList.contains('is-open')) return;
    busy = true;
    box.classList.remove('ui-on');
    var tile = opener;
    var done = function () {
      box.classList.remove('is-open');
      document.body.classList.remove('lb-lock');
      stage.innerHTML = '';
      backdrop.style.opacity = '0';
      frame = null;
      if (tile) {
        tile.style.visibility = '';
        tile.focus({ preventScroll: true });
      }
      busy = false;
    };
    var current = getComputedStyle(frame).transform;
    var to = tile ? tileState(frame, tile) : { visible: false };
    var bgFrom = getComputedStyle(backdrop).opacity;
    animate(backdrop, { opacity: bgFrom }, { opacity: 0 }, 260, 'ease');
    if (to.visible) {
      // shrink back into the tile, a little faster than opening
      animate(frame,
        { transform: current === 'none' ? 'none' : current, clipPath: 'inset(0px 0px)' },
        { transform: to.transform, clipPath: to.clipPath },
        300, EASE_OUT).then(done);
    } else {
      animate(frame, { opacity: 1, transform: current === 'none' ? 'none' : current },
        { opacity: 0, transform: 'translateY(24px) scale(.96)' }, 220, EASE_OUT).then(done);
    }
  }

  /* ---- Change photo ---- */
  // dir: +1 next, -1 previous. fromX: where the old frame is now (after a swipe)
  function show(i, dir, fromX) {
    if (busy || photos.length < 2) return;
    var v = viewport();
    var old = frame;
    index = (i + photos.length) % photos.length;
    frame = makeFrame(index);
    stage.appendChild(frame);
    updateCaption();

    var swiped = typeof fromX === 'number';
    var outX = swiped ? -dir * v.w * 0.6 : -dir * 48;
    var inX = swiped ? dir * v.w * 0.3 : dir * 48;
    animate(old,
      { transform: 'translateX(' + (fromX || 0) + 'px)', opacity: 1, filter: 'blur(0px)' },
      { transform: 'translateX(' + outX + 'px)', opacity: 0, filter: 'blur(2px)' },
      swiped ? 280 : 220, EASE_OUT).then(function () { old.remove(); });
    animate(frame,
      { transform: 'translateX(' + inX + 'px)', opacity: 0, filter: 'blur(2px)' },
      { transform: 'none', opacity: 1, filter: 'blur(0px)' },
      swiped ? 340 : 260, EASE_OUT);
    preload(index + dir);
  }

  /* ---- Drag / swipe ---- */
  var drag = null;
  stage.addEventListener('pointerdown', function (e) {
    if (drag || busy || !frame) return;          // ignore a second finger
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    drag = { id: e.pointerId, x: e.clientX, y: e.clientY, t: Date.now(), axis: null, dx: 0, dy: 0 };
    stage.setPointerCapture(e.pointerId);
  });

  stage.addEventListener('pointermove', function (e) {
    if (!drag || e.pointerId !== drag.id) return;
    var dx = e.clientX - drag.x;
    var dy = e.clientY - drag.y;
    if (!drag.axis) {
      if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
      drag.axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
      box.classList.remove('ui-on');
    }
    drag.dx = dx;
    drag.dy = dy;
    if (drag.axis === 'x') {
      // a single photo can still be pulled a little, with friction
      var x = photos.length > 1 ? dx : dx * 0.25;
      frame.style.transform = 'translateX(' + x + 'px)';
    } else {
      // down closes; up meets growing resistance instead of a hard stop
      var y = dy > 0 ? dy : -Math.sqrt(-dy) * 4;
      var progress = Math.min(1, Math.max(0, dy) / (window.innerHeight * 0.5));
      frame.style.transform = 'translateY(' + y + 'px) scale(' + (1 - progress * 0.2) + ')';
      backdrop.style.opacity = String(1 - progress * 0.85);
    }
  });

  function endDrag(e) {
    if (!drag || e.pointerId !== drag.id) return;
    var d = drag;
    drag = null;
    var elapsed = Math.max(1, Date.now() - d.t);

    if (!d.axis) {
      // a tap: outside the photo closes, on the photo toggles the buttons
      var r = frame._rect;
      var inside = e.clientX >= r.x && e.clientX <= r.x + r.w && e.clientY >= r.y && e.clientY <= r.y + r.h;
      if (!inside) close();
      else box.classList.toggle('ui-on');
      return;
    }
    box.classList.add('ui-on');
    if (d.axis === 'x') {
      var vx = Math.abs(d.dx) / elapsed;
      if (photos.length > 1 && (Math.abs(d.dx) > window.innerWidth * 0.2 || (vx > 0.11 && Math.abs(d.dx) > 20))) {
        var dir = d.dx < 0 ? 1 : -1;
        show(index + dir, dir, d.dx);
      } else {
        settle();
      }
    } else {
      var vy = d.dy / elapsed;
      if (d.dy > 120 || (vy > 0.11 && d.dy > 30)) close();
      else settle();
    }
  }
  stage.addEventListener('pointerup', endDrag);
  stage.addEventListener('pointercancel', endDrag);

  // spring back to the resting position
  function settle() {
    var current = getComputedStyle(frame).transform;
    animate(frame, { transform: current }, { transform: 'none' }, 260, EASE_OUT);
    animate(backdrop, { opacity: getComputedStyle(backdrop).opacity }, { opacity: 1 }, 200, 'ease');
  }

  /* ---- Buttons and keys ---- */
  albums.forEach(function (tile) {
    tile.addEventListener('click', function () { open(tile); });
    // start loading the first photo as soon as the finger or mouse is on the tile
    var warm = function () {
      try {
        var p = JSON.parse(tile.getAttribute('data-photos'))[0];
        new Image().src = srcFor(p, fitRect(p[1], p[2]));
      } catch (e) { /* ignore */ }
    };
    tile.addEventListener('pointerenter', warm, { once: true });
    tile.addEventListener('pointerdown', warm, { once: true });
    tile.addEventListener('focus', warm, { once: true });
  });

  closeBtn.addEventListener('click', close);
  box.querySelector('.lb-prev').addEventListener('click', function () { show(index - 1, -1); });
  box.querySelector('.lb-next').addEventListener('click', function () { show(index + 1, 1); });

  document.addEventListener('keydown', function (e) {
    if (!box.classList.contains('is-open')) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft') show(index - 1, -1);
    else if (e.key === 'ArrowRight') show(index + 1, 1);
    else if (e.key === 'Tab') {
      var f = Array.prototype.filter.call(box.querySelectorAll('button'), function (b) {
        return b.offsetParent !== null;
      });
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { last.focus(); e.preventDefault(); }
      else if (!e.shiftKey && document.activeElement === last) { first.focus(); e.preventDefault(); }
    }
  });

  window.addEventListener('resize', function () {
    if (!frame || busy) return;
    var r = fitRect(photos[index][1], photos[index][2]);
    frame._rect = r;
    frame.style.left = r.x + 'px';
    frame.style.top = r.y + 'px';
    frame.style.width = r.w + 'px';
    frame.style.height = r.h + 'px';
  });
})();
