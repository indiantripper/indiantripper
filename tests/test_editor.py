import datetime
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('blog', ROOT / 'build.py')
blog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blog)


class EditorCompatibility(unittest.TestCase):
    def test_editor_yaml_dates_categories_and_quoted_title(self):
        with tempfile.TemporaryDirectory() as temp:
            content = Path(temp)
            posts = content / 'posts'
            posts.mkdir()
            file = posts / '2026-11-17-new-story.html'
            metadata = {'title': 'घर: धूप और समय', 'date': datetime.datetime(2026, 11, 17, 10, 30),
                        'categories': ['life-and-philosophy', 'rambling'], 'language': 'hi',
                        'excerpt': 'पहली पंक्ति।\nदूसरी पंक्ति।'}
            body = '<p>पहला paragraph।</p><p>दूसरा paragraph।</p>'
            file.write_text('---\n' + yaml.safe_dump(metadata, allow_unicode=True) + '---\n\n' + body)
            with patch.object(blog, 'CONTENT', str(content)):
                loaded, problems = blog.load({})
            self.assertEqual(problems, [])
            self.assertEqual(loaded[0]['title'], metadata['title'])
            self.assertEqual(loaded[0]['cats'], metadata['categories'])
            self.assertEqual(loaded[0]['raw'], body)
            self.assertEqual(loaded[0]['lang'], 'hi')
            self.assertTrue(loaded[0]['id'])
            metadata['date'] = datetime.date(2026, 12, 1)
            metadata['title'] = 'A changed title'
            file.write_text('---\n' + yaml.safe_dump(metadata, allow_unicode=True) + '---\n\n' + body)
            with patch.object(blog, 'CONTENT', str(content)):
                updated, problems = blog.load({})
            self.assertEqual(problems, [])
            self.assertEqual(updated[0]['path'], loaded[0]['path'])
            self.assertEqual(updated[0]['id'], loaded[0]['id'])

    def test_existing_explicit_paths_and_scalar_categories_still_work(self):
        with tempfile.TemporaryDirectory() as temp:
            content = Path(temp)
            (content / 'posts').mkdir()
            file = content / 'posts' / '2026-11-17-title.html'
            metadata = {'title': 'Legacy title', 'date': '2026-11-17 01:14:00', 'id': '4247',
                        'path': '/original-address/', 'categories': 'travel, rambling'}
            file.write_text('---\n' + yaml.safe_dump(metadata) + '---\n\n<p>Original.</p>')
            with patch.object(blog, 'CONTENT', str(content)):
                loaded, problems = blog.load({})
            self.assertEqual(problems, [])
            self.assertEqual(loaded[0]['path'], '/original-address/')
            self.assertEqual(loaded[0]['id'], '4247')
            self.assertEqual(loaded[0]['cats'], ['travel', 'rambling'])

    def test_cms_plain_yes_no_and_folded_excerpt_are_text(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'post.html'
            file.write_text('---\ntitle: Yes\ndate: 2026-11-17 10:30:00\nexcerpt: >-\n  First line.\n  Second line.\n---\n<p>Body</p>')
            meta, body = blog.parse_file(file)
            self.assertEqual(meta['title'], 'Yes')
            self.assertEqual(meta['date'], '2026-11-17 10:30:00')
            self.assertEqual(meta['excerpt'], 'First line. Second line.')

    def test_uploaded_images_use_production_and_preview_paths(self):
        body = '<p>Picture</p><img src="/images/upload.jpg" alt="धूप">'
        self.assertIn('src="/images/upload.jpg"', blog.render_body(body, {'site_url': 'https://indiantripper.in'}, ''))
        self.assertIn('src="/indiantripper/images/upload.jpg"', blog.render_body(body, {'site_url': 'https://indiantripper.in'}, '/indiantripper'))

    def test_malformed_or_unsafe_yaml_fails_without_publishing(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'unsafe.html'
            file.write_text('---\ntitle: !!python/object/apply:os.system ["false"]\n---\nbody')
            with self.assertRaises(yaml.YAMLError):
                blog.parse_file(file)
            file.write_text('---\ntitle: Missing delimiter\nbody')
            with self.assertRaises(ValueError):
                blog.parse_file(file)

    def test_editor_media_and_repository_scope(self):
        config = yaml.safe_load((ROOT / '.pages.yml').read_text())
        self.assertEqual(config['media']['input'], 'static/images')
        self.assertEqual(config['media']['output'], '/images')
        self.assertEqual(config['content'][0]['path'], 'content/posts')
        self.assertTrue(config['settings']['content']['merge'])
        body = next(f for f in config['content'][0]['fields'] if f['name'] == 'body')
        self.assertEqual(body['options']['format'], 'html')
        self.assertNotIn('status', [f['name'] for f in config['content'][0]['fields']])


if __name__ == '__main__':
    unittest.main()
