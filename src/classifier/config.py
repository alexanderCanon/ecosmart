"""
EcoSmart Waste Classifier Configuration
Pins, thresholds, and model parameters.
"""

import os

# Gemini API Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# GPIO Pins (Physical / BCM numbering)
# Ultrasonic Sensor HC-SR04
PIN_TRIGGER = 23  # Physical Pin 16
PIN_ECHO = 24     # Physical Pin 18 (Must connect via voltage divider!)

# 3 Servomotors (PWM)
PIN_SERVO_ORGANIC = 17    # Physical Pin 11 (Tacho 1: Orgánico)
PIN_SERVO_RECYCLABLE = 27 # Physical Pin 13 (Tacho 2: Reciclable)
PIN_SERVO_INORGANIC = 22  # Physical Pin 15 (Tacho 3: Inorgánico)

# LED RGB Pins
PIN_LED_RED = 25    # Physical Pin 22 (via 220 Ohm resistor)
PIN_LED_GREEN = 8   # Physical Pin 24 (via 220 Ohm resistor)
PIN_LED_BLUE = 7    # Physical Pin 26 (via 220 Ohm resistor)

# LCD I2C Configuration
LCD_I2C_BUS = 1
LCD_I2C_ADDR = None  # None for auto-detect (0x27 or 0x3F)

# Operational Parameters
DETECTION_DISTANCE_CM = 15.0  # Detection threshold distance
DETECTION_CONFIRM_SECONDS = 0.8  # Stability check before capture
LID_OPEN_SECONDS = 7.0  # Duration servo lid remains open
SERVO_CLOSED_ANGLE = 0
SERVO_OPEN_ANGLE = 90

# Audio TTS Configuration
TTS_ENGINE = "espeak-ng"  # Options: 'espeak-ng', 'edge-tts', 'aplay'
AUDIO_OUTPUT_DEVICE = "hw:2,0"  # ALSA 3.5mm headphone jack
