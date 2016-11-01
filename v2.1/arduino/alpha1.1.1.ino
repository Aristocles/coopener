#include <Servo.h>

#define SERVO_PIN 9
#define LED_PIN 8
#define BAUD 9600

/*
  Project: Coopener (Chicken Coop Door Opener)
  www.makeitbreakitfixit.com - Coopener - v.alpha1.1
  
  The Coopener project is the first of many modules which will make up my
  Smart Home. 
  
  The Arduino will listen on the serial link until it receives a command, it will 
  then execute the command and acknowledge this by responding with the same command
  it received.
  All commands are <rcvChars> in length and are enclosed within braces, { }
  
  When the coop door is closed an small LED is turned on, this is so at night
  I will easily be able to tell from a distance that the door is closed.
  
  Versions:
  alpha1.1.1 (24/10/2016)
  - Added ability for Arduino to be polled on its current state and return whether
    the door is open or closed. see: returnState(). Relevant Python v1.1.1alpha.
*/


// ************** CONFIGURATION **************
int openPos = 160; // Door fully open position for servo
int closePos = 80; // Door fully closed position for servo
int rcvChars = 8; // Max number of protocol chars to receive from serial. The
                  // serial protocol used between Ard and Python shouldnt exceed this
bool testing = false; // Set to true when testing.
// *******************************************

Servo myservo;  // Create servo object to control the servo
int pos = 0;    // Store the servo position

void setup () {
    myservo.attach(SERVO_PIN);  // Attaches pin <SERVO_PIN> to the servo object
    pinMode(LED_PIN, OUTPUT); // Set the LED pin as output
    Serial.begin(BAUD); // Python to Ard comms baud rate
    delay(1000);
    Serial.println("Starting Coopener (Chicken Coop Opener) - Sept 2016");
    Serial.println("www.makeitbreakitfixit.com");
    Serial.println("*****************************************************");
    while (!Serial) {;} // Continue only when serial comms comes up
    pos = closePos; // Initial state of the door
    myservo.write(pos); // servo starting position. This is fully open position
    if (testing) Serial.println("***TESTING MODE***");
}
 
void loop () {
    if (testing) TestLoop(); // Open close door for testing purposes
    readSerial(); // Listen on serial for commands
  }

void readSerial() {
  // TODO: Insert checks to ensure code can handle malformed data. eg. Message
  //       beginning with { but no closing }. Or message too long or invalid chars
  if (Serial.find('{')) { // A protocol message must be enclosed in braces, { }
    char serialData[(rcvChars+1)]; // Array holds incoming serial buffer. +1 for NULL char
    int numChars = Serial.readBytesUntil('}', serialData, (rcvChars+1)); // Store chars until } is found
    serialData[numChars] = NULL; // Add the NULL terminator
    Serial.print("Received signal to "); Serial.println(serialData);
    if ((String(serialData)) == "open") openDoor();
    if ((String(serialData)) == "close") closeDoor();
    if ((String(serialData)) == "status") returnState();
  }
}

void returnState() { // Gets current state of the door and returns it via serial comms
  if (pos == closePos) Serial.println("{close}"); // Let Python know door is closed
  if (pos == openPos) Serial.println("{open}"); // Let Python know door is open
  Serial.flush(); // Wait for serial data to be sent before continuing
}

void openDoor() {
  if (pos == closePos) {
    Serial.println("Opening door");
    for (pos = closePos; pos < openPos; pos += 1) { // opens door in 1degree steps
      myservo.write(pos);
      delay(50); // delay so it doesnt move too quick
    }
    digitalWrite(LED_PIN, LOW); // Turn off light when door open
  }
  Serial.println("Door is now open");
  Serial.println("{open}"); // ACK message to let Python know command was executed
  Serial.flush(); // Wait for serial data to be sent before continuing
}

void closeDoor() {
  if (pos == openPos) {
    Serial.println("Closing door");
    for (pos = openPos; pos > closePos; pos -= 1) { // closes door in 1degree steps
      myservo.write(pos);
      delay(50); // delay so it doesnt move too quick
    }
    digitalWrite(LED_PIN, HIGH); // Turn on light when door closed
  }
  Serial.println("Door is now closed");
  Serial.println("{close}"); // ACK message to let Python know command was executed
  Serial.flush();
}

void TestLoop() {
    // This is used for testing. It opens and closes the door ever 5 seconds
  openDoor();
  delay(5000);
  closeDoor();
  delay(5000);
}

