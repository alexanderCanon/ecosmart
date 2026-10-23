"""
EcoSmart LCD 1602 I2C Driver
Self-contained HD44780 LCD driver via PCF8574 I2C backpack using smbus2.
Supports auto-detection of 0x27 or 0x3F I2C addresses.
"""

import time
import smbus2

# Commands
LCD_CLEARDISPLAY = 0x01
LCD_RETURNHOME = 0x02
LCD_ENTRYMODESET = 0x04
LCD_DISPLAYCONTROL = 0x08
LCD_CURSORSHIFT = 0x10
LCD_FUNCTIONSET = 0x20
LCD_SETCGRAMADDR = 0x40
LCD_SETDDRAMADDR = 0x80

# Flags for display entry mode
LCD_ENTRYRIGHT = 0x00
LCD_ENTRYLEFT = 0x02
LCD_ENTRYSHIFTINCREMENT = 0x01
LCD_ENTRYSHIFTDECREMENT = 0x00

# Flags for display on/off control
LCD_DISPLAYON = 0x04
LCD_DISPLAYOFF = 0x00
LCD_CURSORON = 0x02
LCD_CURSOROFF = 0x00
LCD_BLINKON = 0x01
LCD_BLINKOFF = 0x00

# Flags for display/cursor shift
LCD_DISPLAYMOVE = 0x08
LCD_CURSORMOVE = 0x00
LCD_MOVERIGHT = 0x04
LCD_MOVELEFT = 0x00

# Flags for function set
LCD_8BITMODE = 0x10
LCD_4BITMODE = 0x00
LCD_2LINE = 0x08
LCD_1LINE = 0x00
LCD_5x10DOTS = 0x04
LCD_5x8DOTS = 0x00

# Flags for backlight control
LCD_BACKLIGHT = 0x08
LCD_NOBACKLIGHT = 0x00

En = 0b00000100  # Enable bit
Rw = 0b00000010  # Read/Write bit
Rs = 0b00000001  # Register select bit


class LCD1602:
    def __init__(self, bus_num=1, address=None):
        self.bus_num = bus_num
        self.bus = smbus2.SMBus(bus_num)
        self.backlight_state = LCD_BACKLIGHT

        if address is None:
            self.address = self._detect_address()
        else:
            self.address = address

        self._init_display()

    def _detect_address(self):
        for addr in [0x27, 0x3F, 0x20, 0x38]:
            try:
                self.bus.read_byte(addr)
                return addr
            except Exception:
                continue
        return 0x27

    def _write_word(self, data):
        self.bus.write_byte(self.address, data | self.backlight_state)

    def _send_nibble(self, data):
        self._write_word(data)
        self._write_word(data | En)
        time.sleep(0.0005)
        self._write_word(data & ~En)
        time.sleep(0.0001)

    def _send(self, data, mode=0):
        high = mode | (data & 0xF0)
        low = mode | ((data << 4) & 0xF0)
        self._send_nibble(high)
        self._send_nibble(low)

    def command(self, cmd):
        self._send(cmd, 0)

    def write_char(self, char_val):
        self._send(char_val, Rs)

    def _init_display(self):
        time.sleep(0.05)
        self._send_nibble(0x30)
        time.sleep(0.005)
        self._send_nibble(0x30)
        time.sleep(0.0002)
        self._send_nibble(0x30)
        time.sleep(0.0002)
        self._send_nibble(0x20)  # 4-bit mode
        time.sleep(0.0002)

        self.command(LCD_FUNCTIONSET | LCD_4BITMODE | LCD_2LINE | LCD_5x8DOTS)
        self.command(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF)
        self.clear()
        self.command(LCD_ENTRYMODESET | LCD_ENTRYLEFT | LCD_ENTRYSHIFTDECREMENT)
        time.sleep(0.05)

    def clear(self):
        self.command(LCD_CLEARDISPLAY)
        time.sleep(0.003)

    def backlight(self, on=True):
        self.backlight_state = LCD_BACKLIGHT if on else LCD_NOBACKLIGHT
        self._write_word(0)

    def set_cursor(self, line=0, col=0):
        row_offsets = [0x00, 0x40, 0x14, 0x54]
        self.command(LCD_SETDDRAMADDR | (col + row_offsets[line % 2]))

    def write_text(self, text, line=0, col=0):
        self.set_cursor(line, col)
        # Transliterate common accented Spanish chars if needed
        clean_text = (
            text.replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
            .replace("ñ", "n")
            .replace("Á", "A")
            .replace("É", "E")
            .replace("Í", "I")
            .replace("Ó", "O")
            .replace("Ú", "U")
            .replace("Ñ", "N")
        )
        for char in clean_text[:16]:
            self.write_char(ord(char))

    def show(self, line1="", line2=""):
        self.clear()
        if line1:
            self.write_text(line1[:16], line=0)
        if line2:
            self.write_text(line2[:16], line=1)
