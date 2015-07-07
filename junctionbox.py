#!/usr/bin/python

import curses
import time
import os
import re
import ConfigParser
import sys
import string
import shutil
import os.path
from os.path import expanduser
from subprocess import call

import mpylayer
from unidecode import unidecode

import EpisodeDatabase

#Default Options
DEBUG = True             # enables debug print statements to screen
DEBUG_LOG = False        # enables debug print statements logged to file
UNPRINTABLE_CHAR = "#"   # character to replace unprintable characters on the display

DATA_DIRECTORY = os.path.join(expanduser("~"), "jb_data")     #Default data directory
# Note: All directories dependent on DATA_DIRECTORY need to be updated in load_config(), because DATA_DIRECTORY can be set in user preferences, see "# Update dependent directories" below.
FAV_DIRECTORY = DATA_DIRECTORY
#TODO remove and search for subdirs instead
EPISODE_DIRECTORY = os.path.join(DATA_DIRECTORY, "Late_Junction")
JB_DATABASE = os.path.join(DATA_DIRECTORY, "JB_DATABASE" )
FAVOURITED_LOG_FILE = "favourited.txt"
DIR_AND_FAVOURITED_LOG_FILE = (os.path.join(FAV_DIRECTORY, FAVOURITED_LOG_FILE ))
DISPLAY_REFRESH_TIME = 0.4        #the refresh cycle time for the display in seconds
BUTTON_HOLD_TIME = 1.5            #the time a button must be held down to be considered "held"
BUTTON_DEBOUNCE_TIME = 0.1        #delay before retriggering button press to debounce buttons

SHIELD_BUTTON = False    #set to True if the lcd shield buttons are present
BUTTON =   False         #set to True if buttons are present
LCD =      False         #set to True if there is an LCD screen present
LED =      False         #set to True if there is an RGB LED present
KEYBOARD = True          #set to True if keyboard is present
SCREEN =   True          #set to True if a monitor is present
HIDE_CURSOR = True       # Cursor is hidden by default, but some curses libs don't support it.
LINEWIDTH = 16           # Characters available on display (per line) 
DISPLAYHEIGHT = 2        # Lines available on display
LCD_EMULATION = True     # If true the screen (monitor) will emulate the LCD display
keys = {}                # Keyboard keys used and their methods
buttons = []             # Hardware buttons used and their methods
shield_buttons = {}      # Shield buttons used and their methods

#Navigation options (not in .junctionbox yet)
SKIP_TIME_MEDIUM = 60
SKIP_TIME_SHORT  = 5
PLAY_DIRECTION = - 1

EPISODE_FILE_PATTERN = "*.xml"

NAMESPACE = "{http://linuxcentre.net/xmlstuff/get_iplayer}"
TICKER = ['-','\\','|','/']


STOPPED = 0
PLAYING = 1
PAUSED = 2

PLAY_MODE_DEFAULT   = 0
PLAY_MODE_FAV_ONLY = 1
play_mode = PLAY_MODE_DEFAULT

#main global variables
current_episode = 0
current_track = 0
current_position = 0
player_status = STOPPED
stdscr = None
main_display = None
debug_display = None
favourited_log_string = None
event_queue = []
mplength = None
freeze_debug_display = False

ep = None                   #the episode database
mp = None                   #the media player device
lcd = None                  #the LCD device

# For use of following var, see  check_and_fix_filename_sync_bug()
fix_filename_counter = 0

def getboolean(mystring):
  return mystring == "True"

