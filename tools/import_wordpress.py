#!/usr/bin/env python3
"""One-time import: WordPress export (WXR .xml) -> plain content files.

Usage:
    python3 tools/import_wordpress.py <export.xml> --private-dir <folder outside the repo> [--publish-password-protected]

Writes (inside the repo):
    content/site.json, content/categories.json, content/tags.json
    content/posts/<year>/<date>-<slug>.html      one file per published post
    content/comments/<year>/<date>-<slug>.json   approved comments for that post
    reports/import-summary.txt, reports/images.csv, reports/leftover-shortcodes.csv
Writes (outside the repo, never published):
    <private-dir>/drafts, /password-protected, /trash, /pages

Commenter email and IP addresses are never written anywhere.
Only the Python standard library is used.
"""
import argparse, csv, json, os, re, sys, html
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, unquote

NS = {'wp': 'http://wordpress.org/export/1.2/',
      'content': 'http://purl.org/rss/1.0/modules/content/',
      'excerpt': 'http://wordpress.org/export/1.2/excerpt/',
      'dc': 'http://purl.org/dc/elements/1.1/'}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def t(el, tag):
    x = el.find(tag, NS)
    return (x.text or '') if x is not None else ''


def safe_name(s):
    s = unquote(s)
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '-', s).strip('. ')
    return s[:80] or 'untitled'


def clean_body(body, stats):
    body = body.replace('\r\n', '\n').replace('\r', '\n')
    # Microsoft Word leftovers: invisible conditional comments
    junk = r'<!--\[if[^\]]*\](?:>|&gt;).*?(?:<|&lt;)!\[endif\]-->'
    if re.search(junk, body, flags=re.S):
        stats['word_junk_posts'] += 1
        body = re.sub(junk, '', body, flags=re.S)
    return body.strip('\n') + '\n'


