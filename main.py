import requests
import csv
import random
import time
import RPi.GPIO as GPIO
from escpos.printer import Usb
from PIL import Image

BUTTON_PIN = 18  # BCM pin
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vROAMqfaTHwU2WXO_99A16hJqkfp2FR0gjbpyVcujaXu3OjgLua_LzKb0pURJluWaMqvHKKJZvw3XR3/pub?output=csv"
POLL_DELAY = 0.02  # seconds
MAX_WIDTH = 384  # 58mm paper width

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

printer = Usb(0x04b8, 0x0e15)
printer.set(align="center", bold=True, width=2, height=2)

def load_image(path):
    img = Image.open(path).convert("RGBA")

    # Remove white background
    clean_pixels = []
    for r, g, b, a in img.getdata():
        if r > 240 and g > 240 and b > 240:
            clean_pixels.append((255, 255, 255, 0))
        else:
            clean_pixels.append((r, g, b, 255))
    img.putdata(clean_pixels)

    # Flatten transparency
    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(background, img)

    # Convert to grayscale
    img = img.convert("L")

    # Resize for printer width
    ratio = MAX_WIDTH / img.width
    img = img.resize((MAX_WIDTH, int(img.height * ratio)))
    return img

column_images = {
    0: load_image("oracle.png"),
    1: load_image("challenges.png"),
    2: load_image("recipes.png")
}

def get_random_sentence():
    r = requests.get(CSV_URL, timeout=5)
    r.raise_for_status()

    rows = list(csv.reader(r.content.decode("utf-8").splitlines()))
    # Remove completely empty rows
    rows = [row for row in rows if row and any(cell.strip() for cell in row)]
    if not rows:
        raise RuntimeError("CSV contains no sentences")

    # Transpose rows to get columns
    max_columns = max(len(row) for row in rows)
    columns = [[] for _ in range(max_columns)]
    for row in rows:
        for i in range(max_columns):
            if i < len(row) and row[i].strip():
                columns[i].append(row[i].strip())

    # Pick a random column that has data
    non_empty_columns = [i for i, col in enumerate(columns) if col]
    if not non_empty_columns:
        raise RuntimeError("No non-empty columns found")

    col_index = random.choice(non_empty_columns)
    sentence = random.choice(columns[col_index])

    return sentence, col_index


def wrap_text(text, max_chars=32):
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        if len(current_line) + len(word) + 1 > max_chars:
            lines.append(current_line)
            current_line = word
        else:
            if current_line:
                current_line += " " + word
            else:
                current_line = word

    if current_line:
        lines.append(current_line)

    return lines

def print_sentence(sentence, img_to_use):
    if not printer:
        print("Printer not available")
        return

    printer.set(align="center")
    printer.image(img_to_use)
    printer.text("\n\n")

    wrapped_lines = wrap_text(sentence, max_chars=32)
    for line in wrapped_lines:
        printer.text(line + "\n")

    printer.text("\n\n")
    printer.text("*** gesponsert von eurer Lieblings-WG! ***\n\n")
    printer.cut()

print("Waiting for button press...")

last_state = GPIO.HIGH  # button released

try:
    while True:
        current_state = GPIO.input(BUTTON_PIN)

        if last_state == GPIO.HIGH and current_state == GPIO.LOW:
            try:
                sentence, col_index = get_random_sentence()
                img_to_use = column_images.get(col_index, column_images[0])
                print("Printing:", sentence)
                print_sentence(sentence, img_to_use)
            except Exception as e:
                print("Error:", e)

        last_state = current_state
        time.sleep(POLL_DELAY)

except KeyboardInterrupt:
    pass

finally:
    GPIO.cleanup()
