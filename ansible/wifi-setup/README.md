# EcoSmart Wi-Fi Onboarding Portal (Raspberry Pi)

Sistema autónomo de aprovisionamiento de Wi-Fi para Raspberry Pi (NetworkManager + Python).

## Comportamiento

1. **Al encender la Raspberry Pi (Boot):**
   - Espera unos segundos para que NetworkManager intente conectarse automáticamente a las redes Wi-Fi previamente guardadas.
   - Verifica si `wlan0` tiene conexión activa con salida a internet.
   - **Si ya tiene internet vía Wi-Fi:** El servicio finaliza silenciosamente (código 0). No abre ningún punto de acceso y la Pi opera normalmente.

2. **Si NO detecta conexión a internet en `wlan0`:**
   - Levanta automáticamente una red Wi-Fi temporal abierta: **`EcoSmart-Setup`** en `10.42.0.1`.
   - Inicia un portal web cautivo en el puerto `80`.
   - Cuando conectas tu teléfono o laptop a `EcoSmart-Setup`, el dispositivo detecta el portal cautivo y abre automáticamente la pantalla de configuración (o puedes navegar a `http://10.42.0.1`).
   - Muestra las redes Wi-Fi detectadas a su alrededor con su nivel de señal y solicita la contraseña.

3. **Al pulsar "Conectar a internet":**
   - La Pi intenta conectarse a la red seleccionada usando `nmcli`.
   - Si la conexión tiene éxito y confirma salida a internet:
     - **Apaga inmediatamente el punto de acceso `EcoSmart-Setup`**.
     - **Cierra el servidor web del portal**.
     - La configuración queda guardada en NetworkManager para conectarse sola en futuros reinicios.
   - Si la contraseña fue incorrecta o falló la conexión:
     - Restaura `EcoSmart-Setup` para que puedas volver a intentar.

## Despliegue con Ansible

Desde tu equipo local (con la Raspberry Pi conectada por Ethernet / Tailscale):

```bash
ansible-playbook -i ansible/inventory.ini ansible/wifi-setup.yml -K
```

*(El parámetro `-K` te solicitará la contraseña de sudo del usuario `sef` en la Raspberry Pi).*

## Verificación y Monitoreo

Para revisar los logs en tiempo real del servicio en la Raspberry Pi:

```bash
sudo journalctl -u ecosmart-wifi-setup.service -f
```

Para forzar la apertura del portal manualmente si deseas probarlo:

```bash
sudo systemctl restart ecosmart-wifi-setup.service
```