def load_config():
    global DEBUG, DEBUG_LOG, BUTTON, LCD, LED, KEYBOARD, SCREEN, HIDE_CURSOR, LINEWIDTH, \
        DISPLAYHEIGHT, UNPRINTABLE_CHAR, DATA_DIRECTORY, FAV_DIRECTORY, \
        DIR_AND_FAVOURITED_LOG_FILE, JB_DATABASE, SHIELD_BUTTON

    # Check for configuration files
    configfile = os.path.join(expanduser("~"), ".junctionbox")
    Config = ConfigParser.ConfigParser()
    if os.path.isfile(configfile):  
        Config.read(configfile)
        if 'basic' in Config.sections():
            confitems = dict(Config.items('basic'))
            if 'debug' in confitems:
                DEBUG = getboolean(confitems['debug'])
            if 'debug_log' in confitems:
                DEBUG_LOG = getboolean(confitems['debug_log'])
            if 'button' in confitems:
                BUTTON = getboolean(confitems['button'])
            if 'shield_button' in confitems:
                SHIELD_BUTTON = getboolean(confitems['shield_button'])                
            if 'lcd' in confitems:
                LCD = getboolean(confitems['lcd'])
            if 'led' in confitems:
                LED = getboolean(confitems['led'])
            if 'keyboard' in confitems:
                KEYBOARD = getboolean(confitems['keyboard'])
            if 'screen' in confitems:
                SCREEN = getboolean(confitems['screen'])
            if 'hide_cursor' in confitems:
                HIDE_CURSOR = getboolean(confitems['hide_cursor'])
            if 'linewidth' in confitems:
                LINEWIDTH = int(confitems['linewidth'])
            if 'displayheight' in confitems:
                DISPLAYHEIGHT = confitems['displayheight']
            if 'unprintable_char' in confitems:
                UNPRINTABLE_CHAR = confitems['unprintable_char']
            if 'data_directory' in confitems:
                DATA_DIRECTORY = confitems['data_directory']
                # Update dependent directories:
                if not('fav_directory' in confitems):
                    FAV_DIRECTORY = DATA_DIRECTORY
                    DIR_AND_FAVOURITED_LOG_FILE = (os.path.join(FAV_DIRECTORY, FAVOURITED_LOG_FILE ))
                if not('jb_database' in confitems):
                    JB_DATABASE = os.path.join(DATA_DIRECTORY, "JB_DATABASE" )
            if 'fav_directory' in confitems:
                FAV_DIRECTORY = confitems['fav_directory']
                DIR_AND_FAVOURITED_LOG_FILE = (os.path.join(FAV_DIRECTORY, FAVOURITED_LOG_FILE ))
            if 'jb_database' in confitems:
                JB_DATABASE = confitems['jb_database']

    else:
        #if there's no config file then copy over the default one
        default_config_file = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), ".junctionbox")

        shutil.copyfile(default_config_file, configfile)

    if (not os.path.isdir(DATA_DIRECTORY)):
        try:
            os.mkdir(DATA_DIRECTORY)
            debug("No data directory found. Creating data directory.")
        except:
            sys.exit("Failed to create DATA_DIRECTORY")
    else:
        debug("DATA_DIRECTORY: "+DATA_DIRECTORY)   

    if (not os.path.isdir(FAV_DIRECTORY)):
        try:
            debug("No FAV directory found.")
            sys.exit("No FAV _DIRECTORY")
        except:
            pass
    else:
        debug("FAV_DIRECTORY: "+FAV_DIRECTORY)   


