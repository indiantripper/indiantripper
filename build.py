#!/usr/bin/env python3
"""Builds the static site from content/ into docs/.

    python3 build.py                      production build for https://indiantripper.in
    python3 build.py --preview /repo-name build for a temporary address such as
                                          https://USER.github.io/repo-name/ (hidden from search engines)
    python3 build.py --serve              build, then preview at http://localhost:8000

Install the frontmatter parser with: python3 -m pip install -r requirements.txt
"""
import argparse, datetime, hashlib, html, json, os, re, shutil, sys
from urllib.parse import quote, unquote
from html.parser import HTMLParser
try:
    import yaml
except ImportError:
    raise SystemExit("Install build dependencies first: python3 -m pip install -r requirements.txt")

class ContentLoader(yaml.SafeLoader):
    """CMS YAML uses strings for dates and words such as Yes/No."""

ContentLoader.yaml_implicit_resolvers = {
    key: [(tag, regex) for tag, regex in entries
          if tag not in ('tag:yaml.org,2002:bool', 'tag:yaml.org,2002:timestamp')]
    for key, entries in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


ROOT = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(ROOT, 'content')
esc = html.escape

BLOCKS = ('(?:table|thead|tfoot|caption|col|colgroup|tbody|tr|td|th|div|dl|dd|dt|ul|ol|li|pre|form|map|area|'
          'blockquote|address|style|p|h[1-6]|hr|fieldset|legend|section|article|aside|hgroup|header|footer|'
          'nav|figure|figcaption|details|menu|summary)')
HOURGLASS = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
             'aria-hidden="true"><path d="M6 2h12M6 22h12M7 2c0 5 10 6 10 10S7 17 7 22M17 2c0 5-10 6-10 10s10 5 10 10"/></svg>')
FONTS = ('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;1,400&'
         'family=Noto+Serif+Devanagari:wght@400;500&family=DM+Sans:wght@400;500&display=swap')


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


def local_image_width(src):
    """Read local image headers so small originals are never enlarged to column width."""
    path = unquote(src.split('?', 1)[0])
    if not path.startswith('/images/'):
        return None
    static = os.path.realpath(os.path.join(ROOT, 'static'))
    file = os.path.realpath(os.path.join(static, path.lstrip('/')))
    if os.path.commonpath([static, file]) != static:
        return None
    try:
        with open(file, 'rb') as stream:
            data = stream.read()
        if data.startswith(b'\x89PNG\r\n\x1a\n') and len(data) >= 24:
            return int.from_bytes(data[16:20], 'big')
        if data.startswith((b'GIF87a', b'GIF89a')) and len(data) >= 10:
            return int.from_bytes(data[6:8], 'little')
        if data.startswith(b'\xff\xd8'):
            pos = 2
            rotate = False
            while pos + 4 <= len(data):
                if data[pos] != 255:
                    break
                while pos < len(data) and data[pos] == 255:
                    pos += 1
                marker = data[pos]; pos += 1
                if marker in (0xd8, 0x01) or 0xd0 <= marker <= 0xd7:
                    continue
                if marker in (0xd9, 0xda):
                    break
                length = int.from_bytes(data[pos:pos + 2], 'big')
                if length < 2:
                    break
                if marker == 0xe1 and data[pos + 2:pos + 8] == b'Exif\0\0':
                    tiff = pos + 8
                    order = 'little' if data[tiff:tiff + 2] == b'II' else 'big'
                    directory = tiff + int.from_bytes(data[tiff + 4:tiff + 8], order)
                    count = int.from_bytes(data[directory:directory + 2], order)
                    for entry in range(directory + 2, min(directory + 2 + count * 12, pos + length), 12):
                        if int.from_bytes(data[entry:entry + 2], order) == 0x112:
                            rotate = int.from_bytes(data[entry + 8:entry + 10], order) in (5, 6, 7, 8)
                if marker in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf) and pos + 7 <= len(data):
                    return int.from_bytes(data[pos + 3:pos + 5] if rotate else data[pos + 5:pos + 7], 'big')
                pos += length
        if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
            if data[12:16] == b'VP8X' and len(data) >= 30:
                return 1 + int.from_bytes(data[24:27], 'little')
            if data[12:16] == b'VP8L' and len(data) >= 25:
                return 1 + (int.from_bytes(data[21:25], 'little') & 0x3fff)
            if data[12:16] == b'VP8 ' and len(data) >= 30:
                return int.from_bytes(data[26:28], 'little') & 0x3fff
    except (OSError, IndexError, ValueError):
        pass
    return None


def size_image_figure(match):
    figure = match.group(0)
    image = re.search(r'<img\b[^>]*\bsrc=([\"\'])(.*?)\1', figure, flags=re.S)
    width = local_image_width(html.unescape(image.group(2))) if image else None
    if not width:
        return figure
    tag = re.match(r'<figure\b[^>]*>', figure).group(0)
    style = re.search(r'\bstyle=([\"\'])(.*?)\1', tag, flags=re.S)
    rule = '--image-width:%spx;' % width
    if style:
        updated = tag[:style.start(2)] + style.group(2).rstrip(';') + ';' + rule + tag[style.end(2):]
    else:
        updated = tag[:-1] + ' style="' + rule + '">'
    return updated + figure[len(tag):]


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
    body = re.sub(r'<figure\b[^>]*>.*?</figure>', size_image_figure, body, flags=re.S)
    host = site['site_url'].split('//', 1)[1]
    # links to the blog's own address follow the current build (production or preview)
    body = re.sub(r'(href=["\'])https?://(?:www\.)?' + re.escape(host) + r'(?=[/"\'])', r'\1' + base, body)
    if base:
        body = re.sub(r'''(\bhref=["'])(/(?!/)[^"']*)''', lambda m: m.group(1) + (m.group(2) if m.group(2) == base or m.group(2).startswith(base + '/') else base + m.group(2)), body)
        body = re.sub(r'''(\b(?:src|poster)=["'])(/images/)''', lambda m: m.group(1) + base + m.group(2), body)
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


