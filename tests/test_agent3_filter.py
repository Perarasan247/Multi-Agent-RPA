"""Tests for Agent 3: Filter — config parsing and checkbox logic."""

import unittest
from unittest.mock import patch, MagicMock


class TestFilterConfigParsing(unittest.TestCase):
    """Test filter configuration loading and application."""

    def test_filters_present_are_applied(self):
        """Reports with filters should return a non-empty list."""
        from config.report_loader import get_filters

        filters = get_filters("spareparts_sales_statement")
        self.assertIn("Show Taxes", filters)
        self.assertIn("Show Tax Detail", filters)
        self.assertEqual(len(filters), 2)

    def test_no_filters_key_skips_checkboxes(self):
        """Reports without a 'filters' key should return empty list."""
        from config.report_loader import get_filters

        filters = get_filters("spareparts_sale_return_statement")
        self.assertEqual(filters, [])

    def test_nonexistent_report_returns_empty(self):
        """Non-existent report key should return empty filter list."""
        from config.report_loader import get_filters

        filters = get_filters("this_report_does_not_exist")
        self.assertEqual(filters, [])


class TestHandleTaxCheckboxesNode(unittest.TestCase):
    """Test the handle_tax_checkboxes node logic."""

    def test_empty_filters_skips(self):
        """When filters list is empty, node should pass without error."""
        from agents.agent3_filter.nodes.handle_tax_checkboxes import handle_tax_checkboxes_node

        state = {
            "error": None,
            "app_handle": MagicMock(),
            "filters": [],
        }
        result = handle_tax_checkboxes_node(state)
        self.assertTrue(result.get("tax_boxes_handled"))
        self.assertIsNone(result.get("error"))


class TestFilenameBuilder(unittest.TestCase):
    """Test filename construction logic from Agent 4."""

    @patch("agents.agent4_download.nodes.build_filename.settings")
    def test_filename_format_correct(self, mock_settings):
        """Filename should follow expected pattern."""
        mock_settings.dealer_code = "D10836"
        mock_settings.branch_code = "BR001"
        mock_settings.report_key = "spareparts_sales_statement"
        mock_settings.filter_from_date = "01/03/2026"
        mock_settings.filter_to_date = "31/03/2026"

        from agents.agent4_download.nodes.build_filename import build_filename_node

        state = {
            "error": None,
            "report_key": "spareparts_sales_statement",
            "from_date": "01/03/2026",
            "to_date": "31/03/2026",
        }
        result = build_filename_node(state)

        filename = result.get("filename_built", "")
        self.assertTrue(filename.endswith(".xlsx"))
        self.assertIn("D10836", filename)
        self.assertIn("BR001", filename)
        self.assertIn("spareparts_sales_statement", filename)

    @patch("agents.agent4_download.nodes.build_filename.settings")
    def test_filename_no_spaces(self, mock_settings):
        """Filename should contain no spaces."""
        mock_settings.dealer_code = "D10836"
        mock_settings.branch_code = "BR001"
        mock_settings.report_key = "spareparts_sales_statement"
        mock_settings.filter_from_date = "01/03/2026"
        mock_settings.filter_to_date = "31/03/2026"

        from agents.agent4_download.nodes.build_filename import build_filename_node

        state = {
            "error": None,
            "report_key": "spareparts_sales_statement",
            "from_date": "01/03/2026",
            "to_date": "31/03/2026",
        }
        result = build_filename_node(state)
        filename = result.get("filename_built", "")
        self.assertNotIn(" ", filename)

    @patch("agents.agent4_download.nodes.build_filename.settings")
    def test_filename_date_format(self, mock_settings):
        """Date portions should use dashes instead of slashes."""
        mock_settings.dealer_code = "D10836"
        mock_settings.branch_code = "BR001"
        mock_settings.report_key = "spareparts_sales_statement"
        mock_settings.filter_from_date = "01/03/2026"
        mock_settings.filter_to_date = "31/03/2026"

        from agents.agent4_download.nodes.build_filename import build_filename_node

        state = {
            "error": None,
            "report_key": "spareparts_sales_statement",
            "from_date": "01/03/2026",
            "to_date": "31/03/2026",
        }
        result = build_filename_node(state)
        filename = result.get("filename_built", "")
        # Slashes should be converted to dashes or removed
        self.assertNotIn("/", filename)


if __name__ == "__main__":
    unittest.main()
