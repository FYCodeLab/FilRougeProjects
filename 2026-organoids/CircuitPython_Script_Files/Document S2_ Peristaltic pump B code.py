import time
import board, busio, displayio, terminalio, digitalio, microcontroller
from i2cdisplaybus import I2CDisplayBus
import adafruit_displayio_ssd1306
from adafruit_display_text import label

# ---------------- CONFIGURE YOUR MOTOR / TIMING HERE ----------------
STEPS_PER_REV = 1600        # 200 full-steps x 8 microstep → one full 360° turn
PULSE_HIGH_US = 3          # STEP pin pulse HIGH width (A3967 requires ≥ ~1 µs)
DELAY_US = 8000            # Time between pulses -> the higher the time, the lower the speed
REVERSE_EVERY = STEPS_PER_REV   # Reverse once per full revolution

# NOTE: If you want to display TOTAL period in ms instead of LOW time, you can compute:
#   total_period_ms = (PULSE_HIGH_US + DELAY_US) / 1000.0

# ---------------- OLED SETUP (same I2C pins as your working code) ----------------
displayio.release_displays()
i2c = busio.I2C(board.IO6, board.IO5, frequency=400000)   # IO6=SCL, IO5=SDA on your board
bus = I2CDisplayBus(i2c, device_address=0x3C)            # typical SSD1306 address
display = adafruit_displayio_ssd1306.SSD1306(bus, width=128, height=64)

root = displayio.Group()
display.root_group = root

# Full black background (clears the whole screen)
bg = displayio.TileGrid(displayio.Bitmap(128, 64, 1), pixel_shader=displayio.Palette(1))
bg.pixel_shader[0] = 0x000000
root.append(bg)

# ---------------- YOUR CALIBRATED WINDOW ----------------
# This is the 72x40 area you measured to be reliably visible on your 0.42" OLED,
# placed with top-left corner at (x0,y0) = (28,24).
W, H = 72, 40
x0, y0 = 28, 24
win = displayio.Group(x=x0, y=y0)
root.append(win)

# ---------------- LEFT-HALF PANE (36x40) WITH BORDER ----------------
LW, LH = W // 2, H      # 36 x 40 (left half of your calibrated window)
pane = displayio.Bitmap(LW, LH, 2)
pal = displayio.Palette(2); pal[0] = 0x000000; pal[1] = 0xFFFFFF
frame = displayio.TileGrid(pane, pixel_shader=pal)
win.append(frame)

# 1-pixel white border around the left pane
for x in range(LW):
    pane[x, 0] = 1
    pane[x, LH-1] = 1

for y in range(LH):
    pane[0, y] = 1
    pane[LW-1, y] = 1

# ---------------- LABELS INSIDE LEFT PANE ----------------
# terminalio.FONT is 6x8 pixels; positions (x,y) are chosen to fit inside 36x40 nicely.
lbl_ang = label.Label(terminalio.FONT, text="ANG:+000°", color=0xFFFFFF, x=2, y=14)
lbl_spd = label.Label(terminalio.FONT, text="SPEED:0.0ms", color=0xFFFFFF, x=2, y=28)
win.append(lbl_ang); win.append(lbl_spd)

def format_angle(signed_steps: int) -> str:
    """
    Convert signed step counter into a signed ANGLE in degrees.
    - signed_steps counts up when moving forward and down when moving backward.
    - We show the angle within [0, 360) and attach the sign from signed_steps.
    - Using integer degrees for simplicity; change to float if you want a decimal.
    """
    steps_abs = abs(signed_steps) % STEPS_PER_REV
    deg = (steps_abs * 360) // STEPS_PER_REV   # integer division → 0..359
    sign = '+' if signed_steps >= 0 else '-'
    # The literal "°" degree symbol is used directly (no Unicode escape).
    return f"{sign}{deg:03d}°"

def format_speed_ms(delay_us: int) -> str:
    """
    Show the LOW interval between pulses in milliseconds.
    Smaller value → faster step rate.
    """
    ms = delay_us / 1000.0
    return f"{ms:.1f}ms"

def ui_update(signed_steps: int, delay_us: int) -> None:
    """Update both labels in the left pane."""
    lbl_ang.text = format_angle(signed_steps)
    lbl_spd.text = format_speed_ms(delay_us)

# ---------------- STEPPER PINS (change to match your wiring) ----------------
STEP = digitalio.DigitalInOut(board.IO2); STEP.direction = digitalio.Direction.OUTPUT   # pulse generator
DIR  = digitalio.DigitalInOut(board.IO3); DIR.direction  = digitalio.Direction.OUTPUT   # direction selector
ENA  = digitalio.DigitalInOut(board.IO4); ENA.direction  = digitalio.Direction.OUTPUT   # enable (active-low)
ENA.value = False

# Motion state start
direction_pos = True
DIR.value = direction_pos

# Signed step counter
# - increments when moving forward
# - decrements when moving backward
signed_steps = 0

# Initial UI
ui_update(signed_steps, DELAY_US)

# ---------------- MAIN LOOP ----------------
last_refresh = time.monotonic()  # controls how often we refresh the OLED (to reduce overhead)

while True:
    # Emit one STEP pulse (HIGH for PULSE_HIGH_US, then LOW for DELAY_US)
    STEP.value = True
    microcontroller.delay_us(PULSE_HIGH_US)   # HIGH width (meets A3967 timing)
    STEP.value = False
    microcontroller.delay_us(DELAY_US)        # LOW interval → dominates the step frequency

    # Update the signed step counter according to the current direction
    if direction_pos:
        signed_steps += 1
    else:
        signed_steps -= 1

    # Periodically update the OLED (every ~0.2 s to keep it responsive but light)
    now = time.monotonic()
    if now - last_refresh >= 0.2:
        ui_update(signed_steps, DELAY_US)
        last_refresh = now
