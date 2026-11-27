"""Pruebas de las fuentes de imagen del visor."""

import unittest
from unittest.mock import patch

from scripts import preview_image


class PreviewImageTests(unittest.TestCase):
    def test_only_the_builtin_sample_can_be_fetched(self):
        with patch.object(preview_image.requests, "get") as fetch:
            with self.assertRaisesRegex(ValueError, "ruta local"):
                preview_image.load_image("https://example.com/image.jpg")
            fetch.assert_not_called()

    def test_loads_the_local_path(self):
        with patch.object(preview_image.cv2, "imread") as read:
            self.assertIs(preview_image.load_image("demo.jpg"), read.return_value)
            read.assert_called_once_with("demo.jpg")

    def test_builtin_sample_uses_the_fixed_url(self):
        with (
            patch.object(preview_image.requests, "get") as fetch,
            patch.object(preview_image.cv2, "imdecode") as decode,
        ):
            fetch.return_value.__enter__.return_value.content = b"sample"
            self.assertIs(preview_image.load_image(preview_image.DEFAULT_SOURCE), decode.return_value)
            fetch.assert_called_once_with(preview_image.DEFAULT_SOURCE, timeout=15)