class VerseText(HTMLParser):
    """Extract authored line breaks without image captions or embedded markup."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('figure', 'figcaption', 'script', 'style'):
            self.hidden += 1
        if tag == 'br' and not self.hidden:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('figure', 'figcaption', 'script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'div', 'h1', 'h2', 'h3', 'blockquote', 'li') and not self.hidden:
            self.parts.append('\n')

    def handle_data(self, text):
        if not self.hidden:
            self.parts.append(text)


def verse_lines(post):
    if post.get('form') != 'poem' or post.get('excerpt'):
        return []
    raw = re.sub(r'\[caption[^\]]*\].*?\[/caption\]', '', post['raw'], flags=re.S)
    parser = VerseText()
    parser.feed(strip_shortcodes(raw))
    return [line.strip() for line in ''.join(parser.parts).splitlines() if line.strip()][:4]


def preview_of(post):
    lines = verse_lines(post)
    return '<br>'.join(esc(line) for line in lines) if lines else excerpt_of(post)


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
    with open(path, encoding='utf-8') as source:
        text = source.read().replace('\r\n', '\n')
    meta = {}
    if text.startswith('---\n'):
        head, separator, body = text[4:].partition('\n---\n')
        if not separator:
            raise ValueError('missing closing frontmatter delimiter')
        values = yaml.load(head, Loader=ContentLoader) or {}
        if not isinstance(values, dict):
            raise ValueError('frontmatter must be a mapping')
        for key, value in values.items():
            if isinstance(value, list):
                if any(isinstance(item, (dict, list)) for item in value):
                    raise ValueError('frontmatter lists must contain simple values')
                value = ', '.join(str(item) for item in value)
            elif isinstance(value, datetime.datetime):
                value = value.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(value, datetime.date):
                value = value.isoformat()
            elif isinstance(value, dict):
                raise ValueError('nested frontmatter objects are not supported')
            meta[str(key).lower()] = '' if value is None else str(value)
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
            try:
                meta, raw = parse_file(full)
            except (ValueError, yaml.YAMLError) as error:
                problems.append('%s: invalid frontmatter: %s' % (f, error))
                continue
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
            slug = meta.get('slug') or re.sub(r'^\d{4}-\d{2}-\d{2}-', '', stem).strip().lower().replace(' ', '-').strip('-')
            # CMS filenames keep the creation date, so editing a title or publish date
            # does not change the address. Existing explicit paths always take precedence.
            url_date = d
            if not meta.get('path') and re.match(r'^\d{4}-\d{2}-\d{2}-', stem):
                url_date = datetime.datetime.strptime(stem[:10], '%Y-%m-%d')
            path = meta.get('path') or '/%04d/%02d/%02d/%s/' % (url_date.year, url_date.month, url_date.day, quote(slug, safe='-_.~').lower())
            if not path.endswith('/'):
                path += '/'
            cfile = os.path.join(CONTENT, 'comments', os.path.relpath(dirpath, pdir), stem + '.json')
            comments = json.load(open(cfile, encoding='utf-8')) if os.path.exists(cfile) else []
            posts.append({
                'title': meta['title'], 'date': d, 'path': path, 'id': meta.get('id') or hashlib.sha1(path.encode('utf-8')).hexdigest()[:12], 'raw': raw,
                'excerpt': meta.get('excerpt', ''),
                'form': 'poem' if meta.get('form') == 'poem' else 'prose',
                'image': meta.get('image', ''), 'image_alt': meta.get('image_alt', ''),
                'share_image': meta.get('share_image', ''), 'share_slug': meta.get('share_slug', ''),
                'cats': [c.strip() for c in meta.get('categories', '').split(',') if c.strip()],
                'tags': [c.strip() for c in meta.get('tags', '').split(',') if c.strip()],
                'comments': comments, 'file': f,
                'lang': meta['language'] if meta.get('language') in ('hi', 'en') else 'hi' if is_hindi(meta['title']) else 'en',
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
        comments_file = os.path.join(CONTENT, 'comments.json')
        self.comments_config = {}
        if os.path.exists(comments_file):
            with open(comments_file, encoding='utf-8') as source:
                self.comments_config = json.load(source)
        if self.comments_config.get('enabled'):
            cfg = self.comments_config
            if not re.fullmatch(r'https://[a-z0-9]+\.supabase\.co', cfg.get('supabase_url', '')) or not cfg.get('publishable_key', '').startswith('sb_publishable_') or not cfg.get('turnstile_site_key'):
                raise ValueError('Comments need a Supabase URL, publishable key and Turnstile site key. Never put a secret key here.')
        self.posts, self.problems = load(self.site)
        self.share_paths = self.load_share_paths()
        counts = self.cat_counts()
        self.cats.sort(key=lambda c: (-counts.get(c['slug'], 0), c['name'].casefold()))
        self.pages_written = 0
        self.asset_v = ''

    def load_share_paths(self):
        config = os.path.join(CONTENT, 'share-links.json')
        slugs = {}
        if os.path.exists(config):
            with open(config, encoding='utf-8') as source:
                slugs = json.load(source)
        if not isinstance(slugs, dict):
            raise ValueError('share-links.json must map post IDs to short slugs')
        known = {p['id'] for p in self.posts}
        unknown = set(slugs) - known
        if unknown:
            raise ValueError('Share links reference missing posts: ' + ', '.join(sorted(unknown)))
        paths, used = {}, set()
        originals = {unquote(p['path']).casefold() for p in self.posts}
        for p in self.posts:
            slug = p.get('share_slug') or slugs.get(p['id'], '')
            if not slug:
                continue
            if not isinstance(slug, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
                raise ValueError('Use lowercase Roman letters, numbers and hyphens for share_slug: ' + p['file'])
            path = '/read/' + slug + '/'
            if path in used or path.casefold() in originals:
                raise ValueError('Duplicate share address: ' + path)
            paths[p['id']] = path
            used.add(path)
        return paths

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

    def category_label(self, slug):
        c = next((c for c in self.cats if c['slug'] == slug), None)
        return esc(c.get('name_en') or c['name']) if c else esc(slug)

    def category_navigation(self, current):
        counts = self.cat_counts()
        links = ''.join('<a href="%s"%s><span>%s</span><span class="nav-count">%s</span></a>' % (
            self.u('/category/%s/' % c['slug']), ' aria-current="page"' if c['slug'] == current else '',
            self.category_label(c['slug']), counts[c['slug']]) for c in self.cats if counts.get(c['slug']))
        return '<nav class="browse-nav" aria-label="Threads">%s</nav>' % links

    def year_navigation(self, current):
        counts = {}
        for p in self.posts:
            y = p['date'].year
            counts[y] = counts.get(y, 0) + 1
        links = ''.join('<a href="%s"%s><span>%s</span><span class="nav-count">%s</span></a>' % (
            self.u('/%s/' % y), ' aria-current="page"' if str(y) == str(current) else '', y, counts[y])
            for y in sorted(counts, reverse=True))
        return '<nav class="browse-nav year-nav" aria-label="Years">%s</nav>' % links

    def home_extras(self):
        collection = json.load(open(os.path.join(CONTENT, 'start-here.json'), encoding='utf-8'))
        by_id = {p['id']: p for p in self.posts}
        picks, seen = [], set()
        for group in collection['groups']:
            for choice in group['posts']:
                p = by_id.get(choice['post_id'])
                if p is not None and p['id'] not in seen:
                    seen.add(p['id'])
                    picks.append({'path': self.u(p['path']), 'title': html.unescape(p['title']),
                                  'note': choice['note'], 'date': p['date'].strftime('%B %Y'), 'lang': p['lang']})
        earlier = ''
        if picks:
            pick = picks[0]
            earlier = ('<section class="earlier-page" data-daily-favourites="%s"><div><p class="label">FROM AN EARLIER PAGE</p><p class="old-date">%s</p></div>'
                       '<div><h2 lang="%s"><a href="%s">%s</a></h2><p class="earlier-note">%s</p>'
                       '<a class="text-link" href="%s">Revisit this story ↗</a></div></section>') % (
                           esc(json.dumps(picks, ensure_ascii=False)), esc(pick['date']), pick['lang'],
                           esc(pick['path']), esc(pick['title']), esc(pick['note']), esc(pick['path']))
        links = ' <span aria-hidden="true">·</span> '.join('<a href="%s">%s</a>' % (self.u('/%s/' % y), y) for y in [2026, 2020, 2014, 2008])
        return earlier + ('<section class="years-invitation"><div><p class="label">A LIFE, IN CHAPTERS</p><h2>Some things change.<br><em>Some pages stay.</em></h2></div>'
                          '<div><p>College days. New cities. Long walks.<br>A few pets, and a lot of passing thoughts.</p><div class="year-links">%s</div>'
                          '<a class="text-link" href="%s">Wander through the years →</a></div></section>') % (links, self.u('/years/'))

    def post_image(self, post):
        image = post.get('share_image') or post.get('image', '')
        if not image:
            match = re.search(r'''<img\b[^>]*\bsrc=["'](/images/[^"']+)["']''', post['raw'])
            image = html.unescape(match.group(1)) if match else ''
        if image.startswith('/images/') and os.path.isfile(os.path.join(ROOT, 'static', image.lstrip('/'))):
            return image, post.get('image_alt') or html.unescape(post['title'])
        if post.get('share_image') or post.get('image'):
            self.problems.append('Missing local share image for %s: %s' % (post['file'], image))
        return '/images/share/time-turner.jpg', 'Time Turner — Stories from my life'

    SOCIAL_CARD_BYTES = 200 * 1024

    def social_card(self, image):
        """Return a preview-sized copy of a share image for link previews.

        Messaging apps skip preview images that are too heavy, so any local image above
        SOCIAL_CARD_BYTES is copied at a smaller size into the built site. The original stays
        in the article. If the image library is missing or the file cannot be read, the
        original address is returned unchanged.
        """
        cache = self.__dict__.setdefault('_social_cards', {})
        if image in cache:
            return cache[image]
        cache[image] = image
        source = os.path.join(ROOT, 'static', image.lstrip('/'))
        try:
            if not image.startswith('/images/') or os.path.getsize(source) <= self.SOCIAL_CARD_BYTES:
                return image
            from io import BytesIO
            from PIL import Image, ImageOps
            with Image.open(source) as opened:
                picture = ImageOps.exif_transpose(opened)
                if picture.mode in ('RGBA', 'LA', 'P'):
                    picture = picture.convert('RGBA')
                    flat = Image.new('RGB', picture.size, (255, 255, 255))
                    flat.paste(picture, mask=picture.split()[-1])
                    picture = flat
                else:
                    picture = picture.convert('RGB')
            data = None
            for side in (1200, 1000, 800, 600):
                small = picture.copy()
                small.thumbnail((side, side), Image.LANCZOS)
                for quality in (82, 74, 66, 58):
                    buffer = BytesIO()
                    small.save(buffer, 'JPEG', quality=quality, optimize=True)
                    if buffer.tell() <= self.SOCIAL_CARD_BYTES:
                        data = buffer.getvalue()
                        break
                if data:
                    break
            if not data:
                return image
            card = '/images/share/auto/%s.jpg' % hashlib.sha1(image.encode('utf-8') + data).hexdigest()[:16]
            target = os.path.join(self.out, card.lstrip('/'))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, 'wb') as handle:
                handle.write(data)
            cache[image] = card
        except Exception as error:      # never let a preview image stop the blog from publishing
            print('Share preview kept at full size for %s (%s)' % (image, error))
        return cache[image]

    def share_controls(self, post, image):
        title = html.unescape(post['title'])
        url = self.canonical(self.share_paths.get(post['id'], post['path']))
        whatsapp = 'https://wa.me/?text=' + quote(title + '\n' + url, safe='')
        return ('<details class="post-share" data-share-title="%s" data-share-url="%s" data-share-image="%s">'
                '<summary class="share-trigger"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M12 16V3m-5 5 5-5 5 5M4 13v7h16v-7"/></svg>Share</summary>'
                '<div class="share-panel"><p class="share-heading">Share this post</p>'
                '<div class="share-preview"><img src="%s" alt="" width="240" height="126"><strong lang="%s">%s</strong><span>indiantripper.in</span></div>'
                '<div class="share-actions"><button type="button" data-share-native hidden>Share…</button>'
                '<a href="%s" target="_blank" rel="noopener noreferrer">WhatsApp</a>'
                '<button type="button" data-share-copy>Copy link</button>'
                '<button type="button" data-share-image-native hidden>Share image</button>'
                '<a href="%s" download>Save image</a></div>'
                '<label class="share-manual" hidden>Post link<input type="text" readonly value="%s" aria-label="Post link"></label>'
                '<p class="share-status" role="status" aria-live="polite"></p></div></details>') % (
                    esc(title, quote=True), esc(url, quote=True), esc(self.u(image), quote=True),
                    esc(self.u(image), quote=True), post['lang'], esc(title), esc(whatsapp, quote=True),
                    esc(self.u(image), quote=True), esc(url, quote=True))

    def page(self, path, title, body, body_class='', description='', singular=False, noindex=False, og_type='website', story_filter=None, social_image='/images/share/time-turner.jpg', social_alt='Time Turner — Stories from my life'):
        s = self.site
        description = description or s['description']
        robots = '<meta name="robots" content="noindex, nofollow">\n' if (noindex or self.preview) else ''
        if story_filter is None:
            story_filter = self.story_language_control('/')
        icons = {
            'moon': '<path d="M20 15A8 8 0 0 1 9 4a8 8 0 1 0 11 11Z"/>',
            'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
            'user': '<circle cx="12" cy="8" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/>',
            'settings': '<path d="M3 6h18M3 18h18"/><circle cx="8" cy="6" r="3"/><circle cx="16" cy="18" r="3"/>',
            'search': '<circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/>'}
        icon = lambda name: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true">%s</svg>' % icons[name]
        selected = lambda match: ' aria-current="page"' if match else ''
        return '''<!doctype html>
<html lang="%(lang)s" data-base="%(base)s">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<script>try{var t=localStorage.getItem('tt-theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t;var f=Number(localStorage.getItem('tt-fs-v2'));if(f>=19&&f<=27)document.documentElement.style.setProperty('--fs',f+'px');}catch(e){}
document.addEventListener('error',function(e){var i=e.target;if(i&&i.tagName==='IMG'){i.classList.add('img-missing');var f=i.closest('figure,.wp-caption');if(f)f.classList.add('media-missing');}},true);</script>
<title>%(title)s</title><meta name="description" content="%(description)s">
%(robots)s<link rel="canonical" href="%(canonical)s">
<meta property="og:site_name" content="%(site)s"><meta property="og:type" content="%(og_type)s"><meta property="og:title" content="%(title)s"><meta property="og:description" content="%(description)s"><meta property="og:url" content="%(canonical)s">
<meta property="og:image" content="%(social_image)s"><meta property="og:image:alt" content="%(social_alt)s">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="%(title)s"><meta name="twitter:description" content="%(description)s"><meta name="twitter:image" content="%(social_image)s">
<link rel="icon" type="image/svg+xml" href="%(favicon)s"><meta name="color-scheme" content="light dark"><link rel="alternate" type="application/rss+xml" title="%(site)s" href="%(feed)s">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="%(fonts)s"><link rel="stylesheet" href="%(css)s">
</head><body class="%(body_class)s"><a class="screen-reader-text" href="#content">Skip to content</a>
<header class="site-header wrap">%(brand)s
<nav class="main-nav" aria-label="Main"><a class="desktop-nav-link" href="%(start)s"%(start_current)s>Favourites</a><a class="desktop-nav-link" href="%(threads)s"%(threads_current)s>Threads</a><a class="desktop-nav-link" href="%(years)s"%(years_current)s><span class="nav-long">Through the years</span><span class="nav-short">Years</span></a>
<details class="mobile-menu"><summary class="icon-btn" aria-label="Open menu"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg></summary><nav class="mobile-menu-panel" aria-label="Explore"><a href="%(start)s">Favourites</a><a href="%(threads)s">Threads</a><a href="%(years)s">Through the years</a><a href="%(about)s">About Harsh</a></nav></details>
<a class="icon-btn profile-link" href="%(about)s" aria-label="About Harsh">%(user_icon)s</a><a class="icon-btn" href="%(search)s" aria-label="Search the notebook">%(search_icon)s</a>
<button class="icon-btn" id="tt-theme" aria-label="Switch light or dark mode"><span class="theme-dark">%(moon)s</span><span class="theme-light">%(sun)s</span></button>
<details class="preferences"><summary class="icon-btn" aria-label="Reading controls">%(settings_icon)s</summary><div class="preferences-panel"><h2>Reading comfort</h2><div class="preference-row"><span>Text size</span><div class="sizer"><button class="icon-btn" data-tt-size="-1" aria-label="Smaller text">A−</button><button class="icon-btn" data-tt-size="1" aria-label="Larger text">A+</button></div></div>%(story_filter)s</div></details></nav></header>
<div id="content">%(body)s</div>
<footer class="wrap site-footer"><div><a class="footer-title" href="%(home)s">%(site)s</a><p>Somewhere between a memory and a thought.</p></div><nav aria-label="Footer"><a href="%(start)s">Favourites</a><a href="%(threads)s">Threads</a><a href="%(years)s">The years</a><a href="%(about)s">About</a><a href="%(random)s">Surprise me</a><a href="%(feed)s">RSS</a><span>© %(year)s Harsh</span></nav></footer>
<div class="toast" id="tt-toast" role="status" aria-live="polite"></div><script src="%(js)s" defer></script>%(comments_script)s</body></html>''' % {
            'lang': esc(s.get('language', 'en-US')), 'base': esc(self.base), 'title': esc(html.unescape(title)),
            'description': esc(description), 'robots': robots, 'canonical': esc(self.canonical(path)),
            'site': esc(s['title']), 'og_type': og_type, 'feed': self.u('/feed.xml'), 'fonts': esc(FONTS),
            'favicon': self.u('/favicon.svg') + '?v=sprout1',
            'css': self.u('/assets/style.css') + self.asset_v, 'js': self.u('/assets/theme.js') + self.asset_v,
            'brand': ('<h1 class="site-brand"><a class="site-title" href="%s" rel="home">%s</a></h1>' if path == '/' else '<a class="site-title" href="%s" rel="home">%s</a>') % (self.u('/'), esc(s['title'])),
            'body_class': body_class, 'home': self.u('/'), 'body': body, 'year': datetime.date.today().year,
            'start': self.u('/favourites/'), 'start_current': selected(path == '/favourites/'),
            'threads': self.u('/threads/'), 'years': self.u('/years/'), 'about': self.u('/about/'),
            'search': self.u('/search/'), 'random': self.u('/random/'),
            'threads_current': selected(path.startswith(('/threads/', '/category/'))),
            'years_current': selected(path.startswith('/years/') or re.match(r'^/\d{4}/', path)),
            'user_icon': icon('user'), 'search_icon': icon('search'), 'moon': icon('moon'), 'sun': icon('sun'),
            'settings_icon': icon('settings'), 'story_filter': story_filter,
            'comments_script': ('<script src="%s" defer></script>' % esc(self.u('/assets/comments.js') + self.asset_v)) if singular and self.comments_config.get('enabled') else '',
            'social_image': esc(self.canonical(social_image)), 'social_alt': esc(social_alt)}

    def search_form(self):
        return ('<form role="search" method="get" class="search-form" action="%s"><label>'
                '<span class="screen-reader-text">Search stories</span>'
                '<input type="search" class="search-field" placeholder="Search stories…" value="" name="s"></label>'
                '<button type="submit" class="search-submit" aria-label="Search"><svg viewBox="0 0 24 24" fill="none" '
                'stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/>'
                '<path d="m20 20-3.5-3.5"/></svg></button></form>') % self.u('/search/')

    def sidebar(self):
        return ''

    def first_cat(self, p):
        if not p['cats']:
            return ''
        c = p['cats'][0]
        return '<span class="cat"><a href="%s">%s</a></span>' % (self.u('/category/%s/' % c), self.category_label(c))

    def reading(self, p):
        if 'reading' not in p:
            n = len(strip_tags(strip_shortcodes(p['raw'])).split())
            p['reading'] = '%d min read' % max(1, int(n / 200 + 0.5))
        return p['reading']

    def thumbnail(self, post):
        if 'thumbnail' not in post:
            candidates = [post.get('image', '')] + re.findall(r'''<img\b[^>]*\bsrc=["'](/images/[^"']+)["']''', post['raw'])
            post['thumbnail'] = ''
            for candidate in candidates:
                image = html.unescape(candidate).split('?', 1)[0]
                if image.startswith('/images/') and image.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) and (local_image_width(image) or 0) >= 320:
                    post['thumbnail'] = image
                    break
        return post['thumbnail']

    def start_here(self):
        collection = json.load(open(os.path.join(CONTENT, 'start-here.json'), encoding='utf-8'))
        by_id = {post['id']: post for post in self.posts}
        sections, number = [], 0
        for group in collection['groups']:
            cards = []
            for choice in group['posts']:
                post = by_id.get(choice['post_id'])
                if post is None:
                    self.problems.append('Start here references missing post: %s' % choice['post_id'])
                    continue
                number += 1
                image = self.thumbnail(post)
                picture = '<img class="start-thumb" src="%s" alt="" loading="lazy" width="144" height="108">' % esc(self.u(image)) if image else ''
                cards.append('<a class="start-card%s" href="%s"><span class="start-meta">%02d · %s · %s</span>'
                             '<h3 lang="%s">%s</h3>%s<p>%s</p></a>' % (
                                 ' has-image' if image else '', self.u(post['path']), number,
                                 'हिंदी' if post['lang'] == 'hi' else 'English', post['date'].year,
                                 post['lang'], esc(html.unescape(post['title'])), picture, esc(choice['note'])))
            sections.append('<section class="start-group"><h2>%s</h2><div class="start-grid">%s</div></section>' % (esc(group['title']), ''.join(cards)))
        body = '<main class="wrap start-page"><h1 class="screen-reader-text">Favourites</h1>%s</main>' % ''.join(sections)
        self.write('/favourites/', self.page('/favourites/', 'Favourites – ' + self.site['title'], body, body_class='favourites', description=collection['description']))
        # Preserve the former introduction URL for existing bookmarks and shared links.
        destination = self.u('/favourites/')
        redirect = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex"><meta http-equiv="refresh" content="0;url=%s"><link rel="canonical" href="%s"><title>Favourites – %s</title></head><body><p><a href="%s">Continue to Favourites</a></p></body></html>' % (esc(destination), esc(self.canonical('/favourites/')), esc(self.site['title']), esc(destination))
        self.write('/start-here/', redirect)

    def row(self, p):
        n = len(p['comments'])
        comments = '<span>%s</span>' % plural(n, 'comment') if n else ''
        image = self.thumbnail(p)
        picture = '<a class="row-thumbnail" href="%s" aria-label="Read %s"><img src="%s" alt="" loading="lazy" width="160" height="120"></a>' % (self.u(p['path']), esc(html.unescape(p['title'])), esc(self.u(image))) if image else ''
        classes = (' has-thumbnail' if image else '') + (' is-poem' if verse_lines(p) else '')
        return ('<article id="post-%s" class="entry-row post%s"><div class="when"><time datetime="%s">%s</time><span>%s</span></div>'
                '<div class="body">%s<h2 lang="%s"><a href="%s">%s</a></h2>%s<div class="excerpt%s" lang="%s"><p>%s</p></div>'
                '<div class="meta"><span>%s</span>%s</div></div><span class="row-arrow" aria-hidden="true">↗</span></article>\n') % (
            esc(p['id']), classes, p['date'].strftime('%Y-%m-%d'), p['date'].strftime('%d %b').lstrip('0').upper(), p['date'].year,
            self.first_cat(p), p['lang'], self.u(p['path']), esc(html.unescape(p['title'])), picture,
            ' verse' if verse_lines(p) else '', p['lang'], preview_of(p), self.reading(p), comments)

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

    def story_language_control(self, root, lang=''):
        options = ''.join('<option value="%s"%s>%s</option>' % (
            self.u(root if not code else root + 'lang/%s/' % code),
            ' selected' if lang == code else '', label)
            for code, label in [('', 'All languages'), ('hi', 'हिंदी'), ('en', 'English')])
        return '<label class="preference-row"><span>Post language</span><select id="tt-story-language">%s</select></label>' % options

    def listing(self, base_path, posts, title, intro='', lang='', current_cat='', noindex=False, body_class='archive'):
        per = int(self.site.get('posts_per_page', 10))
        total = max(1, -(-len(posts) // per))
        year_match = re.match(r'^/(\d{4})/(?:lang/(?:hi|en)/)?$', base_path)
        current_year = year_match.group(1) if year_match else str(self.posts[0]['date'].year) if base_path == '/years/' else ''
        side = self.category_navigation(current_cat) if current_cat else self.year_navigation(current_year) if current_year else ''
        root = '/category/%s/' % current_cat if current_cat else '/%s/' % current_year if current_year else '/'
        is_home = body_class == 'home blog'
        for n in range(1, total + 1):
            chunk = posts[(n - 1) * per:n * per]
            rows = ''.join(self.row(p) for p in chunk) or '<p class="empty">No stories here yet. Try another thread or language.</p>'
            path = base_path if n == 1 else '%spage/%d/' % (base_path, n)
            heading = self.category_label(current_cat) if current_cat else current_year
            hub_heading = '<h2 class="hub-title">%s</h2><p class="hub-count">%s · newest first</p>' % (heading, plural(len(posts), 'page')) if side else ''
            filters = '<div class="list-toolbar"><h2 class="label">%s</h2></div>' % ('Recent posts' if is_home else 'The pages')
            content = '%s%s%s%s' % (hub_heading, filters, rows, self.pagination(base_path, n, total))
            if side:
                content = '<div class="browse-layout">%s<div class="browse-posts">%s</div></div>' % (side, content)
            extras = self.home_extras() if is_home and n == 1 else ''
            body = '<main class="wrap notebook-list">%s%s%s</main>' % (intro if n == 1 or not is_home else '', content, extras)
            t = title if n == 1 else '%s – Page %d' % (title, n)
            self.write(path, self.page(path, t, body, body_class=body_class, noindex=noindex, story_filter=self.story_language_control(root, lang)))

    def archive_intro(self, label, heading, desc=''):
        d = '<div class="desc">%s</div>' % wpautop(desc) if desc else ''
        return '<section class="archive-intro"><div class="label">%s</div><h1%s>%s</h1>%s</section>' % (
            esc(label), ' lang="hi"' if is_hindi(heading) else '', esc(html.unescape(heading)), d)

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
        return ('<section id="comments" class="comments-area"><h2 class="comments-title">Comments <span>%s</span></h2><ol class="comment-list">%s</ol>'
                '%s</section>') % (plural(len(cs), 'comment'), items, '' if getattr(self, 'comments_config', {}).get('enabled') else '<p class="mono">Comments are closed.</p>')

    def live_comments_html(self, post):
        cfg = self.comments_config
        if not cfg.get('enabled'):
            return ''
        section_id = 'new-comments' if post['comments'] else 'comments'
        return ('<section id="%s" class="live-comments" data-blog-comments data-post-id="%s" data-endpoint="%s" data-publishable-key="%s" data-turnstile-site-key="%s" data-preview="%s">'
                '<div data-live-comments hidden><h2 class="comments-title">Comments</h2><ol class="comment-list" data-comment-list></ol><button type="button" class="comments-more" data-comments-more hidden>More comments</button></div>'
                '<details class="comment-compose"><summary>Leave a comment</summary><form class="comment-form">'
                '<p class="comment-form-note">Your name and approved comment will be public. No email address is collected.</p>'
                '<div class="comment-reply-context"><span data-reply-context></span><button type="button" data-cancel-reply hidden>Cancel reply</button></div>'
                '<label>Your name<input name="author_name" required minlength="2" maxlength="60" autocomplete="name"></label>'
                '<label>Your comment<textarea name="body" required minlength="2" maxlength="10000" rows="5"></textarea></label>'
                '<label class="comment-honeypot" aria-hidden="true">Leave this empty<input name="website" tabindex="-1" autocomplete="off"></label>'
                '<div data-turnstile></div><button class="comment-send" type="submit" disabled>Submit</button>'
                '<p class="comment-form-status" data-comment-status role="status" aria-live="polite"></p></form></details>'
                '<noscript><p class="comment-form-note">JavaScript is needed to load new comments and send a reply.</p></noscript></section>') % (
                    section_id, esc(post['id']), esc(cfg['supabase_url'] + '/functions/v1/blog-comments'), esc(cfg['publishable_key']),
                    esc(cfg['turnstile_site_key']), 'true' if self.preview else 'false')

    def single(self, i):
        p = self.posts[i]
        image, image_alt = self.post_image(p)
        social = self.social_card(image)
        older = self.posts[i + 1] if i + 1 < len(self.posts) else None
        newer = self.posts[i - 1] if i > 0 else None
        nav = ''
        for other, label in [(older, '← An earlier page'), (newer, 'A newer page →')]:
            nav += '<a href="%s"><span class="label">%s</span><h2 lang="%s">%s</h2></a>' % (
                self.u(other['path']), label, other['lang'], esc(html.unescape(other['title']))) if other else '<span></span>'
        cats = ''.join('<a href="%s">%s</a>' % (self.u('/category/%s/' % c), self.category_label(c)) for c in p['cats'])
        body = '''<main class="wrap reader"><div class="reader-tools"><a class="back" href="%(home)s">← <span class="back-long">Back to the notebook</span><span class="back-short">Home</span></a><div class="reader-actions"><div class="sizer"><button class="icon-btn" data-tt-size="-1" aria-label="Smaller text">A−</button><button class="icon-btn" data-tt-size="1" aria-label="Larger text">A+</button></div>%(share)s</div></div>
<article id="post-%(id)s" class="single-entry post">%(cat)s<h1 class="entry-title" lang="%(lang)s">%(title)s</h1><div class="byline"><span class="author-initial" aria-hidden="true">H</span><div><span>%(author)s</span><time datetime="%(iso)s">%(date)s</time></div><span class="reading-time">%(reading)s</span></div><div class="entry-content" lang="%(lang)s">%(content)s</div><div class="article-ending"><span aria-hidden="true">✳</span><nav class="post-threads" aria-label="This post’s threads">%(cats)s</nav></div></article>
<section class="author-note"><span class="author-initial" aria-hidden="true">H</span><div><h2>Written by %(author)s</h2><p>I’ve been keeping these pages since 2008. Some posts are trips, some are poems, most are just life.</p><a class="text-link" href="%(about)s">A little about me →</a></div></section>
%(comments)s<section class="next-pages"><h2 class="label">STAY A LITTLE LONGER</h2><nav class="post-nav" aria-label="More posts">%(nav)s</nav></section></main>''' % {
            'home': self.u('/'), 'id': esc(p['id']), 'cat': self.first_cat(p), 'lang': p['lang'],
            'title': esc(html.unescape(p['title'])), 'author': esc(self.site.get('author', 'Harsh')),
            'iso': p['date'].isoformat(), 'date': fmt_date(p['date'], 'long'), 'reading': self.reading(p),
            'content': render_body(p['raw'], self.site, self.base), 'cats': cats, 'about': self.u('/about/'),
            'comments': self.comments_html(p) + self.live_comments_html(p), 'nav': nav, 'share': self.share_controls(p, image)}
        desc = html.unescape(p.setdefault('excerpt_html', excerpt_of(p)))[:300]
        title = '%s – %s' % (html.unescape(p['title']), self.site['title'])
        self.write(p['path'], self.page(p['path'], title, body,
                   body_class='single single-post', description=desc, singular=True, og_type='article', social_image=social, social_alt=image_alt))
        share_path = self.share_paths.get(p['id'])
        if share_path:
            # A full static article gives link-preview crawlers the same image and text
            # without relying on JavaScript or a redirect. The historical URL stays canonical.
            self.write(share_path, self.page(p['path'], title, body, noindex=True,
                       body_class='single single-post', description=desc, singular=True, og_type='article', social_image=social, social_alt=image_alt))

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
        self.write('/comments-posts.json', json.dumps({'posts': [p['id'] for p in posts], 'details': {p['id']: {'title': html.unescape(p['title']), 'path': p['path']} for p in posts}}, ensure_ascii=False, separators=(',', ':')))
        self.pages_written -= 1
        for i in range(len(posts)):
            self.single(i)

        # Compact notebook home; the brand is the home link.
        intro = '<section class="intro intro-compact"><div class="intro-copy"><p>%s <a class="start-link" href="%s">Favourites →</a></p></div></section>' % (esc(s['description']), self.u('/favourites/'))
        home_title = '%s – %s' % (s['title'], s['description'])
        self.listing('/', posts, home_title, intro=intro, body_class='home blog')
        self.start_here()
        for lang, label in (('hi', 'हिंदी'), ('en', 'English')):
            self.listing('/lang/%s/' % lang, [p for p in posts if p['lang'] == lang], '%s – %s' % (label, s['title']),
                         lang=lang, intro=self.archive_intro('The notebook', label), noindex=True)
        threads_intro = self.archive_intro('The notebook, by subject', 'Follow a thought.',
                                          'Places, poems, ordinary days. Find a thread to follow.')
        first_thread = next(c['slug'] for c in self.cats if self.cat_counts().get(c['slug']))
        self.listing('/threads/', [p for p in posts if first_thread in p['cats']], 'Threads – ' + s['title'],
                     intro=threads_intro, current_cat=first_thread)
        latest_year = posts[0]['date'].year
        years_intro = self.archive_intro('%s · %s posts' % (s['title'], len(posts)), 'The years, kept here.',
                                        'Different places. Different versions of me. The same little corner of the internet.')
        self.listing('/years/', [p for p in posts if p['date'].year == latest_year], 'The years – ' + s['title'],
                     intro=years_intro, noindex=True)
        about = '<main class="wrap about-page">%s<div class="about-copy"><p>%s</p><p>The name Time Turner comes from Harry Potter, a favourite of mine. This blog previously lived at magicalharsh.com.</p></div><a class="text-link" href="%s">Meet me through the years →</a></main>' % (
            self.archive_intro('The person behind the pages', "Hi, I’m Harsh."), esc(s['about']), self.u('/years/'))
        self.write('/about/', self.page('/about/', 'About Harsh – ' + s['title'], about, body_class='about'))
        # categories, tags, dates
        for c in self.cats:
            sel = [p for p in posts if c['slug'] in p['cats']]
            if sel:
                self.listing('/category/%s/' % c['slug'], sel, '%s – %s' % (c['name'], s['title']),
                             intro=threads_intro, current_cat=c['slug'])
                for lang, label in [('hi', 'हिंदी'), ('en', 'English')]:
                    self.listing('/category/%s/lang/%s/' % (c['slug'], lang), [p for p in sel if p['lang'] == lang],
                                 '%s · %s – %s' % (c['name'], label, s['title']), intro=threads_intro,
                                 current_cat=c['slug'], lang=lang, noindex=True)
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
            self.listing('/tag/%s/' % t, sel, '%s – %s' % (name, s['title']), intro=self.archive_intro('An older collection', name), noindex=True)
        for (key, name), sel in by_date.items():
            self.listing(key, sel, '%s – %s' % (name, s['title']), intro=years_intro if re.match(r'^/\d{4}/$', key) else self.archive_intro('An earlier chapter', name), noindex=True)
            if re.match(r'^/\d{4}/$', key):
                for lang, label in [('hi', 'हिंदी'), ('en', 'English')]:
                    self.listing(key + 'lang/%s/' % lang, [p for p in sel if p['lang'] == lang], '%s · %s – %s' % (name, label, s['title']), intro=years_intro, lang=lang, noindex=True)

        # search, random, 404
        index = [{'i': p['id'], 't': html.unescape(p['title']), 'u': p['path'], 'x': html.unescape(p['excerpt_html']),
                  'v': verse_lines(p), 'im': self.thumbnail(p),
                  'd': fmt_date(p['date'], 'd'), 'm': fmt_date(p['date'], 'my'), 'l': p['lang'],
                  'c': self.cat_name.get(p['cats'][0], '') if p['cats'] else '', 'cs': p['cats'][0] if p['cats'] else '',
                  'r': self.reading(p), 'n': len(p['comments']),
                  'ce': next((c.get('name_en', c['name']) for c in self.cats if p['cats'] and c['slug'] == p['cats'][0]), ''),
                  'k': ' '.join(self.cat_name.get(c, c) for c in p['cats'])} for p in posts]
        self.write('/search.json', json.dumps(index, ensure_ascii=False, separators=(',', ':')))
        self.pages_written -= 1
        body = ('%s\n<div class="wrap layout">\n<main id="posts"><div class="filters">%s</div>'
                '<div id="tt-search-results"><p class="empty">Type a word above to search all %d stories.</p></div>'
                '<noscript><p class="empty">Search needs JavaScript. You can browse Threads instead.</p></noscript></main>\n%s\n</div>') % (
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
        urls = ['<url><loc>%s%s</loc></url>' % (s['site_url'], path) for path in ['/', '/favourites/', '/threads/', '/about/']]
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
