#!/usr/bin/python3

# Eddy's Automated Chicken Coop Door Controller - aka Coopener (Coop Opener)
# October 2016 - v1.1.1 alpha - http://www.makeitbreakitfixit.com - https://github.com/Aristocles/coopener
# ** Warning: This code is in alpha, don't trust it to do anything right **
#
# script.py --help - To see execution options.
# USAGE: --test [open_time] [close_time] (optional)
#          Will open and close the door depending on times set (second)
#          If no --open_time or --close_time set it will use default of 20 and 40 seconds.
#        -c Initialise script with door closed (optional)
#        -o Initialise script with door open (optional)
#
# The purpose of this script is to send a serial signal to the Arduino to signal when the Arduino
# should open and close the door.
# The door that it is operating is the chicken coop door. The chickens put themselves to bed around
# sunset and like to come out and roam after sunrise. This script automates the process of putting
# the chickens away and then letting them out. They need to be put away at night to avoid foxes eating
# them or possums eating their food.
#
# The script will first attempt to get the UTC+0 times for civil twilight in the morning and evening.
# This is the time when the sky is only barely lit up by whatever sunlight is hitting the atmosphere
# above your location. It's a little before sunrise and a little after sunset (I asked the chickens
# and they said this is their preferred time).
# Once the times are retrieved from the website, the script will then use the local system GMT offset
# and calculate when these two times are in local time. It will then write these times to a file.
# There is only one file and every time a new time is grabbed this file is overwritten.
# If it is unable to get this info (eg. no internet or unable to parse for some reason) then it will
# look for a file it has previously written and use the times from there. If this also doesn't work
# (eg. file is missing or corrupt) then it will tell the Arduino to close the door and fail gracefully.
#
# The script expects that there is one open event and one close event per day (near sunrise and sunset),
# once there are no more events to count down towards it will then go to sleep and wait until 1am the
# next day, at which time it wakes and starts all over again with fresh open and close times.
# The script was initially designed to be executed daily with cron, but that is not as elegent as what
# we have now. Instead, this script is designed to start on boot and just keep running.
# It is still suggested to have the script start every few minutes via cron (just in case of some failure),
# but the script will automatically exit if it sees an instance is already running.
#
# In order for Serial comms to work with RasPi, don't forget to disable console over serial in 
# raspi-config and reboot.
#
# TODO:
# - Still need to build the Smart Home section of code, this is where the script tells a central
#   server its status and can be remotely controlled by the server too.
#
## KNOWN BUGS:
# - The code expects to end the day with closing the door (ie. at sunset), using testing
#   variables you can change this to open the door at the end of the day. The code may not handle that
#   well (it is untested) as it isn't expected in the real world.
#
#
# v.1.1.1 (24/10/2016)
# - Added ability to poll Arduino to get the status (relevant Arduino v1.1.1alpha) and return the status
# - Added command line arg --flip to flip status of the door then exit script
#
#


import json, os, re, serial, time, logging, argparse, sys, socket
from logging.handlers import RotatingFileHandler
from os import path
from datetime import date
from datetime import time
from datetime import datetime
from datetime import timedelta
from time import sleep
from urllib.request import urlopen
from threading import Thread
import threading
import urllib.request

###### Look at bottom of script for more configuration options ######

logfile = "/home/pi/bin/coopener.log" # file to log all events to
#scriptLog.basicConfig(filename=logfile, filemode='w', level=logging.DEBUG) # enable logging to file
# Not using basicConfig for logging because cant specify max log file size, so have to use the below
logFormatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
myHandler = RotatingFileHandler(logfile, mode='a', maxBytes=5*1024*1024,
                                backupCount=2, encoding=None, delay=0)
myHandler.setFormatter(logFormatter)
myHandler.setLevel(logging.DEBUG)
scriptLog = logging.getLogger('root')
scriptLog.setLevel(logging.DEBUG)
scriptLog.addHandler(myHandler)

