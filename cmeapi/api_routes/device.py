# api/device routes

import os, shutil, glob, threading, logging, fnmatch, json, tempfile

import urllib.request
from xml.dom.minidom import parseString
import xml.dom.minidom

from . import (Config, router, settings, request, path_parse, secure_filename,
	allowed_file, json_response, APIError, json_filter, require_auth)

from ..common.LockedOpen import LockedOpen
from ..common.Reboot import restart

@router.route('/device/')
@router.route('/device/cme/')
@router.route('/device/cme/modelNumber')
@router.route('/device/cme/serialNumber')
@router.route('/device/cme/firmware')
@router.route('/device/cme/dateCode')
@router.route('/device/host/')
@router.route('/device/host/modelNumber')
@router.route('/device/host/serialNumber')
@router.route('/device/host/dateCode')
@router.route('/device/recovery')
def device_read_only_settings():
	''' Read-only device settings - NOT password protected.
		These are saved in settings, but under the "__device" key.
	'''
	# parse out the setting name (last element of request path)
	segments = path_parse(request.path)
	item = segments[-1]

	# get visible device parameters
	device = json_filter(settings['__device'].items())

	# add 'recovery' flag depends on how Config.py
	# loaded (i.e., the presence of a recovery flag file)
	device['recovery'] = Config.RECOVERY.RECOVERY_MODE

	if item == 'device':
		# request all device parameters
		res = device
	elif item == 'cme' or item == 'host':
		# else just a specific item type
		res = device[item]
	else:
		res = device[segments[-2]][item]

	return json_response({ item: res })

@router.route('/device/versions/')
def device_version():
	# Cme-init is responsible for maintaining the /data/VERSIONS file

	# give Recovery Mode, App Mode versions (if available)
	versions = {
		'Cme-init': ['--', '--' ],
		'Cme-api': ['--', '--'],
		'Cme-hw': ['--', '--'],
		'Cme-web': ['--', '--']
	}

	try:
		with open(os.path.join(Config.PATHS.USERDATA, 'VERSIONS')) as f:
			versions = json.load(f)
	except Exception as e:
		pass

	return json_response({ 'versions': versions })



@router.route('/device/', methods=['POST'])
@require_auth
def device_write():
	''' Device CME data can be written the first time only (during production).
		Device data is stored in 'device.json' file in the /data volume.  Once
		created, the API layer will prevent further updates.
	'''
	
	# updating device only works if NOT recovery mode
	if Config.RECOVERY.RECOVERY_MODE:
		raise APIError('Calibration not supported in recovery mode', 400)

	currentDevice = settings['__device']
	currentCme = currentDevice['cme']
	currentHost = currentDevice['host']
	unlocked = currentCme.get('unlocked', False)

	# this is from the body of the request
	newDevice = request.get_json()['device']

	if not newDevice:
		raise APIError('Invalid data', 400)

	requestedCme = newDevice.get('cme', None)
	requestedHost = newDevice.get('host', None)

	# Once created, the cme device data becomes read-only
	# and all future POSTS must set cme = None.  Alert
	# API users who try to violate this.
	if requestedCme is not None and not unlocked:
		raise APIError('CME device data is read-only', 400)

	newCme = objectAssign(requestedCme, currentCme)
	newHost = objectAssign(requestedHost, currentHost)

	# Rewrite the firmware and productName from the
	# currentCme - clients aren't allowed to update these.
	newCme['firmware'] = Config.INFO.VERSION
	newCme['productName'] = currentCme['productName']

	# We can now update the Config.INFO.DEVICE w/new Cme and Host data
	Config.INFO.DEVICE = {
		'cme': newCme,
		'host': newHost
	}

	# save device data to disk
	devicefile = os.path.join(Config.PATHS.USERDATA, Config.PATHS.DEVICE_FILE)
	with LockedOpen(devicefile, 'a') as f:
		with tempfile.NamedTemporaryFile('w', dir=os.path.dirname(Config.PATHS.USERDATA), delete=False) as tf:
			json.dump(Config.INFO.DEVICE, tf, indent="\t")
			tempname = tf.name

		shutil.move(tempname, devicefile)

	# Finally, we need to update __device key held in the settings.
	settings['__device'] = Config.INFO.DEVICE

	# return unfiltered device data
	device = settings['__device']

	# return updated device as stored in settings
	return json_response(device)


