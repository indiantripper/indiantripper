import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sharing_blog', ROOT / 'build.py')
blog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blog)


class Sharing(unittest.TestCase):
    def site(self):
        site = blog.Site.__new__(blog.Site)
        site.posts = [{'id': '1', 'file': 'story.html', 'path': '/2020/12/05/monsters/', 'share_slug': ''}]
        return site

    def test_share_slugs_are_validated_without_moving_original_addresses(self):
        site = self.site()
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'share-links.json'
            with patch.object(blog, 'CONTENT', temp):
                file.write_text(json.dumps({'1': 'pret-aatmaaye'}))
                self.assertEqual(site.load_share_paths(), {'1': '/read/pret-aatmaaye/'})
                self.assertEqual(site.posts[0]['path'], '/2020/12/05/monsters/')
                for slug in ['../escape', 'A title', 'नमस्ते', '/read/hello/', 'hello?x=1']:
                    file.write_text(json.dumps({'1': slug}))
                    with self.assertRaises(ValueError):
                        site.load_share_paths()
                file.write_text(json.dumps({'missing': 'hello'}))
                with self.assertRaises(ValueError):
                    site.load_share_paths()

    def test_editor_slug_can_set_a_link_but_duplicates_fail(self):
        site = self.site()
        site.posts[0]['share_slug'] = 'a-short-link'
        site.posts.append({'id': '2', 'file': 'another.html', 'path': '/another/', 'share_slug': 'a-short-link'})
        with tempfile.TemporaryDirectory() as temp, patch.object(blog, 'CONTENT', temp):
            with self.assertRaises(ValueError):
                site.load_share_paths()
            site.posts.pop()
            self.assertEqual(site.load_share_paths(), {'1': '/read/a-short-link/'})

    def test_share_override_never_becomes_a_list_thumbnail(self):
        site = self.site()
        site.problems = []
        post = {'title': 'A story', 'file': 'story.html', 'image': '',
                'share_image': '/images/share/cards/story.jpg', 'raw': '<p>Original text only.</p>'}
        with patch.object(blog.os.path, 'isfile', return_value=True):
            self.assertEqual(site.post_image(post)[0], '/images/share/cards/story.jpg')
        self.assertEqual(site.thumbnail(post), '')

    def test_share_controls_copy_the_short_link_and_keep_preview_images(self):
        site = self.site()
        site.site = {'site_url': 'https://indiantripper.in'}
        site.base = '/preview'
        site.share_paths = {'1': '/read/pret-aatmaaye/'}
        post = dict(site.posts[0], title='प्रेत आत्माएं', lang='hi')
        controls = site.share_controls(post, '/images/ghost.jpg')
        self.assertIn('data-share-url="https://indiantripper.in/read/pret-aatmaaye/"', controls)
        self.assertIn('src="/preview/images/ghost.jpg"', controls)
        self.assertIn('https%3A%2F%2Findiantripper.in%2Fread%2Fpret-aatmaaye%2F', controls)
        self.assertNotIn('http-equiv="refresh"', controls)

    def test_heavy_share_images_get_a_light_preview_copy(self):
        from PIL import Image
        site = self.site()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'static' / 'images').mkdir(parents=True)
            noisy = Image.effect_noise((2400, 1600), 90).convert('RGB')
            noisy.save(root / 'static' / 'images' / 'heavy.jpg', quality=95)
            Image.new('RGB', (600, 315), 'white').save(root / 'static' / 'images' / 'light.jpg')
            site.out = str(root / 'out')
            with patch.object(blog, 'ROOT', str(root)):
                self.assertGreater((root / 'static' / 'images' / 'heavy.jpg').stat().st_size, site.SOCIAL_CARD_BYTES)
                card = site.social_card('/images/heavy.jpg')
                self.assertTrue(card.startswith('/images/share/auto/'))
                self.assertLessEqual((root / 'out' / card.lstrip('/')).stat().st_size, site.SOCIAL_CARD_BYTES)
                self.assertEqual(site.social_card('/images/heavy.jpg'), card)
                self.assertEqual(site.social_card('/images/light.jpg'), '/images/light.jpg')
                self.assertEqual(site.social_card('/images/missing.jpg'), '/images/missing.jpg')


if __name__ == '__main__':
    unittest.main()
