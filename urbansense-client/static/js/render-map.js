

const API_TOKEN = 'pk.eyJ1IjoibmF5YWtrYXlhayIsImEiOiJjajI5czFjd3AwMDAyMzhsdno5dDBwYXVqIn0.TGWOxkZ1uW4wYHh35_AY8g';
const MAPBOX_URL = "https://api.mapbox.com/styles/v1/mapbox/dark-v9/tiles/256/{z}/{x}/{y}?access_token={token}"

const INIT_COORDINATES = [40.444623, -79.942986]

function init_map() {
	L.mapbox.accessToken = API_TOKEN

	var darkLayer = L.tileLayer(MAPBOX_URL, {token: API_TOKEN});

	var map = L.map('map-one',{
		center: INIT_COORDINATES,
		zoom: 14,
		layers: [darkLayer]
	})
	map.setView(INIT_COORDINATES, 14);

	return map
}


function generate_map(points) {
	var map = init_map()
	var accel_heat = L.heatLayer(points["accel"], {radius: 25, blur: 30}).addTo(map);

	var ir_heat = L.heatLayer(points["ir"], {radius: 25, blur: 30}).addTo(map);

	var baseLayers = {
		"Accelerometer": accel_heat,
		"IR": ir_heat
	}

	L.control.layers(baseLayers, [],{
		collapsed: false
	}).addTo(map);
	map.addLayer(accel_heat)
	map.removeLayer(ir_heat)

}