@router.route('/device/updates', methods=['GET', 'DELETE', 'PUT', 'POST'])
@require_auth
def device_updates():
	''' Firmware image update handling.  Works with HTTP verbs to act upon
		and/or return the available software updates and update status.

		GET: returns result object with current updates status:
	     	updates: {
				pending: [ < image filenames ready for update > ]
				usb: [ < image filenames found on usb storage > ],
				web: [ < image urls found on web site > ],
				uploads: [ < image filenames found in uploads folder > ]
	     	}

	     DELETE: removes a pending update (NOP if no pending update)

	     POST: uploads a update image file which may overwrite current uploaded images

	     PUT: move the indentified update to pending status (move file into pending update location)
	'''

	# result object
	result = { 
		'pending': [],  
		# Cme software image files can be placed in a special location to make them 'pending' updates.
		# The update location is checked after every Cme restart, and if a valid image is found it
		# will be used.

		'usb': [],
		# Software images may be placed on external (USB) drive.  Any matching Cme images found
		# will have their base filenames listed in the 'usb' item list.

		'web': [],
		# Software images can be provided by our company web site.  We'll list available Cme
		# image base filenames in the 'web' item list.

		'uploads': []
		# Finally, users may upload Cme software images they might have on their client.  Only
		# one software image at a time may be uploaded, so uploads overwrite previous uploads
		# of the same filename.  The 'uploads' result will list all uploaded files.
	}

	# read configurable items into local variables
	update_dir = Config.PATHS.UPDATE
	upload_dir = Config.PATHS.UPLOADS
	usb_dir = Config.PATHS.USB
	update_glob = Config.UPDATES.UPDATE_GLOB
	pub_url = Config.UPDATES.PUBLIC_UPDATES_URL

	logger = logging.getLogger(__name__)

	# find pending updates for DELETE
	pending_files = glob.glob(os.path.join(update_dir, update_glob))
	
	if request.method == 'DELETE':
		for file in pending_files:
			os.remove(file)
			logger.info("Update `{0}` was removed.".format(os.path.basename(file)))

	
	# from USB drive
	usb_files = glob.glob(os.path.join(usb_dir, update_glob))
	result['usb'] = [ os.path.basename(p) for p in usb_files ]

	# from web (our distribution URL)
	# TODO: get official web repo for Cme updates set up
	for url in pub_url:
		try:
			with urllib.request.urlopen(url) as response:
				web_listing_raw = response.read()

			web_listing_xml = xml.dom.minidom.parseString(web_listing_raw)
			ListBucketResult = web_listing_xml.documentElement

			# Get all the items in the S3 bucket
			items = ListBucketResult.getElementsByTagName('Contents')

			# Now filter for Cme items - these will have a Key property
			# that starts with 'Cme/' and the top-level Cme 'folder' will
			# just have Key = 'Cme/', so it can also be discarded.
			for item in items:
				key = item.getElementsByTagName('Key')[0].childNodes[0].data
				if key.startswith('Cme/') and key != 'Cme/' and fnmatch.fnmatch(key.split('/')[1], update_glob):
					result['web'].append(key.split('/')[1])
		except:
			logger.error("Error listing updates from web {0}".format(url))


	# are we handling an upload (POST)?
	if request.method == 'POST':

		# handle upload new firmware
		file = request.files['files[]']

		if file and allowed_file(file.filename):
			
			filename = secure_filename(file.filename)
			path = os.path.join(upload_dir, filename)
			file.save(path)
			logger.info("File uploaded: {0}".format(os.path.basename(path)))

		else:
			logger.error("File upload failed: {0}".format(file.filename))


	# finally, allow PUT to install an image to update folder
	error = False
	if request.method == 'PUT':
		source = request.get_json()['source']
		name = request.get_json()['name']

		
		# just copy USB source images
		if source.lower() == 'usb':
			src = os.path.join(usb_dir, name)
			if os.path.isfile(src):
				shutil.copy2(src, update_dir)
			else:
				error = True

		
		# copy web updates
		if source.lower() == 'web':
			for url in pub_url:
				try:
					# Download the file from `url` and save it locally under update_dir:
					with urllib.request.urlopen(url + 'Cme/' + name) as src, open(os.path.join(update_dir, name), 'wb') as dst:
					    shutil.copyfileobj(src, dst)
				except:
					error = True


		# move uploaded updates
		if source.lower() == 'upload':
			src = os.path.join(upload_dir, name)
			if os.path.isfile(src):
				shutil.move(src, update_dir)
			else:
				error = True

		if error:
			logger.error("Failed to install {0}::{1}".format(source, name))
		else:
			logger.info("Update installed: {0}::{1}".format(source, name))


	# refresh the uploads listing after installs (PUT) because
	# any uploaded files are moved (not copied) on install
	result['uploads'] = [ os.path.basename(p) for p in glob.glob(os.path.join(upload_dir, update_glob)) ]

	# refresh pending updates - may have been DELETED or PUT
	result['pending'] = [ os.path.basename(p) for p in glob.glob(os.path.join(update_dir, update_glob)) ]

	return json_response({ 'updates': result })


