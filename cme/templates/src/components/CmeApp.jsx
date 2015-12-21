/**
 * CmeApp.jsx
 * james.brunner@kaelus.com
 *
 * Core monitoring engine top-level component.
 * This component operates as a "Controller-View".  It listens for changes
 * in the CmeStore and passes the new data to its children.
 */
var React = require('react');

var Header = require('./Header');
var Login = require('./Login');
var ConfigPanel = require('./ConfigPanel');
var HomePanel = require('./HomePanel');
var ErrorPanel = require('./ErrorPanel');

var Actions = require('../Actions');
var Constants = require('../Constants');
var Store = require('../Store');

var CmeApp = React.createClass({

	getInitialState: function () {
		return Store.getState();
	},

	componentDidMount: function() {
		Store.addChangeListener(this._onChange);
	},

	componentWillUnmount: function() {
		Store.removeChangeListener(this._onChange);
	},

	render: function() {

		return (
			<div>
				<Header device={this.state.device}
						isLoggedIn={this.state.isLoggedIn} />

				{!this.state.isLoggedIn

					? <Login errors={this.state.errors} isSubmitting={this.state.isSubmitting} />
					
					: <div id="console">

						{this.state.isConfigVisible

							? <ConfigPanel config={this.state.config} />

							: <HomePanel status={this.state.status}
										 clock={this.state.config.clock} />
						}

						<ErrorPanel errors={this.state.errors} />

					</div>
				}

				<div id="test-buttons">
					<button onClick={this._testError}
							disabled={this.state.errors.length > 0}>Test Error</button>

					<button onClick={this._pausePolling}
							disabled={this.state.errors.length > 0}>Pause Polling</button>

					<button onClick={this._unpausePolling}
							disabled={this.state.errors.length > 0}>UnPause Polling</button>
				</div>
				
			</div>
		);
	},

	_onChange: function() {
		this.setState(Store.getState());
	},

	_testError: function() {
		Actions.injectError('This is a test');
	},

	_pausePolling: function() {
		Actions.poll(Constants.PAUSE);
	},

	_unpausePolling: function() {
		Actions.poll(Constants.UNPAUSE);
	}
});

module.exports = CmeApp;