def main(latitude, longitude, script, url, port, myport, serialName="/dev/ttyAMA0", name="Coopener", filename="times.txt"):
  '''
    This is a loop within a loop. Outer loop is run once per day, at around 1am
    Inner loop runs every few minutes and counts down until an action is to be taken (ie. open or close door)
    This script is designed to run forver.
  '''

  if getProcess(os.path.basename(script)): exit() # If the script is already running, then exit

  args = parseArgs() # Parse cmd line args. Show help & quit if invalid args.

  scriptLog.info("****************************************************")
  scriptLog.info("*  Starting Coopener - www.makeitbreakitfixit.com")
  scriptLog.info("*  Thread instance name: " + name)
  scriptLog.info("****************************************************")

  try:
    ser = serial.Serial(
      port=serialName,
      baudrate = 9600,
      parity=serial.PARITY_NONE,
      stopbits=serial.STOPBITS_ONE,
      bytesize=serial.EIGHTBITS,
      timeout=1
    )
    ser.close()
    ser.open()
  except:
    scriptLog.exception("Critical failure: Serial problem. Exiting.")
    sys.exit("Exiting due to error. Check log")

  firstRun = True # When the script first starts we use this to set initial door position according to the time,
                  # unless the user specifies a position for the door during execution
  door = Door(serial=ser) # Create a door object. Object defintions are at bottom of the script
  
  doorThread = Thread(target=doorWatch, args=(door, url, port, myport)) # This is a separate thread which monitors for HTTP comms from SmartHome
  doorThread.start() # Begin the thread and let it run parallel to the main program. See bottom of this script for more info.
  
  if args.open:
    scriptLog.info("Argument supplied at execution to have initial state of door to open.")
    door.setStatus("open") # If argument is passed during execution to open door, then open it now
    firstRun = False
  if args.close:
    scriptLog.info("Argument supplied at execution to have initial state of door to closed.")
    door.setStatus("close") # ditto for close door
    firstRun = False
  if args.flip: # The 'flip' arg simply changes the state of the door then exits script.
    scriptLog.info("[FLIP MODE] Door is currently in state: " + door.getStatus() + ". Flipping door then exiting script.")
    door.flipStatus()
    sys.exit("Flip mode completed successfully. Door is now " + door.getStatus() + ". Exiting.")

  url = "http://api.sunrise-sunset.org/json?lat=" + latitude + "&lng=" + longitude + "&formatted=0" # Prepare full URI to grab unsanitised times

############################# OUTSIDE LOOP - Runs once per day (before sunrise) #############################
  while(True): # This should loop once a day  
    times = getTimes(url)
    if times == None: # Something went wrong with getting times from the internet, try getting times from file
      times = openFile(filename)
      if times == None: # Something went wrong with opening the file
        scriptLog.error("Critical failure: Cannot get times to open/close the door. Exiting.")
        sys.exit("Exiting due to error. Check log")
    else: # Successfully retrieved local times, now write them to file
      writeFile(filename, times)
    scriptLog.info("\nRetrieved Times: " + str(times[0]) + " " + str(times[1]) + "\nInitialisation complete, beginning timers...\n")

    # Getting times was successful. Now we compare current time with open/close times
    openTime = door.getOpenTime(times) # Send the extracted open/close times and get open time
    closeTime = door.getCloseTime(times) # Send the extracted open/close times and get close time

    if args.test: # Override the times with testing times, if in test mode
      openTime = door.setOpenTime(args.open_time)
      closeTime = door.setCloseTime(args.close_time)

    today = True # While it is today, keep looping
    loopCount = 0
############################# INSIDE LOOP - Runs ever few secs until end of day #############################
    while (today): # This loop will keep running until both open and close signals have been sent, then script quits
      now = datetime.now() # get current time
      timeLeft2Open = door.getOpenTimeLeft() # number of seconds until door open
      timeLeft2Close = door.getCloseTimeLeft() # number of seconds until door close

      if now > openTime and now > closeTime:
        # How embarrassing, this piece of code is only here in the extremely unlikely event that the script is
        # started after sunset. This will close the door and avoid any further actions.
        firstRun = False
        door.setStatus("close")

      # Decide what the next action should be. Open or close.
      #firstRun = nextAction(firstRun) # Returns what the next action should be. Also sets initiate state of door.
      if now > openTime: # Door already opened, next action is to close
        timeLeft = timeLeft2Close
        action = "close"
        if firstRun:
          door.setStatus("open") # If this is the first time script is running, we should set the door in correct position
          scriptLog.info("Setting state of door to open.")
          firstRun = False # This should only happen once
      elif now > closeTime: # Door already closed, next action is to open
        timeLeft = timeLeft2Open
        action = "open"
        if firstRun:
            door.setStatus("close")
            scriptLog.info("Setting state of door to closed.")
            firstRun = False
      elif timeLeft2Open < timeLeft2Close: # Next action is to open
        timeLeft = timeLeft2Open
        action = "open"
      elif timeLeft2Close < timeLeft2Open: # Next action is to close
        timeLeft = timeLeft2Close
        action = "close"

      # The Arduino is using the serial line for outputting its status etc. Much of this is white noise.
      # We also want the flexibility of Python to send some non-critical/arbitrary data to the Arduino.
      # For this reason, all actual actionable commands (ie. open/close door) are placed inside
      # curly braces { }. The maximum number of chars to send/receive inside the braces is 8.
      # This particular project is very simple, but the aim here is to reuse this basic framework for
      # other projects.
      if ((loopCount % 120) == 0): # This is used to to only write to the log file and Arduino periodically
                                  # instead of every interation of the loop. Increase mod number for longer gaps
        scriptLog.info("Time left to " + action + " door: " + str(timeLeft)) # Tell Linux
        ser.write(bytes("Time left to " + action + " door: " + str(timeLeft), 'UTF-8')) # Tell Arduino
      loopCount = loopCount + 1 # Increment loop counter.
      if timeLeft < timedelta(seconds=10) and timeLeft > timedelta(seconds=1): # Send signal to Arduino
        door.setStatus(action)

      if now > openTime and now > closeTime: # Door has already been opened and closed today.
      # Once both actions are performed in a day, we then wait until the next day
      # where we get the new twilight times and start all over again
        today = waitForNextDay() # Will only return once it is the next day

      sleep(5) # Wait a little before looping again

