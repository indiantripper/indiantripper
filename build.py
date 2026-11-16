#!/usr/bin/env python3
"""Builds the static site from content/ into docs/.

    python3 build.py                      production build for https://indiantripper.in
    python3 build.py --preview /repo-name build for a temporary address such as
                                          https://USER.github.io/repo-name/ (hidden from search engines)
    python3 build.py --serve              build, then preview at http://localhost:8000

Only the Python standard library is used.
"""
import argparse, datetime, hashlib, html, json, os, re, shutil, sys
from urllib.parse import quote, unquote

ROOT = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(ROOT, 'content')
esc = html.escape

BLOCKS = ('(?:table|thead|tfoot|caption|col|colgroup|tbody|tr|td|th|div|dl|dd|dt|ul|ol|li|pre|form|map|area|'
          'blockquote|address|style|p|h[1-6]|hr|fieldset|legend|section|article|aside|hgroup|header|footer|'
          'nav|figure|figcaption|details|menu|summary)')
HOURGLASS = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
             'aria-hidden="true"><path d="M6 2h12M6 22h12M7 2c0 5 10 6 10 10S7 17 7 22M17 2c0 5-10 6-10 10s10 5 10 10"/></svg>')
FONTS = ('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Source+Serif+4:'
         'ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=Tiro+Devanagari+Hindi:ital@0;1&family=IBM+Plex+Mono:wght@400;500&display=swap')


# ---------------------------------------------------------------- text helpers

def wpautop(text):
    """Port of WordPress's paragraph formatter: blank line = new paragraph, single newline = line break."""
    if not text.strip():
        return ''
    pre = {}
    text += '\n'
    if '<pre' in text:
        parts = text.split('</pre>')
        last = parts.pop()
        text = ''
        for i, part in enumerate(parts):
            start = part.find('<pre')
            if start == -1:
                text += part
                continue
            name = '<pre wp-pre-tag-%d></pre>' % i
            pre[name] = part[start:] + '</pre>'
            text += part[:start] + name
        text += last
    text = re.sub(r'<br\s*/?>\s*<br\s*/?>', '\n\n', text)
    text = re.sub(r'(<' + BLOCKS + r'[\s/>])', r'\n\n\1', text)
    text = re.sub(r'(</' + BLOCKS + r'>)', r'\1\n\n', text)
    text = re.sub(r'(<hr\s*?/?>)', r'\1\n\n', text)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'<!--.*?-->|<[^<>]*>', lambda m: m.group(0).replace('\n', ' <!-- wpnl --> '), text, flags=re.S)
    if '<option' in text:
        text = re.sub(r'\s*<option', '<option', text)
        text = re.sub(r'</option>\s*', '</option>', text)
    if '</object>' in text:
        text = re.sub(r'(<object[^>]*>)\s*', r'\1', text)
        text = re.sub(r'\s*</object>', '</object>', text)
        text = re.sub(r'\s*(</?(?:param|embed)[^>]*>)\s*', r'\1', text)
    if '<source' in text or '<track' in text:
        text = re.sub(r'([<\[](?:audio|video)[^>\]]*[>\]])\s*', r'\1', text)
        text = re.sub(r'\s*([<\[]/(?:audio|video)[>\]])', r'\1', text)
        text = re.sub(r'\s*(<(?:source|track)[^>]*>)\s*', r'\1', text)
    if '<figcaption' in text:
        text = re.sub(r'\s*(<figcaption[^>]*>)', r'\1', text)
        text = re.sub(r'</figcaption>\s*', '</figcaption>', text)
    text = re.sub(r'\n\n+', '\n\n', text)
    paras = [p for p in re.split(r'\n\s*\n', text) if p.strip()]
    text = ''.join('<p>' + p.strip('\n') + '</p>\n' for p in paras)
    text = re.sub(r'<p>\s*</p>', '', text)
    text = re.sub(r'<p>([^<]+)</(div|address|form)>', r'<p>\1</p></\2>', text)
    text = re.sub(r'<p>\s*(</?' + BLOCKS + r'[^>]*>)\s*</p>', r'\1', text)
    text = re.sub(r'<p>(<li.+?)</p>', r'\1', text)
    text = re.sub(r'<p><blockquote([^>]*)>', r'<blockquote\1><p>', text, flags=re.I)
    text = text.replace('</blockquote></p>', '</p></blockquote>')
    text = re.sub(r'<p>\s*(</?' + BLOCKS + r'[^>]*>)', r'\1', text)
    text = re.sub(r'(</?' + BLOCKS + r'[^>]*>)\s*</p>', r'\1', text)
    text = re.sub(r'<(script|style|svg|math)\b.*?</\1>', lambda m: m.group(0).replace('\n', '<WPPreserveNewline />'), text, flags=re.S)
    text = text.replace('<br>', '<br />').replace('<br/>', '<br />')
    text = re.sub(r'(?<!<br />)\s*\n', '<br />\n', text)
    text = text.replace('<WPPreserveNewline />', '\n')
    text = re.sub(r'(</?' + BLOCKS + r'[^>]*>)\s*<br />', r'\1', text)
    text = re.sub(r'<br />(\s*</?(?:p|li|div|dl|dd|dt|th|pre|td|ul|ol)[^>]*>)', r'\1', text)
    text = re.sub(r'\n</p>$', '</p>', text)
    for name, original in pre.items():
        text = text.replace(name, original)
    return text.replace(' <!-- wpnl --> ', '\n')


