from machine import Pin, PWM, Timer
import network
import utime as time
from umqtt.simple import MQTTClient
from led_pwm import LED
import dht
import ntptime
import ujson
import urandom
import urequests as requests

# ------------ HELPER METHODS ----------------- #
# Synchronize with NTP server
def synchronize_ntp_time():
    # Specify a different NTP server (e.g., Google's NTP server)
    ntptime.host = "time.google.com"
    # Synchronize with the NTP server
    ntptime.settime()

# Get UTC Date String
def get_formatted_time_string():
    # Get the current time in UTC
    current_time_utc = time.gmtime()

    # Format the time
    formatted_time = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}.{:06d}Z".format(
        current_time_utc[0], current_time_utc[1], current_time_utc[2],
        current_time_utc[3], current_time_utc[4], current_time_utc[5],
        current_time_utc[6]
    )

    return formatted_time

# Generate random UUID
def generate_uuid():
    uuid_format = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"
    uuid = ""
    for char in uuid_format:
        if char == "x":
            uuid += "{:x}".format(urandom.getrandbits(4))
        elif char == "y":
            uuid += "{:x}".format(8 | (urandom.getrandbits(3)))
        else:
            uuid += char
    return uuid


# ------------ HELPER CLASSES ----------------- #
# WiFi Connection Manager
class WiFiConnector:
    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        self.wifi_client = None

    def connect(self):
        # Connect to WiFi
        self.wifi_client = network.WLAN(network.STA_IF)
        self.wifi_client.active(True)
        print("Connecting device to WiFi")
        self.wifi_client.connect(self.ssid, self.password)

        # Wait until WiFi is Connected
        while not self.wifi_client.isconnected():
            print("Connecting...")
            time.sleep(0.1)
        print("WiFi Connected!")
        print(self.wifi_client.ifconfig())
        synchronize_ntp_time()

        # Print the current time in UTC
        print("Current Time (UTC): ", get_formatted_time_string())


# MQTT Connection Manager
class MqttConnector:
    def __init__(self, client_id, broker, user, password, ssl=False, ssl_params=None):
        self.client_id = client_id
        self.broker = broker
        self.user = user
        self.password = password
        self.ssl = ssl
        self.ssl_params = ssl_params
        self.client = None


    def connect(self, did_recieve_callback):
        print("Connecting to MQTT broker ...")
        if self.ssl:
            self.client = MQTTClient(self.client_id, self.broker, user=self.user,
                                password=self.password, ssl=self.ssl_params, ssl_params=self.ssl_params)
        else:
            self.client = MQTTClient(self.client_id, self.broker, user=self.user, password=self.password)

        self.client.set_callback(did_recieve_callback)
        self.client.connect()
        print("MQTT broker is Connected.")

        return self.client

    def subscribe(self, topic):
        self.client.subscribe(topic)
        print("subscribed to topic = " + topic)

    def publish(self, topic, data):
        try:
            print("\nUpdating MQTT Broker...")
            self.client.publish(topic, data)
            print("data sent to: ", topic)
        except:
            print("ERROR: MQTT client may not be initialized.")

    def check_incoming_msg(self):
        self.client.check_msg()

# Device Types
class DeviceType:
    LED = "LED"
    THERMOMETER = "THERMOMETER"
    HUMIDITY = "HUMIDITY"
    GATEWAY = "GATEWAY"
    MOTOR = "MOTOR"

# Device Profiles
class DefaultProfileName:
    SENSOR = "SENSOR"
    LED = "LED"
    LAMP = "LAMP"
    HUMIDITY = "HUMIDITY"
    TEMPERATURE = "TEMPERATURE"
    MOTOR = "MOTOR"
    DEFAULT = "DEFAULT"

# Device States
class StateName:
    STATE = "STATE"
    BRIGHTNESS = "BRIGHTNESS"
    TEMPERATURE = "TEMPERATURE"
    HUMIDITY = "HUMIDITY"
    SENSOR = "SENSOR"
    SPEED = "SPEED"

# Device Channel Types
class ChannelTypes:
    COMMAND = "COMMAND"
    TELEMETRY = "TELEMETRY"
    ALERTS = "ALERTS"

