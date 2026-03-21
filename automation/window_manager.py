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

    Connects via process ID so multiple matching windows (e.g. main app
    + an open report) don't cause an ambiguity error.

    Args:
        window_title: Partial or full title of the target window.

    Returns:
        pywinauto Application handle.

    Raises:
        RuntimeError: If the application window is not found.
    """
    try:
        # Find all top-level windows whose title contains window_title
        desktop = Desktop(backend="uia")
        matches = []
        for win in desktop.windows():
            try:
                title = win.window_text()
                if title and window_title.lower() in title.lower():
                    matches.append(win)
            except Exception:
                continue

        if not matches:
            raise RuntimeError(f"No window found with title containing '{window_title}'")

        # Prefer the window whose title starts with the app name (main window)
        # rather than a child/report window
        best = matches[0]
        for win in matches:
            try:
                t = win.window_text()
                if t.lower().startswith(window_title.lower()):
                    best = win
                    break
            except Exception:
                continue

        pid = best.process_id()
        app = Application(backend="uia").connect(process=pid)
        logger.info("Connected to application: {} (pid={})", window_title, pid)
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

    Args:
        app: pywinauto Application handle.
        window_title: Expected window title substring.

    Returns:
        True if focus was successfully set.

    Raises:
        RuntimeError on repeated failure (handled by tenacity).
    """
    try:
        win = app.top_window()
        win.set_focus()
        time.sleep(0.3)

        # Verify focus using pygetwindow
        active_windows = gw.getWindowsWithTitle(window_title)
        if active_windows:
            for w in active_windows:
                if w.isActive:
                    logger.debug("Window '{}' is now focused.", window_title)
                    return True

        # Fallback: check if our window is the active window
        active = gw.getActiveWindow()
        if active and window_title.lower() in active.title.lower():
            logger.debug("Window '{}' verified active via getActiveWindow.", window_title)
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
        main_win = app.top_window()
        children = main_win.children()

        for child in children:
            try:
                ctrl_type = child.element_info.control_type
                if ctrl_type == "Window" or ctrl_type == "Dialog":
                    dialog_title = child.window_text()
                    logger.debug("Modal dialog detected: '{}'", dialog_title)
                    return "modal_open"
            except Exception:
                continue

        # Check for any separate dialog windows
        dialogs = app.windows()
        if len(dialogs) > 1:
            for dlg in dialogs:
                title = dlg.window_text()
                if title and title != main_win.window_text():
                    logger.debug("Separate dialog window found: '{}'", title)
                    return "modal_open"

        return "ready"

    except Exception as exc:
        logger.warning("Could not determine app state: {}", exc)
        return "unknown"


def is_app_running(window_title: str) -> bool:
    """Check if an application is running by searching visible windows.

    Args:
        window_title: Title substring to search for.

    Returns:
        True if a matching window is found.
    """
    try:
        windows = Desktop(backend="uia").windows()
        for win in windows:
            try:
                title = win.window_text()
                if title and window_title.lower() in title.lower():
                    logger.debug("Application window found: '{}'", title)
                    return True
            except Exception:
                continue
        return False
    except Exception as exc:
        logger.warning("Error checking if app is running: {}", exc)
        return False


def launch_app(exe_path: str) -> None:
    """Launch an application by its executable path.

    Args:
        exe_path: Full path to the .exe file.
    """
    logger.info("Launching application: {}", exe_path)
    subprocess.Popen([exe_path])
