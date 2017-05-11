import os
import time
import json
from celery import Celery
import celery
from sqlite3 import dbapi2 as sqlite3

from flask import Flask, request, jsonify, g, render_template, url_for
from .exceptions import InvalidUsage
from .tasks import make_celery, TASK_TIME_INTERVAL
from influxdb import InfluxDBClient
from anomaly import find_anomalies
import sensor_lut

app = Flask(__name__)
# Load default config and override config from an environment variable
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'urbansense.db'),
    DEBUG=True,
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default',
    DB_TABLE="data",
    INFLUX_HOST='localhost',
    INFLUX_PORT=8086,
    INFLUX_DB='beta',
    ENV='dev',
    CELERY_BROKER_URL='redis://localhost:6379/0',
    CELERY_RESULT_BACKEND='redis://localhost:6379/0',
    CELERYBEAT_SCHEDULE={
        'process-ir-every-30-secs': {
            'task': 'urbansense-client.urbansense_client.process_data',
            'schedule': TASK_TIME_INTERVAL,
            'args': ["ir", 'SELECT * FROM %s', 0.2]
        },
        'process-accel-every-30-secs': {
            'task': 'urbansense-client.urbansense_client.process_data',
            'schedule': TASK_TIME_INTERVAL,
            'args': ["accel", 'SELECT * FROM %s WHERE tag_name=\'z\'', 0.1]
        }
    },
    CELERY_TIMEZONE='UTC'
))

celery = make_celery(app)

def get_influx_client():
    return InfluxDBClient(app.config['INFLUX_HOST'], app.config['INFLUX_PORT'], database=app.config['INFLUX_DB'])

def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv


def init_db():
    """Initializes the database."""
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()

@app.cli.command('initdb')
def initdb_command():
    """Creates the database tables."""
    init_db()
    print('Initialized the database...')

def get_db():
   """Opens a new database connection if there is none yet for the
   current application context.
   """
   if not hasattr(g, 'sqlite_db'):
       g.sqlite_db = connect_db()
   return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
   """Closes the database again at the end of the request."""
   if hasattr(g, 'sqlite_db'):
       g.sqlite_db.close()

@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

# Browser Cache bbuster code
@app.context_processor
def override_url_for():
    return dict(url_for=dated_url_for)

def dated_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(app.root_path,
                                     endpoint, filename)
            values['q'] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)

# -------------------------------------------------------------------------------

def get_data():
    db = get_db()
    c = db.cursor()
    data = {}
    for sensor_name in sensor_lut.SENSOR_MAPPINGS.values():
        rows = c.execute("SELECT * FROM %s WHERE lat != 0 AND lng != 0 AND sensor_name = '%s'" % (app.config["DB_TABLE"], sensor_name)).fetchall()
        data[sensor_name] = rows

    return data

@app.route('/')
def hello_world():
	return 'UrbanSense server ready to receive data...\n'

@app.route('/getData')
def get_data_route():
    data = get_data()
    json_data = {}
    for sensor_name, rows in data.iteritems():
        json_data[sensor_name] = []
        for row in rows:
            json_data[sensor_name].append({
                "value": row["value"],
                "is_pothole": row["is_pothole"],
                "lat": row["lat"],
                "lng": row["lng"]
            })

    return jsonify(json_data)


@app.route('/map')
def render_test_map():
       
    return render_template("index.html", data=get_data())

# --------------------------------- TASKS --------------------------------------

@celery.task()
def process_data(sensor_name, query_string, smoothing_factor):
    """Polls for 10 minutes of data every 10 minutes and selects the maximum
    value in that time period"""
    current_time = int(time.time())
    client = get_influx_client()
    if app.config["ENV"] == 'dev':
        results = client.query(
            query_string % (sensor_name),
            epoch="s"
        )
    else:
        results = client.query(
            (query_string + ' and "time" <= %d AND "time" > %d') % (sensor_name, current_time, current_time - TASK_TIME_INTERVAL),
            epoch="s"
        )
        
    pts = list(results.get_points(measurement=sensor_name))
    if len(pts) == 0:
        print "No new {} values to be processed!".format(sensor_name)
        return

    anomalies = find_anomalies(pts, smoothing_factor)

    db = get_db()
    for m in pts:
        is_pothole = m["time"] in anomalies
        db.execute("INSERT INTO data (time, lat, lng, value, is_pothole, sensor_name) VALUES (?, ?, ?, ?, ?, ?)",
            (m["time"], m["lat"], m["lng"], m["value"], is_pothole, sensor_name))
    
    db.commit()
    print "Success! {} data parsed!".format(sensor_name)
    return