######################################

def writeSerial(action, ser):
  '''
    Commands are sent via serial to the Arduino. All actual actionable commands (ie. open/close door)
    are placed inside curly braces { }. The maximum number of chars to send/receive inside the braces
    is 8. This particular project is very simple, but the aim here is to reuse this basic framework for
    other projects.
  '''
  scriptLog.info("[Serial Comms] SENT command to " + action + " door.")
  timeout = datetime.now() + timedelta(minutes=3) # loop timeout is 3 minutes from now
  while True: # Keep sending the signal until we receive an ACK or timeout expires
    ser.write(bytes("{" + action + "}", 'UTF-8')) # Send signal
    sleep(.1) # Wait a little before reading serial
    status = readSerial(ser) # Listen for acknowledgement
    scriptLog.info("[Serial Comms] Waiting for reply from Arduino. RCVed: " + str(status))
    if status != None: # If Ard hasn't sent anything back we get None. Otherwise, we got a response.
      if status == action: # An ACK is rcv'd when the Arduino sends the same action back to Python
        scriptLog.info("[Serial Comms] RCV ACK \'" + action + "\' from Arduino")
      if action == "status": # The response back from Ard should be the status of the door
        scriptLog.info("[Serial Comms] RCV Status \'" + status + "\' from Arduino")
      ser.flushInput() # Flush the serial buffer
      ser.flushOutput()
      return status
    if datetime.now() > timeout: # No ACK rcv'd. Timeout of loop anyway
      scriptLog.warning("Command has been sent, but no ACK received from Arduino.")
      break
    sleep(1) # Wait a little before communicating again
  return None # If execution gets here something went wrong

def readSerial(ser):
  '''
    The Arduino is using the serial line for outputting its status etc. Much of this is white noise.
    We also want the flexibility of Python to send some non-critical/arbitrary data to the Arduino.
    For this reason, all actual actionable commands (ie. open/close door) are placed inside
    curly braces { }. The maximum number of chars to send/receive inside the braces is 8.
    This particular project is very simple, but the aim here is to reuse this basic framework for
    other projects.
  '''
  while (ser.inWaiting() > 1): # Loop until no more bytes left in serial input buffer
    line = ser.readline().decode('utf-8').strip() # Read a whole line from Ard (ends in \r\n), decode it to a str. Strip newline chars
    if len(line) > 1 and line[0] == '{' and line[-1] == '}': # Only keep it if it inside { }
      status = line[1:-1] # Remove the curly braces (first and last char) from the string
      return status
  return None


def getTimes(urlData):
  """
    Connect to website and grab the full raw data for your location
  """
  try:
    with urlopen(urlData) as url:
      if (url.getcode() == 200): # if HTTP 200 OK returned
        data = url.read().decode('utf-8') # read in contents of the webpage. Needs to be decoded to utf-8 for Python3
      else:
        scriptLog.warning("Error reading website to get times. HTTP Return Code: " + str(url.getcode()))
        return None
  except:
    scriptLog.warning("Problem retrieving data from " + urlData)
    return None
  rawTimes = parseResults(data) # Send website page for parsing. Should get back raw twilight times
  if rawTimes != None:
    return parseData(rawTimes) # Send raw times for parsing. Should get back sanitised times
  else:
    scriptLog.warning("Website contactable, but cannot find specified data")
    return None

