# CME sensor/control channels API

from datetime import datetime, timezone
import subprocess, json

from . import router, request, path_parse, json_response, APIError, require_auth, Config

from ..common.Switch import switch
from .Models import ChannelManager, AlarmManager


HISTORY = ['live', 'daily', 'weekly', 'monthly', 'yearly']


def get_request_param(key):
	''' Searches the request args (i.e., query string of the request URL)
		for parameters named by key.  Parameters can have a couple of
		different types of values: boolean or comma-separated integers.
		
		Here are a few examples of how the URL's might look and the
		value that should be returned from this function:

		http:<blah-blah>/api/ch/0?reset=true&expand=false
			get_request_param('reset') = True
			get_request_param('expand') = []

		http:<blah-blah>/api/ch/0?test=0,1,2&warning=true
			get_request_param('test') = [0,1,2]
			get_request_param('warning') = True

		http:<blah-blah>/api/ch/0?expand=0
			get_request_param('expand') = [0]
	'''
	value = request.args.get(key, None)

	if not value:
		return []

	if value.lower() == 'true':
		return True

	try:
		return [int(i) for i in value.split(',')]
	
	except:
		return []


def status(ch_index=-1):
	''' Top-level CME status object

		Returns a single channel identified with integer ch_index
		or all channels if ch_index < 0 (the default).
	'''	


	ch_mgr = ChannelManager()


	# get list of available channels
	channels = ch_mgr.channels # [ 'ch0', ..., 'chN' ]

	# select all channels (ch_index < 0)
	if ch_index < 0:
		return { 'channels': [ ch_mgr.get_channel(ch) for ch in channels ] }

	# select specific channel 'chX'
	return ch_mgr.get_channel('ch' + str(ch_index))


# CME list of available channels
@router.route('/channels/')
@require_auth
def channels_list():
	return json_response({ 'channels': ChannelManager().channels })


# CME channels request - actual channel objects returned
@router.route('/ch/')
@require_auth
def channels():
	return json_response(status(-1))



# CME channel updates
# 	DELETE a channel will clear its RRD database history
# 	GET a complete channel or bits of it (name, description, error, controls, or sensors)
# 	POST updates to the name or description (or both at the same time)
#
# Supports optional query strings to specify channel history and alarms.
# History is attached in the 'data' attribute, and alarms are in the 'alarms'.
#
# h=[resolution], resolution can be one of 'live', 'daily', 'weekly', 'monthly', 'yearly'
# a=True | 1
# If no h or a parameter, then data and alarms attributes are not returned.
@router.route('/ch/<int:ch_index>', methods=['GET', 'POST', 'DELETE'])
@router.route('/ch/<int:ch_index>/name', methods=['GET', 'POST'])
@router.route('/ch/<int:ch_index>/description', methods=['GET', 'POST'])
@router.route('/ch/<int:ch_index>/recordAlarms', methods=['GET', 'POST'])
@router.route('/ch/<int:ch_index>/error')
@require_auth
def channel(ch_index):

	ch = status(ch_index)

	if not ch:
		raise APIError('Channel not found', 404)

	ch_mgr = ChannelManager()

	# parse out the item name (last element of request path)
	segments = path_parse(request.path)
	item = segments[-1]

	isFullChannel = item not in ['name', 'description', 'error', 'recordAlarms']

	if request.method == 'DELETE': 
		# clear any history in ch buffer
		ch.clear_history()

		# clear the channel's historic data
		ch_mgr.clear_channel_history(ch.id)

		return json_response({ ch.id: ch })


	if request.method == 'POST':
		# update name or description (or both) from POST data
		ch_update = request.get_json()
		ch.name = ch_update.get('name', ch.name)
		ch.description = ch_update.get('description', ch.description)
		ch.recordAlarms = ch_update.get('recordAlarms', ch.recordAlarms)

	else:
		# GET request - see if we need to read ch history
		# check query string for h(istory) = RESOLUTION 
		if isFullChannel:
			h = request.args.get('h')
			h = h.lower() if h else None

			s = request.args.get('s')
			try:
				s = int(s) if s else 1
			except:
				s = 1

			e = request.args.get('e')
			try:
				e = int(e) if e else 0
			except:
				e = 0

			if h in HISTORY:
				ch.load_history(h, s, e)
			else:
				ch.clear_history()

			a = request.args.get('a')
			a = a.lower() if a else None

			if a in ['true', '1']:
				ch.alarms = AlarmManager().load_ch_alarms(ch, )
			else:
				ch.alarms = None


	# return either full channel or the item requested
	if isFullChannel:
		return json_response({ ch.id: ch })

	return json_response({ ch.id: { item: ch.__dict__[item] }})



