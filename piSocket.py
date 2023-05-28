import socketio
import RPi.GPIO as GPIO
import time
import datetime
import multiprocessing
import os
from dotenv import load_dotenv

relay = 4

connected = False
next_ring = None
last_date = None
today_times = []
patterns = {}
isLoop = {
  'normal': False,
  'riot': True,
  'fire': True,
  'bomb': True,
}
speeds = {
    ' ': 0.5,
    '.': 0.5,
    '-': 1,
    '_': 2,
}

GPIO.setwarnings(False)
GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
GPIO.setup(relay, GPIO.OUT)

sio = socketio.Client()

# Function to power the relay for a specified time
def power_relay(seconds):
    GPIO.output(relay, GPIO.HIGH)
    time.sleep(seconds)

    
# Global variable to keep track of the current process
current_process = None
currently_ringing = None

def clear_ringing_thread():
    global current_process

    if current_process is not None and current_process.is_alive():
        os.kill(current_process.pid, 9)
        current_process.join()

    current_process = None

# Function to apply the pattern to the relay
def apply_pattern(pattern, isLoop):
    global speeds, relay
    # Iterate through each character in the pattern
    times = 0

    while times < 1 or isLoop:
        times += 1

        for c in pattern:
            if c == ' ':
                GPIO.output(relay, GPIO.LOW)
                time.sleep(speeds.get(c, 0.5))
                pass
            else:
                _tempTime = speeds.get(c, 0.5)
                power_relay(_tempTime / 2)

                if c == '.':
                    GPIO.output(relay, GPIO.LOW)
                    
                time.sleep(_tempTime / 2)

    clear_ringing_thread()

# Function to start a new apply_pattern process
def start_process(pattern, isLoop):
    global current_process, next_ring
    next_ring = None
    # If a process is already running, terminate it
    if current_process is not None:
        clear_ringing_thread()
    # Start the new apply_pattern process
    current_process = multiprocessing.Process(target=apply_pattern, args=(pattern, isLoop,))
    current_process.start()

_offline_ringer = None

def offline_ringer():
    global connected, isLoop, patterns, next_ring, last_date, today_times

    while (not connected) and (last_date is not None) and (today_times is not None):
        if (last_date == datetime.date.today().strftime('%Y%m%d')):
            seconds = (datetime.datetime.now() - datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
            old_last_rung = next_ring

            for period in today_times:
                for bell_time in [period.get("start", 0) * 60, period.get("end", 0) * 60]:
                    if (seconds < bell_time and ((next_ring is None) or bell_time < next_ring)):
                        next_ring = bell_time

            if (next_ring is not None and next_ring > today_times[-1].get("end", 0) * 60):
                next_ring = None

            if (next_ring != old_last_rung):
                print("Next ring:", next_ring)

            if (next_ring is not None and seconds >= next_ring):
                start_process(patterns.get("normal", " "), isLoop.get("normal", False))

        time.sleep(0.5)

def start_offline_ringer():
    global _offline_ringer

    _offline_ringer = multiprocessing.Process(target=offline_ringer)
    _offline_ringer.start()

@sio.event
def connect():
    global currently_ringing, connected, _offline_ringer

    print('connection established')
    sio.emit("isPi", True)
    connected = True

    if _offline_ringer is not None:
        _offline_ringer.terminate()
        _offline_ringer.join()

    if currently_ringing is not None:
        sio.emit("ring-bell", currently_ringing)

@sio.on("pi-init")
def onPiInit(data):
    global isLoop, speeds, patterns, today_times, last_date

    patterns = data.get("patterns", patterns)
    isLoop = data.get("isLoop", isLoop)
    speeds = data.get("speeds", speeds)
    last_date = data.get("date", last_date)
    today_times = data.get("times", today_times)

@sio.on("set-times-pi")
def onSetTimesPi(data):
    global today_times, last_date

    last_date = data.get("date", last_date)
    today_times = data.get("times", today_times)

@sio.on("bell-rung")
def onBellRung(bell):
    global current_process, currently_ringing, patterns

    if bell is not None:
        bell_type = bell.get("type", None)

    if(currently_ringing is not None and bell is not None and currently_ringing.get("type") == bell_type):
        return

    currently_ringing = bell

    if bell != None:
        start_process(patterns.get(bell_type, " "), isLoop.get(bell_type, False))
    elif current_process is not None:
        current_process.terminate()
        current_process.join()
        GPIO.output(relay, GPIO.LOW)

@sio.event
def disconnect():
    global connected

    connected = False
    print('disconnected from server, started offline ringer')

    start_offline_ringer()

GPIO.output(relay, GPIO.LOW)
load_dotenv()
while not connected:
    try:
        sio.connect(os.getenv("SERVER_URL", "http://192.168.110.225:80"))
        print("Socket established")
        connected = True
    except Exception as ex:
        print("Failed to establish initial connnection to server:", type(ex).__name__)
        time.sleep(2)