def front_matter(d):
    out = ['---']
    for k, v in d.items():
        if v is None or v == '':
            continue
        out.append('%s: %s' % (k, str(v).replace('\n', ' ')))
    out.append('---')
    return '\n'.join(out) + '\n'


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('export')
    ap.add_argument('--private-dir', required=True)
    ap.add_argument('--out', default=ROOT)
    ap.add_argument('--publish-password-protected', action='store_true',
                    help='publish posts that had a WordPress password (a static site cannot lock them)')
    a = ap.parse_args()
    out = a.out
    priv = os.path.abspath(a.private_dir)
    if os.path.commonpath([priv, os.path.abspath(out)]) == os.path.abspath(out):
        sys.exit('The private folder must be outside the site repository.')

    ch = ET.parse(a.export).getroot().find('channel')
    site_url = t(ch, 'wp:base_site_url').rstrip('/').replace('http://', 'https://')
    host = urlparse(site_url).netloc

    cats, cat_by_id = [], {}
    for c in ch.findall('wp:category', NS):
        d = {'slug': t(c, 'wp:category_nicename'), 'name': t(c, 'wp:cat_name'),
             'description': t(c, 'wp:category_description')}
        cats.append(d)
        cat_by_id[t(c, 'wp:term_id')] = d['slug']
    tag_names = {t(x, 'wp:tag_slug'): t(x, 'wp:tag_name') for x in ch.findall('wp:tag', NS)}

    stats = {k: 0 for k in ['published', 'drafts', 'password', 'trash', 'pages', 'comments',
                            'pingbacks_skipped', 'unapproved_skipped', 'word_junk_posts',
                            'posts_with_comments', 'featured_images_lost']}
    used_tags, menu, image_rows, shortcode_rows = {}, [], [], []
    seen_files = set()

    for it in ch.findall('item'):
        ptype, status = t(it, 'wp:post_type'), t(it, 'wp:status')
        if ptype == 'nav_menu_item':
            meta = {t(m, 'wp:meta_key'): t(m, 'wp:meta_value') for m in it.findall('wp:postmeta', NS)}
            if meta.get('_menu_item_object') == 'category' and meta.get('_menu_item_object_id') in cat_by_id:
                menu.append((int(t(it, 'wp:menu_order') or 0), cat_by_id[meta['_menu_item_object_id']]))
            continue
        if ptype not in ('post', 'page'):
            continue

        title = t(it, 'title')
        date = t(it, 'wp:post_date')
        body = clean_body(t(it, 'content:encoded'), stats)
        slug = unquote(t(it, 'wp:post_name')) or safe_name(title)
        link = t(it, 'link')
        path = urlparse(link).path
        cats_of = [c.get('nicename') for c in it.findall('category') if c.get('domain') == 'category']
        tags_of = [c.get('nicename') for c in it.findall('category') if c.get('domain') == 'post_tag']
        fm = {'title': title, 'date': date, 'id': t(it, 'wp:post_id'), 'path': path,
              'categories': ', '.join(cats_of), 'tags': ', '.join(tags_of),
              'excerpt': t(it, 'excerpt:encoded').strip()}
        fname = '%s-%s' % (date[:10], safe_name(slug))

        private_kind = None
        if ptype == 'page':
            private_kind = 'pages'; stats['pages'] += 1
        elif status == 'trash':
            private_kind = 'trash'; stats['trash'] += 1
        elif status != 'publish':
            private_kind = 'drafts'; stats['drafts'] += 1
        elif t(it, 'wp:post_password') and not a.publish_password_protected:
            private_kind = 'password-protected'; stats['password'] += 1

        comments = []
        for c in it.findall('wp:comment', NS):
            if t(c, 'wp:comment_approved') != '1':
                stats['unapproved_skipped'] += 1; continue
            if t(c, 'wp:comment_type') in ('pingback', 'trackback'):
                if not private_kind:
                    stats['pingbacks_skipped'] += 1
                continue
            comments.append({'id': int(t(c, 'wp:comment_id')), 'parent': int(t(c, 'wp:comment_parent') or 0),
                             'author': t(c, 'wp:comment_author'), 'url': t(c, 'wp:comment_author_url'),
                             'date': t(c, 'wp:comment_date'), 'by_site_author': t(c, 'wp:comment_user_id') not in ('', '0'),
                             'content': t(c, 'wp:comment_content')})
        comments.sort(key=lambda c: (c['date'], c['id']))

        if private_kind:
            fm['status'] = status
            del fm['path']
            base = os.path.join(priv, private_kind, fname)
            write(base + '.html', front_matter(fm) + '\n' + body)
            if comments:
                write(base + '.comments.json', json.dumps(comments, ensure_ascii=False, indent=1))
            continue

        stats['published'] += 1
        if fname in seen_files:
            fname += '-' + fm['id']
        seen_files.add(fname)
        year = date[:4]
        write(os.path.join(out, 'content', 'posts', year, fname + '.html'), front_matter(fm) + '\n' + body)
        if comments:
            stats['comments'] += len(comments); stats['posts_with_comments'] += 1
            write(os.path.join(out, 'content', 'comments', year, fname + '.json'),
                  json.dumps(comments, ensure_ascii=False, indent=1))
        for s in tags_of:
            used_tags[s] = tag_names.get(s, s)
        if any(t(m, 'wp:meta_key') == '_thumbnail_id' for m in it.findall('wp:postmeta', NS)):
            stats['featured_images_lost'] += 1
        for src in re.findall(r'<img[^>]+src=["\']([^"\']+)', body):
            image_rows.append([path, title, urlparse(src).netloc or host, src])
        for sc in set(re.findall(r'\[/?([a-zA-Z][\w-]*)(?=[\s\]=])', body)) - {'caption'}:
            shortcode_rows.append([path, title, sc])

    site = {
        'title': t(ch, 'title'), 'description': t(ch, 'description'), 'site_url': site_url,
        'language': 'en-US', 'author': 'Harsh', 'posts_per_page': 10,
        'menu': [s for _, s in sorted(menu)],
        'eyebrow': 'Stories from my life 🌱 · since June 2008',
        'show_headline': False,
        'headline': 'Turn back <span>the hourglass.</span>',
        'intro': 'Trips, college days at NITIE, pets, books, and a lot of Hindi scribbles. Written by Harsh, one post at a time.',
        'random_label': 'Read a random story',
        'about_title': "Hi, I'm Harsh",
        'about': 'I started this blog in 2008 and it has followed me through college, NITIE, new cities and a few pets. Some posts are trips, some are poems, most are just life.',
        'about_photo': '',
        'comment_author_links': False,
    }
    site_path = os.path.join(out, 'content', 'site.json')
    if not os.path.exists(site_path):
        write(site_path, json.dumps(site, ensure_ascii=False, indent=2) + '\n')
    write(os.path.join(out, 'content', 'categories.json'), json.dumps(cats, ensure_ascii=False, indent=1) + '\n')
    write(os.path.join(out, 'content', 'tags.json'), json.dumps(dict(sorted(used_tags.items())), ensure_ascii=False, indent=0) + '\n')

    os.makedirs(os.path.join(out, 'reports'), exist_ok=True)
    for name, head, rows in [('images.csv', ['post', 'title', 'image host', 'image address'], image_rows),
                             ('leftover-shortcodes.csv', ['post', 'title', 'bracket word'], shortcode_rows)]:
        with open(os.path.join(out, 'reports', name), 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f); w.writerow(head); w.writerows(rows)
    lines = ['Import summary', '==============',
             'Published posts written:            %d' % stats['published'],
             'Comments written:                   %d (on %d posts)' % (stats['comments'], stats['posts_with_comments']),
             'Pingbacks/trackbacks left out:      %d' % stats['pingbacks_skipped'],
             'Unapproved/trashed comments left out: %d' % stats['unapproved_skipped'],
             '',
             'Kept private (outside the repo, in %s):' % priv,
             '  drafts:                 %d' % stats['drafts'],
             '  password-protected:     %d' % stats['password'],
             '  trashed:                %d' % stats['trash'],
             '  pages (incl. drafts):   %d' % stats['pages'],
             '',
             'Posts with Word leftovers cleaned:  %d' % stats['word_junk_posts'],
             'Posts whose featured image is lost: %d' % stats['featured_images_lost'],
             'Image tags listed in images.csv:    %d' % len(image_rows)]
    write(os.path.join(out, 'reports', 'import-summary.txt'), '\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
