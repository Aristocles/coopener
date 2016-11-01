#!/usr/bin/python3


from flask import Flask
import os
import requests
from flask import Flask, render_template, request
import urllib.request
import time
from time import sleep
#import threading # performing multiple tasks at the same time
#from queue import Queue # " "

print (requests.__file__)
print (urllib.request.__file__)

app = Flask(__name__)

# Initialising variables to be used globally
# Not the best way of doing this, but I am trying to keep it super simple
# as I learn how to use Flask. I promise next time it'll be better.
otime = 0
ctime = 0
state = "init"
ip = "none" # Coopener should tell us what its IP is
port = "none" # Coopener should tell us what port its listening on
connstate = False # Used to track connection status of Coopener to SmartHome
lastSeen = int(time.time()) # Number of seconds since epoch. Used to track heartbeats for connection
timeout = 30 # Number of seconds to wait for heartbeat before dropping connection


@app.route("/")
def index():
  global timeout
  global lastSeen
  global connstate
  #if connstate == True: # Coopener is connected, display information
  if (int(time.time()) - lastSeen) >= timeout:
    connstate = False
    return render_template('index.html', connstate=connstate)
  print("render port is: " + port)
  print("render IP is: "+ ip)
  return render_template('index.html', connstate=connstate, otime=otime, ctime=ctime, state=state, ip=ip, port=port)
  #return "Hello World! - Love from SmartHome"



@app.route('/handshake')
def shake():
  '''
    Handshake between Coopener and Smarthome srvr
    3-way handshake, initiated by Coopener.
      Coopener ---> SmartHome. Sends Coopener IP and shake=1
      SmartHome ---> Coopener. Responds "OK(2)"
      Coopener ---> SmartHome. Sends shake=3. state=x, ctime=y, otime=z
    Where state is whether door is currently open or close. otime is how many seconds to open door (0 is already open)
    ctime is how many seconds to close door (0 is already closed)

  '''
  global otime
  global ctime
  global state
  global ip
  global port
  global connstate
  global lastSeen
  if request.args.get('shake'):
    if request.args.get('shake') == "1": # Coopener is initiating handshake
      if request.args.get('ip'): ip = request.args.get('ip') # grab the ip sent from coopener
      if request.args.get('port'): port = request.args.get('port') # grab the port sent from coopener
      print("port is: " + port)
      print("IP is: " + ip)
      connstate = False # Even if connection was already established, tear it down and let Coopener start again
      return "OK(2)" 
    if request.args.get('shake') == "3": # Initial contact made, Coopener is now sending its info
      if request.args.get('otime'): # Get door open time (second remaining)
        otime = request.args.get('otime')
        otime = int(otime) # Convert to integer. Yes, I know this is ugly.
      if request.args.get('ctime'): # Get door close time (seconds remaining)
        ctime = request.args.get('ctime')
        ctime = int(ctime)
      if request.args.get('state'): state = request.args.get('state')
      lastSeen = int(time.time()) # Number of seconds since epoch. This is when we last got a heartbeat
      connstate = True # Connection to Coopener is now established
      return "OK(4)"


@app.route('/heartbeat')
def beat():
  '''
    Every n seconds Coopener should send a heartbeat/keepalive for the established connection
    It will contain the current state of Coopener in it. Yes, its extra overhead... but its simpler.
    I will need to re-write this entire protocol one day as it is really ugly and way too rigid.
  '''
  global otime
  global ctime
  global state
  global ip
  global connstate
  global lastSeen
  if (connstate == True):
    lastSeen = int(time.time()) # Number of seconds since epoch. This is when we last got a heartbeat
    if request.args.get('otime'): # Get door open time (second remaining)
      otime = request.args.get('otime')
      otime = int(otime) # Convert to integer. Yes, I know this is ugly.
    if request.args.get('ctime'): # Get door close time (seconds remaining)
      ctime = request.args.get('ctime')
      ctime = int(ctime)
    if request.args.get('state'): state = request.args.get('state')
    return "OK(HB)"
  else:
    return "No established connection found"


if __name__ == "__main__":
  app.debug = True
  app.run(host='0.0.0.0')