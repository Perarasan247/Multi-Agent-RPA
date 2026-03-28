"""Popup detection and dismissal for Excellon application.

Uses BOTH 'uia' and 'win32' pywinauto backends to catch all popup types,
including .NET/WinForms modal dialogs that the UIA backend alone misses.
"""

import re
import time
from typing import Any, List, Tuple

from pywinauto import Desktop
from loguru import logger

# Window titles to ignore (not popups)
IGNORED_POPUP_TITLES = {"", "Program Manager", "Taskbar"}

# Button click priority order for dismissal
DISMISS_PRIORITY = ["Yes", "OK", "Continue", "Close"]


def find_excellon_pid() -> int | None:
    """Find the process ID of the running Excellon application."""
    for backend in ["uia", "win32"]:
        try:
            for win in Desktop(backend=backend).windows(visible_only=True):
                try:
                    title = win.window_text().strip()
                    if re.search(r"Excellon\s+\d+\.\d+", title, re.IGNORECASE):
                        pid = win.process_id()
                        logger.debug("Found Excellon main window: '{}' pid={}", title, pid)
                        return pid
                    # Also match the login dialog titled just "Excellon"
                    if title == "Excellon":
                        pid = win.process_id()
                        logger.debug("Found Excellon window: '{}' pid={}", title, pid)
                        return pid
                except Exception:
                    continue
        except Exception:
            continue
    return None


def get_popup_windows(app: Any = None) -> List[Tuple[Any, str, str]]:
    """Return list of (window_spec, title, backend) for non-main Excellon windows.

    Scans both 'uia' and 'win32' backends to catch all dialog types.

    Args:
        app: Optional pywinauto Application handle (used to get PID).

    Returns:
        List of (window_specification, title, backend) tuples.
    """
    # Determine the Excellon PID
    pid = None
    if app is not None:
        try:
            pid = app.process
        except Exception:
            try:
                from automation.window_manager import get_main_window
                pid = get_main_window(app).process_id()
            except Exception:
                pass
    if pid is None:
        pid = find_excellon_pid()
    if pid is None:
        logger.debug("Could not find Excellon PID")
        return []

    all_wins = []
    for backend in ["uia", "win32"]:
        try:
            for w in Desktop(backend=backend).windows(visible_only=True):
                try:
                    if w.process_id() != pid:
                        continue
                    title = w.window_text().strip()
                    if len(title) < 2 or title in IGNORED_POPUP_TITLES:
                        continue
                    r = w.rectangle()
                    wd = r.right - r.left
                    ht = r.bottom - r.top
                    if wd < 100 or ht < 40:
                        continue
                    win_spec = Desktop(backend=backend).window(handle=w.handle)
                    all_wins.append((win_spec, title, wd * ht, backend))
                except Exception:
                    continue
        except Exception:
            continue

    if not all_wins:
        return []

    # Identify main window(s) to exclude by TITLE, not by size.
    # Main windows are: "Excellon" (login form) or "Excellon 5.0.xxx" (main app).
    # Everything else from the same process is a popup.
    def _is_main_window(title: str) -> bool:
        t = title.strip()
        # Exact match: just "Excellon" (login form)
        if t.lower() == "excellon":
            return True
        # Versioned: "Excellon 5.0.214.22654"
        if re.search(r"Excellon\s+\d+\.\d+", t, re.IGNORECASE):
            return True
        return False

    popups = []
    seen = set()
    for w, title, area, backend in all_wins:
        if _is_main_window(title):
            continue
        key = (title, backend)
        if key in seen:
            continue
        seen.add(key)
        popups.append((w, title, backend))
        logger.info("[POPUP] Detected: '{}' ({})", title, backend)

    # Sort: known popup titles first
    known_titles = {"login confirmation", "application installation alert",
                    "hsrp compliance", "confirm", "confirmation", "alert",
                    "warning", "information", "error"}

    def _popup_priority(item):
        _, t, _ = item
        t_lower = t.lower()
        for kw in known_titles:
            if kw in t_lower:
                return 0
        return 1

    popups.sort(key=_popup_priority)

    # --- Embedded dialog detection ---
    # Some popups (e.g. HSRP Compliance) are child controls inside the main
    # app window, not separate top-level windows. Search via win32 backend
    # using pygetwindow + HwndWrapper (avoids slow UIA tree walk).
    if not popups:
        try:
            import pygetwindow as pgw
            from pywinauto.controls.hwndwrapper import HwndWrapper
            from automation.window_manager import _is_excellon_window
            from config.settings import settings

            for w in pgw.getAllWindows():
                if not w.title or not _is_excellon_window(w.title, settings.app_window_title):
                    continue
                dlg = HwndWrapper(w._hWnd)
                dialog_buttons = {"ok", "yes", "no", "cancel"}
                for d in dlg.descendants():
                    try:
                        if d.friendly_class_name() != "Button":
                            continue
                        txt = (d.window_text() or "").strip().lower()
                        if txt in dialog_buttons:
                            # Found a dialog button in main window — likely embedded popup
                            logger.info("[POPUP] Detected embedded dialog button: '{}'", txt)
                            popups.append((dlg, w.title, "win32"))
                            return popups
                    except Exception:
                        continue
                break  # Only check first matching window
        except Exception as exc:
            logger.debug("Embedded dialog scan failed: {}", exc)

    return popups


