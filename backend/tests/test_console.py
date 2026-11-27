import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from backend.__main__ import run_console


class ConsoleTests(unittest.TestCase):
    def test_arrow_selects_a_single_command_then_escape_exits(self):
        keyboard = SimpleNamespace(getwch=Mock(side_effect=["x", "\xe0", "K", "\x00", "P", "\r", "\x1b"]))
        channel = Mock()
        channel.send_command.return_value = {"status": "accepted"}
        with patch.dict("sys.modules", {"msvcrt": keyboard}), redirect_stdout(StringIO()) as output:
            run_console(channel)
        channel.send_command.assert_called_once_with("move_right")
        self.assertIn("PyTapo aceptó la orden.", output.getvalue())

    def test_enter_on_exit_does_not_send_a_command(self):
        keyboard = SimpleNamespace(getwch=Mock(side_effect=["\xe0", "H", "\r"]))
        channel = Mock()
        with patch.dict("sys.modules", {"msvcrt": keyboard}), redirect_stdout(StringIO()):
            run_console(channel)
        channel.send_command.assert_not_called()
