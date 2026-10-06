"""Entry point. Keep the complete folder; Start.bat uses a private virtualenv."""
import logging
from logging.handlers import RotatingFileHandler
import sys
import tkinter as tk
from lolpicker.storage import data_dir
from lolpicker.platform_win import SingleInstance, private_directory, bundle_dir


def main():
    directory = data_dir()
    private_directory(directory)
    instance = SingleInstance(directory)
    if not instance.acquired:
        instance.close()
        return
    handler = RotatingFileHandler(directory / "autopicker.log", maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    root = tk.Tk()
    controller = None
    try:
        from lolpicker.controller import Controller
        from lolpicker.ui import App
        controller = Controller(bundle=bundle_dir())
        App(root, controller)
        root.mainloop()
    except Exception:
        logging.exception("Start fehlgeschlagen")
        if controller:
            controller.close()
        root.destroy()
        raise
    finally:
        instance.close()


if __name__ == "__main__":
    if sys.platform != "win32" and "--dev-linux" not in sys.argv:
        raise SystemExit("Dieses Programm ist für Windows. --dev-linux ist nur für Oberflächentests.")
    main()