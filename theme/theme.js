/* Open notebook: local reading preferences, search, and legacy post links. */
(function () {
  'use strict';
  var root = document.documentElement, base = root.getAttribute('data-base') || '';
  function store(key, value) { try { localStorage.setItem(key, value); } catch (e) {} }
  function read(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  var system = window.matchMedia('(prefers-color-scheme: dark)'), saved = read('tt-theme');
  var theme = saved === 'light' || saved === 'dark' ? saved : system.matches ? 'dark' : 'light';
  var themeButton = document.getElementById('tt-theme');
  function applyTheme() {
    root.dataset.theme = theme;
    if (themeButton) { themeButton.setAttribute('aria-label', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'); themeButton.setAttribute('aria-pressed', String(theme === 'dark')); }
  }
  applyTheme();
  if (themeButton) themeButton.addEventListener('click', function () { theme = theme === 'dark' ? 'light' : 'dark'; store('tt-theme', theme); applyTheme(); });
  if (system.addEventListener) system.addEventListener('change', function (e) { if (!read('tt-theme')) { theme = e.matches ? 'dark' : 'light'; applyTheme(); } });
  var fs = Number(read('tt-fs-v2')) || 21, buttons = document.querySelectorAll('[data-tt-size]');
  function applySize() {
    fs = Math.max(19, Math.min(27, fs)); root.style.setProperty('--fs', fs + 'px');
    buttons.forEach(function (b) { b.disabled = Number(b.dataset.ttSize) < 0 ? fs <= 19 : fs >= 27; });
  }
  applySize();
  buttons.forEach(function (b) { b.addEventListener('click', function () { fs += Number(b.dataset.ttSize); applySize(); store('tt-fs-v2', fs); }); });
  var storyLanguage = document.getElementById('tt-story-language');
  if (storyLanguage) storyLanguage.addEventListener('change', function () { location.assign(storyLanguage.value); });
  var preferences = document.querySelector('.preferences');
  if (preferences) {
    document.addEventListener('click', function (e) { if (!preferences.contains(e.target)) preferences.open = false; });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && preferences.open) { preferences.open = false; preferences.querySelector('summary').focus(); } });
  }
  function loadPosts(callback, onError) { fetch(base + '/search.json').then(function (r) { if (!r.ok) throw new Error('Search unavailable'); return r.json(); }).then(callback).catch(function () { if (onError) onError(); }); }
  var params = new URLSearchParams(location.search), oldId = params.get('p');
  if (oldId && /^\d+$/.test(oldId)) loadPosts(function (posts) { var p = posts.find(function (p) { return p.i === oldId; }); if (p) location.replace(base + p.u); });
  var box = document.getElementById('tt-search-results'); if (!box) return;
  var query = (params.get('s') || '').trim(), field = document.querySelector('.search-field'); if (field) field.value = query; if (!query) return;
  var title = document.getElementById('tt-search-title'); if (title) title.textContent = query;
  box.setAttribute('aria-live', 'polite'); box.textContent = 'Looking through the notebook…';
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function category(p) {
    var wrapper = el('span', 'cat'), a = el('a'); a.href = base + '/category/' + p.cs + '/';
    if (!p.ce || p.ce === p.c) a.textContent = p.c;
    else { var pair = el('span', 'thread-label'), hi = el('span', 'label-hi', p.c), en = el('span', 'label-en', p.ce), divider = el('span', 'label-separator', ' · '); hi.lang = 'hi'; en.lang = 'en'; divider.setAttribute('aria-hidden', 'true'); pair.append(hi, divider, en); a.append(pair); }
    wrapper.append(a); return wrapper;
  }
  loadPosts(function (posts) {
    var words = query.toLowerCase().split(/\s+/), hits = posts.filter(function (p) { var text = (p.t + ' ' + p.x + ' ' + p.k + ' ' + p.c + ' ' + p.ce).toLowerCase(); return words.every(function (word) { return text.indexOf(word) !== -1; }); });
    box.replaceChildren(); if (!hits.length) { box.append(el('p', 'empty', 'No pages match that. Try another word or browse Threads.')); return; }
    box.append(el('p', 'hub-count', hits.length + (hits.length === 1 ? ' page found' : ' pages found')));
    hits.forEach(function (p) {
      var article = el('article', 'entry-row post'), when = el('div', 'when'), body = el('div', 'body'); when.append(el('span', '', p.d), el('span', '', p.m)); if (p.cs) body.append(category(p));
      var h = el('h2'), a = el('a', '', p.t); h.lang = p.l; a.href = base + p.u; h.append(a); body.append(h);
      var excerpt = el('div', 'excerpt'); excerpt.lang = p.l; excerpt.append(el('p', '', p.x)); body.append(excerpt);
      var meta = el('div', 'meta'); meta.append(el('span', '', p.r)); if (p.n) meta.append(el('span', '', p.n + (p.n === 1 ? ' comment' : ' comments'))); body.append(meta);
      var arrow = el('span', 'row-arrow', '↗'); arrow.setAttribute('aria-hidden', 'true'); article.append(when, body, arrow); box.append(article);
    });
  }, function () { box.replaceChildren(el('p', 'empty', 'Search could not load. Please try again, or browse Threads and the year archive.')); });
})();