def _dismiss_window(window: Any, backend: str, target_button: str | None = None) -> Tuple[bool, str]:
    """Try to dismiss a popup window.

    Handles both WindowSpecification objects (top-level popups) and
    raw UIAWrapper/control objects (embedded dialogs).

    Args:
        window: pywinauto WindowSpecification or control wrapper.
        backend: 'uia' or 'win32'.
        target_button: If specified, only click this button. Otherwise use DISMISS_PRIORITY.

    Returns:
        Tuple of (success, button_text_clicked).
    """
    try:
        title = window.window_text()
    except Exception:
        title = "Unknown"

    try:
        window.set_focus()
        time.sleep(0.2)
    except Exception:
        pass

    buttons_to_try = [target_button] if target_button else DISMISS_PRIORITY

    # --- Method 1: child_window() (works for WindowSpecification) ---
    for btn_text in buttons_to_try:
        if btn_text is None:
            continue
        for ctrl_type in ["Button", None]:
            try:
                kwargs = {"title": btn_text, "found_index": 0}
                if ctrl_type:
                    kwargs["control_type"] = ctrl_type
                b = window.child_window(**kwargs)
                if b.exists(timeout=0.3):
                    logger.info("[DISMISS] '{}' → '{}'", title, btn_text)
                    try:
                        window.set_focus()
                    except Exception:
                        pass
                    b.click_input()
                    time.sleep(0.4)
                    return True, btn_text.lower()
            except Exception:
                continue

    # --- Method 2: descendants() scan (works for embedded controls) ---
    dialog_buttons = {"yes", "ok", "continue", "close"}
    if target_button:
        dialog_buttons = {target_button.lower()}

    try:
        for btn in window.descendants(control_type="Button"):
            try:
                txt = btn.window_text().strip().lower()
                if txt in dialog_buttons:
                    logger.info("[DISMISS] '{}' → '{}' (descendant scan)", title, txt)
                    btn.click_input()
                    time.sleep(0.4)
                    return True, txt
            except Exception:
                continue
    except Exception:
        pass

    # --- Method 3: Regex fallback ---
    patterns = [r".*OK.*", r".*Yes.*", r".*Close.*", r".*Continue.*"]
    if target_button:
        patterns = [rf".*{re.escape(target_button)}.*"]

    for pat in patterns:
        try:
            b = window.child_window(title_re=pat, control_type="Button", found_index=0)
            if b.exists(timeout=0.2):
                btn_name = b.window_text().strip()
                logger.info("[DISMISS] '{}' → '{}' (regex match)", title, btn_name)
                try:
                    window.set_focus()
                except Exception:
                    pass
                b.click_input()
                time.sleep(0.4)
                return True, btn_name.lower()
        except Exception:
            continue

    logger.warning("[DISMISS] Could not dismiss: '{}'", title)
    return False, ""


# ── Public API (kept compatible with existing callers) ────────────────────────

def wait_for_popup(timeout: int = 5, app: Any = None) -> Any | None:
    """Poll for a popup/dialog belonging to the Excellon app.

    Args:
        timeout: Maximum seconds to wait.
        app: pywinauto Application handle.

    Returns:
        Tuple of (window_spec, title, backend) or None if not found.
    """
    start = time.time()
    while time.time() - start < timeout:
        popups = get_popup_windows(app=app)
        if popups:
            return popups[0]  # Return first popup found
        time.sleep(0.5)
    return None