def configure_hardware():
    global keys, buttons, shield_buttons

    if KEYBOARD:
        #key definitions of the form:
        #key:["description", function]
        keys = {'z':["previous episode", prev_episode],
                'x':["previous track", prev_track],
                ',':["skip back", skip_back_short],
                '<':["jump back", skip_back_long],
                'c':["play/pause", toggle_pause],
                'C':["resync pause status", fix_pause],
                'v':["next track", next_track],
                'b':["next episode", next_episode],
                '>':["jump forward", skip_forward_long],
                '.':["skip forward", skip_forward_short],
                'n':["mark favourite", mark_favourite],
                'm':["change mode", change_mode],
                '/':["adjust track start", adjust_track_start],
                '\\':["adjust track end", adjust_track_end],
                'V':["mute", mute_unmute],
                'q':["quit", quit],
                'Q':["turn off", shutdown],
                'd':["freeze debug display", toggle_debug_freeze],
                '?':["help", help]}


    if BUTTON or LED or LCD or SHIELD_BUTTON:
        """Can only import RPi.GPIO on supported hardware (eg. raspberrypi).
        Trying to import on any other platform causes an error."""
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

    if BUTTON:
        #button definitions of the form:
        #[GPIO_PIN, function]
        buttons = [ [4, prev_episode],
                    [5, prev_track],
                    [6, toggle_pause],
                    [7, next_track],
                    [8, next_episode],
                    [12, mark_favourite]
                  ]

        for button in buttons():
            GPIO.setup(button[0], GPIO.IN, pull_up_down = GPIO.PUD_UP)
            GPIO.add_event_detect(button[0], GPIO.FALLING, 
                                  callback=button[1], bouncetime=300)


    if LCD:
        """Can only import Adafruit_CharLCD on supported hardware as it depends
        on RPi.GPIO""" 
        global lcd
        import Adafruit_CharLCD
        lcd = Adafruit_CharLCD.Adafruit_CharLCDPlate()

    if SHIELD_BUTTON:
        #shield button definitions of the form:
        #[button_code, function, held_function]
        shield_buttons = [ [Adafruit_CharLCD.SELECT, toggle_pause, shutdown],
                           [Adafruit_CharLCD.LEFT, prev_track, None],
                           [Adafruit_CharLCD.UP, prev_episode, mark_favourite],
                           [Adafruit_CharLCD.DOWN, next_episode, None],
                           [Adafruit_CharLCD.RIGHT, next_track, None]
                         ]

    if LED:
        RED_PIN = 17
        GREEN_PIN = 27
        BLUE_PIN = 22

        GPIO.setup(RED_PIN, GPIO.OUT)       #red
        GPIO.setup(GREEN_PIN, GPIO.OUT)     #green
        GPIO.setup(BLUE_PIN, GPIO.OUT)      #blue



###################################################
# Built in key functions                          #
###################################################

def prev_episode(channel=0):
    episode_nav(-1)

def prev_track(channel=0):
    if current_track > -1:
        track_nav(-1)

def skip_back_short():
    skip_time(-SKIP_TIME_SHORT)

def skip_back_long():
        skip_time(-SKIP_TIME_MEDIUM)

def play_pause(channel=0):
    play_pause()

def toggle_pause():
    global player_status

#    debug("Player status in:  "+str(player_status)+" (pl=1, pau=2)")
    if player_status == PLAYING:
        player_status = PAUSED
    else:
        player_status = PLAYING

#    debug("Player status out: "+str(player_status))
    mp.pause()
# If play_pause is rapidly called twice, mp doesn't keep up, hence insert a delay.
# This does cause a delay in the display too. A better way would be to check the time since this fn was last called.
    time.sleep(0.2)


def fix_pause():
    mp.pause()
    time.sleep(0.2)

def next_track(channel=0):
    if current_track < ep.ntracks(current_episode) - 1:
        track_nav(+1)

def next_episode(channel=0):
    episode_nav(+1)

def skip_forward_long():
    skip_time(SKIP_TIME_MEDIUM)

def skip_forward_short():
    skip_time(SKIP_TIME_SHORT)

def mark_favourite(channel=0):
    global favourited_log_string

    logdata = get_fav_log_string(current_episode,current_track)
    ep.setfavourite(current_episode,current_track,not(ep.favourite(current_episode,current_track)))
    if favourited_log_string != None:
        #if the current track has been un-favourited then take it off the log queue
        #if there is another track on the queue then write it to the log file
        if favourited_log_string != logdata:
            log_favourited(favourited_log_string)
        favourited_log_string = None
    else:
        if ep.favourite(current_episode,current_track):
            favourited_log_string = logdata

    show_favourite(ep.favourite(current_episode,current_track))


def change_mode():
    global play_mode
    if play_mode == PLAY_MODE_DEFAULT:
        debug("PLAY_MODE_FAV_ONLY")
        play_mode = PLAY_MODE_FAV_ONLY
    else:
        debug("PLAY_MODE_DEFAULT")
        play_mode = PLAY_MODE_DEFAULT


def adjust_track_start():
    msg = ep.adjust_track_start(current_episode, current_track, mp.time_pos)
    debug(msg)

