# wifi_manager.py, impostare il reset_wifi() tramite bottone e/o via app
import network
import time
import json
import socket
import _thread
import machine
import os
from ssd1306 import SSD1306_I2C
oled_width = 128
oled_height = 64
i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21))
oled = SSD1306_I2C(oled_width, oled_height, i2c)
# === Configurazione base ===
WIFI_FILE = "wifi.json"

# === Decodifica URL semplice ===
def urldecode(s):
    return s.replace('+', ' ').replace('%3A', ':').replace('%2F', '/').replace('%40', '@')

# === Salva credenziali ===
def save_credentials(ssid, password):
    with open(WIFI_FILE, "w") as f:
        json.dump({"ssid": ssid, "pass": password}, f)

# === Carica credenziali ===
def load_credentials():
    try:
        with open(WIFI_FILE) as f:
            return json.load(f)
    except:
        return None

# === Cancella credenziali e riavvia ===
def reset_wifi():
    try:
        load_credentials()
        print(" Credenziali WiFi trovate")
        oled.fill(0)
        oled.text("Credenziali WiFi", 0, 0)
        oled.text("trovate", 0, 10)
        oled.show()
        time.sleep(2)
    except:
        print("⚠️ Nessun file da leggere")
        time.sleep(1)
        machine.reset()

# === Connetti in STA (client) ===
def connect_sta(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    print("📡 Connessione a:", ssid)
    for _ in range(15):
        if wlan.isconnected():
            print("✅ Connesso:", wlan.ifconfig())
            return True
        time.sleep(1)
    print("❌ Connessione fallita")
    #reset_wifi()
    return False

# === Modalità Access Point e server configurazione ===
def start_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid="Growbox_Setup")
    print("📶 Access Point attivo: Growbox_Setup")
    return ap

# === Web server minimal per configurazione con scansione reti ===
def web_server():
    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket()
    s.bind(addr)
    s.listen(1)
    print("🌐 Server attivo su http://192.168.4.1")

    while True:
        cl, addr = s.accept()
        print("📥 Connessione da", addr)
        request = cl.recv(1024).decode()
        if "POST" in request:
            try:
                body = request.split("\r\n\r\n", 1)[1]
                params = dict(x.split("=") for x in body.split("&"))
                ssid = urldecode(params.get("ssid"))
                password = urldecode(params.get("pass"))
                if ssid and password:
                    save_credentials(ssid, password)
                    cl.send("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n")
                    cl.send("<h2>✅ Configurazione salvata. Riavvio...</h2>")
                    cl.close()
                    time.sleep(2)
                    machine.reset()
                    return
            except Exception as e:
                print("Errore parsing POST:", e)

        # Pagina HTML con elenco reti WiFi
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        nets = wlan.scan()
        options = "".join([f"<option value='{ssid.decode()}'>{ssid.decode()}</option>" for ssid, *_ in nets])

        response = f"""
            <!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Growstation – Login</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f5f7ff; }}
    .card {{ max-width: 640px; border: 1px solid #e5e7eb; border-radius: 14px; padding: 18px; margin: 0 auto; box-shadow: 0 2px 10px rgba(0,0,0,.04); }}
    
  </style>
</head>
<body>
  <div class="card mt-5">
        <h2>Configurazione WiFi Growstation </h2>
        <form method='POST'>
        SSID: <select name='ssid'>{options}</select><br>
        Password: <input name='pass' type='password'><br>
        <input type='submit' value='Connetti'>
        </form>
        </div>
    </body>
    </html>

        """
        cl.send("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n")
        cl.send(response)
        cl.close()

# === Gestione WiFi: prova STA o attiva setup AP ===
def setup_wifi():
    creds = load_credentials()
    if creds:
        oled.fill(0)
        oled.text("Credenziali", 0, 20)
        oled.text("WiFi", 15, 30)
        oled.text("trovate", 10, 40)
        oled.show()
        print(" Credenziali WiFi trovate")
        time.sleep(2)
        success = connect_sta(creds["ssid"], creds["pass"])
        if success:
            oled.fill(0)
            oled.text("WiFi Connesso", 0, 30)
            oled.show()
            time.sleep(2)
            return True
    print("⚙️  Avvio setup WiFi...")
    start_ap()
    oled.fill(0)
    oled.text("Setup WiFi", 10, 10)
    oled.text("Connetti", 15, 20)
    oled.text("Access Point", 0, 30)
    oled.text("Growbox_Setup", 0, 40)
    oled.show()
    web_server()  # Bloccante: il programma prosegue solo dopo inserimento credenziali
    oled.fill(0)
    oled.text("Server attivo", 0, 20)
    oled.text("su http://", 10, 30)
    oled.text("192.168.4.1", 0, 40)
    oled.show()
    return False

