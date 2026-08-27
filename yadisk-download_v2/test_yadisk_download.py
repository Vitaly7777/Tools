import unittest
from unittest.mock import patch
import sys
import os

from yadisk_download import fix_long_path


class TestFixLongPath(unittest.TestCase):

    @patch('os.path.abspath')
    def test_non_windows_returns_original(self, mock_abspath):
        with patch('sys.platform', 'linux'):
            path = 'some/path'
            result = fix_long_path(path)
            self.assertEqual(result, path)
            mock_abspath.assert_not_called()

    @patch('os.path.abspath')
    def test_windows_already_has_prefix(self, mock_abspath):
        with patch('sys.platform', 'win32'):
            path = r'\\?\C:\very\long\path'  # это raw-строка, даёт два слеша, вопрос, один слеш? 
            # r'\\?\C:\...' - интерпретируется как: два слеша, вопрос, один слеш, затем C:... 
            # потому что после вопроса идёт слеш, а затем C, но в raw-строке слеш не экранирует, всё нормально.
            # Однако наш префикс - это именно '\\\\?\\' (два слеша, вопрос, один слеш), а здесь в raw-строке 
            # r'\\?\C:\...' - это два слеша, вопрос, один слеш, затем C: - да, это тот же самый префикс.
            result = fix_long_path(path)
            self.assertEqual(result, path)
            mock_abspath.assert_not_called()

    @patch('os.path.abspath')
    def test_windows_short_path_no_prefix(self, mock_abspath):
        with patch('sys.platform', 'win32'):
            short_path = 'C:\\short\\path'
            abs_path = 'C:\\absolute\\short\\path'
            mock_abspath.return_value = abs_path
            result = fix_long_path(short_path)
            self.assertEqual(result, abs_path)
            mock_abspath.assert_called_once_with(short_path)

    @patch('os.path.abspath')
    def test_windows_exactly_250_no_prefix(self, mock_abspath):
        with patch('sys.platform', 'win32'):
            base = 'C:\\' + 'a' * 246
            abs_path = base
            mock_abspath.return_value = abs_path
            result = fix_long_path(base)
            self.assertEqual(result, abs_path)
            # Проверяем, что не начинается с префикса
            self.assertFalse(result.startswith('\\\\?\\'))  # используем обычную строку

    @patch('os.path.abspath')
    def test_windows_long_path_adds_prefix(self, mock_abspath):
        with patch('sys.platform', 'win32'):
            long_path = 'C:\\' + 'a' * 251
            abs_path = long_path
            mock_abspath.return_value = abs_path
            result = fix_long_path(long_path)
            expected = '\\\\?\\' + abs_path
            self.assertEqual(result, expected)
            mock_abspath.assert_called_once_with(long_path)

    @patch('os.path.abspath')
    def test_windows_abspath_already_called(self, mock_abspath):
        with patch('sys.platform', 'win32'):
            path = 'relative\\path'
            abs_path = 'C:\\absolute\\relative\\path'
            mock_abspath.return_value = abs_path
            result = fix_long_path(path)
            self.assertEqual(result, abs_path)
            mock_abspath.assert_called_once_with(path)


if __name__ == '__main__':
    unittest.main()