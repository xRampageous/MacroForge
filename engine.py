import time
import threading
import random
import base64
import io
import os
import ctypes
from copy import deepcopy

import pyautogui
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.0
from pynput import keyboard
from pynput.keyboard import Key

from PlatformInput import PlatformInput
from models import Action


class ExecutionEngine:
    def __init__(self, status_cb, play_cb, complete_cb, progress_cb):
        self.actions = []
        self.running = False
        self.paused = False
        self.status = status_cb
        self.play_cb = play_cb
        self.complete_cb = complete_cb
        self.progress_cb = progress_cb
        self.time_cursor = 0.0
        self.current_action_index = -1
        self.total_actions = 0
        self.speed_multiplier = 1.0
        self.infinite_loop = False
        self.before_action_hook = None
        self.after_action_hook = None
        self.pause_cb = None
        self.retry_count = 3
        self.simulation_mode = False
        self.loops_completed_count = 0
        self.human_curve = True   # Adds subtle ease-in/out jitter to key presses
        self._flash_cb = None     # Optional callback(loc) to flash matched region on screen
        self._last_image_found = False  # Set by _exec_image_search; read by loop_until_found
        self.focus_lock = False         # If True, refocus _focus_hwnd before each action
        self._focus_hwnd = None         # Window handle captured at start
        self.input = PlatformInput()    # Fast Windows SendInput backend
        self.ai_matcher = None          # Lazy-load AIImageMatcher when first image search uses it

    def capture_focus_window(self):
        """Capture whichever window currently has focus (call on Start)."""
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            self._focus_hwnd = hwnd if hwnd else None
        except Exception:
            self._focus_hwnd = None

    def _refocus(self):
        """Bring the locked window back to foreground."""
        if not self.focus_lock or not self._focus_hwnd:
            return
        try:
            import ctypes
            u32 = ctypes.windll.user32
            # If minimised, restore it first
            if u32.IsIconic(self._focus_hwnd):
                u32.ShowWindow(self._focus_hwnd, 9)  # SW_RESTORE
            u32.SetForegroundWindow(self._focus_hwnd)
        except Exception:
            pass

    def _human_sample(self, max_s: float) -> float:
        """Return a beta-distributed random seconds value in [0, max_s].
        Biased toward the low end (alpha=1.5, beta=4) — short most of the time,
        natural long-tail outliers occasionally.
        """
        return random.betavariate(1.5, 4.0) * max_s

    def _exec_image_search(self, action: 'Action'):
        """Execute an image-search action: locate template on screen and react."""
        if not action.image_data:
            self.status("Image action: no template captured — skipping")
            return
        try:
            import cv2  # noqa — needed by pyautogui confidence matching
        except ImportError:
            self.status("Image search requires: pip install opencv-python")
            return
        try:
            from PIL import Image
            import pyautogui as _pag

            # ── Build template list (primary + extra OR images) ───────────
            templates = []
            for b64 in [action.image_data] + [x for x in action.extra_images.split("|") if x]:
                try:
                    templates.append(Image.open(io.BytesIO(base64.b64decode(b64))))
                except Exception:
                    pass
            if not templates:
                self.status("Image action: no valid template — skipping")
                return

            # ── Parse region ──────────────────────────────────────────────
            region = None
            if action.search_region == "foreground":
                try:
                    import ctypes
                    hwnd = ctypes.windll.user32.GetForegroundWindow()
                    r = ctypes.wintypes.RECT()
                    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
                    region = (r.left, r.top, r.right - r.left, r.bottom - r.top)
                except Exception:
                    region = None
            elif action.search_region:
                try:
                    parts = [int(v.strip()) for v in action.search_region.split(",")]
                    if len(parts) == 4:
                        region = tuple(parts)
                except Exception:
                    pass

            if self.simulation_mode:
                self.status(f"[Simulate] Image search ({len(templates)} template(s), conf={action.similarity:.2f})")
                return

            # ── Polling loop (respects wait_timeout + pause) ────────────
            timeout       = max(0.0, action.wait_timeout)
            poll_interval = 0.10
            deadline      = time.time() + timeout
            loc           = None
            matched_tmpl  = 0
            _last_status  = 0.0

            # Use all_screens=True for multi-monitor; grayscale speeds up matching
            _use_grayscale = action.similarity < 0.98
            while self.running:
                # Respect pause
                if self.paused:
                    pause_start = time.time()
                    while self.paused and self.running:
                        time.sleep(0.05)
                    deadline += time.time() - pause_start

                for ti, tmpl in enumerate(templates):
                    try:
                        loc = _pag.locateOnScreen(
                            tmpl,
                            confidence=action.similarity,
                            region=region,
                            grayscale=_use_grayscale,
                            minSearchTime=0,
                        )
                        if loc is not None:
                            matched_tmpl = ti + 1
                            break
                    except _pag.ImageNotFoundException:
                        loc = None
                    except Exception as search_err:
                        # Skip this template instead of aborting entire macro
                        self.status(f"Image search warning (template {ti+1}): {search_err}")
                        loc = None
                        continue

                if loc is not None:
                    break
                if time.time() >= deadline:
                    break
                remaining = deadline - time.time()
                now = time.time()
                if now - _last_status >= 1.0:
                    self.status(f"Waiting for image… {remaining:.1f}s left")
                    _last_status = now
                time.sleep(min(poll_interval, remaining))

            # ── React ─────────────────────────────────────────────────────
            if loc is not None:
                # Compute click point
                cx, cy = _pag.center(loc)

                if action.random_click:
                    # Random point within the matched bbox (human-like, avoids dead centre)
                    margin = max(2, int(min(loc.width, loc.height) * 0.15))
                    cx = random.randint(loc.left + margin, loc.left + loc.width  - margin)
                    cy = random.randint(loc.top  + margin, loc.top  + loc.height - margin)

                # Apply offset
                cx += action.click_offset_x
                cy += action.click_offset_y

                tmpl_lbl = f" (template {matched_tmpl})" if len(templates) > 1 else ""
                self.status(f"Image found at {cx},{cy}{tmpl_lbl} -> {action.on_found_action}")
                self._last_image_found = True

                try:
                    # Move mouse to match first if requested (independent of action)
                    if action.position_mouse or action.on_found_action == "move_to":
                        self.input.move_to(cx, cy)

                    if action.on_found_action == "click":
                        self.input.click(cx, cy)
                    elif action.on_found_action == "double_click":
                        self.input.double_click(cx, cy)
                    elif action.on_found_action == "press_key" and action.on_found_key:
                        self.input.press(action.on_found_key)
                    # "continue" / "move_to" — just move on after the moveTo above
                except Exception as act_err:
                    self.status(f"Image action failed: {act_err}")

                # Flash AFTER the action so topmost overlay never intercepts the click
                if hasattr(self, '_flash_cb') and self._flash_cb:
                    self._flash_cb(loc)
            else:
                self._last_image_found = False
                waited = f" (waited {timeout:.0f}s)" if timeout > 0 else ""
                if action.on_not_found == "stop":
                    self.status(f"✗ Image not found{waited} — STOPPED (set 'When not found' to skip to continue)")
                    self.running = False
                elif action.on_not_found == "warn":
                    self.status(f"⚠ Image not found{waited} — continuing")
                else:
                    self.status(f"↷ Image not found{waited} — skipping action")

        except Exception as e:
            self.status(f"Image search error: {e}")

    def stop(self):
        self.running = False
        self.paused = False

    def toggle_pause(self):
        if self.running:
            self.paused = not self.paused
            self.status("Paused" if self.paused else "Running")
            if self.pause_cb:
                self.pause_cb(self.paused)

    def _eval_condition(self, action: Action) -> bool:
        """Evaluate a condition action and return True/False."""
        ctype = action.condition_type
        if ctype == "pixel_color":
            try:
                import ctypes
                dc = ctypes.windll.user32.GetDC(0)
                color = ctypes.windll.gdi32.GetPixel(dc, action.condition_x, action.condition_y)
                ctypes.windll.user32.ReleaseDC(0, dc)
                if color == 0xFFFFFFFF:
                    return False
                # Convert 0x00BBGGRR → #RRGGBB
                r = color & 0xFF
                g = (color >> 8) & 0xFF
                b = (color >> 16) & 0xFF
                actual_hex = f"#{r:02x}{g:02x}{b:02x}"
                return actual_hex.lower() == action.condition_color.lower()
            except Exception:
                return False
        elif ctype == "variable":
            val = getattr(self, f"_var_{action.condition_var_name}", "")
            return str(val) == str(action.condition_var_value)
        return True

    def apply_randomization(self, action: Action) -> Action:
        """Apply randomization to action with error handling"""
        try:
            needs_copy = (action.random_delay > 0) or (action.random_key and not action.is_pause())
            if not needs_copy:
                return action
            action = deepcopy(action)
            if action.random_delay > 0:
                delay_variance = random.uniform(-action.random_delay, action.random_delay)
                action.duration = max(0.1, action.duration + delay_variance)
            if action.random_key:
                key_variations = {
                    "w": ["w", "a", "s", "d"],
                    "a": ["a", "w", "s", "d"],
                    "s": ["s", "w", "a", "d"],
                    "d": ["d", "w", "a", "s"],
                    "1": ["1", "2", "3"],
                    "2": ["2", "1", "3"],
                    "3": ["3", "1", "2"],
                }
                if action.key in key_variations:
                    action.key = random.choice(key_variations[action.key])
        except Exception:
            pass  # Fallback to original action if randomization fails

        return action
 
    def run(self, loops: int):
        self.running = True
        self.paused = False
        self.time_cursor = 0.0
        self.total_actions = len(self.actions)
        loop_actions_executed = 0
        self.loops_completed_count = 0
        _completed_naturally = False
 
        self.status("Running...")
 
        try:
            loop_num = 0
            while self.running:
                if not self.infinite_loop and loop_num >= loops:
                    break
 
                if self.infinite_loop:
                    self.status("Loop: ∞")
                else:
                    self.status(f"Loop {loop_num + 1}/{loops}")
 
                loop_actions_executed = 0
                _restart_loop = False
                i = 0
                while i < len(self.actions):
                    if not self.running:
                        break

                    action = self.actions[i]
                    actual_action = self.apply_randomization(action)

                    self.current_action_index = i
                    self.play_cb(i)

                    # Refocus locked window before every action
                    self._refocus()

                    # Before action hook
                    if self.before_action_hook:
                        try:
                            self.before_action_hook(actual_action)
                        except Exception:
                            pass

                    repeat = max(1, getattr(actual_action, 'repeat_count', 1))

                    if actual_action.is_image():
                        for _r in range(repeat):
                            if not self.running:
                                break
                            self._exec_image_search(actual_action)
                        loop_actions_executed += 1
                        if self.total_actions > 0:
                            self.progress_cb((loop_actions_executed / self.total_actions) * 100)
                        # Conditional jump on found / not found
                        if self._last_image_found:
                            jf = getattr(actual_action, 'jump_to_on_found', -1)
                            if 0 <= jf < len(self.actions):
                                i = jf
                                continue
                        else:
                            jnf = getattr(actual_action, 'jump_to_on_not_found', -1)
                            if 0 <= jnf < len(self.actions):
                                i = jnf
                                continue
                        # loop_until_found: restart sequence without incrementing loop count
                        if actual_action.loop_until_found and self.running:
                            if not self._last_image_found:
                                self.status("Image not found — looping sequence...")
                                _restart_loop = True
                                break
                        i += 1
                        continue

                    if actual_action.is_pause():
                        for _r in range(repeat):
                            if not self.running:
                                break
                            sleep_time = actual_action.duration / self.speed_multiplier
                            end_pause = time.time() + sleep_time
                            while time.time() < end_pause and self.running:
                                if self.paused:
                                    pause_start = time.time()
                                    while self.paused:
                                        time.sleep(0.05)
                                    end_pause += time.time() - pause_start
                                time.sleep(0.01)
                            self.time_cursor += actual_action.duration
                        loop_actions_executed += 1
                        if self.total_actions > 0:
                            self.progress_cb((loop_actions_executed / self.total_actions) * 100)
                        i += 1
                        continue

                    if actual_action.is_click():
                        for _r in range(repeat):
                            if not self.running:
                                break
                            cx, cy = actual_action.click_x, actual_action.click_y
                            mode = actual_action.click_coord_mode
                            if mode == "foreground":
                                try:
                                    import ctypes, ctypes.wintypes as _wt
                                    hwnd = ctypes.windll.user32.GetForegroundWindow()
                                    rect = _wt.RECT()
                                    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                                    cx += rect.left; cy += rect.top
                                except Exception:
                                    pass
                            elif mode == "offset":
                                try:
                                    mx, my = self.input.position()
                                    cx += mx; cy += my
                                except Exception:
                                    pass
                            elif mode == "current":
                                try:
                                    cx, cy = self.input.position()
                                except Exception:
                                    pass
                            r = actual_action.click_rand_radius
                            if r > 0:
                                cx += random.randint(-r, r)
                                cy += random.randint(-r, r)
                            if not self.simulation_mode:
                                btn = actual_action.click_button
                                if btn == "double":
                                    self.input.double_click(cx, cy)
                                elif getattr(actual_action, 'hold_mode', False):
                                    self.input.move_to(cx, cy)
                                    time.sleep(0.005)
                                    self.input.mouse_down(btn)
                                    end_time = time.time() + (actual_action.duration / self.speed_multiplier)
                                    while time.time() < end_time and self.running:
                                        if self.paused:
                                            pause_start = time.time()
                                            while self.paused:
                                                time.sleep(0.05)
                                            end_time += time.time() - pause_start
                                        time.sleep(0.01)
                                    self.input.mouse_up(btn)
                                elif btn == "right":
                                    self.input.right_click(cx, cy)
                                elif btn == "middle":
                                    self.input.middle_click(cx, cy)
                                else:
                                    self.input.click(cx, cy)
                            mode = "hold" if getattr(actual_action, 'hold_mode', False) else "click"
                            self.status(f"{mode.capitalize()} {actual_action.click_button} at {cx},{cy}")
                        loop_actions_executed += 1
                        if self.total_actions > 0:
                            self.progress_cb((loop_actions_executed / self.total_actions) * 100)
                        i += 1
                        continue

                    if actual_action.is_condition():
                        result = self._eval_condition(actual_action)
                        self.status(f"Condition {actual_action.condition_type} → {result}")
                        if result:
                            j = actual_action.condition_jump_true
                        else:
                            j = actual_action.condition_jump_false
                        if 0 <= j < len(self.actions):
                            i = j
                            continue
                        loop_actions_executed += 1
                        if self.total_actions > 0:
                            self.progress_cb((loop_actions_executed / self.total_actions) * 100)
                        i += 1
                        continue

                    # Key action — execute repeat_count times
                    start_time = time.time()
                    for _r in range(repeat):
                        if not self.running:
                            break
                        hc_in = hc_out = 0.0
                        if self.human_curve:
                            budget = 0.004
                            hc_in  = self._human_sample(budget)
                            hc_out = self._human_sample(budget - hc_in)
                            time.sleep(hc_in)
                        end_time = time.time() + (actual_action.duration / self.speed_multiplier) - hc_out
                        for attempt in range(self.retry_count):
                            if not self.running:
                                break
                            try:
                                if not self.simulation_mode:
                                    self.input.key_down(actual_action.key)
                                while time.time() < end_time and self.running:
                                    if self.paused:
                                        pause_start = time.time()
                                        while self.paused:
                                            time.sleep(0.05)
                                        end_time += time.time() - pause_start
                                    time.sleep(0.01)
                                if self.human_curve and self.running:
                                    time.sleep(hc_out)
                                break
                            except Exception as e:
                                if attempt == self.retry_count - 1:
                                    self.status(f"Error after {self.retry_count} retries: {e}")
                                else:
                                    time.sleep(0.1)
                            finally:
                                try:
                                    if not self.simulation_mode:
                                        self.input.key_up(actual_action.key)
                                except Exception:
                                    pass

                    # After action hook
                    if self.after_action_hook:
                        try:
                            self.after_action_hook(actual_action)
                        except Exception:
                            pass

                    loop_actions_executed += 1
                    if self.total_actions > 0:
                        self.progress_cb((loop_actions_executed / self.total_actions) * 100)
                    actual_duration = time.time() - start_time
                    self.time_cursor += actual_duration * self.speed_multiplier
                    i += 1

                if not _restart_loop:
                    loop_num += 1
                self.loops_completed_count = loop_num
 
            _completed_naturally = True

        except Exception as e:
            self.status(f"Engine error: {e}")
        finally:
            self.running = False
            self.current_action_index = -1
            self.complete_cb()
            if _completed_naturally:
                self.status("Done")
