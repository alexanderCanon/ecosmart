#!/usr/bin/env python3
"""
EcoSmart Hardware Diagnostic & Verification Utility
Test each hardware component individually to verify wiring.
Usage:
  python3 test_hardware.py --test-all
  python3 test_hardware.py --test-led
  python3 test_hardware.py --test-lcd
  python3 test_hardware.py --test-distance
  python3 test_hardware.py --test-servos
  python3 test_hardware.py --test-camera
  python3 test_hardware.py --test-audio
"""

import argparse
import os
import subprocess
import sys
import time

import config


def test_led():
    print("\n--- [1/6] Probando LED RGB (Pines 22, 24, 26) ---")
    try:
        from gpiozero import LED
        red = LED(config.PIN_LED_RED)
        green = LED(config.PIN_LED_GREEN)
        blue = LED(config.PIN_LED_BLUE)

        print("-> Encendiendo ROJO...")
        red.on()
        time.sleep(1.5)
        red.off()

        print("-> Encendiendo VERDE...")
        green.on()
        time.sleep(1.5)
        green.off()

        print("-> Encendiendo AZUL...")
        blue.on()
        time.sleep(1.5)
        blue.off()

        print("✓ Prueba de LED RGB completada con éxito.")
    except Exception as exc:
        print(f"✗ Error al probar LED RGB: {exc}")


def test_lcd():
    print("\n--- [2/6] Probando Pantalla LCD 1602 I2C (Pines 3 y 5) ---")
    try:
        from lcd_i2c import LCD1602
        lcd = LCD1602(bus_num=config.LCD_I2C_BUS, address=config.LCD_I2C_ADDR)
        print(f"-> LCD detectada en dirección I2C: 0x{lcd.address:02X}")
        lcd.show("EcoSmart Bin", "LCD 1602 Test OK")
        time.sleep(3)
        lcd.show("Sistema Listo", "Acerca objeto...")
        print("✓ Pantalla LCD 1602 probada con éxito.")
    except Exception as exc:
        print(f"✗ Error al inicializar LCD 1602: {exc}")
        print("  Verifica que I2C esté habilitado y los cables SDA/SCL conectados firmemente.")


def test_distance():
    print("\n--- [3/6] Probando Sensor Ultrasónico HC-SR04 (Pines 16 y 18) ---")
    print("Mueve tu mano frente al sensor durante 10 segundos para ver lecturas en vivo:")
    try:
        from gpiozero import DistanceSensor
        sensor = DistanceSensor(echo=config.PIN_ECHO, trigger=config.PIN_TRIGGER, max_distance=3.0)
        for i in range(10):
            dist_cm = sensor.distance * 100
            print(f"  Lectura #{i+1}: {dist_cm:.1f} cm")
            time.sleep(1)
        print("✓ Sensor ultrasónico probado con éxito.")
    except Exception as exc:
        print(f"✗ Error con el sensor ultrasónico: {exc}")
        print("  Recuerda: El pin ECHO debe pasar por el divisor de tensión (10kΩ + 20kΩ).")


def test_servos():
    print("\n--- [4/6] Probando los 3 Servomotores (Pines 11, 13 y 15) ---")
    print("ATENCIÓN: Verifica que los servos estén alimentados por una fuente externa de 5V!")
    try:
        from gpiozero import AngularServo
        # Micro servo SG90 pulse widths: 0.5ms to 2.4ms (-90 to +90 deg or 0 to 180)
        servos = [
            ("Orgánico (Pin 11)", AngularServo(config.PIN_SERVO_ORGANIC, min_angle=0, max_angle=180, min_pulse_width=0.0005, max_pulse_width=0.0024)),
            ("Reciclable (Pin 13)", AngularServo(config.PIN_SERVO_RECYCLABLE, min_angle=0, max_angle=180, min_pulse_width=0.0005, max_pulse_width=0.0024)),
            ("Inorgánico (Pin 15)", AngularServo(config.PIN_SERVO_INORGANIC, min_angle=0, max_angle=180, min_pulse_width=0.0005, max_pulse_width=0.0024)),
        ]

        for name, s in servos:
            print(f"-> Moviendo Servo {name} a posición CERRADO (0°)...")
            s.angle = 0
            time.sleep(1)
            print(f"-> Moviendo Servo {name} a posición ABIERTO (90°)...")
            s.angle = 90
            time.sleep(2)
            print(f"-> Regresando Servo {name} a 0°...")
            s.angle = 0
            time.sleep(1)
        print("✓ Prueba de servomotores completada.")
    except Exception as exc:
        print(f"✗ Error al probar servomotores: {exc}")


def test_camera():
    print("\n--- [5/6] Probando Cámara OV5647 (Puerto CSI) ---")
    try:
        from picamera2 import Picamera2
        picam2 = Picamera2()
        config_cam = picam2.create_still_configuration(main={"size": (1280, 720)})
        picam2.configure(config_cam)
        picam2.start()
        time.sleep(1.5)
        test_path = "/tmp/ecosmart_cam_test.jpg"
        picam2.capture_file(test_path)
        picam2.stop()
        size_kb = os.path.getsize(test_path) / 1024
        print(f"✓ Foto capturada exitosamente: {test_path} ({size_kb:.1f} KB)")
    except Exception as exc:
        print(f"✗ Error con la cámara Picamera2: {exc}")
        print("  Verifica que el cable ribbon de la cámara esté bien insertado en el conector CSI.")


def test_audio():
    print("\n--- [6/6] Probando Salida de Audio (Jack 3.5mm) ---")
    frase = "Prueba de audio EcoSmart completada exitosamente."
    try:
        subprocess.run(["espeak-ng", "-v", "es", frase], check=True)
        print("✓ Audio reproducido vía espeak-ng.")
    except Exception:
        try:
            subprocess.run(["espeak", "-v", "es", frase], check=True)
            print("✓ Audio reproducido vía espeak.")
        except Exception as exc:
            print(f"✗ No se pudo reproducir audio con sintetizador: {exc}")
            print("  Instala espeak-ng con: sudo apt install -y espeak-ng")


def main():
    parser = argparse.ArgumentParser(description="Verificación de Hardware EcoSmart")
    parser.add_argument("--test-all", action="store_true", help="Probar todos los componentes")
    parser.add_argument("--test-led", action="store_true", help="Probar LED RGB")
    parser.add_argument("--test-lcd", action="store_true", help="Probar LCD 1602 I2C")
    parser.add_argument("--test-distance", action="store_true", help="Probar sensor ultrasónico")
    parser.add_argument("--test-servos", action="store_true", help="Probar los 3 servomotores")
    parser.add_argument("--test-camera", action="store_true", help="Probar cámara OV5647")
    parser.add_argument("--test-audio", action="store_true", help="Probar salida de audio")

    args = parser.parse_args()

    if len(sys.argv) == 1 or args.test_all:
        test_led()
        test_lcd()
        test_distance()
        test_servos()
        test_camera()
        test_audio()
    else:
        if args.test_led: test_led()
        if args.test_lcd: test_lcd()
        if args.test_distance: test_distance()
        if args.test_servos: test_servos()
        if args.test_camera: test_camera()
        if args.test_audio: test_audio()


if __name__ == "__main__":
    main()