def parseResults(data):
  """
    Pull out of full raw data the raw civil twilight hours
    Use the JSON module to load the string data in to a tuple
  """
  try:
    theJSON = json.loads(data)
    begin = theJSON["results"]["civil_twilight_begin"]
    end = theJSON["results"]["civil_twilight_end"]
  except:
    #print "Error pulling data out of JSON response from URL"
    scriptLog.warning("Error pulling data out of JSON response from URL")
    return None
  times = (begin, end) # Create a tuple with the begin & end times in there
  scriptLog.info("Retrieved raw data from URL: " + str(times))
  return times

# Parse the raw civil twilight hours to something we can use in this script
def parseData(data):
  pattern = "T([0-2][0-9]:[0-5][0-9]):[0-9][0-9][\+\-]" # Regex search pattern to grab the time
  if len(data) != 2:
    #print "Pre-parsing failure. Invalid tuple length. Should be 2, is " + str(len(data))
    scriptLog.warning("Pre-parsing failure. Invalid tuple length. Should be 2, is " + str(len(data)))
    return None
  match1 = re.search(pattern, data[0]) # Find the regex pattern in raw data. Match group (1) inside regex pattern
  match2 = re.search(pattern, data[1])
  if match1 and match2: # If either regex match fails then go to else
    times = []
    times.append(re.sub(':', '', match1.group(1))) # remove the colon (:) from the matched string
    times.append(re.sub(':', '', match2.group(1))) # we should now be left with just the 24hr time
    del match1 # Delete the variables. No longer needed
    del match2
  else:
    #print "Regex fail. Unable to find time inside raw data"
    scriptLog.warning("Regex fail. Unable to find time inside raw data")
    return None
  # At this point we have the open/close door times, but they are in UTC
  # So we need to get the Linux systems GMT offset and calculate the local time
  # The assumption is that if we were successfully able to get the JSON data from the internet,
  # then internet is working so NTP should also be working, therefore we should have correct GMT offset
  # This only applies if the RasPi doesn't have a RTC module plugged in. It's a very good idea to have
  # the RTC module.
  gmt = getGMT()
  if gmt == None: return None
  #print "GMT offset from system is: " + gmt[0] + gmt[1]
  scriptLog.info("GMT offset from system is: " + gmt[0] + gmt[1])
  # Calculate the local time
  local = []
  local.append(getLocalTime(times[0], gmt))
  local.append(getLocalTime(times[1], gmt))
  #print "Converted times: " + str(local[0]) + " " + str(local[1])
  scriptLog.info("Converted times: " + str(local[0]) + " " + str(local[1]))
  return local

def getLocalTime(time, gmt):
  """
  Convert UTC +0 time to local (system) time
  """
  if "+" in gmt[0]: # Need to add the offset to UTC time
    result = int(time) + int(gmt[1]) # Add offset to UTC+0 time
    result = result % 2400 # Modulo to get back to 24hrs
    result = str(result).zfill(4) # Pad with leading zero if needed
  elif "-" in gmt[0]: # Need to subtract the offset from UTC time
    result = int(time) - int(gmt[1])
    result = result % 2400
    result = str(result).zfill(4)
  else:
    #print "Something is wrong with the GMT offset pulled from the system"
    scriptLog.warning("Something is wrong with the GMT offset pulled from the system")
    return None
  if len(result) != 4:
    #print "Something went wrong while converting to local time (returned: " + result + ")"
    scriptLog.warning("Something went wrong while converting to local time (returned: " + result + ")")
    return None
  return result

def getGMT():
  '''
  Get the local (system) time/GMT offset
  '''
  gmt = os.popen("/bin/date +%z") # Linux cmd to get the GMT offset of this PC
  dt = gmt.read()
  #dt = "+1000" # comment out above lines and use this line for testing
  pattern = "^([\+\-])([0-1][0-9][0-9][0-9])$"
  match = re.search(pattern, dt)
  if match:
    offset = (match.group(1), match.group(2))
    del match
  else:
    #print "Unable to parse GMT offset from PC. \"date +%z\" should give a GMT offset (eg. +1000)"
    scriptLog.warning("Unable to parse GMT offset from PC. \"date +%z\" should give a GMT offset (eg. +1000)")
    return None
  return offset

def openFile(filename):
  '''
  Open the file and pull the times from it. The file format should be just two lines of text
  First line has the local time to open the door. 4 chars. (eg. 0530 for 5:30am)
  Second line has the local time to close the door. 4 chars. (eg. 1835 for 6:35pm)
  '''
  if path.exists(filename):
    file = open(filename, "r")
    lines = file.readlines()
    if len(lines) != 2: return None # Should be 2 lines in the file
    lines[0] = lines[0].strip() # Remove whitespace from string
    lines[1] = lines[1].strip()
    if len(lines[0]) != 4: return None # Should be 4 chars per line
    if len(lines[1]) != 4: return None
    #print "Successfully retrieved times from file"
    scriptLog.info("Successfully retrieved times from file")
    return lines
  else:
    #print "File " + filename + " doesnt exist"
    scriptLog.warning("File " + filename + " doesnt exist")
    return None

