"""Tests for Agent 1: Login — popup handler logic."""

import unittest
from unittest.mock import patch, MagicMock


class TestPopupHandler(unittest.TestCase):
    """Test popup handler behavior used in Agent 1."""

    @patch("automation.popup_handler.wait_for_popup", return_value=None)
    def test_no_popup_is_not_error(self, mock_wait):
        """Zero popups found should not raise an error."""
        from automation.popup_handler import handle_popup_yes_ok

        result = handle_popup_yes_ok(timeout=1)
        self.assertEqual(result, "none_found")

    @patch("automation.popup_handler.wait_for_popup")
    def test_yes_button_priority_over_ok(self, mock_wait):
        """When both Yes and OK are present, Yes should be clicked first."""
        from automation.popup_handler import handle_popup_yes_ok, get_popup_buttons

        mock_popup = MagicMock()
        mock_popup.window_text.return_value = "Confirm"
        mock_wait.return_value = mock_popup

        mock_yes_btn = MagicMock()
        mock_ok_btn = MagicMock()

        mock_buttons = [mock_yes_btn, mock_ok_btn]
        mock_yes_btn.window_text.return_value = "Yes"
        mock_ok_btn.window_text.return_value = "OK"

        mock_popup.children.return_value = mock_buttons

        with patch("automation.popup_handler.get_popup_buttons") as mock_get_buttons:
            mock_get_buttons.return_value = {"yes": mock_yes_btn, "ok": mock_ok_btn}
            result = handle_popup_yes_ok(timeout=1)

        self.assertEqual(result, "yes_clicked")
        mock_yes_btn.click_input.assert_called_once()
        mock_ok_btn.click_input.assert_not_called()

    @patch("automation.popup_handler.handle_popup_yes_ok")
    def test_multiple_popups_all_dismissed(self, mock_handle):
        """dismiss_all_popups should loop until no popup is found."""
        from automation.popup_handler import dismiss_all_popups

        # Simulate 3 popups then none
        mock_handle.side_effect = ["yes_clicked", "ok_clicked", "yes_clicked", "none_found"]
        count = dismiss_all_popups(max_iterations=5)
        self.assertEqual(count, 3)
        self.assertEqual(mock_handle.call_count, 4)


class TestHandlePopupsPreNode(unittest.TestCase):
    """Test the handle_popups_pre node behavior."""

    @patch("automation.popup_handler.dismiss_all_popups", return_value=0)
    def test_zero_popups_sets_cleared(self, mock_dismiss):
        """When 0 popups found, pre_popups_cleared should be True, no error."""
        from agents.agent1_login.nodes.handle_popups_pre import handle_popups_pre_node

        state = {"error": None}
        result = handle_popups_pre_node(state)
        self.assertTrue(result.get("pre_popups_cleared"))
        self.assertIsNone(result.get("error"))

    @patch("automation.popup_handler.dismiss_all_popups", return_value=2)
    def test_two_popups_sets_cleared(self, mock_dismiss):
        """When 2 popups found and dismissed, should still succeed."""
        from agents.agent1_login.nodes.handle_popups_pre import handle_popups_pre_node

        state = {"error": None}
        result = handle_popups_pre_node(state)
        self.assertTrue(result.get("pre_popups_cleared"))
        self.assertIsNone(result.get("error"))


if __name__ == "__main__":
    unittest.main()
