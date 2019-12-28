from flask import Flask, request, Response
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from functools import wraps
from time import sleep
import RPi.GPIO as GPIO
import os
import json
import datetime


# read the config file
with open('config.json') as config_file:
    data = json.load(config_file)
    api_key = data['api_key']
    car_pin = data['car']['pin']
    car_pulse = data['car']['pulse']
    garage_pin = data['garage']['pin']
    garage_pulse = data['garage']['pulse']
    garage_state_pin = data['garage']['state_pin']
    garage_time = data['garage']['time']

# setup RPI GPIO pins
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(car_pin, GPIO.OUT)
GPIO.setup(garage_pin, GPIO.OUT)
GPIO.setup(garage_state_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# flask stuff
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# sqlite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'db.sqlite')

# init orm/db & marshmallow
db = SQLAlchemy(app)
ma = Marshmallow(app)


# because all my base are not belong to them
def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization')
        if auth == api_key:
            return f(*args, **kwargs)
        return Response(json.dumps({'error': 'unauthorized'}), status=401, mimetype='application/json')
    return decorated


# car db model
class Car(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String())
    ip = db.Column(db.String())
    datetime = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, action, ip):
        self.action = action
        self.ip = ip


# car schema
class CarSchema(ma.Schema):
    class Meta:
        fields = ('action', 'ip', 'datetime')


# garage db model
class Garage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String())
    ip = db.Column(db.String())
    state = db.Column(db.String())
    datetime = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, action, ip, state):
        self.action = action
        self.ip = ip
        self.state = state


# garage schema
class GarageSchema(ma.Schema):
    class Meta:
        fields = ('action', 'ip', 'state', 'datetime')


# init schemas
car_schema = CarSchema()
garage_schema = GarageSchema()


# routes
@app.route('/car', methods=['GET', 'POST'])
@auth_required
def car():
    if request.method == 'POST':
        action = request.args.get('action')
        ip = request.remote_addr

        if action == 'start':
            print('starting car')
            GPIO.output(car_pin, GPIO.LOW)
            sleep(car_pulse)
            GPIO.output(car_pin, GPIO.HIGH)

            db_write = Car(action, ip)
            db.session.add(db_write)
            db.session.commit()
            return car_schema.jsonify(db_write)
        else:
            return Response(json.dumps({'error': 'understood, but not valid'}), status=422, mimetype='application/json')
    if request.method == 'GET':
        query_result = Car.query.order_by(Car.datetime.desc()).first()
        if not query_result:
            return Response(json.dumps({'error': 'no history'}), status=404, mimetype='application/json')
        else:
            return car_schema.jsonify(query_result)
    else:
        return Response(json.dumps({'error': 'understood, but not valid'}), status=422, mimetype='application/json')


@app.route('/garage', methods=['GET', 'POST'])
@auth_required
def garage():
    if request.method == 'POST':
        action = request.args.get('action')
        ip = request.remote_addr

        if action == 'open':
            GPIO.output(garage_pin, GPIO.LOW)
            sleep(garage_pulse)
            GPIO.output(garage_pin, GPIO.HIGH)
            sleep(garage_time)
            if not GPIO.input(garage_state_pin):
                state = 'open'
            else:
                state = 'closed'
        if action == 'close':
            GPIO.output(garage_pin, GPIO.LOW)
            sleep(garage_pulse)
            GPIO.output(garage_pin, GPIO.HIGH)
            sleep(garage_time)
            if GPIO.input(garage_state_pin):
                state = 'closed'
            else:
                state = 'open'

        db_write = Garage(action, ip, state)
        db.session.add(db_write)
        db.session.commit()
        return garage_schema.jsonify(db_write)
    if request.method == 'GET':
        query_result = Garage.query.order_by(Garage.datetime.desc()).first()
        if not query_result:
            return Response(json.dumps({'error': 'no history'}), status=404, mimetype='application/json')
        else:
            return garage_schema.jsonify(query_result)
    else:
        return Response(json.dumps({'error': 'understood, but not valid'}), status=422, mimetype='application/json')


# run server
if __name__ == '__main__':
    app.run(debug=False)