def writeFile(filename, times):
  '''
  Write the sanitised (local) time to file. The file format should be just two lines of text
  First line has the local time to open the door. 4 chars. (eg. 0530 for 5:30am)
  Second line has the local time to close the door. 4 chars. (eg. 1835 for 6:35pm)
  '''
  #print "Writing local times to file: " + filename
  scriptLog.info("Writing local times to file: " + filename)
  try:
    file = open(filename, "w+") # Open or create file for writing
    file.write(times[0] + "\r\n")
    file.write(times[1] + "\r\n")
    file.close()
  except:
    #print "Problem writing " + filename + ". Check permissions and if disk is rw"
    scriptLog.warning("Problem writing " + filename + ". Check permissions and if disk is rw")


def getProcess(program):
  '''
    INPUT: Expects to receive the name of the process to search for in Linux
    PROCESS: Returns a list of PIDs.
    OUTPUT: Retuns None if no PIDs found. Otherwise, returns list of PIDs
  '''
  pids = [pid for pid in os.listdir('/proc') if pid.isdigit()]
  result = []
  for pid in pids:
    try:
      my_line = open(os.path.join('/proc', pid, 'cmdline'), 'rb').readline() # Read first line in from /proc/<PID>/status. This contains the name of process
      match = re.search(str(program), str(my_line)) # Regex search for process name
      if match:
        if (int(pid) != int(os.getpid())): # Make sure we dont get the PID of this script
          print("My PID is " + str(os.getpid()) + ". Found PID: " + str(pid) + " [" + str(my_line) + "]")
          print("Script is already running. My PID is " + str(os.getpid()) + ". Found PID: " + str(pid) + " [" + str(my_line) + "]")
          result.append(pid) # Add PID to the list
    except IOError:
      continue
  if not result:
    return
  else:
    return result


def parseArgs():
  '''
    INPUT: None
    PROCESS: Parse the command line arguments
    OUTPUT: Returns an argparse object

    If invalid arguments given, program will not start.
    More info for argument parser: https://docs.python.org/3/library/argparse.html under 16.4.4.6
  '''
  parser = argparse.ArgumentParser() # Instantiate an object of argparse
  parser.add_argument("-t", "--test",
                      help="Run in testing mode. Can optionally be used with --open_time and --close_time. When used on its own\
                      the default open time is 20 seconds and close time is 40 seconds",
                      action="store_true") # True/false optional arg for testing
  parser.add_argument("-o", "--open",
                      help="Start script with door open",
                      action="store_true")
  parser.add_argument("-c", "--close",
                      help="Start script with door closed",
                      action="store_true")
  parser.add_argument("--open_time",
                      type=int,
                      help="Must be used with --test and --close_time options. Specifies how many seconds to wait until door is opened"
                      )
  parser.add_argument("--close_time",
                      type=int,
                      help="Must be used with --test and --open_time options. Specifies how many seconds to wait until door is closed"
                      )
  parser.add_argument("-f", "--flip",
                      help="Flip the door status. This will open the door if already closed or close if already opened. Once finished, the\
                      script will exit",
                      action="store_true")
  args = parser.parse_args()

  if ((not args.test) and (args.open_time or args.close_time)):
    scriptLog.error("You cannot use --open_time or --close_time without --test. See --help. Exiting")
    sys.exit("Exiting due to error. Check log")

  if args.close and args.open:
    scriptLog.error("Cannot start script with door both closed and open. Select just one. See --help. Exiting.")
    sys.exit("Exiting due to error. Check log")

  if args.test: # If --test arg given it can either use default open/close times or times given in --open_time and --close_time
    scriptLog.info("################ Running in TESTING MODE ######")
    if args.open_time and not args.close_time:
      scriptLog.error("--test and --open_time option set, but no --close_time option seen. See --help. Exiting.")
      sys.exit("Exiting due to error. Check log")
    elif args.close_time and not args.open_time:
      scriptLog.error("--test and --close_time option set, but no --open_time option seen. See --help. Exiting.")
      sys.exit("Exiting due to error. Check log")
    elif args.close_time and args.open_time:
      scriptLog.info("####[TEST]#### Opening door in " + str(args.open_time) + " seconds ####")
      scriptLog.info("####[MODE]#### Closing door in " + str(args.close_time) + " seconds ####")
      scriptLog.info("###############################################")
    else: # If the open and close times aren't given, then use the defaults
      defOpen = 20 # Default open time (seconds) if not given in args
      defClose = 40 # ditto for close time
      args.open_time = defOpen
      args.close_time = defClose
      scriptLog.info("####[TEST]#### Opening door in " + str(defOpen) + " seconds ####")
      scriptLog.info("####[MODE]#### Closing door in " + str(defClose) + " seconds ####")
      scriptLog.info("##############################################")
  #print(vars(args)) # convert args from object to a dict 
  return args