def adjust_track_end():
    msg = ep.adjust_track_end(current_episode, current_track, mp.time_pos)
    debug(msg)

def mute_unmute():
    debug("current volume: "+str(mp.volume))
    if mp.volume > 0:
        mp.volume = 0
    else:
        # This doesn't work.
        mp.volume = 99.5
    debug("New volume: "+str(mp.volume))

def toggle_debug_freeze():
    global freeze_debug_display
    freeze_debug_display = not(freeze_debug_display)

def help():
    for key in keys:
        debug(str(key) + ": " + keys[key][0])

def quit():
    clean_up()
    sys.exit("JunctionBox exited normally.\nYou listened to: ep="+str(current_episode)+", tr="+str(current_track)+", pos="+format_time(current_position)+", date="+ep.date(current_episode)+"\n"+
             "Continue listening like this: "+ sys.argv[0] + " " + str(current_episode)+" "+str(current_track))

def shutdown():
    clean_up()
    call(["sudo", "shutdown", "now", "-h", "-P"])



###################################################



class Event:
    def __init__(self, name, handlers = []):
        self.name = name
        self.handlers = handlers

    def add_handler(self, proc):
        self.handlers.append(proc)

    def get_handlers(self):
        return self.handlers


class Event_Queue: 
    def __init__(self):
        self.event_queue = []

    def push(self, event):
        self.event_queue.append(event)

    def pop(self):
        self.event_queue



def episode_nav(ep_offset):
    global current_episode

    if (ep_offset > 0):
        disp_str = ">|"
    else:
        disp_str = "|<"

    target_episode = current_episode + ep_offset

    try:
        if target_episode > -1 and target_episode < ep.nepisodes():
            display(disp_str, str(target_episode) + " / " + str(ep.nepisodes()))
            current_episode = target_episode
            play_episode(current_episode)
        else:
            debug("Cannot change episode: "+str(ep_offset))
    except:
        debug("ERROR: Cannot change episode")


def track_nav(track_offset):
    global current_track

    if (track_offset > 0):
        disp_str = ">>"
    elif (track_offset < 0):
        disp_str = "<<"
    else:
        disp_str = "><"

    target_track = current_track + track_offset
        
    try:

        if ep.validtrack(current_episode, target_track):
            current_track = target_track
            display(disp_str, format_track_number(target_track) + " / " + 
                str(ep.ntracks(current_episode)))
            mp.time_pos = ep.start(current_episode, current_track) 
        else:
            current_track = 0
            mp.time_pos = 0
    except:
        debug("Cannot change track. len="+str(ep.ntracks(current_episode))+", current_track="+str(current_track)+", pid="+ep.pid(current_episode)+", date="+ep.date(current_episode))


def skip_time(SKIP_TIME):
    global current_episode
    target_time = mp.time_pos + SKIP_TIME
    if target_time > 0 and target_time < get_episode_length(current_episode) - 2:
        mp.time_pos = target_time
    else:
        debug(str(mp.time_pos) + " " + str(SKIP_TIME) + " " + str(get_episode_length(current_episode)))




def get_fav_log_string(episode,track):
    start_end_time = format_time(ep.start(episode,track))
    if (ep.endseconds(episode,track) > 0):
        start_end_time = start_end_time + "-" + format_time(ep.get_track_end(episode,track))
    cont_etc = ""
    if ep.trackcontributors(episode,track) != "":
        cont_etc = ep.trackcontributors(episode,track) + "\n" 
    if ep.tracketc(episode,track) != "":
        cont_etc = cont_etc + ep.tracketc(episode,track) + "\n"
    data = ep.tracktitle(episode,track) + "\n" + ep.trackartist(episode,track) + "\n" + \
           cont_etc + start_end_time + "\n" + \
           ep.title(episode) + "  " + ep.date(episode) + "\n" + \
           "http://www.bbc.co.uk/programmes/" + ep.pid(episode) + "\n\n"
    return data