# Devices Manager
class DevicesManager:
    def __init__(self, gateway_name, gateway_id):
        self.gateway_name = gateway_name
        self.gateway_id = gateway_id
        self.devices = {}
        device = {
            "device_id": self.gateway_id,
            "device_name": self.gateway_name,
            "device_type": DeviceType.GATEWAY,
            "parent": "0",   # Default Gateway Parent = 0
            "pin": -1,
            "controller": None
        }
        self.devices[self.gateway_name] = device

    def add_device(self, device_id, device_name, device_type, pin):
        if device_name not in self.devices:
            controller = self.create_controller(device_type, pin)
            device = {
                "device_id": device_id,
                "device_name": device_name,
                "device_type": device_type,
                "pin": pin,
                "parent": self.gateway_id,
                "controller": controller
            }
            self.devices[device_name] = device

            return device
        else:
            raise ValueError("A device with name '{}' already exists. Device Names must be unique.".format(device_name))

    def create_device(self, device_data):
        return self.add_device(device_data["id"], device_data["name"], device_data["type"], device_data["pin"])
    
    def create_controller(self, device_type, pin):
        if device_type == DeviceType.LED or device_type == DeviceType.MOTOR:
            return LED(pin)
        elif device_type == DeviceType.THERMOMETER or device_type == DeviceType.HUMIDITY:
            DHT_PIN = Pin(pin)
            dht_sensor = dht.DHT22(DHT_PIN)
            return dht_sensor
        
        return None

    def get_controller(self, device_name):
        return self.devices[device_name]["controller"]

    def get_devices_list_json(self):
        return ujson.dumps(self.get_data())

    def get_device_command(self, topic, message):
        command_message = ujson.loads(message.decode())
        command_topic = topic.decode().split('/')
        command_data = {}

        if command_topic[-1] == ChannelTypes.COMMAND:
            command_data = {
                "type": ChannelTypes.COMMAND,
                "group_id": command_topic[0],
                "parent_id": command_topic[1] if not command_topic[1] == command_topic[-2] else "0",
                "device_id": command_topic[-2],
                "commands": command_message,
            }
        else:
            print("** command is not supported **")

        return command_data

    def run_device_command(self, device_command):
        # if device is not a gatweay
        if not device_command["parent_id"] == "0":
            s_device = {}
            for key, device in self.devices.items():
                if device["device_id"] == device_command["device_id"]:
                    s_device = device
                    self._set_command_for_device(device, device_command)
                    break
        else:
            print("gateway commands are not yet supported")

    def _set_command_for_device(self, device, device_command):
        states = []
        for command in device_command["commands"]:
            command_name = command["name"]
            command_value = command["value"]

            if device["device_type"] == DeviceType.GATEWAY:
                print("gateway commands are not yet supported")
            elif device["device_type"] == DeviceType.LED:
                if command_name == StateName.STATE:
                    device["controller"].set_value(1 if command_value == "ON" else 0)
                elif command_name == StateName.BRIGHTNESS:
                    command_value_int = int(command_value)
                    device["controller"].set_value(1 if command_value_int > 0 else 0)
                    device["controller"].set_brightness(command_value_int)
            if device["device_type"] == DeviceType.MOTOR:
                if command_name == StateName.STATE:
                    device["controller"].set_value(1 if command_value == "ON" else 0)
                elif command_name == StateName.SPEED:
                    command_value_int = int(command_value)
                    device["controller"].set_value(1 if command_value_int > 0 else 0)
                    device["controller"].set_brightness(command_value_int)
            elif device["device_type"] == DeviceType.THERMOMETER or device["device_type"] == DeviceType.HUMIDITY:
                print("** humidity and temperature sensor commands are not yet supported")

    def get_data(self):
        devices_data_list = []
        uuid_str = generate_uuid()
        for key, device in self.devices.items():
            device_data = {}
            device_data["device_id"] = device["device_id"]
            device_data["type"] = device["device_type"]
            device_data["name"] = device["device_name"]
            device_data["parent"] = device["parent"]
            device_data["log_id"] = uuid_str
            device_data["log_time"] = get_formatted_time_string()
            device_data["states"] = self.get_device_states(device)
            devices_data_list.append(device_data)
        
        return devices_data_list
    
    def get_device_states(self, device):
        states = []
        if device["device_type"] == DeviceType.GATEWAY:
            states.append({"name": StateName.STATE, "value": "ON"})
        elif device["device_type"] == DeviceType.LED:
            states.append({"name": StateName.STATE, "value": "ON" if device["controller"].value() == 1 else "OFF"})
            states.append({"name" : StateName.BRIGHTNESS , "value": device["controller"].get_brightness()})
        if device["device_type"] == DeviceType.MOTOR:
            states.append({"name": StateName.STATE, "value": "ON" if device["controller"].value() == 1 else "OFF"})
            states.append({"name" : StateName.SPEED , "value": device["controller"].get_brightness()})
        elif device["device_type"] == DeviceType.THERMOMETER or device["device_type"] == DeviceType.HUMIDITY:
            dht_sensor = device["controller"]
            dht_sensor.measure()
            time.sleep(0.1)
            states.append({"name" : StateName.SENSOR , "value": dht_sensor.temperature() if device["device_type"] == DeviceType.THERMOMETER else dht_sensor.humidity()})

        return states

    def get_provisioning_device_data(self, secrete_key):
        all_devices = self.get_data()
        parent_device = {}
        sub_devices = []

        for device_data in all_devices:
            p_device_data = self.map_provision_device_data(device_data)
            if device_data["type"] == DeviceType.GATEWAY:
                parent_device = p_device_data
            else:
                sub_devices.append(p_device_data)
        
        response = {
            "parent_device": parent_device,
            "sub_devices": sub_devices,
            "provision_parent": True,
            "secrete_key": secrete_key
        }

        return response
    
    def map_provision_device_data(self, device_data):

        profile_name = DefaultProfileName.DEFAULT
        if device_data["type"] == DeviceType.HUMIDITY or device_data["type"] == DeviceType.THERMOMETER:
            profile_name = DefaultProfileName.SENSOR
        elif device_data["type"] == DeviceType.LED:
            profile_name = DefaultProfileName.LED
        elif device_data["type"] == DeviceType.MOTOR:
            profile_name = DefaultProfileName.MOTOR


        provision_device_data = {
            "name": device_data["name"],
            "type": device_data["type"],
            "parent_id": device_data["parent"],
            "location": "",
            "zone": "",
            "profile_name": profile_name,
            "id": device_data["device_id"],
            "is_new": True
        }

        return provision_device_data

        

