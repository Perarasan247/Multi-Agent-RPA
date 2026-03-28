"""Debug: enumerate controls in the filter panel for the current report."""
import time
from automation.window_manager import connect_to_app, focus_window
from config.settings import settings

app = connect_to_app(settings.app_window_title)
try:
    focus_window(app, settings.app_window_title)
except Exception:
    pass
time.sleep(1.0)

main_win = app.top_window()
title = main_win.window_text()
print(f"Main window: '{title}'")

# Try both backends
for backend_name in ["uia"]:
    print(f"\n=== Backend: {backend_name} ===")
    try:
        from pywinauto import Application
        pid = app.process
        app2 = Application(backend=backend_name).connect(process=pid)
        win = app2.top_window()
        print(f"Top window: '{win.window_text()}'")
        print(f"Number of descendants: ", end="")
        try:
            descs = list(win.descendants())
            print(len(descs))
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        print("\n--- CheckBoxes ---")
        for d in descs:
            try:
                ct = d.element_info.control_type
                if ct == "CheckBox":
                    txt = (d.window_text() or "").strip()
                    aid = (d.element_info.automation_id or "")
                    r = d.rectangle()
                    print(f"  text='{txt}' id='{aid}' rect=({r.left},{r.top},{r.right},{r.bottom})")
            except:
                pass

        print("\n--- Controls with 'Date' in text or name ---")
        for d in descs:
            try:
                txt = (d.window_text() or "").strip()
                name = (d.element_info.name or "").strip()
                aid = (d.element_info.automation_id or "")
                if "date" in txt.lower() or "date" in name.lower() or "Date" in aid:
                    ct = d.element_info.control_type
                    r = d.rectangle()
                    print(f"  type={ct:15s} text='{txt[:40]:40s}' id='{aid}' rect=({r.left},{r.top},{r.right},{r.bottom})")
            except:
                pass

        print("\n--- Controls with 'Generate' in text ---")
        for d in descs:
            try:
                txt = (d.window_text() or "").strip()
                if "generate" in txt.lower():
                    ct = d.element_info.control_type
                    aid = (d.element_info.automation_id or "")
                    r = d.rectangle()
                    print(f"  type={ct:15s} text='{txt}' id='{aid}' rect=({r.left},{r.top},{r.right},{r.bottom})")
            except:
                pass

        print("\n--- Controls with 'Show' in text ---")
        for d in descs:
            try:
                txt = (d.window_text() or "").strip()
                if "show" in txt.lower():
                    ct = d.element_info.control_type
                    aid = (d.element_info.automation_id or "")
                    r = d.rectangle()
                    print(f"  type={ct:15s} text='{txt}' id='{aid}' rect=({r.left},{r.top},{r.right},{r.bottom})")
            except:
                pass

        print("\n--- All controls in right panel (x > win.right - 500) ---")
        wr = win.rectangle()
        count = 0
        for d in descs:
            try:
                r = d.rectangle()
                if r.left > wr.right - 500 and r.right > r.left:
                    txt = (d.window_text() or "").strip()
                    ct = d.element_info.control_type
                    aid = (d.element_info.automation_id or "")
                    if txt or aid:
                        print(f"  type={ct:15s} text='{txt[:35]:35s}' id='{aid:20s}' rect=({r.left},{r.top},{r.right},{r.bottom})")
                        count += 1
            except:
                pass
        print(f"  Total: {count}")

    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        traceback.print_exc()