@router.route('/ch/<int:ch_index>/history/<history>', methods=['GET', 'DELETE'])
@require_auth
def channel_history(ch_index, history):
	ch = status(ch_index)

	if not ch:
		raise APIError('Channel not found', 404)

	# TODO: look at channel RRA config to see if history is okay
	h = history.lower()
	if h not in HISTORY:
		raise APIError('Channel data {0} history not collected'.format(h), 400)

	ch_mgr = ChannelManager()

	if request.method == 'DELETE':
		ch.clear_history()
		ch_mgr.clear_channel_history(ch.id)

	else:
		s = request.args.get('s')
		try:
			s = int(s) if s else 1
		except:
			s = 1

		e = request.args.get('e')
		try:
			e = int(e) if e else 0
		except:
			e = 0

		ch.load_history(h, s, e)
	
	return json_response({ ch.id + '.data': ch.data })



# CME channel configuration (used in hardware calibration)
@router.route('/ch/<int:ch_index>/config', methods=['GET', 'POST'])
@require_auth
def ch_config(ch_index):

	ch_mgr = ChannelManager()

	# retrieve the desired channel configuration
	ch = ch_mgr.get_channel('ch' + str(ch_index))

	if not ch:
		raise APIError('Channel not found', 404)

	if request.method == 'POST':
		response = ch.set_hw_config(request.get_json())

	else:
		response = ch.get_hw_config()

	return json_response(response)



@router.route('/ch/<int:ch_index>/alarms/', methods=['GET', 'DELETE'])
@require_auth
def ch_alarms(ch_index):
	# retrieve the desired channel configuration

	ch_mgr = ChannelManager()

	ch = ch_mgr.get_channel('ch' + str(ch_index))

	if not ch:
		raise APIError('Channel not found', 404)

	alarm_mgr = AlarmManager()

	if request.method == 'DELETE':
		alarm_mgr.clear_ch_alarms(ch)

	else:
		s = request.args.get('s')
		try:
			s = int(s) if s else 1
		except:
			s = 1

		e = request.args.get('e')
		try:
			e = int(e) if e else 0
		except:
			e = 0

		alarm_mgr.load_ch_alarms(ch, s, e)

	return json_response({ ch.id + '.alarms': ch.alarms })


# CME channel sensors request
@router.route('/ch/<int:ch_index>/sensors/')
@require_auth
def sensors(ch_index):
	ch = status(ch_index)

	if not ch:
		raise APIError('Channel not found', 404)

	return json_response({ ch.id + ':sensors': ch.sensors })



# GET/POST sensors on specified channel individually
@router.route('/ch/<int:ch_index>/sensors/<int:s_index>')
@router.route('/ch/<int:ch_index>/sensors/<int:s_index>/name', methods=['GET', 'POST'])
@require_auth
def sensor(ch_index, s_index):
	ch = status(ch_index)

	if not ch:
		raise APIError('Channel not found', 404)


	sensor = ch.sensors.get('s' + str(s_index), None)

	if not sensor:
		raise APIError('Sensor not found', 404)

	# parse out the item (last key in request)
	# it will be either the sensor index or a sensor attribute name
	segments = path_parse(request.path)
	item = segments[-1].lower()

	isFullSensor = item not in ['name']

	if isFullSensor:
		return json_response({ ch.id + ':' + sensor.id : sensor })

	# update from POST data (item will only match POST method names)
	if request.method == 'POST':
		update = request.get_json()
		sensor.name = update.get('name', sensor.name)

	# return item attribute
	return json_response({ ch.id + ':' + sensor.id: { 'name': sensor.name }})