def get_popup_buttons(popup: Any) -> dict[str, Any]:
    """Extract named buttons from a popup.

    Args:
        popup: Tuple of (window_spec, title, backend) from wait_for_popup,
               or a raw pywinauto window wrapper (legacy).

    Returns:
        Dict mapping lowercase button names to their elements.
    """
    # Handle tuple format from new API
    if isinstance(popup, tuple):
        window, title, backend = popup
    else:
        window = popup
        backend = "uia"

    result: dict[str, Any] = {}
    button_names = {"yes", "ok", "no", "cancel", "close", "continue"}

    for ctrl_type in ["Button", None]:
        for name in button_names:
            if name in result:
                continue
            try:
                kwargs = {"title": name.capitalize() if name != "ok" else "OK",
                          "found_index": 0}
                if ctrl_type:
                    kwargs["control_type"] = ctrl_type
                b = window.child_window(**kwargs)
                if b.exists(timeout=0.1):
                    result[name] = b
            except Exception:
                continue

    # Also try case-insensitive regex for Yes/OK/No/Cancel
    for name in button_names - set(result.keys()):
        try:
            b = window.child_window(title_re=rf"(?i)^{name}$",
                                     control_type="Button", found_index=0)
            if b.exists(timeout=0.1):
                result[name] = b
        except Exception:
            continue

    return result


def handle_popup_yes_ok(timeout: int = 5, app: Any = None) -> str:
    """Wait for a popup and click Yes or OK.

    Priority: Yes button first, then OK if Yes not available.

    Returns:
        'yes_clicked', 'ok_clicked', or 'none_found'.
    """
    start = time.time()
    while time.time() - start < timeout:
        popups = get_popup_windows(app=app)
        if popups:
            window, title, backend = popups[0]
            # Try Yes first, then OK — with both original and alternate backend
            for btn in ["Yes", "OK"]:
                success, clicked = _dismiss_window(window, backend, target_button=btn)
                if success:
                    return f"{clicked}_clicked"
            # Fallback: try any dismissal
            success, clicked = _dismiss_window(window, backend)
            if success:
                return f"{clicked}_clicked"

            # If original backend failed, try the OTHER backend on the same handle
            alt_backend = "uia" if backend == "win32" else "win32"
            try:
                handle = window.handle if hasattr(window, 'handle') else None
                if handle is None:
                    handle = window.wrapper_object().handle
                alt_window = Desktop(backend=alt_backend).window(handle=handle)
                for btn in ["Yes", "OK"]:
                    success, clicked = _dismiss_window(alt_window, alt_backend, target_button=btn)
                    if success:
                        return f"{clicked}_clicked"
                success, clicked = _dismiss_window(alt_window, alt_backend)
                if success:
                    return f"{clicked}_clicked"
            except Exception as exc:
                logger.debug("Alt backend ({}) fallback failed: {}", alt_backend, exc)

            # Last resort: try embedded dialog scan via win32
            try:
                import pyautogui
                import pygetwindow as pgw
                from pywinauto.controls.hwndwrapper import HwndWrapper
                from automation.window_manager import _is_excellon_window
                from config.settings import settings as _settings

                for w in pgw.getAllWindows():
                    if not w.title or not _is_excellon_window(w.title, _settings.app_window_title):
                        continue
                    dlg = HwndWrapper(w._hWnd)
                    for d in dlg.descendants():
                        try:
                            if d.friendly_class_name() != "Button":
                                continue
                            txt = (d.window_text() or "").strip().lower()
                            if txt in ("ok", "yes"):
                                r = d.rectangle()
                                pyautogui.click(r.mid_point().x, r.mid_point().y)
                                logger.info("[DISMISS] Embedded button '{}' clicked", txt)
                                time.sleep(0.4)
                                return f"{txt}_clicked"
                        except Exception:
                            continue
                    break
            except Exception:
                pass

            return "none_found"
        time.sleep(0.5)

    logger.debug("No popup found within {}s.", timeout)
    return "none_found"


def handle_popup_no(timeout: int = 5, app: Any = None) -> str:
    """Wait for a popup and click No.

    Returns:
        'no_clicked' or 'none_found'.
    """
    start = time.time()
    while time.time() - start < timeout:
        popups = get_popup_windows(app=app)
        if popups:
            window, title, backend = popups[0]
            success, clicked = _dismiss_window(window, backend, target_button="No")
            if success:
                return "no_clicked"
            return "none_found"
        time.sleep(0.5)

    logger.debug("No popup found within {}s.", timeout)
    return "none_found"


def dismiss_all_popups(max_iterations: int = 5, app: Any = None,
                       first_timeout: int = 10) -> int:
    """Dismiss all popups by clicking Yes/OK repeatedly.

    Returns:
        Count of popups dismissed.
    """
    count = 0
    for i in range(max_iterations):
        timeout = first_timeout if i == 0 else 5
        result = handle_popup_yes_ok(timeout=timeout, app=app)
        if result == "none_found":
            break
        count += 1
        logger.info("Popup #{} dismissed: {}", count, result)
        time.sleep(1.0)

    logger.info("Total popups dismissed: {}", count)
    return count
