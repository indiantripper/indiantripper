import datetime
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('discovery_blog', ROOT / 'build.py')
blog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blog)


class Discovery(unittest.TestCase):
    def post(self, **changes):
        post = {'id': 'example', 'title': 'A poem', 'date': datetime.datetime(2026, 11, 18),
                'path': '/example/', 'raw': '<p>One<br>Two</p><p>Three</p><p>Four</p><p>Five</p>',
                'form': 'poem', 'excerpt': '', 'cats': ['poem-humor-fiction'], 'lang': 'en',
                'image': '', 'comments': []}
        post.update(changes)
        return post

    def site(self):
        site = blog.Site.__new__(blog.Site)
        site.base = '/preview'
        site.cats = [{'slug': 'poem-humor-fiction', 'name': 'Poems & Stories'}]
        return site

    def test_poem_preview_preserves_four_authored_lines(self):
        post = self.post()
        self.assertEqual(blog.verse_lines(post), ['One', 'Two', 'Three', 'Four'])
        row = self.site().row(post)
        self.assertIn('One<br>Two<br>Three<br>Four', row)
        self.assertNotIn('Five', row)
        self.assertNotIn('<br>', blog.excerpt_of(post))

    def test_story_in_shared_thread_and_explicit_teasers_stay_prose(self):
        story = self.post(form='prose')
        self.assertEqual(blog.verse_lines(story), [])
        self.assertNotIn('<br>', self.site().row(story))
        poem = self.post(excerpt='A short <teaser> & nothing else.')
        self.assertEqual(blog.verse_lines(poem), [])
        self.assertEqual(blog.preview_of(poem), 'A short &lt;teaser&gt; &amp; nothing else.')

    def test_poem_excludes_figures_comments_and_scripts_and_escapes_text(self):
        post = self.post(raw='<figure><img src="/images/photo.jpg"><figcaption>Not a verse</figcaption></figure><!-- comment -->\n<p>One &amp; two<br>&lt;three&gt;</p><script>Hidden</script><p>Four</p>')
        self.assertEqual(blog.verse_lines(post), ['One & two', '<three>', 'Four'])
        self.assertEqual(blog.preview_of(post), 'One &amp; two<br>&lt;three&gt;<br>Four')

    def test_thumbnail_uses_local_sufficient_size_and_preview_prefix(self):
        site = self.site()
        post = self.post(raw='<img src="/images/tiny.png"><img src="/images/photo.jpg">', image='https://example.com/external.jpg')
        with patch.object(blog, 'local_image_width', side_effect=lambda u: 16 if 'tiny' in u else 640) as width:
            row = site.row(post)
            self.assertIn('src="/preview/images/photo.jpg"', row)
            self.assertNotIn('external.jpg', row)
            self.assertIn('has-thumbnail', row)
            self.assertEqual(width.call_count, 2)
            site.thumbnail(post)
            self.assertEqual(width.call_count, 2)

    def test_repaired_reading_links_follow_preview_without_double_prefix(self):
        body = '<p><a href="/2014/01/05/story/">Story</a><a href="https://indiantripper.in/about/">About</a><a href="/search/?s=memories">Search</a><a href="https://other.example/story/">Elsewhere</a></p>'
        output = blog.render_body(body, {'site_url': 'https://indiantripper.in'}, '/preview')
        self.assertIn('href="/preview/2014/01/05/story/"', output)
        self.assertIn('href="/preview/about/"', output)
        self.assertIn('href="/preview/search/?s=memories"', output)
        self.assertIn('href="https://other.example/story/"', output)
        self.assertNotIn('/preview/preview/', output)

    def test_posts_without_a_local_photo_do_not_get_placeholder_thumbnails(self):
        post = self.post(raw='<p>Only text.</p><img src="https://old.example.com/missing.jpg">')
        self.assertEqual(self.site().thumbnail(post), '')
        self.assertNotIn('row-thumbnail', self.site().row(post))


if __name__ == '__main__':
    unittest.main()
