import os
from setuptools import setup

# version (i.e., cme.firmware) is stored in the VERSION file in package root
with open(os.path.join(os.getcwd(), 'VERSION')) as f:
	version = f.readline().strip()

setup (
	name					= "cmeapi",
	version					= version,
	description 			= "CME Application Programming Interface (API)",
	packages				= ['cmeapi', 'cmeapi.api_routes', 'cmeapi.common'],
	include_package_data	= True,
	zip_safe				= False,
	install_requires		= ["CherryPy", "Paste", "Flask", "rrdtool==0.1.4" ],
	entry_points			= {'console_scripts': ['cmeapi = cmeapi.__main__:main'] }
)