def waitForNextDay():
  '''
    In here we just wait for the next day (at 1am) then exit the loop.
    When exiting the loop we return False, which will trigger the whole script to start over
    (ie. get new twilight hours and write to file etc...)
  '''
  scriptLog.info("No more actions left to do today, will go to sleep until tomorrow")
  # There HAS to be an easier way to do the below, but this works and I cant be bothered finding a nicer way
  # below few lines will build two time objects and subtract them from each other to get a countdown timer
  eta = datetime.now() + timedelta(days=1) # First, build a datetime object which is right now plus 1 day
  eta = eta.strftime("%Y-%m-%d 01:00:00.0") # Return string representation of the object but at 1am
  eta = datetime.strptime(eta, "%Y-%m-%d %H:%M:%S.%f") # This takes a string of date/time and turns it in to an object
  # So what is happened above is: 1) get current datetime and add 1 day. 2) Manipulate the result of #1 so it shows 1am
  # and return it as a string. 3) Using a datetime string, turn it back in to an object which can be used to subtract
  # from other datetime objects.
  loopCount = 0
  while (True): # Now we wait until it is 1am on the next day
    now = datetime.now()
    counter = eta - now
    if ((loopCount % 120) == 0): # This is used to to only write to the log file and Arduino periodically
                                  # instead of every interation of the loop. Increase mod number for longer gaps
      scriptLog.info("Sleeping " + str(counter.total_seconds()) + " seconds until restarting script")
    loopCount = loopCount + 1
    if int(counter.total_seconds()) < 60: # Not long left until 1am next day
      return False # Exit loop
    sleep(5) # Wait for a few minutes before checking again
  
def get_ip_address(): # This will open a socket so we can get the IP address of the RasPi.
# It doesnt actually need to make a connection or do anything with the socket.
# Returns this devices IP.
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  s.connect(("8.8.8.8", 80))
  return s.getsockname()[0]

#######################################################
####################### CLASSES #######################
#######################################################

class Door(object):
  '''
    This object is used to control the status of the door.
    Currently, there is only one door to control so a separate class is not really
    needed. But this is just for future-proofing the project as there may be a 
    chance that we will want to control multiple doors at some stage.
  '''
  def __init__(self, serial):
    self.ser = serial
    self.status = self.getStatus()
    self.connect = False
    self.openTime = 0
    self.closeTime = 0

  def setConnected(self, connected): # Sets state of the HTTP connection to SmartHome
    self.connect = connected
    return self.connect

  def getConnected(self): # Returns state of HTTP connection to SmartHome
    return self.connect

  def setStatus(self, status): # open or close the door
    writeSerial(status, self.ser)
    self.status = status

  def getStatus(self): # get state of the door. either open or close
    self.status = writeSerial("status", self.ser)
    if (self.status == None):
      scriptLog.warning("No status returned from Arduino. Don't know if door is open or closed. Continuing...")
      self.status = "close" # Just assume it is closed. Meh. (fix this another time)
    return self.status

  def getStatusNoArd(self): # This returns status of the door without talking to the Arduino
  # This is used for giving the status for the HTTP heartbeat protocol. Because I am lazy
    return self.status

  def flipStatus(self): # If door is opened, it'll close. If it's closed, it'll open
                      # If state is unknown (ie. at script start) nothing happens
    if self.status == "open":
      self.setStatus("close")
      return self.status
    if self.status == "close":
      self.setStatus("open")
      return self.status

  def getOpenTime(self, times): # Receives the open/close times from either the net or
                    # from file, calculated what time door should open and returns it
    now = datetime.now() # Get current date and time
    # Build a complete date and time string for the open and close times
    # Look in waitForNextDay() function for a detailed explanation of what is going on here
    self.openTime = now.strftime("%Y-%m-%d " + times[0][0] + times[0][1] + ":" + times[0][2] + times[0][3] + ":%S.%f") # Create string
    self.openTime = datetime.strptime(self.openTime, "%Y-%m-%d %H:%M:%S.%f") # Turn in to datetime object
    return self.openTime

  def getCloseTime(self, times): # Same as getOpenTime() but for the close time
    now = datetime.now()
    self.closeTime = now.strftime("%Y-%m-%d " + times[1][0] + times[1][1] + ":" + times[1][2] + times[1][3] + ":%S.%f")
    self.closeTime = datetime.strptime(self.closeTime, "%Y-%m-%d %H:%M:%S.%f")
    return self.closeTime

  def setOpenTime(self, newTime): # Used for overriding the opentime (eg. when testing)
    self.openTime = datetime.now() + timedelta(seconds=newTime)
    return self.openTime

  def setCloseTime(self, newTime):
    self.closeTime = datetime.now() + timedelta(seconds=newTime)
    return self.closeTime

  def getOpenTimeLeft(self): # Returns time left to open the door
    now = datetime.now() # Get current date and time
    return (self.openTime - now)

  def getCloseTimeLeft(self): # Same as getOpenTimeLeft() but for close time
    now = datetime.now()
    return (self.closeTime - now)

  def getOpenTimeLeftInt(self): # Same as getOpenTimeLeft() but returns an int and not less than zero
    now = datetime.now() # Get current date and time
    if (int((self.openTime - now).total_seconds()) < 0): # If number of seconds left is negative, 
      return 0 # then time has passed so just return zero
    return int((self.openTime - now).total_seconds()) # Returns number of seconds left as int

  def getCloseTimeLeftInt(self): # Same as getCloseTimeLeft() but returns int and not less than zero
    now = datetime.now()
    if (int((self.closeTime - now).total_seconds()) < 0):
      return 0
    return int((self.closeTime - now).total_seconds())

