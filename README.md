# coopener
Chicken Coop Opener project (placeholder)
www.makeitbreakitfixit.com

The Coopener project is the first of many modules which will make up my
Smart Home.
For detailed description see: https://makeitbreakitfixit.com/2016/08/30/diy-home-automation-chicken-enclosure/

NOTE: The latest version of the Coopener Python code will always work with the latest version of the SmartHome Python code, which will always work with the latest Arduino code. Any other combination is untested.

# Arduino
The Arduino will listen on the serial link until it receives a command, it will 
then execute the command and acknowledge this by responding with the same command
it received.
All commands are <rcvChars> in length and are enclosed within braces, { }
When the coop door is closed an small LED is turned on, this is so at night
I will easily be able to tell from a distance that the door is closed.

# Python (running on Linux (CentOS). _SmartHome_)
This is the central control server which all smart home modules will eventually talk to. The user can control the smart modules via a web interface.

The server is running Python3, Flask, mod_wsgi. There are a number of tutorials on installing this on the internet. Once you have a test script up and running, you can replace it with the ones provided in this project.

# Python (running on Linux (Raspbian) on Raspberry Pi. _Coopener_)
This script will grab the civil twilight hours from the web, parse this data and use it to open and close the door. Because we can’t be certain that internet will always be available, it also saves these times in a file and they are used again in the event of no web access. Once web access is back the file is updated with the latest times.
Coopener Python script will then connect to a centralised Linux server (on the local network) called SmartHome. SmartHome can be accessed via its HTTP server to see the current state of and to send commands to Coopener.

The RasPi is running Python3, Flask, mod_wsgi also.

<img src="https://makeitbreakitfixit.files.wordpress.com/2016/10/flow.jpg">

[Updated: 6 Sept, 2016]
Project is currently incomplete and ongoing. Updates to follow as progress is made.

[Updated: 6 Oct, 2016]
Initial Python (v1.0alpha) uploaded. Main difference with this code to what I thought the script would exit at the end of each night and start again (via cron) every early morning. This turned out to be a bad idea, so instead the script now runs indefinitely and will get new twilight times each morning around 1am.

[Updated: 31 Oct, 2016]
Happy Halloween!
v1.1.1alpha is tested and worked fine. It is the Standalone version of Coopener where it does everything mentioned above except communicating with SmartHome (in either direction).
All code v2 or newer includes the ability for Coopener to connect to Smarhome. Because now there is 3 different sets of code to keep updated (Arduino, Coopener Python, SmartHome Python) the newest version of each of those 3 will always work together.