def update_position():
    global current_position, current_track

    if player_status == PAUSED:
        return True     #playing normally (not seeking), paused so don't ask for position

    pos = mp.time_pos
    
    #really hacky bit but it seems sometimes mplayer only responds every second call
    if not(isinstance(pos, float)):
        pos = mp.time_pos

    if isinstance(pos, float):

        current_position = pos

        track_index = ep.ntracks(current_episode) - 1
        for i in range(ep.ntracks(current_episode)):
            if ep.start(current_episode, i) > round(current_position):
                track_index = i - 1
                break

        current_track = track_index

        return True     #playing normally
    else:
        return False    #seeking


###################################################
# display and formatting functions                #
###################################################

# track numbers in the database start at zero but are displayed starting from 1.
def format_track_number(track):
    return str(track + 1)


def strip_unprintable_characters(in_string):

    return unidecode(in_string)


def display(line1, line2):

    line1 = strip_unprintable_characters(line1)
    line2 = strip_unprintable_characters(line2)

    line1 = line1[0:LINEWIDTH]
    line2 = line2[0:LINEWIDTH]

    line1 = line1.ljust(LINEWIDTH, " ")
    line2 = line2.ljust(LINEWIDTH, " ")
 
    if lcd != None:
        try:
            lcd.set_cursor(0,0)
            lcd.message(line1 + "\n" + line2)
        except:
            debug("error writing to LCD")
        
    if SCREEN:
        line1 = line1.encode('utf-8')
        line2 = line2.encode('utf-8')

        main_display.addstr(0,0,line1)
        main_display.addstr(1,0,line2)

        main_display.refresh()


def led(red, green, blue):
    if LED:
        import RPi.GPIO as GPIO
        GPIO.output(RED_PIN, 1 - red)
        GPIO.output(GREEN_PIN, 1 - green)
        GPIO.output(BLUE_PIN, 1 - blue)

    elif SCREEN:    #simulate LED on the screen

        colour = red + green * 2 + blue * 4
        if colour == 0:
            char = " "
        else:
            char = "*"    
        stdscr.addstr(0, 22, char, curses.color_pair(colour))

    else:
        #TODO show LED status on the LCD somehow
        pass



class Scroller:
    def __init__(self, left_text, centre_text, right_text, line_size=LINEWIDTH):
        self.left_text = left_text
        self.centre_text = centre_text
        self.right_text = right_text
        self.line_size = line_size
        self.i = 0                  #scrolling index
        self.centre_space = self.line_size - len(self.left_text) - len(self.right_text)

    def scroll(self):
        if len(self.centre_text) > self.centre_space:
            self.centre = (self.centre_text[self.i:self.i+self.centre_space] +
                       ".  "[max(0, self.i-len(self.centre_text)):max(0,self.i + self.centre_space - len(self.centre_text))] +
                       self.centre_text[0:max(0, self.i - (len(self.centre_text) - self.centre_space) - 2)])
                       
            self.i = (self.i + 1) % (len(self.centre_text) + 3)
        else:
            self.centre = self.centre_text.ljust(self.centre_space, " ")

        return self.left_text + self.centre + self.right_text


def format_time(seconds):
    """Formats seconds into a time string of the form:
       mm:ss
       If seconds is large enough it will return:
       hours:mm:ss,  days:hours:mm:ss
    """

    if(seconds == None or seconds < 0):
        return "--:--"

    seconds = int(seconds)
    secs = seconds % 60
    mins = int(seconds / 60) % 60
    hrs = int(seconds / 3600) % 24
    days = int(seconds / 86400)

    time_str = str(mins).rjust(2, "0") + ":" + str(secs).rjust(2, "0")

    if days > 0:
        time_str = str(days) + ":" + str(hrs).rjust(2, "0") + ":" + time_str
    else:
        if hrs > 0:
            time_str = str(hrs) + ":" + time_str

    return time_str


def show_favourite(favourite):
    if favourite:
        led(1, 0, 1)
    else:
        led(0, 0, 0)