#####################################################################
#################### END OF MAIN COOPENER SCRIPT ####################
############### BEGINNING OF FLASK WEB SERVER SCRIPT ################
#####################################################################


def doorWatch(door, url, port, myport):
  '''
    This is a function run in a separate thread. Its purpose is to monitor a variable
    for changes. The change can only be made by the Flask function which is accessed through
    a HTTP GET. So a HTTP GET from the server can send us commands and this function will
    monitor for those commands and execute them.
  '''
  sleep(5) # Wait 5 seconds for everything in main script to initialise, then try to connect
  connected = False # This tracks the state of the HTTP connection to SmartHome
  counter = 0 # Heartbeat timeout counter
  delay = 0 # Introduce a delay between sending heartbeats
  myip = get_ip_address() # Get the WiFi IP of the RasPi
  while(True): # This thread keeps running
    while(connected == False): # If connection is not made with SmartHome, then attempt to make it
      try:
        scriptLog.info("[HTTP Comms] >>> Attempting handshake with SmartHome. " + url + ":" + port)
        result = urllib.request.urlopen(url + ":" + port + "/handshake?shake=1&ip=" + myip + "&port=" + myport).read()
        # Attempt initial handshake with SmartHome. Returns a byte var
        if result.decode("utf-8") == "OK(2)":
          scriptLog.info("[HTTP Comms] <<< Recieved HTTP response. " + result.decode("utf-8"))
          scriptLog.info("[HTTP Comms] >>> Sending HTTP data.")
          result2 = urllib.request.urlopen(url + ":" + port + "/handshake?shake=3&otime=" + \
                                            str(door.getOpenTimeLeftInt()) + "&ctime=" + \
                                            str(door.getCloseTimeLeftInt()) + "&state=" + \
                                            door.getStatusNoArd()).read() # Send Coopener info to SmartHome
          if result2.decode("utf-8") == "OK(4)":
            scriptLog.info("[HTTP Comms] <<< Recieved HTTP response. " + result2.decode("utf-8"))
            # Handshake complete. Set connection state as established.
            scriptLog.info("[HTTP Comms] HTTP Connection established.")
            connected = True
            break # Exit the loop
      except:
        scriptLog.warning("[HTTP Comms] Exception. Problem connecting to SmartHome on " + url + ":" + port)
      sleep(5) # Wait before trying again
    delay = delay + 1
    if (connected == True and delay % 10 == 0): # If connected then send a heartbeat signal
      try:
        result = urllib.request.urlopen(url + ":" + port + "/heartbeat?hbeat=0&otime=" + \
                                        str(door.getOpenTimeLeftInt()) + "&ctime=" + \
                                        str(door.getCloseTimeLeftInt())+ "&state=" + \
                                        door.getStatusNoArd()).read()
        if result.decode("utf-8") == "OK(HB)":
          counter = 0
        else:
          scriptLog.info("[HTTP Comms] Server says: " + result.decode("utf-8"))
          scriptLog.info("[HTTP Comms] No response for heartbeat packet. (" + str(counter) + ")")
          counter = counter + 1
      except:
        scriptLog.info("[HTTP Comms] Server says: " + result.decode("utf-8"))
        scriptLog.info("[HTTP Comms] No response for heartbeat packet. (" + str(counter) + ")")
        counter = counter + 1
      if counter >= 3: # If too many heartbeat timeouts
        counter = 0
        connected = False # Reset connection

