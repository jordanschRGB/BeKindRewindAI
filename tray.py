"""System tray icon using pystray."""

import threading
import webbrowser

import pystray
from PIL import Image, ImageDraw

URL = "http://127.0.0.1:5000"


def create_tray_icon():
    image = _create_icon_image()
    icon = pystray.Icon(
        "MemoryVault",
        image,
        "MemoryVault",
        menu=pystray.Menu(
            pystray.MenuItem("Open MemoryVault", lambda: webbrowser.open(URL)),
            pystray.MenuItem("Quit", lambda icon, item: icon.stop()),
        ),
    )
    return icon


def _create_icon_image():
    img = Image.new("RGB", (64, 64), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    draw.polygon([(20, 12), (20, 52), (52, 32)], fill=(0, 200, 100))
    return img