def debug(msg, value=""):
    if DEBUG_LOG:
        f = open("logfile.txt","a")
        try:
            f.write(msg+"\n")
            f.write(value+"\n")
        except:
            f.write("OOOPS"+"\n")
        f.close
    if DEBUG and SCREEN and not(freeze_debug_display):
        text = msg

        if value != "":
            text = text + ": " + str(value)

        text = text.encode('utf-8')

        if debug_display != None:
            max_yx = debug_display.getmaxyx()        

            for i in range(0, len(text), max_yx[1]):
                try:
                    debug_display.addstr(max_yx[0]-1,0, text[i:i + max_yx[1]])
                except:
                    try:
                        debug_display.addstr(max_yx[0]-1,0, text[i:i + max_yx[1]].encode('utf-8').strip())
                    except:
                        debug_display.addstr(max_yx[0]-1,0, "debug_display string conversion failed.")
                debug_display.scroll()

            debug_display.hline(0,0, "-", max_yx[1])
            # debug_display.refresh()
        else:
            # if debug_display doesn't (yet) exist, just print to stdout
            print text


###################################################

def play_episode(index):
    global player_status, episode_length, mplength
    
    episode_file = ep.filename(index)

    try:
        mp.loadfile(episode_file)
        #debug("mp.loadfile: "+episode_file)
    except:
        sys.exit("Cannot play " + str(episode_file) + " " + str(index) + ".")
    player_status = PLAYING
    mplength = None

    led(0,0,0)
    line1 = ep.title(index)
    line2 = ep.date(index)

    display(line1, line2)

    episode_length = get_episode_length(index)


def get_episode_length(index):
    global ep, mplength
    if mplength == None:
        mplength = mp.length
        #debug("mplength: "+str(mplength))
    if mplength == None:
        return ep.duration(index)
    else:
        return mplength
    #sometimes mplayer doesn't report back length for a while.
#    while(episode_length == None):
#        episode_length = mp.length

def check_and_fix_filename_sync_bug():
    global current_position, current_track, current_episode
    global fix_filename_counter
    episode_file = ep.filename(current_episode)
    #  This would work if mp.path didn't contain all sorts of random stuff!
    mpfile = mp.path
    expression = r'^\/.*m4a$'
    p = re.compile(expression)
    if not(str(mpfile) == '' or str(mpfile) == episode_file):
        if p.match(mpfile) != None:
            debug("filename_sync_bug. Wrong file playing. Loading episode: "+str(current_episode))
            debug("filename_sync_bug. Current track: " + str(current_track))
            play_episode(current_episode)
            if current_track > -1:
                debug("Seeking to track: " + str(current_track))
                time.sleep(1.5)
                track_nav(0)
        else:
            pass
            # debug("Current track while seeking: " + str(current_track))
    else:
        fix_filename_counter = 0


def seek_next_fav():
    global current_track, current_position
    if not(ep.favourite(current_episode,current_track))  or current_position > ep.get_track_end(current_episode,current_track):
        if not(ep.lasttrack(current_episode,current_track)):
            i = current_track+1
            while (i in range(current_track+1, ep.ntracks(current_episode)-1)) and not ep.favourite(current_episode,i):
                i = i + 1
            if ep.lasttrack(current_episode,i):
                if not ep.favourite(current_episode,i):
                    debug("Favourite mode: go to prev/next episode")
                    if PLAY_DIRECTION == -1:
                        prev_episode()
                    else:
                        next_episode()
                    time.sleep(1.0)
                else:
                    debug("Favourite mode: Skip track to "+ str(i) + " (last track), in "+str(current_episode))
                    current_track = i
                    track_nav(0)
            else:
                debug("Favourite mode: Skip track to "+ str(i) + ", in "+str(current_episode))
                current_track = i
                track_nav(0)
        else:
            debug("Favourite mode: go to prev/next episode")
            if PLAY_DIRECTION == -1:
                prev_episode()
            else:
                next_episode()
            time.sleep(1.0)

def handle_keypress(c):
    global freeze_debug_display

    key_char = chr(c)
    if key_char in keys:
        handler_function = keys[key_char][1]
        handler_function()


#Write a human readable log file of tracks that have been favourited.
#Note: a track is deliberately not removed from the log file if later un-favourited. 
def log_favourited(data):
    f = open(os.path.join(DIR_AND_FAVOURITED_LOG_FILE), "a")
    try:
        f.write(data)
    except:
        debug("Could not write favourite data to logfile!")
    f.close


