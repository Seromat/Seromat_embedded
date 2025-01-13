
from re import I, M
from flask import Flask, jsonify, request
from collections import deque
import json
import time
import adafruit_dht
import board
import datetime as date
import threading
import RPi.GPIO as GPIO
import csv

class DHT_Sensor:

    def __init__(self, dht_sensor, temperature_c = None, humidity = None):
        self.dht_sensor = dht_sensor
        self.temperature_c = temperature_c
        self.humidity = humidity

    def read_data(self):
        try:
            self.temperature_c = self.dht_sensor.temperature
            self.humidity = self.dht_sensor.humidity
            return True
        except RuntimeError as error:
            print("Failed to get sensor data, retrying...")
            return False

    def print_data(self):
        print(f"Temperature: {self.temperature_c}")
        print(f"Humidity: {self.humidity}")
        

class Regulator:
    def __init__(self, dht_sensor):
        self.sensor = dht_sensor
        self.temperature_sp = 14.0
        self.temperature_h = 1
        self.humidity_sp = 80.0
        self.humidity_h = 8
        self.humidifier_gpio = 17
        self.cooler_gpio = 27
        self.cooler_status = 0
        self.humidifier_status = 0
        self.alert_counter = 0
        self.avg_humidity = 0
        self.humidity_buffer = deque(maxlen=500)
        
        '''with open('sensor_data.csv', mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Date", "TemperatureC", "Humidity", "cooler_status", "humidifier_status", "Avg. Humidity"])'''
         
    def save_data_to_csv(self, cooler_status, humidifier_status):
        with open('sensor_data.csv', mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([str(date.datetime.now()), self.sensor.temperature_c, self.sensor.humidity, cooler_status, humidifier_status, self.avg_humidity])
            
    def CurrentHumidityTooLow(self):
        if self.sensor.humidity < (self.humidity_sp - self.humidity_h):
            print("Chwilowa za niska")
        else:
            print("Chwilowa git")
        return self.sensor.humidity < (self.humidity_sp - self.humidity_h)

    def AvgHumidityTooLow(self):
        return self.avg_humidity < (self.humidity_sp - 1) and self.sensor.humidity < self.humidity_sp
    
    def HumidifierTurnoffCondition(self, turnoff_humidity):
        return self.sensor.humidity > self.humidity_sp or (self.sensor.humidity > turnoff_humidity and self.avg_humidity+2.0 > self.humidity_sp)
    
    def Regulate(self):
        turnoff_humidity = self.humidity_sp
        while True:
            read_successful = self.sensor.read_data()

            if read_successful:
                self.alert_counter = 0
                self.sensor.print_data()
                self.humidity_buffer.append(self.sensor.humidity)
                self.avg_humidity = sum(self.humidity_buffer) / len(self.humidity_buffer)
                print(f"Avg. humidity: {self.avg_humidity}, Turnoff humidity: {turnoff_humidity}")

                # Logika sterowania chłodzeniem i nawilżaniem
                if self.sensor.temperature_c >= (self.temperature_sp + self.temperature_h) and self.cooler_status != 1:
                    GPIO.output(self.cooler_gpio, GPIO.HIGH)
                    self.cooler_status = 1
                    print("Cooler ON") 
                elif self.sensor.temperature_c <= self.temperature_sp and self.cooler_status != 0:
                    GPIO.output(self.cooler_gpio, GPIO.LOW)
                    self.cooler_status = 0
                    print("Cooler OFF")

                if self.HumidifierTurnoffCondition(turnoff_humidity) and self.humidifier_status != 0:
                    print("Humidifier OFF")
                    GPIO.output(self.humidifier_gpio, GPIO.LOW)
                    time.sleep(3)
                    GPIO.output(self.humidifier_gpio, GPIO.HIGH)
                    self.humidifier_status = 0
                elif (self.AvgHumidityTooLow() or self.CurrentHumidityTooLow()) and self.humidifier_status != 1:
                    print("Humidifier ON")
                    turnoff_humidity = self.sensor.humidity + 2.0
                    GPIO.output(self.humidifier_gpio, GPIO.LOW)
                    time.sleep(0.5)
                    GPIO.output(self.humidifier_gpio, GPIO.HIGH)
                    self.humidifier_status = 1
                '''elif self.CurrentHumidityTooLow() and self.humidifier_status != 1:
                    print("Humidifier ON")
                    GPIO.output(self.humidifier_gpio, GPIO.LOW)
                    time.sleep(0.5)
                    GPIO.output(self.humidifier_gpio, GPIO.HIGH)
                    self.humidifier_status = 1
                    time.sleep(5)
                    print("Humidifier OFF")
                    GPIO.output(self.humidifier_gpio, GPIO.LOW)
                    time.sleep(3)
                    GPIO.output(self.humidifier_gpio, GPIO.HIGH)
                    self.humidifier_status = 0'''

                #self.save_data_to_csv(self.cooler_status, self.humidifier_status)
                time.sleep(3)
            else:
                self.alert_counter += 1
                print(f"Sensor read failed. Alert counter: {self.alert_counter}")

                if self.alert_counter >= 3:
                    print("Sensor alert, check connection!")
                    if self.humidifier_status != 0:
                        print("Turning off humidifier")
                        GPIO.output(self.humidifier_gpio, GPIO.LOW)
                        time.sleep(3)
                        GPIO.output(self.humidifier_gpio, GPIO.HIGH)
                        self.humidifier_status = 0
                time.sleep(3)   
                

    def set_parameters(self, new_temperature_sp,new_temperature_h,new_humidity_sp,new_humidity_h):
        self.temperature_sp = new_temperature_sp
        self.temperature_h = new_temperature_h
        self.humidity_sp = new_humidity_sp
        self.humidity_h = new_humidity_h
        
    def getStatusJSON(self):
        return {
            "Date": str(date.datetime.now()),
            "TemperatureC": self.sensor.temperature_c,
            "Humidity": self.sensor.humidity,
            "AvgHumidity": self.avg_humidity,
            "CoolerStatus": "ON" if self.cooler_status == 1 else "OFF",
            "HumidifierStatus": "ON" if self.humidifier_status == 1 else "OFF"
        }

    def getParametersJSON(self):
        return {
            "TempSp": self.temperature_sp,
            "TempH": self.temperature_h,
            "HumSp": self.humidity_sp,
            "HumH": self.humidity_h
        }



sensor = DHT_Sensor(adafruit_dht.DHT22(board.D14))
regulatator = Regulator(sensor)
           
if GPIO.getmode() is None:
    GPIO.setmode(GPIO.BCM)

GPIO.setup(regulatator.humidifier_gpio, GPIO.OUT)
GPIO.setup(regulatator.cooler_gpio, GPIO.OUT)

regulate_t = threading.Thread(target=regulatator.Regulate)
regulate_t.daemon = True 
regulate_t.start()

app = Flask(__name__)

@app.route('/sensor_data', methods=['GET'])
def get_sensor_data():
    sensor.read_data()
    status_data_json = regulatator.getStatusJSON()
    print(f"Temperature: {status_data_json['TemperatureC']}°C, Humidity: {status_data_json['Humidity']}%")
    return jsonify(status_data_json), 200


@app.route('/parameters', methods=['GET', 'POST'])
def set_boundaries():
    if request.method == 'POST':
        data = request.json
        print(f"Received JSON data: {data}")
        temp_sp = float(data.get('TempSp'))
        temp_h = float(data.get('TempH'))
        hum_sp = float(data.get('HumSp'))
        hum_h = float(data.get('HumH'))
        regulatator.set_parameters(temp_sp, temp_h, hum_sp, hum_h)
        return "1"
    else:
        regulator_data_json = regulatator.getParametersJSON()
        print(regulator_data_json)
        return jsonify(regulator_data_json), 200
    
'''@app.route('/alert', methods=['POST'])
def send_alert():
    if request.method == 'POST':
        data = request.json
        print(f"Received JSON data: {data}")
        temp_sp = float(data.get('temp_sp'))
        temp_ub = float(data.get('temp_h'))
        hum_lb = float(data.get('hum_sp'))
        hum_ub = float(data.get('hum_h'))
        #print(temp_lb, temp_ub, hum_lb, hum_ub)
        regulatator.set_parameters(temp_sp, temp_h, hum_sp, hum_h)
        return "1"
    else:
        regulator_data_json = regulatator.getParametersJSON()
        print(regulator_data_json)
        return jsonify(regulator_data_json), 200'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
