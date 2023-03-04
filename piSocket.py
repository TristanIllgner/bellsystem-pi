import socketio
import RPi.GPIO as GPIO
import time
import datetime
import multiprocessing

relay = 4

symbol_times = None

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(relay, GPIO.OUT)

sio = socketio.Client()

# Function to power the relay for a specified time
def power_relay(seconds):
    GPIO.output(relay, GPIO.HIGH)
    time.sleep(seconds)

# Function to apply the pattern to the relay
def apply_pattern(pattern, isLoop):
    # Iterate through each character in the pattern
    times = 0

    while times < 1 or isLoop:
        times += 1

        for c in pattern:
            if c == ' ':
                GPIO.output(relay, GPIO.LOW)
                time.sleep(symbol_times.get(c, 0.5))
                pass
            else:
                _tempTime = symbol_times.get(c, 0.5)
                power_relay(_tempTime / 2)

                if c == '.':
                    GPIO.output(relay, GPIO.LOW)
                    
                time.sleep(_tempTime / 2)

# Global variable to keep track of the current process
current_process = None
currently_ringing = None

# Function to start a new apply_pattern process
def start_process(pattern, isLoop):
    global current_process
    # If a process is already running, terminate it
    if current_process is not None:
        current_process.terminate()
        current_process.join()
    # Start the new apply_pattern process
    current_process = multiprocessing.Process(target=apply_pattern, args=(pattern, isLoop,))
    current_process.start()

@sio.event
def connect():
    global currently_ringing

    print('connection established')
    sio.emit("isPi", True)

    if currently_ringing is not None:
        sio.emit("ring-bell", currently_ringing)

@sio.on("bell-rung")
def onBellRung(bell):
    global current_process
    global symbol_times
    global currently_ringing

    if(currently_ringing is not None and bell is not None and currently_ringing.get("type") == bell.get("type", None)):
        return

    currently_ringing = bell

    if bell != None:
        symbol_times = bell.get('speeds', {
            ' ': 0.5,
            '.': 0.5,
            '-': 1,
            '_': 2,
        })

        start_process(bell.get('pattern', ' '), bell.get('isLoop', False))
    elif current_process is not None:
        current_process.terminate()
        current_process.join()
        GPIO.output(relay, GPIO.LOW)

@sio.event
def disconnect():
    print('disconnected from server')

GPIO.output(relay, GPIO.LOW)
connected = False
while not connected:
    try:
        sio.connect("http://192.168.110.216:3001")
        print("Socket established")
        connected = True
    except Exception as ex:
        print("Failed to establish initial connnection to server:", type(ex).__name__)
        time.sleep(2)
sio.wait()

GPIO.cleanup()
