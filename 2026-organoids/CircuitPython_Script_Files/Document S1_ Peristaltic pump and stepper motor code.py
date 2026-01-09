# code.py — ESP32-C3 + EasyDriver + Peristaltic Pump + SSD1306 OLED
# Motor starts at START_DEG and performs full arcs before reversing

import time
import board, busio, displayio, terminalio, digitalio, microcontroller, pwmio
import i2cdisplaybus import I2CDisplayBus
import adafruit_displayio_ssd1306
from adafruit_display_text import label

# ---------------- MOTOR CONFIG ----------------
STEPS_PER_REV = 1600        # 200 full-steps x 8 microstep
PULSE_HIGH_US = 3          # STEP pulse HIGH width
DELAY_US = 10000           # Smaller = faster
ARC_DEGREES = 180          # Arc of oscillation
ARC_STEPS = (STEPS_PER_REV * ARC_DEGREES) // 360
START_DEG = 0              # Initial motor angle

# ---------------- PUMP CONFIG ----------------
PWM_FREQ = 20000           # 20 kHz
PUMP_PERCENT = 60          # Pump PWM (0–100%)

def pct_to_duty(pct):
    return int((max(0,min(100,pct))*65535 + 50)//100)

# ---------------- PINS ----------------
STEP = digitalio.DigitalInOut(board.IO2); STEP.direction = digitalio.Direction.OUTPUT
DIR  = digitalio.DigitalInOut(board.IO3); DIR.direction  = digitalio.Direction.OUTPUT
ENA  = digitalio.DigitalInOut(board.IO4); ENA.direction  = digitalio.Direction.OUTPUT
ENA.value = False   # active-low

# Motor direction
direction_pos = True
DIR.value = direction_pos

# ---------------- INITIAL MOTOR ALIGNMENT ----------------
STEPS_TO_START = (STEPS_PER_REV * START_DEG)//360
for _ in range(STEPS_TO_START):
    STEP.value = True
    microcontroller.delay_us(PULSE_HIGH_US)
    STEP.value = False
    microcontroller.delay_us(DELAY_US)

signed_steps = 0            # signed step counter (0 at start)
steps_since_arc = 0        # counts steps for current arc

# ---------------- INITIALIZE PUMP PWM ----------------
pump_pwm = pwmio.PWMOut(board.IO10, frequency=PWM_FREQ, duty_cycle=pct_to_duty(PUMP_PERCENT))

# ---------------- INITIALIZE OLED ----------------
displayio.release_displays()
i2c = busio.I2C(board.IO6, board.IO5, frequency=400000)
bus = I2CDisplayBus(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(bus, width=128, height=64)
root = displayio.Group()
display.root_group = root

# Background
bg = displayio.TileGrid(displayio.Bitmap(128,64,1), pixel_shader=displayio.Palette(1))
bg.pixel_shader[0] = 0x000000
root.append(bg)

# Calibrated window
W, H = 72, 40
x0, y0 = 28, 24
win = displayio.Group(x=x0, y=y0)
root.append(win)

# ---------------- LEFT PANE (MOTOR) ----------------
LW, LH = W//2, H
left = displayio.Bitmap(LW, LH, 2)
pal = displayio.Palette(2); pal[0]=0x000000; pal[1]=0xFFFFFF
frame_left = displayio.TileGrid(left, pixel_shader=pal, x=0, y=0)
win.append(frame_left)
for x in range(LW):
    left[x,0] = 1; left[x,LH-1] = 1
for y in range(LH):
    left[0,y] = 1; left[LW-1,y] = 1

lbl_ang = label.Label(terminalio.FONT, text="ANG:+000°", color=0xFFFFFF, x=2, y=14)
lbl_spd = label.Label(terminalio.FONT, text="SPEED 0.0ms", color=0xFFFFFF, x=2, y=28)
win.append(lbl_ang); win.append(lbl_spd)

# ---------------- RIGHT PANE (PUMP) ----------------
RW, RH = W//2, H
right = displayio.Bitmap(RW, RH, 2)
frame_right = displayio.TileGrid(right, pixel_shader=pal, x=LW, y=0)
win.append(frame_right)
for x in range(RW):
    right[x,0] = 1; right[x,RH-1] = 1
for y in range(RH):
    right[0,y] = 1; right[RW-1,y] = 1

lbl_pump_speed = label.Label(terminalio.FONT, text="PUMP:0%", color=0xFFFFFF, x=LW+4, y=14)
lbl_pwm = label.Label(terminalio.FONT, text="PWM:0/65", color=0xFFFFFF, x=LW+4, y=28)
win.append(lbl_pump_speed); win.append(lbl_pwm)

# ---------------- UI FUNCTIONS ----------------
def format_angle(s):
    deg = (abs(s)*360)//STEPS_PER_REV
    sign = '+' if s>=0 else '-'
    return f"{sign}{deg:03d}°"

def format_speed_ms(delay):
    return f"{delay/1000:.1f}ms"

def duty_to_pct(d):
    return int((d*100+32767)//65535)

def duty_to_scaled(d):
    return int((d*65+32767)//65535)

def ui_update_motor(s, delay):
    lbl_ang.text = format_angle(s)
    lbl_spd.text = format_speed_ms(delay)

def ui_update_pump(d):
    lbl_pump_speed.text = f"{duty_to_pct(d)}%"
    lbl_pwm.text = f"{duty_to_scaled(d)}/65"

# ---------------- MAIN LOOP ----------------
last_refresh = time.monotonic()

while True:
    # Step motor
    STEP.value = True
    microcontroller.delay_us(PULSE_HIGH_US)
    STEP.value = False
    microcontroller.delay_us(DELAY_US)

    signed_steps += 1 if direction_pos else -1
    steps_since_arc += 1

    # Reverse after completing one full arc
    if steps_since_arc >= ARC_STEPS:
        direction_pos = not direction_pos
        DIR.value = direction_pos
        steps_since_arc = 0

    # OLED update (~5 Hz)
    now = time.monotonic()
    if now - last_refresh >= 0.2:
        ui_update_motor(signed_steps, DELAY_US)
        ui_update_pump(pump_pwm.duty_cycle)
        last_refresh = now
