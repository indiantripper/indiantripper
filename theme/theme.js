/* Open notebook: local reading preferences, search, and legacy post links. */
(function () {
  'use strict';
  var root = document.documentElement, base = root.getAttribute('data-base') || '';
  var earlier = document.querySelector('[data-daily-favourites]');
  if (earlier) {
    var favourites = JSON.parse(earlier.getAttribute('data-daily-favourites'));
    // One shared daily pick, changing at midnight in India without a rebuild.
    var day = Math.floor((Date.now() + 330 * 60000) / 86400000);
    var pick = favourites[day % favourites.length];
    if (pick) {
      var heading = earlier.querySelector('h2');
      heading.lang = pick.lang;
      heading.querySelector('a').textContent = pick.title;
      earlier.querySelectorAll('a').forEach(function (a) { a.setAttribute('href', pick.path); });
      earlier.querySelector('.old-date').textContent = pick.date;
      earlier.querySelector('.earlier-note').textContent = pick.note;
    }
  }
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
  var mobileMenu = document.querySelector('.mobile-menu');
  if (mobileMenu) {
    document.addEventListener('click', function (e) { if (!mobileMenu.contains(e.target)) mobileMenu.open = false; });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && mobileMenu.open) { mobileMenu.open = false; mobileMenu.querySelector('summary').focus(); } });
  }
  var shareMenu = document.querySelector('.post-share');
  if (shareMenu) {
    var shareTitle = shareMenu.dataset.shareTitle, shareUrl = shareMenu.dataset.shareUrl;
    var shareData = { title: shareTitle, text: shareTitle, url: shareUrl };
    var shareStatus = shareMenu.querySelector('.share-status');
    var manualLink = shareMenu.querySelector('.share-manual');
    var nativeShare = shareMenu.querySelector('[data-share-native]');
    var imageShare = shareMenu.querySelector('[data-share-image-native]'), shareFile = null;
    function status(message) { shareStatus.textContent = message; }
    if (navigator.share) {
      nativeShare.hidden = false;
      nativeShare.addEventListener('click', function () {
        navigator.share(shareData).catch(function (error) { if (error.name !== 'AbortError') status('Sharing is unavailable. Try WhatsApp or copy the link.'); });
      });
    }
    shareMenu.querySelector('[data-share-copy]').addEventListener('click', function () {
      function fallback() {
        manualLink.hidden = false;
        var input = manualLink.querySelector('input'); input.focus(); input.select();
        try { if (document.execCommand('copy')) { status('Link copied.'); manualLink.hidden = true; return; } } catch (e) {}
        status('Select and copy the post link above.');
      }
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(shareUrl).then(function () { status('Link copied.'); }).catch(fallback);
      else fallback();
    });
    shareMenu.addEventListener('toggle', function () {
      if (!shareMenu.open || shareFile || !navigator.canShare || !navigator.share || !window.isSecureContext) return;
      fetch(shareMenu.dataset.shareImage).then(function (response) {
        if (!response.ok) throw new Error('Image unavailable'); return response.blob();
      }).then(function (blob) {
        var type = blob.type.split(';')[0]; if (!/^image\/(jpeg|png|webp)$/.test(type)) return;
        var ext = type === 'image/jpeg' ? 'jpg' : type.split('/')[1];
        var file = new File([blob], 'time-turner-share.' + ext, { type: type });
        if (navigator.canShare({ files: [file] })) { shareFile = file; imageShare.hidden = false; }
      }).catch(function () {});
    });
    imageShare.addEventListener('click', function () {
      if (!shareFile) return;
      navigator.share({ files: [shareFile], title: shareTitle, text: shareTitle + '\n' + shareUrl }).catch(function (error) { if (error.name !== 'AbortError') status('Image sharing is unavailable. Use Save image instead.'); });
    });
    document.addEventListener('click', function (e) { if (!shareMenu.contains(e.target)) shareMenu.open = false; });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && shareMenu.open) { shareMenu.open = false; shareMenu.querySelector('summary').focus(); } });
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
      if (p.im) { article.classList.add('has-thumbnail'); var thumbnail = el('a', 'row-thumbnail'), photo = el('img'); thumbnail.href = base + p.u; thumbnail.setAttribute('aria-label', 'Read ' + p.t); photo.src = base + p.im; photo.alt = ''; photo.loading = 'lazy'; photo.width = 160; photo.height = 120; thumbnail.append(photo); body.append(thumbnail); }
      var excerpt = el('div', 'excerpt'), preview = el('p'); excerpt.lang = p.l;
      if (p.v && p.v.length) { excerpt.classList.add('verse'); p.v.forEach(function (line, i) { if (i) preview.append(document.createElement('br')); preview.append(document.createTextNode(line)); }); }
      else preview.textContent = p.x;
      excerpt.append(preview); body.append(excerpt);
      var meta = el('div', 'meta'); meta.append(el('span', '', p.r)); if (p.n) meta.append(el('span', '', p.n + (p.n === 1 ? ' comment' : ' comments'))); body.append(meta);
      var arrow = el('span', 'row-arrow', '↗'); arrow.setAttribute('aria-hidden', 'true'); article.append(when, body, arrow); box.append(article);
    });
  }, function () { box.replaceChildren(el('p', 'empty', 'Search could not load. Please try again, or browse Threads and the year archive.')); });
})();
