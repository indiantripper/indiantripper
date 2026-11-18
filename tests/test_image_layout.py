import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('image_blog', ROOT / 'build.py')
blog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blog)


def png(width, height):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + b'\0' * width * 3) * height)) + chunk(b'IEND', b''))


class ImageLayout(unittest.TestCase):
    def test_local_photo_uses_original_width_and_preserves_caption_in_preview(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / 'static/images/photo.png'
            image.parent.mkdir(parents=True)
            image.write_bytes(png(240, 120))
            body = '[caption align="alignright" width="80"]<img src="/images/photo.png" width="80" height="40" />My caption[/caption]'
            with patch.object(blog, 'ROOT', temp):
                output = blog.render_body(body, {'site_url': 'https://indiantripper.in'}, '/preview')
            self.assertIn('--image-width:240px;', output)
            self.assertIn('src="/preview/images/photo.png"', output)
            self.assertIn('>My caption</figcaption>', output)

    def test_remote_missing_and_outside_images_remain_safe_to_render(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(blog, 'ROOT', temp):
            for source in ['https://example.com/photo.jpg', '/images/missing.jpg', '/images/../../outside.jpg']:
                body = '<figure><img src="%s"><figcaption>Caption</figcaption></figure>' % source
                output = blog.render_body(body, {'site_url': 'https://indiantripper.in'}, '')
                self.assertNotIn('--image-width:', output)
                self.assertIn('Caption', output)

    def test_rotated_jpeg_uses_display_width(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / 'static/images/rotated.jpg'
            image.parent.mkdir(parents=True)
            tiff = b'II' + struct.pack('<HIH', 42, 8, 1) + struct.pack('<HHI', 0x112, 3, 1) + struct.pack('<H', 6) + b'\0\0' + b'\0' * 4
            exif = b'Exif\0\0' + tiff
            sof = b'\x08' + struct.pack('>HH', 400, 600) + b'\x01\x01\x11\x00'
            image.write_bytes(b'\xff\xd8\xff\xe1' + struct.pack('>H', len(exif) + 2) + exif + b'\xff\xc0' + struct.pack('>H', len(sof) + 2) + sof)
            with patch.object(blog, 'ROOT', temp):
                self.assertEqual(blog.local_image_width('/images/rotated.jpg'), 400)

    def test_existing_jpeg_and_webp_headers_have_usable_widths(self):
        for pattern in ['*.jpg', '*.webp']:
            image = next((ROOT / 'static/images').rglob(pattern))
            width = blog.local_image_width('/' + str(image.relative_to(ROOT / 'static')))
            self.assertGreater(width, 0)
            self.assertLess(width, 20000)


if __name__ == '__main__':
    unittest.main()