# Switch Types
class SwitchType:
    TOGGLE = "TOGGLE"
    INCREMENT = "INCREMENT"

# Switch Device Manager
class SwitchDeviceManager:
    def __init__(self, switch_pin, switch_type, pwm_device, increment=25):
        self.switch = Pin(switch_pin, Pin.IN, Pin.PULL_UP)
        self.pwm_device = pwm_device
        self.debounce_timer = Timer(0)
        self.timer_running = False

        self.switch.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self.handle_switch_interrupt)
        self.switch_type = switch_type
        self.increment = increment

        self.switch_state = 1  # Initial switch state (1 for pull-up)

    def handle_switch_interrupt(self, pin):
        self.debounce_timer.init(mode=Timer.ONE_SHOT, period=50, callback=self.debounce_callback)

        # if not self.timer_running:
        #     print("bbbbb")
        #     self.debounce_timer.init(mode=Timer.ONE_SHOT, period=50, callback=self.debounce_callback)
        #     self.timer_running = True

    def debounce_callback(self, timer):
        self.timer_running = False
        current_state = self.switch.value()

        if current_state != self.switch_state:  # Check if switch state has changed
            self.switch_state = current_state
            switch_is_pressed_down = 0 # Switch pressed (falling edge)
            if not current_state == switch_is_pressed_down:  # switch is released
                if self.switch_type == SwitchType.TOGGLE:
                    self.toggle_pwm_device()
                if self.switch_type == SwitchType.INCREMENT:
                    self.increment_pwm_device()

    def toggle_pwm_device(self):
        if self.pwm_device.value() == 1:
            self.pwm_device.off()
        else:
            self.pwm_device.on()

    def increment_pwm_device(self):
        current_percent = self.pwm_device.get_brightness()
        set_percent = current_percent + self.increment

        if set_percent > 100:
            set_percent = 0

        if set_percent == 0:
            self.pwm_device.set_brightness(set_percent)
            self.pwm_device.off()
        else:
            self.pwm_device.on(set_percent)
            self.pwm_device.set_brightness(set_percent)


# DelayedMethod: Run a method after a delay
class DelayedMethod:
    def __init__(self, callback, delay_seconds=10):
        # Keep track of the start time
        self.start_time = time.time()
        self.callback = callback
        self.delay_seconds = delay_seconds
        self.current_time = time.time()
    
    def run(self):
        # Check if delayed seconds have passed
        self.current_time = time.time()
        if self.current_time - self.start_time >= self.delay_seconds:
            # Call the delayed method
            self.callback()
            # Reset the start time for the next interval
            self.start_time = self.current_time




class APIClient:
    def __init__(self, base_url):
        self.base_url = base_url

    def _make_request(self, method, endpoint, data=None, params="", headers=None, bearerToken=""):
        url = self.base_url + endpoint
        headers = headers or {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + bearerToken,  # Include any other headers as needed
        }
        response = None

        print("url = ", url)

        try:
            if method == "GET" and params:
                response = requests.get(url, params=params, headers=headers)
            elif method == "POST":
                response = requests.post(url, json=data, headers=headers)
            else:
                raise ValueError("Unsupported HTTP method")

            # Check if the status code is in the 2xx range (success)
            if 200 <= response.status_code < 300:
                return ujson.loads(response.text)
            else:
                raise Exception("HTTP Error - Status Code:", response.status_code, "Error Message:", response.text)
        except Exception as e:
            print("An error occurred...")
            raise e
        finally:
            if not response == None:
                response.close()

    def get(self, endpoint, params=None, headers=None):
        return self._make_request("GET", endpoint, params=params, headers=headers)

    def post(self, endpoint, data=None, headers=None):
        return self._make_request("POST", endpoint, data=data, headers=headers)