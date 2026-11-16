/* Time Turner: theme toggle, mobile menu, reading progress, text size, copy link. */
(function () {
  var root = document.documentElement;
  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  var themeBtn = document.getElementById('tt-theme');
  if (themeBtn) themeBtn.addEventListener('click', function () {
    var cur = root.getAttribute('data-theme');
    var dark = cur ? cur === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    var next = dark ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    store('tt-theme', next);
  });

  var toggle = document.getElementById('tt-menu-toggle'), nav = document.getElementById('tt-nav');
  if (toggle && nav) toggle.addEventListener('click', function () {
    var open = nav.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  var bar = document.getElementById('tt-progress');
  if (bar) {
    var onScroll = function () {
      var max = document.documentElement.scrollHeight - window.innerHeight;
      bar.style.width = (max > 0 ? (window.scrollY / max) * 100 : 100) + '%';
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  var fs = parseInt(getComputedStyle(root).getPropertyValue('--fs'), 10) || 19;
  document.querySelectorAll('[data-tt-size]').forEach(function (b) {
    b.addEventListener('click', function () {
      fs = Math.min(24, Math.max(16, fs + parseInt(b.getAttribute('data-tt-size'), 10)));
      root.style.setProperty('--fs', fs + 'px');
      store('tt-fs', fs);
    });
  });

  var toast = document.getElementById('tt-toast');
  function say(m) {
    if (!toast) return;
    toast.textContent = m; toast.classList.add('show');
    clearTimeout(toast._h); toast._h = setTimeout(function () { toast.classList.remove('show'); }, 1800);
  }
  var copy = document.getElementById('tt-copy');
  if (copy) copy.addEventListener('click', function () {
    var url = copy.getAttribute('data-url') || location.href;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function () { say('Link copied'); }, function () { say(url); });
    } else { say(url); }
  });
})();

/* Static-site additions: search page and old ?p=123 short links. */
(function () {
  var base = document.documentElement.getAttribute('data-base') || '';
  var params = new URLSearchParams(location.search);
  function load(cb) {
    fetch(base + '/search.json').then(function (r) { return r.json(); }).then(cb).catch(function () {});
  }
  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }

  var oldId = params.get('p');
  if (oldId && /^\d+$/.test(oldId)) load(function (posts) {
    for (var i = 0; i < posts.length; i++) if (posts[i].i === oldId) { location.replace(base + posts[i].u); return; }
  });

  var box = document.getElementById('tt-search-results');
  if (!box) return;
  var q = (params.get('s') || '').trim();
  var field = document.querySelector('.search-field');
  if (field) field.value = q;
  if (!q) return;
  var title = document.getElementById('tt-search-title');
  if (title) title.textContent = q;
  load(function (posts) {
    var words = q.toLowerCase().split(/\s+/);
    var hits = posts.filter(function (p) {
      var hay = (p.t + ' ' + p.x + ' ' + p.k + ' ' + p.c).toLowerCase();
      return words.every(function (w) { return hay.indexOf(w) !== -1; });
    });
    if (!hits.length) { box.innerHTML = '<p class="empty">No stories match that. Search looks at titles, opening lines and tags.</p>'; return; }
    box.innerHTML = hits.slice(0, 100).map(function (p) {
      return '<article class="entry-row post"><div class="when"><b>' + esc(p.d) + '</b><span class="mono">' + esc(p.m) + '</span></div>' +
        '<div class="body">' + (p.c ? '<span class="cat"><a href="' + base + '/category/' + p.cs + '/">' + esc(p.c) + '</a></span>' : '') +
        '<h2 lang="' + p.l + '"><a href="' + base + p.u + '">' + esc(p.t) + '</a></h2>' +
        '<div class="excerpt" lang="' + p.l + '"><p>' + esc(p.x) + '</p></div>' +
        '<div class="meta mono"><span>' + esc(p.r) + '</span><span>' + (p.n ? p.n + (p.n === 1 ? ' comment' : ' comments') : 'No comments yet') + '</span></div></div></article>';
    }).join('');
  });
})();
