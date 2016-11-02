#!/usr/bin/python3

from flask import Flask
import os
import requests
from flask import Flask, render_template, request
import urllib.request
import time
from time import sleep

app = Flask(__name__)

# Initialising variables to be used globally... yes, I know. Global vars are ugly... fml. Ill fix next time.
d = {'otimeleft': 0, # Number of second left until this action is taken
    'ctimeleft': 0,
    'otime': "", # Actual open time HH:MM
    'ctime': "",
    'state': "", # State of the door (open/close)
    'ip': "", # Coopener should tell us what its IP is
    'port': "", # Coopener should tell us what port its listening on
    'connstate': False, # Used to track connection status of Coopener to SmartHome
    'lastSeen': int(time.time()), # Number of seconds since epoch. Used to track heartbeats for connection
    'timeout': 30} # Number of seconds to wait for heartbeat before dropping connection

@app.route("/")
def index():
  global d
  if (int(time.time()) - d['lastSeen']) >= d['timeout']:
    d['connstate'] = False
    return render_template('index.html', connstate=d['connstate'])
  return render_template('index.html', connstate=d['connstate'], \
                        otimeleft=d['otimeleft'], ctimeleft=d['ctimeleft'], \
                        otime=d['otime'], ctime=d['ctime'], state=d['state'], \
                        ip=d['ip'], port=d['port'])

@app.route('/handshake')
def shake():
  ''' Handshake between Coopener and SmartHome srvr
        Coopener ---> SmartHome. Sends Coopener IP and shake=1. Expects response.
        SmartHome ---> Coopener. Responds "OK(2)". Expects response.
        Coopener ---> SmartHome. Sends shake=3. Expects response.
  '''
  global d
  if request.args.get('shake'):
    if request.args.get('shake') == "1": # Coopener is initiating handshake
      if request.args.get('ip'): d['ip'] = request.args.get('ip') # grab the ip sent from coopener
      if request.args.get('port'): d['port'] = request.args.get('port') # grab the port sent from coopener
      d['connstate'] = False # Even if connection was already established, tear it down and let Coopener start again
      return "OK(2)" 
    if request.args.get('shake') == "3": # Coopener is completing handshake process
      d['lastSeen'] = int(time.time()) # Number of seconds since epoch. This is when we last got a heartbeat
      d['connstate'] = True # Connection to Coopener is now established
      return "OK(4)"

@app.route('/heartbeat')
def beat():
  '''
    Every n seconds Coopener should send a heartbeat/keepalive for the established connection
    It will contain the current state of Coopener in it. Yes, its extra overhead... but its simpler.
    I will need to re-write this entire protocol one day as it is really ugly and way too rigid.
  '''
  global d
  if (d['connstate'] == True):
    d['lastSeen'] = int(time.time()) # Number of seconds since epoch. This is when we last got a heartbeat
    if request.args.get('otimeleft') and request.args.get('ctimeleft') and \
                      request.args.get('otime') and request.args.get('ctime'): # Only parse if all data is received
      d['otimeleft'] = int(request.args.get('otimeleft')) # Convert to integer the returned seconds
      d['ctimeleft'] = int(request.args.get('ctimeleft'))
      d['otime'] = request.args.get('otime')
      d['ctime'] = request.args.get('ctime')
      d['state'] = request.args.get('state')
    return "OK(HB)"
  else:
    return "No established connection found"

if __name__ == "__main__":
  #app.debug = True
  app.run(host='0.0.0.0')