# login API session handling
# Provide access to API session token (cookie)
# given matching username and passhash

from . import settings, router, request, require_auth, json_response
from .status import timestamp

@router.route('/login')
def login():
	u = request.args.get('u')
	p = request.args.get('p')

	if u.lower() != settings['__username'].lower():
		return json_response([ 'Login failed - unknown user.' ])

	if p != settings['__passhash']:
		return json_response([ 'Login failed - invalid password.' ]),

	# else we've got valid login send response and force set session
	return json_response({ 'timestamp': timestamp() }, True)

# CME root (index) request
@router.route('/')
@require_auth
def index():
	return json_response({ 'timestamp': timestamp() })