/**
 * TextInput.js
 * james.brunner@kaelus.com
 *
 * Generic text input field wrapper.
 */
var React = require('react');

var classNames = require('classnames');

var TextInput = React.createClass({

	propTypes: {
		id: React.PropTypes.string.isRequired
	},

	render: function() {
		var id = this.props.id,
			value = this.props.value,
			placeholder = this.props.placeholder || id.charAt(0).toUpperCase() + id.slice(1),
			onChange = this.props.onChange,
			onBlur = this.props.onBlur,
			readonly = !(onChange || onBlur),
			cn = classNames('textinput', this.props.className);

		return (
			<div className={cn}>
				<label htmlFor={id}>{placeholder}</label>
				<input
					type="text"
					name={id}
					id={id}
					placeholder={placeholder}
					value={value}
					disabled={this.props.disabled}
					onChange={onChange}
					onBlur={onBlur}
					readOnly={readonly}
				/>
			</div>
		);
	}
});

module.exports = TextInput;
