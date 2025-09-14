# wifi_manager.py, impostare il reset_wifi() tramite bottone e/o via app
import network
import time
import json
import socket
import _thread
import machine
import os

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
        os.remove(WIFI_FILE)
        print("🧹 Credenziali WiFi rimosse. Riavvio...")
    except:
        print("⚠️ Nessun file da cancellare")
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
        success = connect_sta(creds["ssid"], creds["pass"])
        if success:
            return True
    print("⚙️  Avvio setup WiFi...")
    start_ap()
    web_server()  # Bloccante: il programma prosegue solo dopo inserimento credenziali
    return False

