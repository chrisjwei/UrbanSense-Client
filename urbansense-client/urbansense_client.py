import os
import time
from sqlite3 import dbapi2 as sqlite3

from flask import Flask, request, jsonify, g
from .exceptions import InvalidUsage
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
    INFLUX_PORT=8086
))

def get_influx_client():
    return InfluxDBClient(app.config['INFLUX_HOST'], app.config['INFLUX_PORT'], database='alpha')

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

@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.route('/')
def hello_world():
	return 'UrbanSense server ready to receive data...\n'

@app.route('/map')
def render_test_map():
    db = get_db()
    db.execute("SELECT * FROM test")
    result = db.fetchall()
    return render_template("index.html", data=result)

@app.route('/test')
def test_task():
    """Polls for 10 minutes of data every 10 minutes and selects the maximum
    value in that time period"""
    current_time = int(time.time())
    client = get_influx_client()
    results = client.query('''SELECT * FROM "ir" WHERE "time" <= %d AND "time" > %d''' % (current_time, current_time - 60*10))
    pts = list(results.get_points(measurement="ir"))
    m = max(pts, key=lambda x: x["value"])
    # insert max result into our sqlite database
    db = get_db()
    db.execute("INSERT INTO test (time, lat, lng, value) VALUES (?, ?, ?, ?)",
        (m["time"], m["lat"], m["lng"], m["value"]))
    db.commit()
    return "success!"
