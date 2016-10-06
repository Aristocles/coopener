# coopener
Chicken Coop Opener project (placeholder)
www.makeitbreakitfixit.com

The Coopener project is the first of many modules which will make up my
Smart Home.
For detailed description see: https://makeitbreakitfixit.com/2016/08/30/diy-home-automation-chicken-enclosure/

NOTE: The latest version of the Python code will always work with the latest version of the Arduino code. Any other combination is untested.

# Arduino
The Arduino will listen on the serial link until it receives a command, it will 
then execute the command and acknowledge this by responding with the same command
it received.
All commands are <rcvChars> in length and are enclosed within braces, { }
When the coop door is closed an small LED is turned on, this is so at night
I will easily be able to tell from a distance that the door is closed.

# Python (running on Linux (Raspbian) on Raspberry Pi)
This script will grab the civil twilight hours from the web, parse this data and use it to open and close the door. Because we can’t be certain that internet will always be available, it also saves these times in a file and they are used again the next day in case there is no web access.
<img src="https://makeitbreakitfixit.files.wordpress.com/2016/08/data-flow.jpg">

The ultimate goal is to update and control all Smart Home modules from a centralised server.
Which will look something like this:
<img src="https://makeitbreakitfixit.files.wordpress.com/2016/09/parts-of-project.jpg">

[Updated: 6 Sept, 2016]
Project is currently incomplete and ongoing. Updates to follow as progress is made.

[Updated: 6 Oct, 2016]
Initial Python (v1.0alpha) uploaded. Main difference with this code to what I thought the script would exit at the end of each night and start again (via cron) every early morning. This turned out to be a bad idea, so instead the script now runs indefinitely and will get new twilight times each morning around 1am.
