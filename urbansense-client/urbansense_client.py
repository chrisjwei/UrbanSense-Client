import os
import time
from celery import Celery
import celery
from sqlite3 import dbapi2 as sqlite3

from flask import Flask, request, jsonify, g, render_template, url_for
from .exceptions import InvalidUsage
from .tasks import make_celery
from influxdb import InfluxDBClient

app = Flask(__name__)
# Load default config and override config from an environment variable
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'urbansense.db'),
    DEBUG=True,
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default',
    INFLUX_HOST='localhost',
    INFLUX_PORT=8086,
    INFLUX_DB='urbansense-data',
    CELERY_BROKER_URL='redis://localhost:6379/0',
    CELERY_RESULT_BACKEND='redis://localhost:6379/0',
    CELERYBEAT_SCHEDULE={
        'process-ir-every-30-secs': {
            'task': 'urbansense-client.urbansense_client.process_ir',
            'schedule': 30.0,
            'args': ()
        },
        'process-accel-every-30-secs': {
            'task': 'urbansense-client.urbansense_client.process_accel',
            'schedule': 30.0,
            'args': ()
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

@app.route('/')
def hello_world():
	return 'UrbanSense server ready to receive data...\n'

@app.route('/map')
def render_test_map():
    db = get_db()
    c = db.cursor()
    rows = c.execute("SELECT * FROM test WHERE lat != 0 AND lng != 0").fetchall()
    
    data = {
        "accel": rows
    }
    return render_template("index.html", data=data)

@app.route('/test')
def test_task():
    """Polls for 10 minutes of data every 10 minutes and selects the maximum
    value in that time period"""
    current_time = int(time.time())
    client = get_influx_client()
    results = client.query('''SELECT * FROM "ir" WHERE "time" <= %d AND "time" > %d''' % (current_time, current_time - 30))
    pts = list(results.get_points(measurement="ir"))
    if len(pts) == 0:
        return "No new values to be processed!"
    m = max(pts, key=lambda x: x["value"])
    # insert max result into our sqlite database
    db = get_db()
    db.execute("INSERT INTO test (time, lat, lng, value) VALUES (?, ?, ?, ?)",
        (m["time"], m["lat"], m["lng"], m["value"]))
    db.commit()
    return "success!"


# --------------------------------- TASKS --------------------------------------

@celery.task()
def process_accel():
    """Polls for 10 minutes of data every 10 minutes and selects the maximum
    value in that time period"""
    current_time = int(time.time())
    client = get_influx_client()
    results = client.query(
        'SELECT * FROM "accel" WHERE tag_name=\'z\' and "time" <= %d AND "time" > %d' % (current_time, current_time - 30)
    )

    pts = list(results.get_points(measurement="accel"))
    if len(pts) == 0:
        print "No new values to be processed!"
        return
    db = get_db()
    for m in pts:
        is_pothole = abs(m["value"]) > 1100 or abs(m["value"]) < 890
        db.execute("INSERT INTO accel (time, lat, lng, value, is_pothole) VALUES (?, ?, ?, ?, ?)",
            (m["time"], m["lat"], m["lng"], m["value"], is_pothole))
    
    db.commit()
    print "success!"
    return

@celery.task()
def process_ir():
    """Polls for 10 minutes of data every 10 minutes and selects the maximum
    value in that time period"""
    current_time = int(time.time())
    client = get_influx_client()
    results = client.query('''SELECT * FROM "ir" WHERE "time" <= %d AND "time" > %d''' % (current_time, current_time - 30))
    
    pts = list(results.get_points(measurement="accel"))
    if len(pts) == 0:
        print "No new values to be processed!"
        return
    db = get_db()
    for m in pts:
        is_pothole = abs(m["value"]) > 1100 or abs(m["value"]) < 890
        db.execute("INSERT INTO ir (time, lat, lng, value, is_pothole) VALUES (?, ?, ?, ?, ?)",
            (m["time"], m["lat"], m["lng"], m["value"], is_pothole))
    
    db.commit()
    print "success!"
    return