def strip_tags(s):
    s = re.sub(r'<(script|style)\b.*?</\1>', '', s, flags=re.S)
    s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
    return html.unescape(re.sub(r'<[^>]+>', ' ', s))


def strip_shortcodes(s):
    s = re.sub(r'\[caption[^\]]*\](.*?)\[/caption\]', r'\1', s, flags=re.S)
    return re.sub(r'\[/?(?:blog_in_blog|gallery|embed)[^\]]*\]', '', s)


def is_hindi(s):
    return bool(re.search('[ऀ-ॿ]', s or ''))


def caption_html(m):
    attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    inner = m.group(2).strip()
    mm = re.match(r'((?:<a[^>]*>\s*)?<img[^>]*>(?:\s*</a>)?)(.*)$', inner, flags=re.S)
    media, cap = (mm.group(1), mm.group(2).strip()) if mm else (inner, '')
    cap = cap or attrs.get('caption', '')
    width = attrs.get('width', '')
    style = ' style="max-width:%spx"' % width if width.isdigit() else ''
    fig = '<figure class="wp-caption %s"%s>%s' % (esc(attrs.get('align', 'alignnone')), style, media)
    if cap:
        fig += '<figcaption class="wp-caption-text">%s</figcaption>' % cap
    return '\n\n' + fig + '</figure>\n\n'


def youtube_embed(m):
    return ('\n\n<figure class="embed"><iframe src="https://www.youtube-nocookie.com/embed/%s" title="YouTube video" '
            'loading="lazy" allowfullscreen></iframe></figure>\n\n' % m.group(1))


def render_body(raw, site, base):
    body = raw
    body = re.sub(r'\[caption([^\]]*)\](.*?)\[/caption\]', caption_html, body, flags=re.S)
    body = re.sub(r'\[/?(?:blog_in_blog|gallery|embed)[^\]]*\]', '', body)
    body = re.sub(r'^[ \t]*https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{6,})\S*[ \t]*$', youtube_embed, body, flags=re.M)
    body = re.sub(r'<!--more.*?-->', '', body)
    if '<!-- wp:' in body:                       # block-editor post: paragraphs already marked up
        body = re.sub(r'<!--\s*/?wp:.*?-->', '', body, flags=re.S)
    else:
        body = wpautop(body)
    host = site['site_url'].split('//', 1)[1]
    # links to the blog's own address follow the current build (production or preview)
    body = re.sub(r'(href=["\'])https?://(?:www\.)?' + re.escape(host) + r'(?=[/"\'])', r'\1' + base, body)
    body = re.sub(r'<img(?![^>]*\bloading=)', '<img loading="lazy"', body)
    return body


ALLOWED_COMMENT_TAGS = {'a', 'b', 'i', 'em', 'strong', 'blockquote', 'code', 'pre', 'br', 'p', 'ul', 'ol', 'li', 'del', 'strike', 'q', 'cite'}


