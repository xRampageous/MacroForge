import tkinter as tk
import base64
import io
from PIL import Image, ImageTk, ImageGrab
from models import Action
from debugger import logger


class ScreenshotMixin:
    """Mixin for in-app screen region capture."""

    def capture_screen_region(self):
        """Open a transparent overlay to let the user drag-select a screen region."""
        logger.info("Starting screen region capture overlay")
        self.root.withdraw()  # hide main window so it doesn't block the screen

        # Get full screen size across all monitors
        try:
            import ctypes
            user32 = ctypes.windll.user32
            sw = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
            sh = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
            sx = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            sy = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
        except Exception:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            sx = sy = 0

        overlay = tk.Toplevel(self.root)
        overlay.overrideredirect(True)
        overlay.attributes("-topmost", True)
        overlay.attributes("-alpha", 0.3)
        overlay.configure(bg="black")
        overlay.geometry(f"{sw}x{sh}+{sx}+{sy}")
        overlay.deiconify()
        overlay.update_idletasks()

        canvas = tk.Canvas(overlay, bg="black", highlightthickness=0, cursor="cross")
        canvas.pack(fill="both", expand=True)

        # Instructions label
        instr = tk.Label(overlay, text="Drag to select region  •  ESC to cancel",
                          bg="#000000", fg="#ffffff", font=("Segoe UI", 12, "bold"))
        instr.place(relx=0.5, rely=0.1, anchor="center")

        self._cap_start = None
        self._cap_rect = None
        self._cap_sel = None

        def _start(event):
            self._cap_start = (event.x, event.y)
            if self._cap_sel:
                canvas.delete(self._cap_sel)
            self._cap_sel = canvas.create_rectangle(
                event.x, event.y, event.x, event.y,
                outline="#20b87e", width=2, fill=""
            )

        def _move(event):
            if self._cap_start is None:
                return
            x0, y0 = self._cap_start
            x1, y1 = event.x, event.y
            canvas.coords(self._cap_sel, x0, y0, x1, y1)
            # Update instructions with dimensions
            w, h = abs(x1 - x0), abs(y1 - y0)
            instr.config(text=f"{w} x {h} px  •  Release to capture  •  ESC to cancel")

        def _end(event):
            if self._cap_start is None:
                _cancel()
                return
            x0, y0 = self._cap_start
            x1, y1 = event.x, event.y
            overlay.destroy()
            self.root.deiconify()

            # Normalize box (left, top, right, bottom)
            left = min(x0, x1) + sx
            top = min(y0, y1) + sy
            right = max(x0, x1) + sx
            bottom = max(y0, y1) + sy
            if right - left < 4 or bottom - top < 4:
                logger.warning("Capture region too small, cancelled")
                return

            try:
                shot = ImageGrab.grab(bbox=(left, top, right, bottom))
                buf = io.BytesIO()
                shot.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                logger.info(f"Captured region {shot.width}x{shot.height} -> {len(b64)} b64 chars")
                self._create_image_action_from_capture(b64, left, top, right - left, bottom - top)
            except Exception as e:
                logger.error(f"Screen capture failed: {e}")
                import traceback
                traceback.print_exc()

        def _cancel(event=None):
            overlay.destroy()
            self.root.deiconify()
            logger.info("Screen capture cancelled")

        canvas.bind("<Button-1>", _start)
        canvas.bind("<B1-Motion>", _move)
        canvas.bind("<ButtonRelease-1>", _end)
        overlay.bind("<Escape>", _cancel)
        overlay.bind("<KeyPress>", lambda e: _cancel() if e.keysym == "Escape" else None)
        overlay.focus_force()

    def _create_image_action_from_capture(self, image_data, left, top, width, height):
        """Create an image action from captured region data."""
        action = Action(
            key="[IMAGE]",
            duration=0.0,
            action_type="image",
            image_data=image_data,
            similarity=0.95,
            search_region=f"{left},{top},{width},{height}",
            on_not_found="skip",
            on_found_action="continue",
            label="Screenshot",
        )
        self.open_image_editor_pending(action)