# GET sensor history
@router.route('/ch/<int:ch_index>/sensors/<int:s_index>/history/<history>')
@require_auth
def sensor_history(ch_index, s_index, history):
	ch = status(ch_index)

	if not ch:
		raise APIError('Channel not found', 404)

	sensor = ch.sensors.get('s' + str(s_index), None)

	if not sensor:
		raise APIError('Sensor not found', 404)

	# TODO: look at channel RRA config to see if history is okay
	h = history.lower()
	if h not in HISTORY:
		raise APIError('Channel data {0} history not collected'.format(h), 400)


	s = request.args.get('s')
	try:
		s = int(s) if s else 1
	except:
		s = 1

	e = request.args.get('e')
	try:
		e = int(e) if e else 0
	except:
		e = 0

	ch.load_history(h, s, e)

	# ch.data has all sensors, so pluck indicated sensor data
	try:
		sensor_index = [ ds.split('_')[0] for ds in  ch.data[1] ].index(sensor.id) # [ "s0_VAC_Vrms", "s1_CAC_Arms", ...] ==> [ 's0', 's1', ...]
	
	except:
		raise APIError('Sensor {0} history not found'.format(sensor.id), 404)


	data = []
	data.append(ch.data[0]) # time series range/step
	data.append([ ch.data[1][sensor_index] ]) # sensor DS name
	data.append([ v[sensor_index] for v in ch.data[2] ]) # data (live or AVERAGE)

	if h != 'live':
		data.append([ v[sensor_index] for v in ch.data[3] ]) # data (MIN if not "live")
		data.append([ v[sensor_index] for v in ch.data[4] ]) # data (MAX if not "live")

	return json_response({ ch.id + ':' + sensor.id + '.data': data })


# CME sensor thresholds request
# GET - list current thresholds
# DELETE - remove all thresholds
# POST - add a new threshold: { value, direction, classification }
@router.route('/ch/<int:ch_index>/sensors/<int:s_index>/thresholds/', methods=['GET', 'POST', 'DELETE'])
@require_auth
def thresholds(ch_index, s_index):
	ch = status(ch_index)

	if not ch:
		raise APIError('Channel not found', 404)

	s = ch.sensors.get('s' + str(s_index), None)

	if not s:
		raise APIError('Sensor not found', 404)

	if request.method == 'GET':
		return json_response({ ch.id + ':' + s.id + ':thresholds': s.thresholds })

	if request.method == 'DELETE':
		s.removeAllThresholds()
		return json_response({ ch.id + ':' + s.id + ':thresholds': s.thresholds })

	# else POST - add new threshold
	#try:
	th = s.addThreshold(request.get_json())
	return json_response(th, 201)
	#except:
	#	raise APIError('Bad request', 400)



# GET/POST thresholds on specified channel/sensor individually
@router.route('/ch/<int:ch_index>/sensors/<int:s_index>/thresholds/<th_id>', methods=['GET', 'POST', 'DELETE'])
@require_auth
def threshold(ch_index, s_index, th_id):
	ch = status(ch_index)

	if not ch:
		raise APIError('Channel not found', 404)

	s = ch.sensors.get('s' + str(s_index), None)

	if not s:
		raise APIError('Sensor not found', 404)

	th = next((th for th in s.thresholds if th.id == th_id), None)

	if not th:
		raise APIError('Threshold not found', 404)

	for case in switch(request.method):
		if case('POST'):
			s.modifyThreshold(th, request.get_json())
			return json_response({ ch.id + ':' + s.id + ':' + th.id: th })

		if case('DELETE'): 
			# DELETE the identified threshold
			s.removeThreshold(th)
			return json_response(th)

		if case():
			# GET is default
			return json_response({ ch.id + ':' + s.id + ':' + th.id: th })

