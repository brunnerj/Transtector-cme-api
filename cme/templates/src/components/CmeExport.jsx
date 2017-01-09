/**
 * CmeExport.jsx
 * james.brunner@kaelus.com
 *
 * CME Export page component.  Acts as a simple data/viewer formatter to hold channel
 * data in a browser tab for the user to save, print, etc. 
 */
var React = require('react');


// loads the page's query string into an object, qs
var qs = (function(a) {
    if (a == "") return {};
    var b = {};
    for (var i = 0; i < a.length; ++i)
    {
        var p=a[i].split('=', 2);
        if (p.length == 1)
            b[p[0]] = "";
        else
            b[p[0]] = decodeURIComponent(p[1].replace(/\+/g, " "));
    }
    return b;
})(window.location.search.substr(1).split('&'));


var CmeExport = React.createClass({

	getInitialState: function () {
		return {
			ch: qs['c'],
			history: qs['h'],
			data: []
		};
	},
	
	componentDidMount: function() {
		alert('Hey, I am mounted!');
	},

	render: function() {

		return (
			<div>
				<div>
					Channel: {this.state.ch}
				</div>
				<div>
					History: {this.state.history}
				</div>
			</div>
		);
	}
});

module.exports = CmeExport;