# This code will execute actions given to it from SmartHome server
    if (webData['flip']):
      scriptLog.info("[HTTP Comms] Flipped door status to " + door.getStatusNoArd())
      door.flipStatus()
    if (webData['reconnect']):
      scriptLog.info("[HTTP Comms] Received command to reconnect to SmartHome server")
      connected = False
    # Always setting back to False prevents commands from banking up/waiting while HTTP server disocnnected
    threadLock.acquire() # Lock will prevent any other thread from modifying webData[] while we modify it
    webData['flip'] = False # Set the variable used for HTTP comms back to False, waiting for next cmd
    webData['reconnect'] = False
    threadLock.release()
    sleep(1)


def flask():
  '''
    This is a web service function which listens for HTTP commands sent from SmartHome server (which is also running
    python/flask).
    The only commands we expect are to reconnect or flip the status of the door.
    When received, they are stored in a variable (webData). The other function doorWatch() is executed in another thread
    which then sees any changes on the variable and acts on them. It might be a good idea to combine both these functions
    in to one and run them under one thread. Maybe later...
  '''
  from flask import Flask
  import os
  import requests
  from flask import Flask, render_template, request
  import urllib.request
  import socket

  app = Flask(__name__)
  print ("Flask application running. My name is: " + __name__)

  connstate = 0

#  while (True):
#    if (connstate == 0): # If no established connection with server, try to connect
#      urllib.request.urlopen("http://www.google.com").read()

  @app.route("/")
  def hello():
    return "Hello World! - Love from Coopener b"

  @app.route("/command")
  def cmd():
    if request.args.get('cmd'):
      scriptLog.info("[HTTP Comms] Received command \'" + request.args.get('cmd') + "\'")
      cmd = request.args.get('cmd')
      threadLock.acquire() # Enable lock to avoid Coopener main script from messing with the contents
      if (cmd == "flip"):
        webData['flip'] = True
      elif (cmd == "reconnect"):
        webData['reconnect'] = True
      else:
        threadLock.release()
        return ("Invalid command "+ str(webData))
      threadLock.release()
      return ("OK " + str(webData) + "<br><FORM><INPUT Type=\"button\" VALUE=\"Back\"\
              onClick=\"history.go(-1);return true;\"></FORM>") # Shows result of command and a button for user to go BACK

    else:
      scriptLog.info("[HTTP Comms] Received invalid command")
      return ("Invalid HTTP syntax "+ str(webData))

  app.run(debug=True, use_reloader=False, host="0.0.0.0")


webData = {
  'flip' : False,
  'reconnect' : False,
}

doorFlip = False

if __name__ == "__main__":
  ### Configuration ###
  # It is possible to control more than one door by running a separate thread for each door.
  # This would allow you to have a different door at a different geographical location,
  # and save open/close times to a different file. Everything is logged to same file.
  # I can't think of a use case for this, but the point here is to flesh this code out so we
  # can use it for other SmartHome applications.
  # Below configuration is for just one Coopener thread. You could create multiple if you chose to.
  name = "Coopener1" # Name of the coopener instance
  latitude = "-33.81528" # Your location latitude
  longitude = "151.10111" # Your location longitude
  filename = "/home/pi/bin/twilight.txt" # Filename to store door open and close times in
  serialName = "/dev/ttyAMA0" # Name of serial interface used to talk to Arduino
  url = "http://coopener.smarthome.vorignet.com" # SmartHome Server URL
  port = "80" # This is the port SmartHome server is listening on
  myport = "5000" # This is the port that Coopener is listening on for return comms

  #####################
  script = __file__ # Get the name of this file

  threadLock = threading.Lock() # When this lock is active in one thread the other thread that tries
  # to activate it will need to wait until the lock has been released.
  t1 = Thread(target=main, args=(latitude, longitude, script, url, port, myport, serialName, name, filename))
  t2 = Thread(target=flask)
  #t2 = Thread(target=main, args=(latitude, longitude, script, serialName, name, filename))
  t1.start()
  t2.start()
  print ("Started thread: " + name)
