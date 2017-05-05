import pandas
import random
import numpy
import time
from influxdb import InfluxDBClient
from luminol import anomaly_detector
from luminol.modules.time_series import TimeSeries


def get_influx_client():
    return InfluxDBClient("localhost", 8086, database="alpha")

def extract_influx_data():
	client = get_influx_client()
	results = client.query(
	    'SELECT * FROM "accel" WHERE tag_name=\'z\''
	)
	pts = list(results.get_points(measurement="accel"))

	data = [m["value"] for m in pts]
	return data


def naive_anomaly_detection(samples):
	rolling_sample = samples.rolling(window=10, min_periods=5, center=True)

	moving_avg = rolling_sample.mean()

	print list(moving_avg)

	moving_std = rolling_sample.std()

	#print list(moving_std)

	results = []
	for i, s in samples.iteritems():
		if moving_avg[i]:
			diff = abs(moving_avg[i] - s)
			if diff > moving_std[i]:
				results.append((s,1))
				continue

		results.append((s,0))


	print "Results...."
	print results


def real_anomaly_detection(samples):

	now = time.time()
	ts = {}
	for s in samples:
		ts[now] = s
		time.sleep(0.01)
		now += 1

	ts = TimeSeries(ts)
	print ts
	detector = anomaly_detector.AnomalyDetector(ts, algorithm_name="derivative_detector", algorithm_params={
      'smoothing_factor': 0.2 # smoothing factor used to compute exponential moving averages
	})
	anomalies = detector.get_anomalies()

	for a in anomalies:
		window = a.get_time_window()
		print "Time: {}, Value: {}, Score: {}".format(window[0], ts[window[0]], a.anomaly_score)	
		print "Time: {}, Value: {}, Score: {}".format(window[1], ts[window[1]], a.anomaly_score)
		print "----"



a = [10, 500, 600]
p = [0.9, 0.05, 0.05]
samples = numpy.random.choice(a, p=p, size=100)
samples = pandas.Series([random.randint(0,x) for x in samples])

samples = extract_influx_data()

#naive_anomaly_detection(samples)
real_anomaly_detection(samples)

