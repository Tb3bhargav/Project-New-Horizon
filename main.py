"""
Project New Horizon — Desktop Application Entry Point.
"""

import sys
import pathlib

# ponytail: durable fallback for isolated venvs (e.g. hermes-agent with include-system-site-packages=false)
# python -> venv has no deps, but Python311 system site-packages does. Fix once, no reinstall needed.
try:
    import customtkinter as ctk
except ModuleNotFoundError:
    _candidates = [
        pathlib.Path(sys.base_prefix) / "Lib" / "site-packages",
        pathlib.Path(r"C:\Users\nj322ws\AppData\Local\Programs\Python\Python311\Lib\site-packages"),
        pathlib.Path(r"C:\Users\nj322ws\AppData\Local\Programs\Python\Python313\Lib\site-packages"),
    ]
    for _p in _candidates:
        if _p.is_dir():
            sys.path.insert(0, str(_p))
    import customtkinter as ctk

from app.gui import HorizonApp

def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    app = HorizonApp(root)

    # Handle window close protocol
    root.protocol("WM_DELETE_WINDOW", app._on_close)

    # Start Tkinter event loop
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app._on_close()

if __name__ == "__main__":
    main()
