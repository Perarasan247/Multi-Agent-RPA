"""Tests for Agent 2: Navigation — exact match logic."""

import unittest
from unittest.mock import MagicMock, patch


class TestExactMatch(unittest.TestCase):
    """Test the three-layer exact match verification."""

    def _make_candidate(self, text, tree_path, depth):
        """Create a mock candidate dict."""
        return {
            "text": text,
            "element": MagicMock(),
            "rect": MagicMock(),
            "tree_path": tree_path,
            "depth": depth,
        }

    @patch("agents.agent2_navigation.nodes.exact_match.capture_screen")
    @patch("agents.agent2_navigation.nodes.exact_match.save_debug_screenshot")
    def test_exact_match_found(self, mock_save, mock_capture):
        """Correct candidate passes all 3 layers."""
        from agents.agent2_navigation.nodes.exact_match import exact_match_node

        candidate = self._make_candidate(
            "Sale Statement",
            ["Spare Parts", "Reports", "Sales", "Statements", "Sale Statement"],
            4,
        )
        state = {
            "error": None,
            "report_name": "Sale Statement",
            "module": "Spare Parts",
            "folders": ["Reports", "Sales", "Statements"],
            "ui_candidates": [candidate],
        }

        result = exact_match_node(state)
        self.assertIsNotNone(result.get("exact_match"))
        self.assertIsNone(result.get("error"))
        self.assertEqual(result["exact_match"]["text"], "Sale Statement")

    @patch("agents.agent2_navigation.nodes.exact_match.capture_screen")
    @patch("agents.agent2_navigation.nodes.exact_match.save_debug_screenshot")
    def test_exact_match_not_found(self, mock_save, mock_capture):
        """No matching candidate should set error."""
        from agents.agent2_navigation.nodes.exact_match import exact_match_node

        candidate = self._make_candidate(
            "Purchase Statement",
            ["Spare Parts", "Reports", "Procurement", "Statements", "Purchase Statement"],
            4,
        )
        state = {
            "error": None,
            "report_name": "Sale Statement",
            "module": "Spare Parts",
            "folders": ["Reports", "Sales", "Statements"],
            "ui_candidates": [candidate],
        }

        result = exact_match_node(state)
        self.assertIsNone(result.get("exact_match"))
        self.assertIsNotNone(result.get("error"))

    @patch("agents.agent2_navigation.nodes.exact_match.capture_screen")
    @patch("agents.agent2_navigation.nodes.exact_match.save_debug_screenshot")
    def test_exact_match_wrong_folder_path(self, mock_save, mock_capture):
        """Correct name but wrong folder path should fail Layer 2."""
        from agents.agent2_navigation.nodes.exact_match import exact_match_node

        candidate = self._make_candidate(
            "Sale Statement",
            ["Spare Parts", "Reports", "Procurement", "Statements", "Sale Statement"],
            4,
        )
        state = {
            "error": None,
            "report_name": "Sale Statement",
            "module": "Spare Parts",
            "folders": ["Reports", "Sales", "Statements"],
            "ui_candidates": [candidate],
        }

        result = exact_match_node(state)
        self.assertIsNone(result.get("exact_match"))
        self.assertIsNotNone(result.get("error"))
        self.assertIn("No exact match", result["error"])

    @patch("agents.agent2_navigation.nodes.exact_match.capture_screen")
    @patch("agents.agent2_navigation.nodes.exact_match.save_debug_screenshot")
    def test_exact_match_partial_name_rejected(self, mock_save, mock_capture):
        """Partial text match (contains but not ==) should fail Layer 1."""
        from agents.agent2_navigation.nodes.exact_match import exact_match_node

        candidate = self._make_candidate(
            "Sale Statement New",
            ["Spare Parts", "Reports", "Sales", "Statements", "Sale Statement New"],
            4,
        )
        state = {
            "error": None,
            "report_name": "Sale Statement",
            "module": "Spare Parts",
            "folders": ["Reports", "Sales", "Statements"],
            "ui_candidates": [candidate],
        }

        result = exact_match_node(state)
        self.assertIsNone(result.get("exact_match"))
        self.assertIsNotNone(result.get("error"))

    @patch("agents.agent2_navigation.nodes.exact_match.capture_screen")
    @patch("agents.agent2_navigation.nodes.exact_match.save_debug_screenshot")
    def test_tree_path_verification(self, mock_save, mock_capture):
        """Full tree path must match exactly including module."""
        from agents.agent2_navigation.nodes.exact_match import exact_match_node

        # Correct path
        good = self._make_candidate(
            "Stock Valuation",
            ["Spare Parts", "Reports", "Inventory", "Stocks", "Stock Valuation"],
            4,
        )
        # Wrong module
        bad = self._make_candidate(
            "Stock Valuation",
            ["Service", "Reports", "Inventory", "Stocks", "Stock Valuation"],
            4,
        )

        state = {
            "error": None,
            "report_name": "Stock Valuation",
            "module": "Spare Parts",
            "folders": ["Reports", "Inventory", "Stocks"],
            "ui_candidates": [bad, good],
        }

        result = exact_match_node(state)
        self.assertIsNotNone(result.get("exact_match"))
        self.assertEqual(result["exact_match"]["tree_path"][0], "Spare Parts")


if __name__ == "__main__":
    unittest.main()