def episode_loop(launch_track):
    global current_episode,stdscr, main_display, debug_display, favourited_log_string, episode_length
    global current_track, current_position
    global ep

    play_episode(current_episode)
    episode_length = get_episode_length(current_episode)

    seeking = not(update_position())
    ticker_index = 0

    last_track = -2
    last_episode = -2

    scroller1 = None
    scroller2 = None

    led_state = 0

    # Added "-2" here because of "end of track" bug:
    while(current_position < int(episode_length) - 2):

        check_and_fix_filename_sync_bug()
        episode_length = get_episode_length(current_episode)
        if launch_track > -1 and current_position > 0:
            current_track = launch_track
            launch_track = -1
            track_nav(0)
        if play_mode == PLAY_MODE_FAV_ONLY and current_position > 0:
            seek_next_fav()
            #debug("Last track "+str(last_track) + ", " + str(current_track))
        if (last_track != current_track) or (last_episode != current_episode):
            last_track = current_track
            #B: Inserted this, because of issue below, see next try/except block:
            if last_episode != current_episode:
                last_track = -2
                current_track = -1
                current_position = -1
                debug("\nNew episode: "+str(current_episode) + ", pid=" + ep.pid(current_episode)+", date="+ep.date(current_episode))
            last_episode = current_episode
            #episode = episodes[current_episode]
            if current_track < 0:
                scroller1 = Scroller("", ep.title(current_episode), "      ",    line_size=LINEWIDTH)
                scroller2 = Scroller("", ep.date(current_episode), "  ", line_size=LINEWIDTH)
            else:
                track_name = ep.tracktitle(current_episode,current_track)
                artist = ep.trackartist(current_episode,current_track)
                track_no = str(current_track + 1)
                track_prefix  = track_no + " "
                if ep.favourite(current_episode, current_track):
                    track_prefix = track_no + "* "

                scroller1 = Scroller("", artist, "      ", line_size=LINEWIDTH)                
                scroller2 = Scroller(track_prefix, track_name, "  ", line_size=LINEWIDTH)

                try:
                   debug("- Playing track " + str(track_no) + ", in ep=" + str(current_episode)  +  " (" + track_name  + ") "
                          + format_time(ep.start(current_episode,current_track)) + ep.starttype(current_episode,current_track)  
                          + "-" + format_time(ep.get_track_end(current_episode,current_track))+ ep.endtype(current_episode,current_track) )
                          #+ "; " + ep.time_info(current_episode,current_track))
                except:
                   debug("- Playing track " + str(track_no) + ", in ep=" + str(current_episode)  +  " (" + track_name  + ") "  )

                show_favourite(ep.favourite(current_episode,current_track))

                #if there is a track in the log queue when the track changes, log it.
                #tracks can be unfavourited before the track changes.
                if favourited_log_string != None:
                    log_favourited(favourited_log_string)
                    favourited_log_string = None                

        line1 = scroller1.scroll()
        line2 = scroller2.scroll()

        if seeking:
            status = TICKER[ticker_index]
            ticker_index = (ticker_index + 1) % 4
        elif player_status == PLAYING:
            status = ">"
        elif player_status == PAUSED:
            status = "="
        else:
            status = "#"
            

        time_str = format_time(current_position)

        line1_len = LINEWIDTH - len(time_str) - 1
        line2_len = LINEWIDTH - len(status) - 1
        line1 = line1[0:line1_len].ljust(line1_len, " ") + " " + time_str
        line2 = line2[0:line2_len].ljust(line2_len, " ") + " " + status
        
        display (line1, line2)


        if KEYBOARD:
            key = stdscr.getch()
            if key > 0:
                handle_keypress(key)
            #TODO do I really need this? Why does the debug window blank after getch()?
            debug_display.refresh()

        if SHIELD_BUTTON:
            #Shield buttons are not buffered so if shield buttons are enabled checking them
            #is put inside the main idle process. 
            idle_start = time.time()
            while time.time() - idle_start < DISPLAY_REFRESH_TIME:
                for button in shield_buttons:
                    try:
                        if lcd.is_pressed(button[0]):
                            button_start = time.time()
                            button_held_time = 0
                            debug("shield button pressed" + str(button[0]))
                        
                            #wait to see if the button is "held" or not
                            while lcd.is_pressed(button[0]) and button_held_time < BUTTON_HOLD_TIME:
                                button_held_time = time.time() - button_start
                        
                            if button_held_time > BUTTON_HOLD_TIME:
                                function = button[2]    #get the held button handler function
                            else:
                                function = button[1]    #get the normal button handler function
                            
                            if callable(function):
                                function()
                        
                            #if the button is still pressed wait until it is released
                            while lcd.is_pressed(button[0]):
                                pass
                            
                            #debounce button
                            while time.time() - button_start < BUTTON_DEBOUNCE_TIME:
                                pass
                    except:
                        debug("error while checking shield buttons")
                        

        else:
            time.sleep(DISPLAY_REFRESH_TIME)
            
        seeking = not(update_position())
    
    debug("Showlength " + str(episode_length) + " reached")
    current_position = 0


