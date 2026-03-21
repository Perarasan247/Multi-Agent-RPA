"""Node: Click the XLSX/Excel export button in the toolbar."""

from loguru import logger

from orchestrator.state import GlobalState
from config.settings import settings
from automation.window_manager import focus_window
from automation.screenshot import capture_screen, save_debug_screenshot


def click_xlsx_export_node(state: GlobalState) -> GlobalState:
    """Locate and click the Excel/XLSX export option.

    Searches toolbar buttons, menu items, and icon buttons
    for an export-to-Excel action.
    """
    logger.info("[Agent4] Node: click_xlsx_export — entering")
    try:
        app = state["app_handle"]

        # Ensure window focus
        try:
            focus_window(app, settings.app_window_title)
        except Exception:
            logger.warning("Could not re-verify focus before export click.")

        main_win = app.top_window()
        export_btn = None

        # Strategy 1: Button/MenuItem with Excel/XLSX text
        buttons = main_win.descendants(control_type="Button")
        menu_items = main_win.descendants(control_type="MenuItem")
        all_clickables = buttons + menu_items

        for elem in all_clickables:
            try:
                text = elem.window_text().strip().lower()
                auto_id = (elem.element_info.automation_id or "").lower()
                if "excel" in text or "xlsx" in text or "export" in text:
                    export_btn = elem
                    break
                if "excel" in auto_id or "xlsx" in auto_id or "export" in auto_id:
                    export_btn = elem
                    break
            except Exception:
                continue

        # Strategy 2: Look in toolbar for export icon
        if export_btn is None:
            try:
                toolbars = main_win.descendants(control_type="ToolBar")
                for tb in toolbars:
                    tb_buttons = tb.children(control_type="Button")
                    for btn in tb_buttons:
                        try:
                            text = btn.window_text().strip().lower()
                            auto_id = (btn.element_info.automation_id or "").lower()
                            tooltip = ""
                            try:
                                tooltip = (btn.element_info.help_text or "").lower()
                            except Exception:
                                pass
                            if any(
                                kw in s
                                for kw in ("excel", "xlsx", "export", "xls")
                                for s in (text, auto_id, tooltip)
                            ):
                                export_btn = btn
                                break
                        except Exception:
                            continue
                    if export_btn:
                        break
            except Exception:
                pass

        # Strategy 3: Try File menu → Export
        if export_btn is None:
            try:
                menu_bars = main_win.descendants(control_type="MenuBar")
                for mb in menu_bars:
                    items = mb.children(control_type="MenuItem")
                    for item in items:
                        try:
                            text = item.window_text().strip().lower()
                            if "file" in text or "export" in text:
                                item.click_input()
                                import time
                                time.sleep(0.5)
                                # Look for Excel option in submenu
                                sub_items = item.descendants(control_type="MenuItem")
                                for si in sub_items:
                                    si_text = si.window_text().strip().lower()
                                    if "excel" in si_text or "xlsx" in si_text:
                                        export_btn = si
                                        break
                                if export_btn:
                                    break
                        except Exception:
                            continue
                    if export_btn:
                        break
            except Exception:
                pass

        if export_btn is None:
            state["error"] = (
                "XLSX export button not found. Searched buttons, menu items, "
                "toolbars, and File menu."
            )
            logger.error("[Agent4] {}", state["error"])
            try:
                save_debug_screenshot(capture_screen(), "xlsx_export_not_found")
            except Exception:
                pass
            return state

        export_btn.click_input()
        state["xlsx_clicked"] = True
        logger.info("[Agent4] XLSX export button clicked.")

    except Exception as exc:
        state["error"] = f"click_xlsx_export failed: {exc}"
        logger.error("[Agent4] {}", state["error"])
        try:
            save_debug_screenshot(capture_screen(), "click_xlsx_export_error")
        except Exception:
            pass

    return state