@router.route('/device/restart', methods=['GET'])
@require_auth
def device_restart():
	'''
	Triggers a device reboot with some optional configuration parameters
	sent along with the query string as:

		recovery_mode - this will ignore pending updates and reboot the CME
			into recovery mode

		factory_reset - this will remove the current settings.json file which
			essentially resets the CME configuration to factory defaults

		power_off - halt the system by removing power (after a short delay)

		If not recovery_mode, then any pending updates will be installed
		and attempted to use after the reboot.
	'''
	recovery_mode = request.args.get('recovery_mode', 'false').lower() in ['true', '1']
	factory_reset = request.args.get('factory_reset', 'false').lower() in ['true', '1']
	power_off = request.args.get('power_off', 'false').lower() in ['true', '1']

	logger = logging.getLogger(__name__)
	t = threading.Thread(target=restart, args=(power_off, recovery_mode, factory_reset, logger))
	t.setDaemon(True)
	t.start()

	# Return nothing (but status = 200) to let 'em know we're resetting
	return json_response(None)



# DEBUGGING
# Use this method to debug file uploads
@router.route('/device/up', methods=['GET', 'POST'])
@require_auth
def upload_file():
	if request.method == 'POST':
		file = request.files['file']
		if file and allowed_file(file.filename):
			filename = secure_filename(file.filename)

			p = os.path.join(Config.PATHS.UPLOADS, filename)

			print ("Saved upload to `", p, "`")
			file.save(p)

			return json_response({ 'update': filename })

	# on GET just return simple form for uploading a file
	return'''
	<!doctype html>
	<title>Upload new File</title>
	<h1>Upload new File</h1>
	<form action="" method=post enctype=multipart/form-data>
	  <p><input type=file name=file>
		 <input type=submit value=Upload>
	</form>'''
# END DEBUGGING


def objectAssign(reqObj, defObj):
	''' Creates a new empty object and for each key in keys pulls associated
		value from reqObj.  Uses default value from defObj (or None) if key
		is not found in reqObj (or defObj)
	'''
	if reqObj is None:
		return defObj
		
	obj = {}

	for k in defObj.keys():
		obj.setdefault(k, reqObj.get(k, defObj.get(k)))

	return obj

