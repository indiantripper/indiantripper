import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('comments_blog', ROOT / 'build.py')
blog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blog)


class Comments(unittest.TestCase):
    def site(self, enabled=True, preview=False):
        site = blog.Site.__new__(blog.Site)
        site.site = {}
        site.preview = preview
        site.comments_config = {'enabled': enabled, 'supabase_url': 'https://example.supabase.co',
                                'publishable_key': 'sb_publishable_public', 'turnstile_site_key': 'public-site-key'}
        return site

    def test_disabled_comments_keep_archive_but_add_no_form(self):
        site = self.site(enabled=False)
        post = {'id': '42', 'comments': []}
        self.assertEqual(site.live_comments_html(post), '')
        self.assertEqual(site.comments_html(post), '')
        post['comments'] = [self.comment()]
        self.assertIn('Comments are closed.', site.comments_html(post))

    def comment(self):
        return {'id': 1, 'parent': 0, 'author': 'Original reader', 'url': '',
                'date': '2014-01-01 12:30:00', 'content': 'An original comment.'}

    def test_archive_remains_intact_and_new_discussion_has_separate_id(self):
        site = self.site()
        post = {'id': '42', 'comments': [self.comment()]}
        archive = site.comments_html(post)
        form = site.live_comments_html(post)
        self.assertIn('Original reader', archive)
        self.assertIn('An original comment.', archive)
        self.assertIn('id="comment-1"', archive)
        self.assertNotIn('Comments are closed.', archive)
        self.assertIn('id="new-comments"', form)
        self.assertIn('data-live-comments hidden', form)
        self.assertNotIn('An original comment.', form)

    def test_paths_do_not_change_the_permanent_comment_identity(self):
        site = self.site()
        post = {'id': '42', 'comments': [], 'path': '/2014/01/01/original/'}
        dated = site.live_comments_html(post)
        post['path'] = '/read/new-short-link/'
        self.assertEqual(dated, site.live_comments_html(post))
        self.assertIn('data-post-id="42"', dated)
        self.assertIn('data-preview="false"', dated)
        self.assertIn('Send for approval', dated)
        self.assertNotIn('name="email"', dated)
        self.assertIn('type="submit" disabled', dated)

    def test_preview_is_explicit_and_attributes_are_escaped(self):
        site = self.site(preview=True)
        form = site.live_comments_html({'id': '42" onmouseover="bad', 'comments': []})
        self.assertIn('data-preview="true"', form)
        self.assertIn('42&quot; onmouseover=&quot;bad', form)
        self.assertNotIn(' onmouseover="', form)


if __name__ == '__main__':
    unittest.main()