def main_loop(screen):
    global current_episode, stdscr, main_display, debug_display, favourited_log_string, episode_length
    # Surely needs: global current_track
    global current_track
    global ep, JB_DATABASE
    global mp

    mp = mpylayer.MPlayerControl()

    stdscr = screen
    main_display = curses.newwin(DISPLAYHEIGHT + 1,LINEWIDTH,1,0)    
    debug_display = curses.newwin(0, 0, DISPLAYHEIGHT + 2, 0)
    debug_display.scrollok(1)

    if HIDE_CURSOR:
        try:
            curses.curs_set(0)
        except:
            debug("Cannot hide cursor.")
    
    stdscr.nodelay(1)
    #curses.halfdelay(4)
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)
    
    display("Junction", "Box") 
    led(0,0,0)

    ep = EpisodeDatabase.EpisodeDatabase(JB_DATABASE)
    
    if ep.nepisodes() == 0:
        #TODO when episode downloading is moved to junctionbox then it should
        #wait here while downloading instead of exiting. 
        #B: Though in an ideal world it would immediately play the one it's downloading.
        sys.exit("Can't find any episodes to play in "+ JB_DATABASE)

    #current_episode = ep.nepisodes() - 1
    current_episode = ep.nepisodes() - 1
    launch_track = -1
    if (len(sys.argv) > 1):
        current_episode = int(sys.argv[1])
    if (len(sys.argv) > 2):
        launch_track = int(sys.argv[2])
    while current_episode > -1 and current_episode < ep.nepisodes():
        episode_loop(launch_track)
        launch_track = -1
        current_episode =  current_episode + PLAY_DIRECTION


def clean_up():
    global favourited_log_string
    global current_episode, current_track, current_position

    debug("Quitting.")

    # Quit mplayer - do this first, so that there's user feedback to the keypress:
    mp.quit()

    #save anything pending in the favourited log queue before quitting
    if favourited_log_string != None:
        log_favourited(favourited_log_string)
        favourited_log_string = None

    if LCD:
        #clear and turn off backlight when shutting down
        lcd.clear()
        lcd.set_backlight(0)    

    if BUTTON or LED or LCD or SHIELD_BUTTON:
        import RPi.GPIO as GPIO
        GPIO.cleanup()


if __name__ == '__main__':    
    load_config()
    if len(sys.argv) > 1 and sys.argv[1] == "dumppatch":
        ep = EpisodeDatabase.EpisodeDatabase(JB_DATABASE)
        ep.dump_db_patch(sys.argv[2])
        sys.exit("Exitting normally after db operation.")
    if len(sys.argv) > 1 and sys.argv[1] == "applypatch":
        ep = EpisodeDatabase.EpisodeDatabase(JB_DATABASE)
        ep.apply_db_patch(sys.argv[2])
        sys.exit("Exitting normally after db operation.")
    configure_hardware()
    curses.wrapper(main_loop)
    quit()

