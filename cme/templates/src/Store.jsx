/*
 * Store.jsx
 * james.brunner@kaelus.com
 *
 * Repository for the Cme application model.
*/
'use strict';
var DEBUG = true;
function debug(/* arguments */) {
	if (!DEBUG) return;
	console.log.apply(console, arguments);
}

var AppDispatcher = require('./AppDispatcher');
var Constants = require('./Constants');
var EventEmitter = require('events').EventEmitter;

var assign = require('object-assign'); // ES6 polyfill

var CHANGE_EVENT = 'change';

var _device = {};
var _config = {};
var _errors = [];
var _isLoggedIn = false;
var _isSubmitting = false;
var _ui_panel = 'home';

var Store = assign({}, EventEmitter.prototype, {

	getState: function() {
		return {
			device: _device, // { modelNumber: <string>, serialNumber: <string>, firmware: <string> }
			config: _config, // { <cme_config> }
			errors: _errors, // [ <string> ]

			// generally UI-specific states follow:

			isLoggedIn: _isLoggedIn, // set via CmeAPI.session(callback(<bool>)); true if valid session
			isSubmitting: _isSubmitting, // Actions that make server requests set this true before request
			ui_panel: _ui_panel // what's displayed in the main page body
		}
	},

	emitChange: function() {

		this.emit(CHANGE_EVENT);
	},

	addChangeListener: function(callback) {

		this.on(CHANGE_EVENT, callback);
	},

	removeChangeListener: function(callback) {

		this.removeListener(CHANGE_EVENT, callback);
	},

	dispatcherIndex: AppDispatcher.register(function(action) {

		switch(action.actionType) {

			case Constants.REQUEST: // a request has been submitted to server
				_isSubmitting = true;
				break;

			case Constants.DEVICE: // a device object has been replied
				_device = action.data;
				break;

			case Constants.SESSION: // a session object has been replied
				// set the _isLoggedIn state (login/logout actions update the session)
				_isLoggedIn = action.data;
				break;

			case Constants.ERROR:
				_errors.push(action.data);
				break;

			case Constants.CLEAR_ERRORS:
				_errors = [];
				break;

			case Constants.CONFIG:
				// item key name:
				var item = Object.keys(action.data)[0];

				if (item === 'config') {

					_config = action.data[item];

				} else if (_config[item] !== undefined) {

					_config[item] = action.data[item] || {};

				} else {

					for (var group in _config) {

						if (_config[group][item] !== undefined) {
							_config[group][item] = (action.data[item] !== null || action.data[item] !== undefined) 
								? action.data[item]
								: '';
							break;
						}

					}

				}
				break;

			case Constants.UI_PANEL:

				_ui_panel = action.data.toLowerCase();
				break;

			default: // unknown action
				// ignore
		}

		// explicitly check here for REQUEST action
		// to reset the _isSubmitting bool
		if (action.actionType !== Constants.REQUEST)
			_isSubmitting = false;

		Store.emitChange(); // notify store changes

		return true; // No errors. Needed by promise in Dispatcher.
	})
});

module.exports = Store;
