#!/usr/bin/python3

import sys

#sys.path.insert(0, '/var/www/flask-prod')
#sys.path.insert(1, '/var/www')
#sys.path.append('/usr/lib/python3.4/site-packages/requests')
sys.path.append('/var/www/flask-prod')

from webtool import app as application

#from werkzeug.debug import DebuggedApplication
#application = DebuggedApplication(app, True)

