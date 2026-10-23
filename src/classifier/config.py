"""
EcoSmart Waste Classifier Configuration
Pins, thresholds, API keys, and model parameters.
Supports loading GEMINI_API_KEY from .env file or environment.
"""

import os


def load_env():
    """Load variables from .env if present."""
    env_paths = [
        os.path.join(os.path.dirname(__file__), ".env"),
        "/opt/ecosmart/classifier/.env",
        os.path.expanduser("~/.ecosmart.env"),
        ".env",
    ]
    for path in env_paths:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k and v:
                                os.environ.setdefault(k, v)
                break
            except Exception:
                pass


load_env()

# Gemini API Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# Audio & Neural Voice Configuration
TTS_VOICE = os.environ.get("TTS_VOICE", "es-MX-DaliaNeural")  # Voz neuronal mexicana natural

# GPIO Pins (Physical / BCM numbering)
# Ultrasonic Sensor HC-SR04
PIN_TRIGGER = 23  # Physical Pin 16
PIN_ECHO = 24     # Physical Pin 18 (Via voltage divider 10k + 20k)

# 3 Servomotors (PWM)
PIN_SERVO_ORGANIC = 17    # Physical Pin 11 (Tacho 1: Orgánico)
PIN_SERVO_RECYCLABLE = 27 # Physical Pin 13 (Tacho 2: Reciclable)
PIN_SERVO_INORGANIC = 22  # Physical Pin 15 (Tacho 3: Inorgánico)

# LED RGB Pins (Optional)
PIN_LED_RED = 25    # Physical Pin 22 (via 220 Ohm resistor)
PIN_LED_GREEN = 8   # Physical Pin 24 (via 220 Ohm resistor)
PIN_LED_BLUE = 7    # Physical Pin 26 (via 220 Ohm resistor)

# LCD I2C Configuration
LCD_I2C_BUS = 1
LCD_I2C_ADDR = None  # None for auto-detect (0x27 or 0x3F)

# Operational Parameters
DETECTION_DISTANCE_CM = 15.0  # Detection threshold distance in cm
DETECTION_CONFIRM_SECONDS = 0.8  # Stability check before capture
LID_OPEN_SECONDS = 7.0  # Duration servo lid remains open
SERVO_CLOSED_ANGLE = 0
SERVO_OPEN_ANGLE = 90
