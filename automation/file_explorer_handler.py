"""Windows File Explorer / Save As dialog handler."""

import time
from typing import Any

from pywinauto import Desktop
from loguru import logger

from automation.keyboard_mouse import clear_field, type_text_slow, press_key


def wait_for_save_dialog(timeout: int = 15) -> Any:
    """Wait for a Save As dialog to appear.

    Args:
        timeout: Maximum seconds to wait.

    Returns:
        Dialog window wrapper.

    Raises:
        TimeoutError: If dialog does not appear within timeout.
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            windows = Desktop(backend="uia").windows()
            for win in windows:
                try:
                    title = win.window_text().strip().lower()
                    if "save as" in title or "save" in title:
                        logger.info("Save dialog found: '{}'", win.window_text())
                        return win
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(0.5)

    raise TimeoutError(
        f"Save As dialog did not appear within {timeout}s."
    )


def set_filename(dialog: Any, filename: str) -> None:
    """Set the filename in a Save As dialog.

    Args:
        dialog: The Save As dialog wrapper.
        filename: Desired filename (without path).
    """
    # Strategy 1: Find Edit control with AutomationId "FileNameControlHost" or similar
    edit_field = None
    try:
        edits = dialog.descendants(control_type="Edit")
        for edit in edits:
            try:
                auto_id = (edit.element_info.automation_id or "").lower()
                name = (edit.element_info.name or "").lower()
                if "filename" in auto_id or "file name" in name or "name" in auto_id:
                    edit_field = edit
                    break
            except Exception:
                continue
    except Exception:
        pass

    # Strategy 2: Find ComboBox with "File name" label, get its Edit child
    if edit_field is None:
        try:
            combos = dialog.descendants(control_type="ComboBox")
            for combo in combos:
                try:
                    name = (combo.element_info.name or "").lower()
                    if "file name" in name or "filename" in name:
                        edit_children = combo.children(control_type="Edit")
                        if edit_children:
                            edit_field = edit_children[0]
                            break
                except Exception:
                    continue
        except Exception:
            pass

    # Strategy 3: Just use the first Edit in the dialog
    if edit_field is None:
        try:
            edits = dialog.descendants(control_type="Edit")
            if edits:
                edit_field = edits[0]
        except Exception:
            pass

    if edit_field is None:
        raise RuntimeError("Could not find filename field in Save As dialog.")

    clear_field(edit_field)
    type_text_slow(edit_field, filename, delay=0.03)
    logger.info("Filename set to: '{}'", filename)


def navigate_to_folder(dialog: Any, folder_path: str) -> None:
    """Navigate to a specific folder in the Save As dialog.

    Uses the address bar to navigate directly.

    Args:
        dialog: The Save As dialog wrapper.
        folder_path: Full path to the target folder.
    """
    # Find the address bar / breadcrumb area
    address_bar = None

    # Strategy 1: Look for address bar by AutomationId
    try:
        edits = dialog.descendants(control_type="Edit")
        for edit in edits:
            try:
                auto_id = (edit.element_info.automation_id or "").lower()
                if "address" in auto_id or "breadcrumb" in auto_id or "path" in auto_id:
                    address_bar = edit
                    break
            except Exception:
                continue
    except Exception:
        pass

    # Strategy 2: Look for toolbar with "Address" in name
    if address_bar is None:
        try:
            toolbars = dialog.descendants(control_type="ToolBar")
            for tb in toolbars:
                try:
                    name = (tb.element_info.name or "").lower()
                    auto_id = (tb.element_info.automation_id or "").lower()
                    if "address" in name or "address" in auto_id:
                        # Click the toolbar to activate address edit mode
                        tb.click_input()
                        time.sleep(0.5)
                        # Now look for the edit field that appeared
                        edits = dialog.descendants(control_type="Edit")
                        for edit in edits:
                            try:
                                auto_id_e = (edit.element_info.automation_id or "").lower()
                                if "address" in auto_id_e or "path" in auto_id_e:
                                    address_bar = edit
                                    break
                            except Exception:
                                continue
                        if address_bar:
                            break
                except Exception:
                    continue
        except Exception:
            pass

    if address_bar is None:
        # Strategy 3: Click the breadcrumb bar area and type path
        logger.warning("Address bar not found, using filename field for navigation.")
        # Type the full path including filename into the filename field
        try:
            edits = dialog.descendants(control_type="Edit")
            if edits:
                address_bar = edits[0]
        except Exception:
            raise RuntimeError("Could not find any input field in Save As dialog.")

    # Activate and type the path
    address_bar.click_input()
    time.sleep(0.2)
    clear_field(address_bar)
    type_text_slow(address_bar, folder_path, delay=0.02)
    press_key("enter")

    # Wait for folder navigation to complete
    start = time.time()
    while time.time() - start < 10:
        time.sleep(0.5)
        try:
            # Check if dialog is still responsive
            dialog.window_text()
            logger.info("Navigated to folder: '{}'", folder_path)
            return
        except Exception:
            pass

    logger.warning("Folder navigation may not have completed for: '{}'", folder_path)


def click_save_button(dialog: Any) -> None:
    """Click the Save button in the Save As dialog.

    Args:
        dialog: The Save As dialog wrapper.
    """
    save_btn = None

    try:
        buttons = dialog.descendants(control_type="Button")
        for btn in buttons:
            try:
                text = btn.window_text().strip().lower()
                if text in ("save", "&save", "s&ave"):
                    save_btn = btn
                    break
            except Exception:
                continue
    except Exception:
        pass

    # Strategy 2: SplitButton
    if save_btn is None:
        try:
            splits = dialog.descendants(control_type="SplitButton")
            for btn in splits:
                try:
                    text = btn.window_text().strip().lower()
                    if "save" in text:
                        save_btn = btn
                        break
                except Exception:
                    continue
        except Exception:
            pass

    if save_btn is None:
        raise RuntimeError("Could not find Save button in dialog.")

    save_btn.click_input()
    logger.info("Save button clicked.")

    # Wait for dialog to close
    start = time.time()
    while time.time() - start < 10:
        try:
            dialog.window_text()
            time.sleep(0.5)
        except Exception:
            logger.info("Save dialog closed successfully.")
            return

    logger.warning("Save dialog may still be open after clicking Save.")
