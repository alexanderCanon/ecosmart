#!/usr/bin/env python3
"""
EcoSmart - Intelligent Waste Classifier
Uses HC-SR04 ultrasonic sensor to detect approaching objects, captures an image
with the OV5647 CSI camera, classifies waste with Gemini 1.5 Flash VLM, displays
the result on LCD 1602, speaks the classification via 3.5mm audio jack, lights
the corresponding RGB LED, and actuates the appropriate servo lid.
"""

import base64
import io
import json
import logging
import os
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error

import config
from lcd_i2c import LCD1602

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s"
)


class EcoSmartClassifier:
    def __init__(self):
        logging.info("Inicializando EcoSmart Classifier...")
        self.api_key = config.GEMINI_API_KEY
        if not self.api_key:
            logging.warning("No se detectó GEMINI_API_KEY en variables de entorno. "
                            "Se usará modo demostración si no se proporciona.")

        self._init_hardware()

    def _init_hardware(self):
        # 1. LCD 1602
        try:
            self.lcd = LCD1602(bus_num=config.LCD_I2C_BUS, address=config.LCD_I2C_ADDR)
            self.lcd.show("EcoSmart Bin", "Iniciando...")
            logging.info("LCD 1602 I2C inicializada en 0x%02X", self.lcd.address)
        except Exception as exc:
            logging.error("No se pudo iniciar LCD 1602: %s", exc)
            self.lcd = None

        # 2. RGB LED
        try:
            from gpiozero import LED
            self.led_red = LED(config.PIN_LED_RED)
            self.led_green = LED(config.PIN_LED_GREEN)
            self.led_blue = LED(config.PIN_LED_BLUE)
            self.set_led(None)
            logging.info("LED RGB inicializado.")
        except Exception as exc:
            logging.error("No se pudo iniciar LED RGB: %s", exc)
            self.led_red = self.led_green = self.led_blue = None

        # 3. Servomotores (1: Orgánico, 2: Reciclable, 3: Inorgánico)
        try:
            from gpiozero import AngularServo
            self.servos = {
                1: AngularServo(config.PIN_SERVO_ORGANIC, min_angle=0, max_angle=180,
                                min_pulse_width=0.0005, max_pulse_width=0.0024),
                2: AngularServo(config.PIN_SERVO_RECYCLABLE, min_angle=0, max_angle=180,
                                min_pulse_width=0.0005, max_pulse_width=0.0024),
                3: AngularServo(config.PIN_SERVO_INORGANIC, min_angle=0, max_angle=180,
                                min_pulse_width=0.0005, max_pulse_width=0.0024),
            }
            for s in self.servos.values():
                s.angle = config.SERVO_CLOSED_ANGLE
            logging.info("3 Servomotores inicializados en 0° (cerrados).")
        except Exception as exc:
            logging.error("No se pudo iniciar servomotores: %s", exc)
            self.servos = {}

        # 4. Sensor ultrasónico HC-SR04
        try:
            from gpiozero import DistanceSensor
            self.sensor = DistanceSensor(echo=config.PIN_ECHO, trigger=config.PIN_TRIGGER, max_distance=3.0)
            logging.info("Sensor ultrasónico HC-SR04 inicializado.")
        except Exception as exc:
            logging.error("No se pudo iniciar sensor ultrasónico: %s", exc)
            self.sensor = None

        # 5. Cámara Picamera2 (OV5647)
        try:
            from picamera2 import Picamera2
            self.picam2 = Picamera2()
            cam_config = self.picam2.create_still_configuration(main={"size": (1024, 768)})
            self.picam2.configure(cam_config)
            self.picam2.start()
            time.sleep(1)
            logging.info("Cámara Picamera2 OV5647 lista.")
        except Exception as exc:
            logging.error("No se pudo iniciar cámara OV5647: %s", exc)
            self.picam2 = None

    def set_led(self, color):
        """Activa color en LED RGB: 'rojo', 'verde', 'azul', 'blanco' o None."""
        if not self.led_red:
            return
        self.led_red.off()
        self.led_green.off()
        self.led_blue.off()

        if color == "rojo":
            self.led_red.on()
        elif color == "verde":
            self.led_green.on()
        elif color == "azul":
            self.led_blue.on()
        elif color == "blanco":
            self.led_red.on()
            self.led_green.on()
            self.led_blue.on()

    def speak(self, text):
        """Reproduce audio con voz neuronal en español de alta fidelidad vía Jack 3.5mm."""
        def _run():
            mp3_path = "/tmp/ecosmart_speech.mp3"
            try:
                # Intento 1: Edge-TTS (Voz neuronal humana de Microsoft)
                import asyncio
                import edge_tts

                async def _gen():
                    communicate = edge_tts.Communicate(text, config.TTS_VOICE)
                    await communicate.save(mp3_path)

                asyncio.run(_gen())
                subprocess.run(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", mp3_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
                )
                return
            except Exception as exc:
                logging.warning("Fallo en TTS neuronal (%s). Usando respaldo offline.", exc)

            try:
                # Intento 2: Respaldo espeak-ng
                subprocess.run(["espeak-ng", "-v", "es", "-s", "150", text],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            except Exception:
                try:
                    # Intento 3: Respaldo espeak tradicional
                    subprocess.run(["espeak", "-v", "es", "-s", "150", text],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                except Exception as exc2:
                    logging.warning("No se pudo sintetizar voz: %s", exc2)

        threading.Thread(target=_run, daemon=True).start()

    def capture_image_bytes(self):
        """Captura un fotograma y retorna bytes JPEG en memoria."""
        if not self.picam2:
            logging.error("Cámara no disponible para captura.")
            return None
        buf = io.BytesIO()
        self.picam2.capture_file(buf, format="jpeg")
        return buf.getvalue()

    def classify_waste(self, image_bytes):
        """Envía la imagen a Gemini 1.5 Flash para clasificación."""
        if not self.api_key:
            logging.warning("Modo simulación: Sin GEMINI_API_KEY. Retornando clasificación demo.")
            return {
                "categoria": "Reciclable",
                "objeto": "Botella de plastico",
                "tacho": 2,
                "color_led": "azul",
                "mensaje_lcd_l1": "Botella Plastico",
                "mensaje_lcd_l2": "Tacho: RECICLABLE",
                "mensaje_audio": "Es una botella de plástico. Por favor deposítala en el tacho reciclable."
            }

        prompt = (
            "Eres el clasificador de residuos inteligente EcoSmart. "
            "Identifica el objeto principal de la imagen y clasifícalo estrictamente en una de estas 3 categorías:\n"
            "1. 'Organico' (restos de comida, frutas, verduras, cáscaras, hojas, servilletas usadas).\n"
            "2. 'Reciclable' (botellas plásticas PET, latas de aluminio, papel limpio, cartón, vidrio).\n"
            "3. 'Inorganico' (desechos comunes, envolturas sucias, bolsas plásticas no reciclables, residuos sanitarios).\n\n"
            "Responde ÚNICAMENTE con un JSON válido con esta estructura exacta:\n"
            "{\n"
            '  "categoria": "Reciclable" | "Organico" | "Inorganico",\n'
            '  "objeto": "Nombre corto del objeto (max 16 letras)",\n'
            '  "tacho": 1 para Organico, 2 para Reciclable, 3 para Inorganico,\n'
            '  "color_led": "verde" para Organico, "azul" para Reciclable, "rojo" para Inorganico,\n'
            '  "mensaje_lcd_l1": "Texto linea 1 max 16 chars",\n'
            '  "mensaje_lcd_l2": "Texto linea 2 max 16 chars",\n'
            '  "mensaje_audio": "Mensaje en español corto para reproducir por voz"\n'
            "}"
        )

        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": b64_img
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2
            }
        }

        url = f"{config.GEMINI_API_URL}?key={self.api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                text_response = result["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(text_response)
                logging.info("Respuesta de Gemini: %s", data)
                return data
        except Exception as exc:
            logging.error("Error al consultar Gemini API: %s", exc)
            return {
                "categoria": "Inorganico",
                "objeto": "No identificado",
                "tacho": 3,
                "color_led": "rojo",
                "mensaje_lcd_l1": "No identificado",
                "mensaje_lcd_l2": "Tacho: GENERAL",
                "mensaje_audio": "No se pudo identificar el objeto. Deposítalo en desechos generales."
            }

    def open_lid(self, tacho_num):
        """Abre la compuerta correspondiente con su servomotor."""
        servo = self.servos.get(tacho_num)
        if servo:
            logging.info("Abriendo tapa del tacho #%d a %d°", tacho_num, config.SERVO_OPEN_ANGLE)
            servo.angle = config.SERVO_OPEN_ANGLE
        else:
            logging.warning("Servo para tacho #%d no disponible.", tacho_num)

    def close_all_lids(self):
        """Cierra todas las compuertas de los servomotores."""
        for num, servo in self.servos.items():
            servo.angle = config.SERVO_CLOSED_ANGLE
        logging.info("Todas las tapas cerradas (0°).")

    def run(self):
        """Bucle principal de la máquina de estados."""
        logging.info("Sistema EcoSmart listo para operar.")
        self.close_all_lids()
        self.set_led(None)

        if self.lcd:
            self.lcd.show("EcoSmart Bin", "Acerca residuo..")

        while True:
            try:
                # 1. Medir distancia
                if self.sensor:
                    dist_cm = self.sensor.distance * 100
                else:
                    time.sleep(2)
                    continue

                # 2. Detección de presencia
                if dist_cm <= config.DETECTION_DISTANCE_CM:
                    logging.info("Objeto detectado a %.1f cm. Confirmando...", dist_cm)
                    time.sleep(config.DETECTION_CONFIRM_SECONDS)

                    # Re-verificar que sigue ahí para descartar falsos positivos
                    if self.sensor.distance * 100 <= (config.DETECTION_DISTANCE_CM + 5):
                        logging.info("Detección confirmada. Iniciando análisis...")
                        if self.lcd:
                            self.lcd.show("Identificando...", "Espera un momento")
                        self.set_led("blanco")

                        # 3. Capturar imagen
                        img_bytes = self.capture_image_bytes()
                        if not img_bytes:
                            if self.lcd:
                                self.lcd.show("Error Camara", "Revisa conexion")
                            time.sleep(3)
                            continue

                        # 4. Clasificar con IA
                        res = self.classify_waste(img_bytes)

                        # 5. Ejecutar acciones
                        categoria = res.get("categoria", "Inorganico")
                        tacho_num = res.get("tacho", 3)
                        color = res.get("color_led", "rojo")
                        l1 = res.get("mensaje_lcd_l1", categoria)[:16]
                        l2 = res.get("mensaje_lcd_l2", f"Tacho {tacho_num}")[:16]
                        audio_msg = res.get("mensaje_audio", f"Desecho {categoria}")

                        # Actualizar LCD y LED
                        if self.lcd:
                            self.lcd.show(l1, l2)
                        self.set_led(color)

                        # Reproducir voz
                        self.speak(audio_msg)

                        # Abrir tapa del basurero
                        self.open_lid(tacho_num)

                        # Mantener abierto durante el tiempo configurado
                        time.sleep(config.LID_OPEN_SECONDS)

                        # Cerrar tapa y apagar LED
                        self.close_all_lids()
                        self.set_led(None)

                        # Pantalla de despedida / retorno
                        if self.lcd:
                            self.lcd.show("¡Gracias por", "reciclar!")
                        time.sleep(2.5)

                        if self.lcd:
                            self.lcd.show("EcoSmart Bin", "Acerca residuo..")

                time.sleep(0.15)

            except KeyboardInterrupt:
                logging.info("Programa detenido por el usuario.")
                self.close_all_lids()
                self.set_led(None)
                if self.lcd:
                    self.lcd.clear()
                break
            except Exception as exc:
                logging.error("Error en bucle principal: %s", exc)
                time.sleep(1)


if __name__ == "__main__":
    app = EcoSmartClassifier()
    app.run()
