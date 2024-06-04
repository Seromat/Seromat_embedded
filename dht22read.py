
from re import M
from flask import Flask, jsonify, request
import json
import time
import adafruit_dht
import board
import datetime as date
import threading
import RPi.GPIO as GPIO

class DHT_Sensor:

    def __init__(self, dht_device, temperature_c = None, humidity = None):
        self.dht_device = dht_device
        self.temperature_c = temperature_c
        self.humidity = humidity

    def read_data(self):
        try:
            self.temperature_c = self.dht_device.temperature
            self.humidity = self.dht_device.humidity
        except RuntimeError as error:
            print("An error occured while reading sensor data, retrying...")

    def print_data(self):
        print(f"Temperature: {self.temperature_c}")
        print(f"Humidity: {self.humidity}")

    def makea_da_Jason(self):
        return {
            "Date": str(date.datetime.now()),
            "TemperatureC": self.temperature_c,
            "Humidity": self.humidity
        }

class Regulator:
    def __init__(self, dht_device):
        self.sensor = dht_device
        self.temperature_lb = 20.0
        self.temperature_ub = 22.0
        self.humidity_lb = 50.0
        self.humidity_ub = 80.0
        self.humidifier_gpio = 17
        self.cooler_gpio = 27
            
    def Regulate(self):
        while 1:
            self.sensor.read_data()
            self.sensor.print_data()
            if self.sensor.temperature_c > self.temperature_ub:
                GPIO.output(self.cooler_gpio, GPIO.LOW)
                print("Cooler ON") 
            elif self.sensor.temperature_c < self.temperature_lb:
                GPIO.output(self.cooler_gpio, GPIO.HIGH)
                print("Cooler OFF")
            if self.sensor.humidity > self.humidity_ub:
                print("Humidifier OFF")
                GPIO.output(self.humidifier_gpio, GPIO.HIGH)
            elif self.sensor.humidity < self.humidity_lb:
                print("Humidifier ON")
                GPIO.output(self.humidifier_gpio, GPIO.LOW)
            time.sleep(3)

    def set_parameters(self, new_temperature_lb,new_temperature_ub,new_humidity_lb,new_humidity_ub):
        self.temperature_lb = new_temperature_lb
        self.temperature_ub = new_temperature_ub
        self.humidity_lb = new_humidity_lb
        self.humidity_ub = new_humidity_ub

    def makea_da_Jason(self):
        return {
            "temp_lb": self.temperature_lb,
            "temp_ub": self.temperature_ub,
            "hum_lb": self.humidity_lb,
            "hum_ub": self.humidity_ub
        }



sensor = DHT_Sensor(adafruit_dht.DHT22(board.D4))
regulatator = Regulator(sensor)
           
if GPIO.getmode() is None:
    GPIO.setmode(GPIO.BCM)

GPIO.setup(regulatator.humidifier_gpio, GPIO.OUT)
GPIO.setup(regulatator.cooler_gpio, GPIO.OUT)

#Run regulation on a separate thread
regulate_t = threading.Thread(target=regulatator.Regulate)
regulate_t.daemon = True 
regulate_t.start()

app = Flask(__name__)

#Different routes for HTTP requests
@app.route('/sensor_data', methods=['GET'])
def get_sensor_data():
    sensor.read_data()
    sensor_data_json = sensor.makea_da_Jason()
    print(f"Temperature: {sensor_data_json['TemperatureC']}°C, Humidity: {sensor_data_json['Humidity']}%")
    return jsonify(sensor_data_json), 200


@app.route('/set_parameters', methods=['GET', 'POST'])
def set_boundaries():
    if request.method == 'POST':
        data = request.json
        print(f"Received JSON data: {data}")
        temp_lb = float(data.get('temp_lb'))
        temp_ub = float(data.get('temp_ub'))
        hum_lb = float(data.get('hum_lb'))
        hum_ub = float(data.get('hum_ub'))
        #print(temp_lb, temp_ub, hum_lb, hum_ub)
        regulatator.set_parameters(temp_lb, temp_ub, hum_lb, hum_ub)
        return "1"
    else:
        regulator_data_json = regulatator.makea_da_Jason()
        print(regulator_data_json)
        return jsonify(regulator_data_json), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
