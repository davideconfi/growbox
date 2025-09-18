import time
import network
import ntptime
import ssl
import machine
import ujson as json
from machine import Pin, PWM, SoftI2C
from umqtt.robust import MQTTClient
from wifi_manager_setup_oled import setup_wifi
import dht 
from ssd1306 import SSD1306_I2C

dht_sensor = dht.DHT22(Pin(25))
temp, hum = None, None
ventilador= Pin(17, Pin.OUT)
bomba_riego =Pin (18, Pin.OUT)
i2c = SoftI2C(scl=Pin(22), sda=Pin(21))
oled = SSD1306_I2C(128, 64, i2c)
pin_PWM = [26,27,33]
leds = [PWM(Pin(pin), freq =1000) for pin in pin_PWM]

for l in leds:
    l.duty(1023)
    time.sleep(1)
    l.duty(0)
ACTIVE_LOW = False  

relay_fan = Pin(ventilador, Pin.OUT)
relay_irr = Pin(bomba_riego, Pin.OUT)

def relay_write(pin_obj, on: bool):
    if ACTIVE_LOW:
        # 0 = ON, 1 = OFF
        pin_obj.value(0 if on else 1)
    else:
        # 1 = ON, 0 = OFF
        pin_obj.value(1 if on else 0)

def relay_off_all():
    relay_write(relay_fan, False)
    relay_write(relay_irr, False)

relay_off_all()  # estado seguro al inicio
# luego del boot y la conexión MQTT:
    
# ====== CONFIG MQTT ======
MQTT_BROKER = "a74d6462f9e64dd1bcb79f0518a2136e.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "growbox"
MQTT_PASS = "Growbox1"

TOPIC_STATUS = b"growstation/sensor/dht22"
TOPIC_CLOCK = b"growstation/clock"
TOPIC_CONTROL_L1 = b"growstation/control/led1"
TOPIC_CONTROL_L2 = b"growstation/control/led2"  
TOPIC_CONTROL_L3 = b"growstation/control/led3"
TOPIC_FAN_CTRL    = b"growstation/control/ventilador"
TOPIC_IRR_CTRL    = b"growstation/control/irrigation"
TOPIC_FAN_STATUS  = b"growstation/status/ventilador"
TOPIC_IRR_STATUS  = b"growstation/status/irrigation"

# ====== FUNCIONES ======
def lectura_dht_sensor():
    dht_sensor.measure() 
    global temp, hum
    temp = dht_sensor.temperature()
    hum = dht_sensor.humidity()
def sync_time(max_retries=5):
    ntptime.host = "pool.ntp.org"
    for i in range(max_retries):
    print("Sincronización horaria...")
        try:
            ntptime.settime()
            print("Hora sincronizada:", time.localtime())
            return True
        except Exception as e:
            print("⏳ Retry NTP...", i+1, "err:", e)
            time.sleep(1)
    print("⚠️ NTP no disponible: sigo sin reset")
    return False

# ====== CALLBACK MQTT ======
def handle_msg(topic, msg):
    try:
        if topic == TOPIC_FAN_CTRL or topic == TOPIC_IRR_CTRL:
            obj = json.loads(msg)          # payload: {"state":"ON"} / {"state":"OFF"}
            state = str(obj.get("state","")).strip().upper()
            if state not in ("ON","OFF"):
                print("⚠️ comando no valido:", obj); return

            is_on = (state == "ON")
            if topic == TOPIC_FAN_CTRL:
                relay_write(relay_fan, is_on)
                client.publish(TOPIC_FAN_STATUS, json.dumps({"state":state}), retain=True)
                print("Ventilador:", state)
            else:
                relay_write(relay_irr, is_on)
                client.publish(TOPIC_IRR_STATUS, json.dumps({"state":state}), retain=True)
                print("Riego:", state)
            return

        # === tuoi topic LED PWM esistenti ===
        if topic == TOPIC_CONTROL_L1:
            leds[0].duty(max(0, min(1023, int(msg))))
        elif topic == TOPIC_CONTROL_L2:
            leds[1].duty(max(0, min(1023, int(msg))))
        elif topic == TOPIC_CONTROL_L3:
            leds[2].duty(max(0, min(1023, int(msg))))
    except Exception as e:
        print("❌ handle_msg error:", e)

