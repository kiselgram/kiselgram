import sys
import time
import threading
import shutil
import select
import termios
import tty
import builtins

# ----------------------------------------------------------------------
# 256‑colour rainbow palette (foreground only)
# ----------------------------------------------------------------------
def _rainbow_ansi(steps=255):
    codes = []
    for i in range(steps):
        hue = (i / steps) * 360
        h = hue / 60
        c, x = 1.0, 1.0 - abs((h % 2) - 1.0)
        if h < 1:   r, g, b = c, x, 0
        elif h < 2: r, g, b = x, c, 0
        elif h < 3: r, g, b = 0, c, x
        elif h < 4: r, g, b = 0, x, c
        elif h < 5: r, g, b = x, 0, c
        else:       r, g, b = c, 0, x
        ri, gi, bi = int(r*255), int(g*255), int(b*255)
        ansi = 16 + 36*(ri//51) + 6*(gi//51) + (bi//51)
        codes.append(f"\033[38;5;{ansi}m")
    return codes

BLACK_BG = "\033[48;5;0m"

# ----------------------------------------------------------------------
# Out – colour‑aware print & input with global override
# ----------------------------------------------------------------------
# Store the genuine built‑in functions at module level
_ORIGINAL_PRINT = builtins.print
_ORIGINAL_INPUT = builtins.input

class Out:
    def __init__(self, stdout, color):
        self.stdout = stdout
        self.color = color
        self._orig_print = _ORIGINAL_PRINT
        self._orig_input = _ORIGINAL_INPUT
        self._active = False

    # ---- basic coloured output ----
    def print(self, *args, sep=' ', end='\n', flush=False):
        """Print with the retained rainbow colour on black background."""
        text = sep.join(str(a) for a in args) + end
        self.stdout.write(f"{BLACK_BG}{self.color}{text}\033[0m")
        if flush:
            self.stdout.flush()

    def input(self, prompt: str = "") -> str:
        """Show *prompt* in colour, then read a line using the real input()."""
        if prompt:
            # print the prompt without a newline
            self.stdout.write(f"{BLACK_BG}{self.color}{prompt}\033[0m")
            self.stdout.flush()
        # Always use the real, original input (never the overridden one)
        return self._orig_input('')

    # ---- global override ----
    def activate(self):
        """Replace global print() and input() with the colour‑aware versions."""
        if not self._active:
            builtins.print = self._wrapped_print
            builtins.input = self._wrapped_input
            self._active = True

    def deactivate(self):
        """Restore the original print() and input()."""
        if self._active:
            builtins.print = self._orig_print
            builtins.input = self._orig_input
            self._active = False

    def _wrapped_print(self, *args, **kwargs):
        self.print(*args, **kwargs)

    def _wrapped_input(self, prompt: str = "") -> str:
        return self.input(prompt)

    # ---- context manager ----
    def __enter__(self):
        self.activate()
        return self

    def __exit__(self, *args):
        self.deactivate()

# ----------------------------------------------------------------------
# Animate – the main class
# ----------------------------------------------------------------------
class Animate:
    def __init__(self, fps=60, enter_escape=False):
        self.buffer_lines = []
        self._stop = threading.Event()
        self._fps = fps
        self._colors = _rainbow_ansi()
        self._enter_escape = enter_escape
        self._animating = False
        self._last_color = None
        self._enter_stopped = False

    # ---- Add content ----
    def print(self, text: str):
        self.buffer_lines.append(text)

    def accii(self, text: str, font: str = "standard"):
        try:
            import pyfiglet
        except ImportError:
            raise ImportError("pyfiglet required: pip install pyfiglet")
        art = pyfiglet.figlet_format(text, font=font)
        self.buffer_lines.extend(art.rstrip('\n').split('\n'))

    # ---- Control ----
    @property
    def enter_escape(self):
        return self._enter_escape

    @enter_escape.setter
    def enter_escape(self, value: bool):
        self._enter_escape = value

    def is_animating(self):
        return self._animating

    def start(self):
        """
        Start the animation. Blocks the calling thread.
        Returns an **Out** instance if stopped by user with Enter, else None.
        """
        if not self.buffer_lines:
            print("⚠️  No text added.")
            return None
        self._stop.clear()
        self._animate()
        if self._enter_stopped:
            last_color = self._last_color or self._colors[0]
            return Out(sys.stdout, last_color)
        return None

    def stop(self):
        self._stop.set()

    # ---- Internals ----
    def _animate(self):
        self._animating = True
        self._enter_stopped = False
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

        old_term = None
        if self._enter_escape:
            try:
                fd = sys.stdin.fileno()
                old_term = termios.tcgetattr(fd)
                tty.setraw(fd)
            except (termios.error, AttributeError):
                self._enter_escape = False
                old_term = None

        lines = self.buffer_lines
        max_w = max(len(l) for l in lines)
        height = len(lines)
        delay = 1.0 / self._fps
        frame = 0
        ncolors = len(self._colors)

        last_tw, last_th = 80, 24
        last_start_y = 0

        try:
            while not self._stop.is_set():
                try:
                    tw, th = shutil.get_terminal_size()
                except:
                    tw, th = 80, 24
                last_tw, last_th = tw, th

                start_x = max(0, (tw - max_w) // 2)
                start_y = max(0, (th - height) // 2)
                last_start_y = start_y

                sys.stdout.write(f"{BLACK_BG}\033[H\033[2J")
                color = self._colors[frame % ncolors]
                self._last_color = color

                for i, line in enumerate(lines):
                    if start_y + i >= th:
                        break
                    sys.stdout.write(f"\033[{start_y + i + 1};{start_x + 1}H")
                    sys.stdout.write(color + line[:max(0, tw - start_x)])

                sys.stdout.flush()
                time.sleep(delay)
                frame += 1

                if self._enter_escape and self._enter_pressed():
                    self._enter_stopped = True
                    break
        finally:
            # Restore terminal to cooked mode, with ICRNL for normal Enter
            if old_term is not None:
                old_term[0] |= termios.ICRNL
                old_term[3] |= (termios.ICANON | termios.ECHO)
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_term)

            if self._enter_stopped:
                target_y = last_start_y + height + 1
                if target_y > last_th:
                    target_y = last_th
                sys.stdout.write(
                    f"{BLACK_BG}{self._last_color}"
                    f"\033[{target_y};1H"
                    f"\033[?25h"
                )
                sys.stdout.flush()
            else:
                sys.stdout.write("\033[0m\033[?25h\n")
                sys.stdout.flush()

            self._animating = False

    def _enter_pressed(self):
        if select.select([sys.stdin], [], [], 0.0)[0]:
            ch = sys.stdin.read(1)
            if ch in ('\r', '\n'):
                return True
        return False