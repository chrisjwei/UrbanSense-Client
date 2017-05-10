from luminol import anomaly_detector
from luminol.modules.time_series import TimeSeries


def real_anomaly_detection(samples, smoothing_factor):

	ts = TimeSeries(samples)
	detector = anomaly_detector.AnomalyDetector(ts, algorithm_name="derivative_detector", algorithm_params={
      'smoothing_factor': smoothing_factor # smoothing factor used to compute exponential moving averages
	})
	anomalies = detector.get_anomalies()

	anomaly_times = []
	for a in anomalies:
		start = a.get_time_window()[0]	
		end = a.get_time_window()[1]
		while (start <= end):
			anomaly_times.append(start)
			start += 1

	print anomaly_times
	return anomaly_times

def find_anomalies(pts, smoothing_factor):

	samples = {}
	for p in pts:
		samples[p["time"]] = p["value"]

	return real_anomaly_detection(samples, smoothing_factor)