def render_comment(text):
    def tag(m):
        closing, name, rest = m.group(1), m.group(2).lower(), m.group(3)
        if name not in ALLOWED_COMMENT_TAGS:
            return ''
        if closing:
            return '</%s>' % name
        if name == 'a':
            h = re.search(r'href\s*=\s*(["\'])(https?://[^"\']*)\1', rest, flags=re.I)
            return '<a href="%s" rel="nofollow ugc noopener">' % esc(html.unescape(h.group(2))) if h else '<a>'
        return '<%s>' % name
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    text = re.sub(r'<(script|style|iframe|object)\b.*?(</\1>|$)', '', text, flags=re.S | re.I)
    text = re.sub(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>', tag, text)
    return wpautop(text)


def excerpt_of(post):
    if post.get('excerpt'):
        return esc(post['excerpt'])
    words = strip_tags(strip_shortcodes(post['raw'])).split()
    return esc(' '.join(words[:40]) + ('…' if len(words) > 40 else ''))


def fmt_date(d, style):
    if style == 'long':
        return '%s %d, %d' % (d.strftime('%B'), d.day, d.year)
    if style == 'my':
        return d.strftime('%b %Y')
    return str(d.day)


def plural(n, word):
    return '%s %s%s' % (format(n, ','), word, '' if n == 1 else 's')


# ---------------------------------------------------------------- loading

def parse_file(path):
    text = open(path, encoding='utf-8').read().replace('\r\n', '\n')
    meta = {}
    if text.startswith('---\n'):
        head, _, body = text[4:].partition('\n---\n')
        for line in head.split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                meta[k.strip().lower()] = v.strip()
    else:
        body = text
    return meta, body.lstrip('\n')


def load(site):
    posts, problems = [], []
    pdir = os.path.join(CONTENT, 'posts')
    for dirpath, _, files in sorted(os.walk(pdir)):
        for f in sorted(files):
            if not f.endswith(('.html', '.txt', '.md')):
                continue
            full = os.path.join(dirpath, f)
            meta, raw = parse_file(full)
            if meta.get('status', 'publish').lower() not in ('publish', 'published'):
                continue
            stem = os.path.splitext(f)[0]
            try:
                d = datetime.datetime.strptime((meta.get('date') or stem[:10]).strip()[:19].ljust(19, '0')
                                               if len((meta.get('date') or stem[:10]).strip()) > 10
                                               else (meta.get('date') or stem[:10]).strip() + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
            except ValueError:
                problems.append('%s: date not understood (use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)' % f)
                continue
            if not meta.get('title'):
                problems.append('%s: missing "title:" line' % f)
                continue
            slug = meta.get('slug') or re.sub(r'^\d{4}-\d{2}-\d{2}-', '', stem).strip().lower().replace(' ', '-')
            path = meta.get('path') or '/%04d/%02d/%02d/%s/' % (d.year, d.month, d.day, quote(slug, safe='-_.~').lower())
            if not path.endswith('/'):
                path += '/'
            cfile = os.path.join(CONTENT, 'comments', os.path.relpath(dirpath, pdir), stem + '.json')
            comments = json.load(open(cfile, encoding='utf-8')) if os.path.exists(cfile) else []
            posts.append({
                'title': meta['title'], 'date': d, 'path': path, 'id': meta.get('id', ''), 'raw': raw,
                'excerpt': meta.get('excerpt', ''),
                'cats': [c.strip() for c in meta.get('categories', '').split(',') if c.strip()],
                'tags': [c.strip() for c in meta.get('tags', '').split(',') if c.strip()],
                'comments': comments, 'file': f,
                'lang': 'hi' if is_hindi(meta['title']) else 'en',
            })
    posts.sort(key=lambda p: (p['date'], p['id'].zfill(9)), reverse=True)
    seen = {}
    for p in posts:
        if p['path'] in seen:
            problems.append('Two posts share the address %s: %s and %s' % (p['path'], seen[p['path']], p['file']))
        seen[p['path']] = p['file']
    return posts, problems


# ---------------------------------------------------------------- site builder

class Site:
    def __init__(self, args):
        self.site = json.load(open(os.path.join(CONTENT, 'site.json'), encoding='utf-8'))
        self.base = (args.preview or '').rstrip('/')
        self.preview = args.preview is not None
        self.out = os.path.join(ROOT, args.out)
        self.cats = json.load(open(os.path.join(CONTENT, 'categories.json'), encoding='utf-8'))
        self.cat_name = {c['slug']: c['name'] for c in self.cats}
        tpath = os.path.join(CONTENT, 'tags.json')
        self.tag_name = json.load(open(tpath, encoding='utf-8')) if os.path.exists(tpath) else {}
        self.posts, self.problems = load(self.site)
        self.pages_written = 0
        self.asset_v = ''

    def u(self, path):
        return self.base + path

    def canonical(self, path):
        return self.site['site_url'] + path

    def write(self, path, text):
        rel = unquote(path).lstrip('/')
        if path.endswith('/') or path == '':
            rel = os.path.join(rel, 'index.html')
        full = os.path.join(self.out, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        self.pages_written += 1

    # ---- shared chrome

    def cat_counts(self):
        counts = {}
        for p in self.posts:
            for c in p['cats']:
                counts[c] = counts.get(c, 0) + 1
        return counts

    def page(self, path, title, body, body_class='', description='', singular=False, noindex=False, og_type='website'):
        s = self.site
        description = description or s['description']
        robots = '<meta name="robots" content="noindex, nofollow">\n' if (noindex or self.preview) else ''
        menu = ''.join('<li%s><a href="%s">%s</a></li>' % (
            ' class="current-cat"' if path.startswith('/category/%s/' % c) else '',
            self.u('/category/%s/' % c), esc(self.cat_name.get(c, c))) for c in s.get('menu', []) if c in self.cat_name)
        desc = ' · ' + esc(s['description']) if s.get('description') else ''
        return '''<!doctype html>
<html lang="%(lang)s" data-base="%(base)s">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>try{var t=localStorage.getItem('tt-theme');if(t)document.documentElement.setAttribute('data-theme',t);var f=localStorage.getItem('tt-fs');if(f)document.documentElement.style.setProperty('--fs',f+'px');}catch(e){}
document.addEventListener('error',function(e){var i=e.target;if(i&&i.tagName==='IMG'){var b=i.closest('figure,.wp-caption,.thumb')||i;b.classList.add('img-missing');}},true);</script>
<title>%(title)s</title>
<meta name="description" content="%(description)s">
%(robots)s<link rel="canonical" href="%(canonical)s">
<meta property="og:site_name" content="%(site)s">
<meta property="og:type" content="%(og_type)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(description)s">
<meta property="og:url" content="%(canonical)s">
<link rel="alternate" type="application/rss+xml" title="%(site)s" href="%(feed)s">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="%(fonts)s">
<link rel="stylesheet" href="%(css)s">
</head>
<body class="%(body_class)s">
<a class="screen-reader-text" href="#content">Skip to content</a>
%(progress)s
<header class="site-header">
	<div class="wrap bar">
		<a class="site-title" href="%(home)s" rel="home">%(hourglass)s%(site)s</a>
		<button class="icon-btn menu-toggle" id="tt-menu-toggle" aria-expanded="false" aria-controls="tt-nav">Menu</button>
		<nav class="main-nav" id="tt-nav" aria-label="Main"><ul>%(menu)s</ul></nav>
		<button class="icon-btn" id="tt-theme" aria-label="Switch light or dark mode">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>
		</button>
	</div>
</header>
<div id="content">
%(body)s
</div>
<div class="wrap">
	<footer class="site-footer">
		<span>&copy; %(year)s %(site)s%(desc)s</span>
		<a href="%(feed)s">RSS</a>
	</footer>
</div>
<div class="toast" id="tt-toast" role="status" aria-live="polite"></div>
<script src="%(js)s"></script>
</body>
</html>
''' % {'lang': esc(s.get('language', 'en-US')), 'base': esc(self.base), 'title': esc(title), 'description': esc(description),
       'robots': robots, 'canonical': esc(self.canonical(path)), 'site': esc(s['title']), 'og_type': og_type,
       'feed': self.u('/feed.xml'), 'fonts': esc(FONTS), 'css': self.u('/assets/style.css') + self.asset_v,
       'js': self.u('/assets/theme.js') + self.asset_v, 'body_class': body_class,
       'progress': '<div class="progress" id="tt-progress"></div>' if singular else '',
       'home': self.u('/'), 'hourglass': HOURGLASS, 'menu': menu, 'body': body,
       'year': datetime.date.today().year, 'desc': desc}

    def search_form(self):
        return ('<form role="search" method="get" class="search-form" action="%s"><label>'
                '<span class="screen-reader-text">Search stories</span>'
                '<input type="search" class="search-field" placeholder="Search stories…" value="" name="s"></label>'
                '<button type="submit" class="search-submit" aria-label="Search"><svg viewBox="0 0 24 24" fill="none" '
                'stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/>'
                '<path d="m20 20-3.5-3.5"/></svg></button></form>') % self.u('/search/')

    def sidebar(self):
        s = self.site
        if s.get('about_photo'):
            avatar = '<img src="%s" alt="%s">' % (esc(self.u(s['about_photo'])), esc(s['about_title']))
        else:
            avatar = esc(s.get('author', s['title'])[:1].upper())
        counts = self.cat_counts()
        cats = ''.join('<li><a href="%s"><span>%s</span><em>%s</em></a></li>' % (
            self.u('/category/%s/' % c['slug']), esc(c['name']), format(counts[c['slug']], ','))
            for c in sorted(self.cats, key=lambda c: c['name']) if counts.get(c['slug']))
        recent = sorted(((c, p) for p in self.posts for c in p['comments']), key=lambda x: (x[0]['date'], x[0]['id']), reverse=True)[:5]
        rec = ''.join('<li><b>%s</b> on <a href="%s#comment-%d" lang="%s">%s</a></li>' % (
            esc(c['author']), self.u(p['path']), c['id'], p['lang'], esc(p['title'])) for c, p in recent)
        rec = '<section><h3>Recent comments</h3><ul class="recent">%s</ul></section>' % rec if rec else ''
        return ('<aside class="sidebar" aria-label="Sidebar"><section class="about"><div class="avatar-letter">%s</div>'
                '<h3>%s</h3><p>%s</p></section><section><h3>Categories</h3><ul class="cats">%s</ul></section>%s</aside>'
                ) % (avatar, esc(s['about_title']), esc(s['about']), cats, rec)

    def first_cat(self, p):
        if not p['cats']:
            return ''
        c = p['cats'][0]
        return '<span class="cat"><a href="%s">%s</a></span>' % (self.u('/category/%s/' % c), esc(self.cat_name.get(c, c)))

    def reading(self, p):
        if 'reading' not in p:
            n = len(strip_tags(strip_shortcodes(p['raw'])).split())
            p['reading'] = '%d min read' % max(1, int(n / 200 + 0.5))
        return p['reading']

    def row(self, p):
        n = len(p['comments'])
        return ('<article id="post-%s" class="entry-row post"><div class="when"><b>%s</b><span class="mono">%s</span></div>'
                '<div class="body">%s<h2 lang="%s"><a href="%s">%s</a></h2><div class="excerpt" lang="%s"><p>%s</p></div>'
                '<div class="meta mono"><span>%s</span><span>%s</span></div></div></article>\n') % (
            p['id'], fmt_date(p['date'], 'd'), fmt_date(p['date'], 'my'), self.first_cat(p), p['lang'],
            self.u(p['path']), esc(p['title']), p['lang'], p.setdefault('excerpt_html', excerpt_of(p)),
            self.reading(p), plural(n, 'comment') if n else 'No comments yet')

    def pagination(self, base_path, cur, total):
        if total < 2:
            return ''
        link = lambda n: self.u(base_path if n == 1 else '%spage/%d/' % (base_path, n))
        out = []
        if cur > 1:
            out.append('<a class="prev page-numbers" href="%s">← Newer</a>' % link(cur - 1))
        dots = False
        for n in range(1, total + 1):
            if n == cur:
                out.append('<span aria-current="page" class="page-numbers current">%d</span>' % n); dots = True
            elif n == 1 or n == total or abs(n - cur) <= 1:
                out.append('<a class="page-numbers" href="%s">%d</a>' % (link(n), n)); dots = True
            elif dots:
                out.append('<span class="page-numbers dots">…</span>'); dots = False
        if cur < total:
            out.append('<a class="next page-numbers" href="%s">Older →</a>' % link(cur + 1))
        return '<nav class="navigation pagination" aria-label="Posts"><div class="nav-links">%s</div></nav>' % '\n'.join(out)

    def listing(self, base_path, posts, title, intro='', lang='', current_cat='', noindex=False, body_class='archive'):
        per = int(self.site.get('posts_per_page', 10))
        total = max(1, -(-len(posts) // per))
        counts = self.cat_counts()
        top = sorted((c for c in self.cats if counts.get(c['slug'])), key=lambda c: -counts[c['slug']])[:8]
        chips = ''.join('<a class="chip" href="%s" aria-current="%s">%s</a>' % (
            self.u('/category/%s/' % c['slug']), 'true' if c['slug'] == current_cat else 'false', esc(c['name'])) for c in top)
        seg = ('<nav class="seg" aria-label="Language"><a href="%s" aria-current="%s">All</a>'
               '<a href="%s" lang="hi" aria-current="%s">हिंदी</a><a href="%s" aria-current="%s">English</a></nav>') % (
            self.u('/'), 'false' if lang else 'true', self.u('/lang/hi/'), 'true' if lang == 'hi' else 'false',
            self.u('/lang/en/'), 'true' if lang == 'en' else 'false')
        side = self.sidebar()
        for n in range(1, total + 1):
            chunk = posts[(n - 1) * per:n * per]
            rows = ''.join(self.row(p) for p in chunk) or '<p class="empty">No stories here yet. Try another filter or search.</p>'
            path = base_path if n == 1 else '%spage/%d/' % (base_path, n)
            body = '%s\n<div class="wrap layout">\n<main id="posts">\n<div class="filters">%s%s</div>\n<nav class="chips" aria-label="Categories">%s</nav>\n%s%s\n</main>\n%s\n</div>' % (
                intro if n == 1 or body_class != 'home blog' else '', seg, self.search_form(), chips, rows,
                self.pagination(base_path, n, total), side)
            t = title if n == 1 else '%s – Page %d' % (title, n)
            self.write(path, self.page(path, t, body, body_class=body_class, noindex=noindex))

    def archive_intro(self, label, heading, desc=''):
        d = '<div class="desc">%s</div>' % wpautop(desc) if desc else ''
        return '<section class="wrap archive-intro"><div class="label">%s</div><h1%s>%s</h1>%s</section>' % (
            label, ' lang="hi"' if is_hindi(heading) else '', esc(heading), d)

    # ---- single posts

    def comments_html(self, p):
        cs = p['comments']
        if not cs:
            return ''
        ids = {c['id'] for c in cs}
        kids = {}
        for c in cs:
            kids.setdefault(c['parent'] if c['parent'] in ids else 0, []).append(c)

        def render(c, depth):
            children = kids.get(c['id'], [])
            name = esc(c['author'] or 'Anonymous')
            if self.site.get('comment_author_links') and c.get('url', '').startswith('http'):
                name = '<a href="%s" rel="nofollow ugc noopener">%s</a>' % (esc(c['url']), name)
            d = datetime.datetime.strptime(c['date'], '%Y-%m-%d %H:%M:%S')
            sub = ''
            if children:
                inner = ''.join(render(k, depth + 1) for k in children)
                sub = '<ol class="children">%s</ol>' % inner if depth < 5 else inner
            item = ('<li id="comment-%d" class="comment%s%s"><div class="comment-body"><span class="avatar avatar-initial" aria-hidden="true">%s</span>'
                    '<div><div class="comment-meta-line"><span class="comment-author">%s</span><a class="mono" href="#comment-%d">%s</a></div>'
                    '<div class="comment-text" lang="%s">%s</div></div></div>') % (
                c['id'], ' bypostauthor' if c.get('by_site_author') else '', ' parent' if children else '',
                esc((c['author'] or 'A').strip()[:1].upper()), name, c['id'], fmt_date(d, 'long'),
                'hi' if is_hindi(c['content']) else 'en', render_comment(c['content']))
            if depth < 5:
                return item + sub + '</li>\n'
            return item + '</li>\n' + sub
        items = ''.join(render(c, 1) for c in kids.get(0, []))
        return ('<section id="comments" class="comments-area"><h2 class="comments-title">%s</h2><ol class="comment-list">%s</ol>'
                '<p class="mono">Comments are closed.</p></section>') % (plural(len(cs), 'comment'), items)

    def single(self, i):
        p = self.posts[i]
        older = self.posts[i + 1] if i + 1 < len(self.posts) else None
        newer = self.posts[i - 1] if i > 0 else None
        nav = '<a class="prev" href="%s"><span class="label">← Older</span><b lang="%s">%s</b></a>' % (
            self.u(older['path']), older['lang'], esc(older['title'])) if older else '<span></span>'
        if newer:
            nav += '<a class="next" href="%s"><span class="label">Newer →</span><b lang="%s">%s</b></a>' % (
                self.u(newer['path']), newer['lang'], esc(newer['title']))
        tags = ''.join('<a href="%s" rel="tag">%s</a>' % (self.u('/tag/%s/' % t), esc(self.tag_name.get(t, unquote(t)))) for t in p['tags'])
        tags = '<div class="tags">%s</div>' % tags if tags else ''
        body = '''<div class="wrap reader">
<div class="reader-tools"><a class="back" href="%(home)s">← All stories</a><div class="sizer">
<button class="icon-btn" data-tt-size="-1" aria-label="Smaller text">A−</button>
<button class="icon-btn" data-tt-size="1" aria-label="Larger text">A+</button>
<button class="icon-btn" id="tt-copy" data-url="%(canonical)s">Copy link</button></div></div>
<article id="post-%(id)s" class="single-entry post">
%(cat)s
<h1 class="entry-title" lang="%(lang)s">%(title)s</h1>
<div class="byline mono"><span>By %(author)s</span><time datetime="%(iso)s">%(date)s</time><span>%(reading)s</span></div>
<div class="entry-content" lang="%(lang)s">
%(content)s
</div>
%(tags)s
<nav class="post-nav" aria-label="More posts">%(nav)s</nav>
</article>
%(comments)s
</div>''' % {'home': self.u('/'), 'canonical': esc(self.canonical(p['path'])), 'id': p['id'], 'cat': self.first_cat(p),
             'lang': p['lang'], 'title': esc(p['title']), 'author': esc(self.site.get('author', '')),
             'iso': p['date'].strftime('%Y-%m-%dT%H:%M:%S+00:00'), 'date': fmt_date(p['date'], 'long'),
             'reading': self.reading(p), 'content': render_body(p['raw'], self.site, self.base), 'tags': tags, 'nav': nav,
             'comments': self.comments_html(p)}
        desc = html.unescape(p.setdefault('excerpt_html', excerpt_of(p)))[:300]
        self.write(p['path'], self.page(p['path'], '%s – %s' % (p['title'], self.site['title']), body,
                                        body_class='single single-post', description=desc, singular=True, og_type='article'))

    # ---- everything

    def build(self):
        s = self.site
        if os.path.isdir(self.out):
            shutil.rmtree(self.out)
        os.makedirs(os.path.join(self.out, 'assets'))
        h = hashlib.sha1()
        for f in sorted(os.listdir(os.path.join(ROOT, 'theme'))):
            data = open(os.path.join(ROOT, 'theme', f), 'rb').read()
            h.update(data)
            open(os.path.join(self.out, 'assets', f), 'wb').write(data)
        self.asset_v = '?v=' + h.hexdigest()[:8]
        static = os.path.join(ROOT, 'static')          # images and files you add later; copied as-is
        if os.path.isdir(static):
            shutil.copytree(static, self.out, dirs_exist_ok=True)

        posts = self.posts
        for i in range(len(posts)):
            self.single(i)

        # home
        intro = ['<section class="wrap intro"><div>']
        if s.get('eyebrow'):
            intro.append('<div class="label">%s</div>' % esc(s['eyebrow']))
        if s.get('show_headline'):
            intro.append('<h1>%s</h1><p>%s</p>' % (s.get('headline', ''), esc(s.get('intro', ''))))
        intro.append('</div><a class="turn" href="%s">%s%s</a></section>' % (self.u('/random/'), HOURGLASS, esc(s.get('random_label', 'Read a random story'))))
        home_title = '%s – %s' % (s['title'], s['description']) if s.get('description') else s['title']
        self.listing('/', posts, home_title, intro=''.join(intro), body_class='home blog')
        for lang, label in (('hi', 'हिंदी'), ('en', 'English')):
            self.listing('/lang/%s/' % lang, [p for p in posts if p['lang'] == lang], '%s – %s' % (label, s['title']),
                         lang=lang, noindex=True)
        # categories, tags, dates
        for c in self.cats:
            sel = [p for p in posts if c['slug'] in p['cats']]
            if sel:
                self.listing('/category/%s/' % c['slug'], sel, '%s – %s' % (c['name'], s['title']),
                             intro=self.archive_intro('Category', c['name'], c.get('description', '')), current_cat=c['slug'])
        by_tag, by_date = {}, {}
        for p in posts:
            for t in p['tags']:
                by_tag.setdefault(t, []).append(p)
            d = p['date']
            for key, name in (('/%04d/' % d.year, str(d.year)),
                              ('/%04d/%02d/' % (d.year, d.month), d.strftime('%B %Y')),
                              ('/%04d/%02d/%02d/' % (d.year, d.month, d.day), fmt_date(d, 'long'))):
                by_date.setdefault((key, name), []).append(p)
        for t, sel in by_tag.items():
            name = self.tag_name.get(t, unquote(t))
            self.listing('/tag/%s/' % t, sel, '%s – %s' % (name, s['title']), intro=self.archive_intro('Tag', name))
        for (key, name), sel in by_date.items():
            self.listing(key, sel, '%s – %s' % (name, s['title']), intro=self.archive_intro('Archive', name), noindex=True)

        # search, random, 404
        index = [{'i': p['id'], 't': p['title'], 'u': p['path'], 'x': html.unescape(p['excerpt_html']),
                  'd': fmt_date(p['date'], 'd'), 'm': fmt_date(p['date'], 'my'), 'l': p['lang'],
                  'c': self.cat_name.get(p['cats'][0], '') if p['cats'] else '', 'cs': p['cats'][0] if p['cats'] else '',
                  'r': self.reading(p), 'n': len(p['comments']),
                  'k': ' '.join(self.tag_name.get(t, t) for t in p['tags'])} for p in posts]
        self.write('/search.json', json.dumps(index, ensure_ascii=False, separators=(',', ':')))
        self.pages_written -= 1
        body = ('%s\n<div class="wrap layout">\n<main id="posts"><div class="filters">%s</div>'
                '<div id="tt-search-results"><p class="empty">Type a word above to search all %d stories.</p></div>'
                '<noscript><p class="empty">Search needs JavaScript. You can browse by category instead.</p></noscript></main>\n%s\n</div>') % (
            '<section class="wrap archive-intro"><div class="label">Search</div><h1 id="tt-search-title">Search</h1></section>',
            self.search_form(), len(posts), self.sidebar())
        self.write('/search/', self.page('/search/', 'Search – ' + s['title'], body, body_class='search', noindex=True))
        body = ('<section class="wrap archive-intro"><div class="label">Random</div><h1>Turning the hourglass…</h1>'
                '<div class="desc"><p><a href="%s">Back to all stories</a></p></div></section>'
                '<script>var u=%s;location.replace(document.documentElement.getAttribute("data-base")+u[Math.floor(Math.random()*u.length)]);</script>'
                ) % (self.u('/'), json.dumps([p['path'] for p in posts]))
        self.write('/random/', self.page('/random/', 'Random story – ' + s['title'], body, noindex=True))
        body = ('<section class="wrap archive-intro"><div class="label">404</div><h1>This page slipped through the hourglass.</h1>'
                '<div class="desc"><p>The link may be old. Search for the story, or start from the latest posts.</p></div></section>'
                '<div class="wrap layout"><main><div class="filters">%s</div><p><a class="turn" href="%s">Back to all stories</a></p></main>%s</div>'
                ) % (self.search_form(), self.u('/'), self.sidebar())
        self.write('/404.html', self.page('/404.html', 'Page not found – ' + s['title'], body, body_class='error404', noindex=True))

        # feed, sitemap, robots
        items = ''.join('<item><title>%s</title><link>%s</link><guid isPermaLink="true">%s</guid><pubDate>%s</pubDate>'
                        '<description>%s</description><content:encoded><![CDATA[%s]]></content:encoded></item>\n' % (
            esc(p['title']), esc(self.canonical(p['path'])), esc(self.canonical(p['path'])),
            p['date'].strftime('%a, %d %b %Y %H:%M:%S +0000'), p['excerpt_html'],
            render_body(p['raw'], s, s['site_url']).replace(']]>', ']]&gt;')) for p in posts[:10])
        self.write('/feed.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">'
                   '<channel><title>%s</title><link>%s/</link><description>%s</description><language>%s</language>\n%s</channel></rss>\n' % (
                       esc(s['title']), s['site_url'], esc(s.get('description', '')), esc(s.get('language', 'en-US')), items))
        urls = ['<url><loc>%s/</loc></url>' % s['site_url']]
        urls += ['<url><loc>%s</loc><lastmod>%s</lastmod></url>' % (esc(self.canonical(p['path'])), p['date'].strftime('%Y-%m-%d')) for p in posts]
        urls += ['<url><loc>%s</loc></url>' % self.canonical('/category/%s/' % c['slug']) for c in self.cats if any(c['slug'] in p['cats'] for p in posts)]
        self.write('/sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n' % '\n'.join(urls))
        self.write('/robots.txt', 'User-agent: *\nDisallow: /\n' if self.preview else 'User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n' % s['site_url'])
        self.write('/.nojekyll', '')
        self.pages_written -= 4
        # the address list is used to check that nothing moved
        with open(os.path.join(ROOT, 'reports', 'post-addresses.txt') if os.path.isdir(os.path.join(ROOT, 'reports')) else os.devnull, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.canonical(p['path']) for p in posts) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--preview', nargs='?', const='', default=None, metavar='/repo-name',
                    help='build for a temporary address; pages are hidden from search engines')
    ap.add_argument('--out', default='docs')
    ap.add_argument('--serve', action='store_true', help='build a local preview and serve it at http://localhost:8000')
    a = ap.parse_args()
    if a.serve:
        a.preview, a.out = '', '_preview'
    site = Site(a)
    site.build()
    print('Built %d posts and %d pages into %s/%s' % (len(site.posts), site.pages_written, a.out,
          '  (PREVIEW build: hidden from search engines)' if site.preview else ''))
    print('Comments shown: %d' % sum(len(p['comments']) for p in site.posts))
    for p in site.problems:
        print('PROBLEM:', p)
    if site.problems:
        sys.exit(1)
    if a.serve:
        import functools, http.server
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=site.out)
        print('Preview at http://localhost:8000  (Ctrl+C to stop)')
        http.server.ThreadingHTTPServer(('127.0.0.1', 8000), handler).serve_forever()


if __name__ == '__main__':
    main()