def setup_mqtt():
    with open("hivemq_ca.pem", "rb") as f:
        cacert = f.read()
    client = MQTTClient(
        client_id="esp32_" + "".join("%02x" % b for b in network.WLAN().config("mac")),
        server=MQTT_BROKER, 
        port=MQTT_PORT,
        user=MQTT_USER,
        password=MQTT_PASS,
        ssl=True, ssl_params={"cert_reqs": ssl.CERT_REQUIRED, 
                              "cadata": cacert, 
                              "server_hostname": MQTT_BROKER})
    client.set_callback(handle_msg)
    client.connect()
    print("client conectado")
    oled.fill(0)
    oled.text("conexión", 20, 20)
    oled.text("al broker Mqtt", 10, 30)    	
    oled.show()
    client.subscribe(TOPIC_CONTROL_L1)
    client.subscribe(TOPIC_CONTROL_L2)
    client.subscribe(TOPIC_CONTROL_L3)
    client.subscribe(TOPIC_FAN_CTRL)
    client.subscribe(TOPIC_IRR_CTRL)
    # Estado inicial (OFF) retained 
    client.publish(TOPIC_FAN_STATUS, json.dumps({"state":"OFF"}), retain=True)
    client.publish(TOPIC_IRR_STATUS, json.dumps({"state":"OFF"}), retain=True)

    return client

# === LOOP no bloquea ===
PUB_MS_SENSORS = 5000
PUB_MS_CLOCK   = 1000
last_sens_ms = 0
last_clk_ms  = 0
last_sec     = -1
tm  = time.localtime()
ora = ""
data = ""
# ====== INICIALIZACION ======
oled.fill(0)
oled.text("Inicio Sistema", 10, 20)
oled.text("GROWSTATION", 18, 30)
oled.show()
print("Inicio sistema Growstation Sample...")
setup_wifi()
oled.fill(0)
oled.text("conectando", 20, 20)
oled.text("a la red", 32, 30)
oled.show()
time.sleep(1)
sync_time()
oled.fill(0)
oled.text("sincronizando", 10, 20)
oled.text("horario", 40, 30)  
oled.show()
client = setup_mqtt()
try:
    ntptime.settime()
except: 
    pass

def publish_data():
    global last_sens_ms, last_clk_ms, last_sec, data, ora, temp, hum

    now = time.ticks_ms()
    tm  = time.localtime()
    Y, M, D = tm[0], tm[1], tm[2]
    h, m, s = (tm[3] - 3) % 24, tm[4], tm[5]

    need_clock = (s != last_sec) or (time.ticks_diff(now, last_clk_ms) >= PUB_MS_CLOCK)
    if need_clock:
        data = "{:02}/{:02}/{:04}".format(D, M, Y)
        ora  = "{:02}:{:02}:{:02}".format(h, m, s)
        last_clk_ms = now
        last_sec    = s
        try:
            payload_clock = json.dumps({"data": data, "ora": ora})
            client.publish(TOPIC_CLOCK, payload_clock, retain=True)
        except Exception as e:
            print("Clock publish err:", e)

    # SENSORI: ogni 5s
    if time.ticks_diff(now, last_sens_ms) >= PUB_MS_SENSORS:
        last_sens_ms = now
        try:
            lectura_dht_sensor()
            payload_dht = json.dumps({
                "temp": None if temp is None else round(temp, 1),
                "hum":  None if hum  is None else round(hum, 1)
            })
            client.publish(TOPIC_STATUS, payload_dht, retain=True)
        except Exception as e:
            print("DHT publish err:", e)

    client.check_msg()
    time.sleep_ms(10)

def display_clock():
    t_str = "--.-" if temp is None else "{:.1f}".format(temp)
    h_str = "--.-" if hum  is None else "{:.1f}".format(hum)

    oled.fill(0)
    oled.text("conectado al web", 6, 0)
    oled.text("T:"+t_str, 0,  14)
    oled.text("H:"+h_str, 0,  24)
    oled.text(data or "--/--/----",  20, 38)
    oled.text(ora  or "--:--:--",    22, 48)
    oled.show()


while True:
    publish_data()
    display_clock()



