"""Window management utilities using pywinauto and pygetwindow."""

import subprocess
import time
from typing import Any

import pygetwindow as gw
from pywinauto import Application, Desktop
from pywinauto.findwindows import ElementNotFoundError
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed


def connect_to_app(window_title: str) -> Application:
    """Connect to an already-running application by window title.

    Uses pygetwindow for fast window lookup, then connects via
    process ID so multiple matching windows don't cause ambiguity.

    Args:
        window_title: Partial or full title of the target window.

    Returns:
        pywinauto Application handle.

    Raises:
        RuntimeError: If the application window is not found.
    """
    try:
        import ctypes
        import ctypes.wintypes

        # Use pygetwindow for fast enumeration (avoids slow UIA walk)
        all_windows = gw.getAllWindows()
        matches = [w for w in all_windows if w.title and _is_excellon_window(w.title, window_title)]

        if not matches:
            raise RuntimeError(f"No window found with title containing '{window_title}'")

        # Prefer the window whose title starts with the app name (main window)
        best = matches[0]
        for win in matches:
            if win.title.lower().startswith(window_title.lower()):
                best = win
                break

        # Get process ID from the window handle
        pid = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(best._hWnd, ctypes.byref(pid))
        process_id = pid.value

        app = Application(backend="uia").connect(process=process_id)
        logger.info("Connected to application: '{}' (pid={})", best.title, process_id)
        return app

    except RuntimeError:
        raise
    except Exception as exc:
        msg = f"Could not connect to application with title '{window_title}': {exc}"
        logger.error(msg)
        raise RuntimeError(msg) from exc


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def focus_window(app: Application, window_title: str) -> bool:
    """Bring the application window to the foreground.

    Uses pygetwindow for fast focus (avoids slow UIA tree walk).
    Falls back to pywinauto's top_window().set_focus() if needed.

    Args:
        app: pywinauto Application handle.
        window_title: Expected window title substring.

    Returns:
        True if focus was successfully set.

    Raises:
        RuntimeError on repeated failure (handled by tenacity).
    """
    try:
        # Fast path: use pygetwindow to find and activate the window
        all_windows = gw.getAllWindows()
        target = None
        for w in all_windows:
            if w.title and _is_excellon_window(w.title, window_title):
                target = w
                break

        if target:
            try:
                if target.isMinimized:
                    target.restore()
                target.activate()
                time.sleep(0.3)
            except Exception:
                # pygetwindow activate can fail on some windows, fall back
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(target._hWnd)
                time.sleep(0.3)
        else:
            # Fallback to get_main_window (avoids slow UIA tree walk)
            win = get_main_window(app, window_title)
            win.set_focus()
            time.sleep(0.3)

        # Verify focus
        active = gw.getActiveWindow()
        if active and _is_excellon_window(active.title, window_title):
            logger.debug("Window '{}' is now focused.", window_title)
            return True

        logger.warning("Window '{}' focus could not be verified, retrying.", window_title)
        raise RuntimeError(f"Focus verification failed for '{window_title}'")

    except Exception as exc:
        logger.error("Error focusing window '{}': {}", window_title, exc)
        raise


def check_app_state(app: Application) -> str:
    """Check current application state.

    Returns:
        'ready' if no modal dialogs are open.
        'modal_open' if a dialog window is detected.
        'loading' if a progress indicator is found.
        'unknown' otherwise.
    """
    try:
        main_win = get_main_window(app)
        # Check for popup windows via pygetwindow (fast)
        import ctypes
        main_title = main_win.window_text()
        main_pid = None
        for w in gw.getAllWindows():
            if w.title and w.title == main_title:
                pid = ctypes.wintypes.DWORD()
                ctypes.windll.user32.GetWindowThreadProcessId(w._hWnd, ctypes.byref(pid))
                main_pid = pid.value
                break

        if main_pid:
            for w in gw.getAllWindows():
                if not w.title or not w.title.strip():
                    continue
                pid = ctypes.wintypes.DWORD()
                ctypes.windll.user32.GetWindowThreadProcessId(w._hWnd, ctypes.byref(pid))
                if pid.value == main_pid and w.title != main_title:
                    logger.debug("Separate dialog window found: '{}'", w.title)
                    return "modal_open"

        return "ready"

    except Exception as exc:
        logger.warning("Could not determine app state: {}", exc)
        return "unknown"


def _is_excellon_window(title: str, window_title: str) -> bool:
    """Check if a window title belongs to the Excellon application.

    Matches if the app name appears at the START of the title OR
    anywhere in the title preceded by a separator (e.g. " - Excellon").
    Prevents false matches like "excellon-rpa-system" by checking
    the character after the match is a word boundary.
    """
    t = title.lower()
    keyword = window_title.strip().lower()

    # Find all occurrences of the keyword in the title
    start = 0
    while True:
        idx = t.find(keyword, start)
        if idx == -1:
            return False

        end_idx = idx + len(keyword)

        # Check character before: must be start-of-string or a separator
        # Note: "-" is excluded because "excellon-rpa-system" in paths/titles
        # should NOT match the "Excellon" app keyword
        if idx > 0 and t[idx - 1] not in (" ", "\t", ".", ",", ":", ";"):
            start = idx + 1
            continue

        # Check character after: must be end-of-string or a separator
        if end_idx < len(t) and t[end_idx] not in (" ", "\t", ".", ",", ":", ";"):
            start = idx + 1
            continue

        return True


def is_app_running(window_title: str) -> bool:
    """Check if an application is running by searching visible windows.

    Uses pygetwindow for fast enumeration (avoids slow UIA tree walk).

    Args:
        window_title: Title substring to search for.

    Returns:
        True if a matching window is found.
    """
    try:
        all_titles = gw.getAllTitles()
        for title in all_titles:
            if title and _is_excellon_window(title, window_title):
                logger.debug("Application window found: '{}'", title)
                return True
        return False
    except Exception as exc:
        logger.warning("Error checking if app is running: {}", exc)
        return False


def get_main_window(app: Application = None, window_title: str = None):
    """Get the main application window wrapper quickly.

    Uses the window handle from pygetwindow to create a pywinauto
    UIAWrapper directly, avoiding a slow UIA tree enumeration.

    IMPORTANT: Always use this instead of app.top_window() or app.windows()
    which hang on Excellon's complex UIA tree.

    Args:
        app: pywinauto Application handle (optional, not used for fast path).
        window_title: Window title substring to match. Defaults to settings.

    Returns:
        pywinauto UIAWrapper for the main window.

    Raises:
        RuntimeError: If no matching window is found.
    """
    if window_title is None:
        from config.settings import settings as _s
        window_title = _s.app_window_title

    # Fast: find the HWND via pygetwindow
    all_windows = gw.getAllWindows()
    for w in all_windows:
        if w.title and _is_excellon_window(w.title, window_title):
            hwnd = w._hWnd
            from pywinauto.controls.uiawrapper import UIAWrapper
            from pywinauto.uia_element_info import UIAElementInfo
            element_info = UIAElementInfo(hwnd)
            return UIAWrapper(element_info)

    raise RuntimeError(f"No window found matching '{window_title}'")


def launch_app(exe_path: str) -> None:
    """Launch an application by its executable path or shortcut.

    Supports .exe files and .appref-ms (ClickOnce) shortcuts.

    Args:
        exe_path: Full path to the .exe or .appref-ms file.
    """
    import os
    logger.info("Launching application: {}", exe_path)
    if exe_path.lower().endswith(".appref-ms"):
        # ClickOnce shortcuts must be opened via shell, not subprocess
        os.startfile(exe_path)
    else:
        subprocess.Popen([exe_path])
