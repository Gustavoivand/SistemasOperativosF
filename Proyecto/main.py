from machine import Pin, PWM
import ujson
import utime as time
import dht
from led_pwm import LED
from helpers import WiFiConnector, MqttConnector
from helpers import ChannelTypes, DeviceType, DevicesManager
from helpers import SwitchType, SwitchDeviceManager
from helpers import DelayedMethod, APIClient
from env_settings import *

# MQTT Setup
MQTT_CLIENT_ID = DEVICE_ID
MQTT_ENABLE_SSL = False
MQTT_SSL_PARAMS = {'server_hostname': MQTT_BROKER}

MQTT_TELEMETRY_TOPIC = "mqtt.publish.TELEMETRY" #'mqtt.publish.{0}'.format(ChannelTypes.TELEMETRY)
MQTT_CONTROL_TOPIC = '{0}.{1}.#'.format(GROUP_ID, DEVICE_ID)
MQTT_CONTROL_TOPIC = MQTT_CONTROL_TOPIC.replace(" ", "")

# Setup Device Params
RED_LED_DEVICE = {"name": "RED_LED_" + DEVICE_NAME.upper(), "type": DeviceType.LED, "pin": 12, "id": RED_LED_DEVICE_ID}
BLUE_LED_DEVICE = {"name": "BLUE_LED_" + DEVICE_NAME.upper(), "type": DeviceType.LED, "pin": 13, "id": BLUE_LED_DEVICE_ID}
RED_FAN_DEVICE = {"name": "RED_FAN_" + DEVICE_NAME.upper(), "type": DeviceType.MOTOR, "pin": 5, "id": RED_FAN_DEVICE_ID}
BLUE_FAN_DEVICE = {"name": "BLUE_FAN_" + DEVICE_NAME.upper(), "type": DeviceType.MOTOR, "pin": 18, "id": BLUE_FAN_DEVICE_ID}
THERMOMETER_DEVICE = {"name": "THERMOMETER_" + DEVICE_NAME.upper(), "type": DeviceType.THERMOMETER, "pin": 15, "id": THERMOMETER_DEVICE_ID}
HUMIDITY_DEVICE = {"name": "HUMIDITY_" + DEVICE_NAME.upper(), "type": DeviceType.HUMIDITY, "pin": 15, "id": HUMIDITY_DEVICE_ID}

# Create Devices
devices_manager = DevicesManager(gateway_name=DEVICE_NAME, gateway_id=DEVICE_ID)
devices_manager.create_device(RED_LED_DEVICE)
devices_manager.create_device(BLUE_LED_DEVICE)
if USE_FAN:
  devices_manager.create_device(RED_FAN_DEVICE)
  devices_manager.create_device(BLUE_FAN_DEVICE)
  RED_FAN = devices_manager.get_controller(RED_FAN_DEVICE["name"])
  BLUE_FAN = devices_manager.get_controller(BLUE_FAN_DEVICE["name"])

if USE_DHT_SENSOR:
  devices_manager.create_device(THERMOMETER_DEVICE)
  devices_manager.create_device(HUMIDITY_DEVICE)


# LED/LAMP Setup
RED_LED = devices_manager.get_controller(RED_LED_DEVICE["name"])
BLUE_LED = devices_manager.get_controller(BLUE_LED_DEVICE["name"])
FLASH_LED = Pin(2, Pin.OUT)


# Turn On LEDs
RED_LED.on(100)
BLUE_LED.on(100)
if USE_FAN:
  RED_FAN.on(25)
  BLUE_FAN.on(25)






# -------------- Application Logic --------------

# Connect to WiFi
wifi_connector = WiFiConnector(WIFI_SSID, WIFI_PASSWORD)
wifi_connector.connect()

# Register Devices to IoTConnector Cloud
api_client = APIClient("http://{0}:{1}".format(URL_HOST, URL_PORT))
provision_device_data = devices_manager.get_provisioning_device_data(DEVICE_SECRETE)
url_params = "/api/v1/devices/provision/group/{0}/{1}".format(GROUP_ID, API_KEY)
provisioning_response = api_client.post(url_params, data=provision_device_data)
print("Provisioned Devices: ", provisioning_response)


# Connect to MQTT
def did_recieve_subscription_message(topic, message):
  print("\n** message received **")
  print("topic: ", topic)
  print("message: ", message)
  received_command = devices_manager.get_device_command(topic, message)
  devices_manager.run_device_command(received_command)
  # print("aaaaaa: ", ujson.dumps(received_command))


mqtt_connector = MqttConnector(MQTT_CLIENT_ID, MQTT_BROKER, MQTT_USER_NAME, MQTT_PASSWORD, MQTT_ENABLE_SSL, MQTT_SSL_PARAMS)
mqtt_connector.connect(did_recieve_subscription_message)
mqtt_connector.subscribe(MQTT_CONTROL_TOPIC)

# Turn Off LEDs
RED_LED.off()
BLUE_LED.off()
if USE_FAN:
  RED_FAN.off()
  BLUE_FAN.off()

# --------- 

RED_LED_SWITCH = SwitchDeviceManager(33, SwitchType.TOGGLE, RED_LED)
BLUE_LED_SWITCH = SwitchDeviceManager(32, SwitchType.TOGGLE, BLUE_LED)

RED_FAN_SWITCH = None
BLUE_FAN_SWITCH = None
if USE_FAN:
  RED_FAN_SWITCH = SwitchDeviceManager(21, SwitchType.INCREMENT, RED_FAN)
  BLUE_FAN_SWITCH = SwitchDeviceManager(19, SwitchType.INCREMENT, BLUE_FAN)


# push sensor data to cloud via mqtt
def push_data():
    telemetry_data = {
        "type": ChannelTypes.TELEMETRY,
        "data": devices_manager.get_data()
    }

    telemetry_data_json = ujson.dumps(telemetry_data)
    mqtt_connector.publish(MQTT_TELEMETRY_TOPIC, telemetry_data_json)
    # print("data: ", devices_manager.get_devices_list_json())


push_device_data_delay = DelayedMethod(push_data, 10)

# send data on connection
push_data()

while True:
  push_device_data_delay.run()
  mqtt_connector.check_incoming_msg()
  time.sleep(0.1)





