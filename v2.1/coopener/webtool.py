#!/usr/bin/python3

from flask import Flask
import os
import requests
from flask import Flask, render_template, request
import urllib.request
import socket

app = Flask(__name__)

print("IP IS: ")
print(socket.gethostbyname(socket.gethostname()))

connstate = 0

while (True):
  if (connstate == 0): # If no established connection with server, try to connect
    urllib.request.urlopen("http://www.google.com").read()

@app.route("/")
def hello():
  return "Hello World! - Love from Coopener"

@app.route("/command")
def cmd():
  if request.args.get('cmd'):
    cmd = request.args.get('cmd')
    if (cmd == "status"):
      return "OK"
    return "I hear you"
  else:
    return "nothing heard"

if __name__ == "__main__":
  app.debug = True
  app.run(host="0.0.0.0")

