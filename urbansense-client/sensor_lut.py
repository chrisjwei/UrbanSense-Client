from flask import Flask, request, jsonify


SENSOR_MAPPINGS = {
	0: "ir",
	1: "accel"
}

TAG_MAPPINGS = {
	"accel": {
		0: "x",	
		1: "y",
		2: "z"
	},
	"ir": {
		0: "0",
		1: "1",
		2: "2"
	}
}

def get_names(sensor_id, tag_id):
	sensor_name = SENSOR_MAPPINGS[int(sensor_id)]
	tag_name = TAG_MAPPINGS[sensor_name][int(tag_id)]

	return sensor_name, tag_name
