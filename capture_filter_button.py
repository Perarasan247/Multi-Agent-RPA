"""One-time script: capture the '<' filter button as a template for OpenCV.

Run this while the Excellon report is open with the filter panel CLOSED
(so the '<' button is visible at the bottom-right).

Usage:
    python capture_filter_button.py
"""
import sys
from pathlib import Path
from automation.screenshot import capture_screen
from automation.window_manager import connect_to_app
from config.settings import settings
import cv2

TEMPLATE_DIR = Path(__file__).resolve().parent / "assets" / "templates"
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

# Connect to Excellon and bring to foreground
from automation.window_manager import focus_window
app = connect_to_app(settings.app_window_title)
main_win = app.top_window()
try:
    focus_window(app, settings.app_window_title)
except Exception:
    main_win.set_focus()
import time
time.sleep(1.0)
win_rect = main_win.rectangle()

# Find "Report Filters" label to locate the button
report_filters_label = None
for ctrl in main_win.descendants():
    try:
        text = ctrl.window_text().strip()
        if text.lower() in ("report filters", "reportfilters"):
            report_filters_label = ctrl
            break
    except Exception:
        continue

if report_filters_label is None:
    print("ERROR: Could not find 'Report Filters' label. Is a report open?")
    sys.exit(1)

label_rect = report_filters_label.rectangle()
print(f"Report Filters label: ({label_rect.left},{label_rect.top}) to ({label_rect.right},{label_rect.bottom})")

# The "<" button is at the bottom of the label area
# Capture a region around it
btn_x = label_rect.left - 25
btn_y = label_rect.bottom - 30
btn_w = 50
btn_h = 40

# Capture full screen and crop
screen = capture_screen()
cropped = screen[btn_y:btn_y + btn_h, btn_x:btn_x + btn_w]

out_path = TEMPLATE_DIR / "filter_arrow_button.png"
cv2.imwrite(str(out_path), cropped)
print(f"Template saved to: {out_path}")
print(f"Template size: {cropped.shape[1]}x{cropped.shape[0]}")

# Also save a wider region for debugging
debug_region = screen[
    max(label_rect.bottom - 60, 0):label_rect.bottom + 10,
    max(label_rect.left - 60, 0):label_rect.right + 10,
]
debug_path = TEMPLATE_DIR / "filter_button_debug_region.png"
cv2.imwrite(str(debug_path), debug_region)
print(f"Debug region saved to: {debug_path}")
