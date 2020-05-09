from unittest import TestCase

from h5pp.url_builder import join_url


class TestJoin_url(TestCase):
    def test_1_segment(self):
        self.assertEqual(join_url(['http://www.example.com']), 'http://www.example.com')

    def test_1_retain_delimiter(self):
        self.assertEqual(join_url(['http://www.example.com/']), 'http://www.example.com/')

    def test_1_remove_trailing_duplicate_delimiters(self):
        self.assertEqual(join_url(['http://www.example.com//']), 'http://www.example.com/')

    pass
