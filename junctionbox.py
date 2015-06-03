#!/usr/bin/python

import curses
import mpylayer
import time
import os
import glob
import xml.etree.ElementTree as ET
import re
import pickle
from subprocess import call
import ConfigParser
from os.path import expanduser
import os.path
import sys
import string
import shutil


#Default Options
DEBUG = True             # enables debug print statements
UNPRINTABLE_CHAR = "#"   # character to replace unprintable characters on the display

DATA_DIRECTORY = os.path.join(expanduser("~"), "jb_data")     #Default data directory
# Note: All directories dependent on DATA_DIRECTORY need to be updated in load_config(), because DATA_DIRECTORY can be set in user preferences, see "# Update dependent directories" below.
FAV_DIRECTORY = DATA_DIRECTORY
#TODO remove and search for subdirs instead
EPISODE_DIRECTORY = os.path.join(DATA_DIRECTORY, "Late_Junction")
FAVOURITED_LOG_FILE = "favourited.txt"
DIR_AND_FAVOURITED_LOG_FILE = (os.path.join(FAV_DIRECTORY, FAVOURITED_LOG_FILE ))
FAST_START_CACHE_FILE = os.path.join(DATA_DIRECTORY,"junctionbox_episodes_cache.p")


FAST_START = False       # If 'True' reads cached episode information, as long as cache is not older than:
FAST_START_CACHE_TIME = 24 * 60 * 60  # duration in s for which episode information in cached
BUTTONS =  False         #set to True if buttons are present
LCD =      False         #set to True if there is an LCD screen present
LED =      False         #set to True if there is an RGB LED present
KEYBOARD = True          #set to True if keyboard is present
SCREEN =   True          #set to True if a monitor is present
HIDE_CURSOR = True       # Cursor is hidden by default, but some curses libs don't support it.
LINEWIDTH = 16           # Characters available on display (per line) 
DISPLAYHEIGHT = 2        # Lines available on display

#Navigation options (not in .junctionbox yet)
SKIP_TIME_MEDIUM = 60
SKIP_TIME_SHORT  = 5

EPISODE_FILE_PATTERN = "*.xml"

NAMESPACE = "{http://linuxcentre.net/xmlstuff/get_iplayer}"
TICKER = ['-','\\','|','/']


if BUTTONS or LED:
	import RPi.GPIO as GPIO


if BUTTONS or LED or LCD:
	GPIO.setmode(GPIO.BCM)
	GPIO.setwarnings(False)

if BUTTONS:
	GPIO.setup(4, GPIO.IN, pull_up_down = GPIO.PUD_UP)	#prev episode
	GPIO.setup(5, GPIO.IN, pull_up_down = GPIO.PUD_UP)	#prev track
	GPIO.setup(6, GPIO.IN, pull_up_down = GPIO.PUD_UP)	#play
	GPIO.setup(7, GPIO.IN, pull_up_down = GPIO.PUD_UP)	#next track
	GPIO.setup(8, GPIO.IN, pull_up_down = GPIO.PUD_UP)	#next episode
	GPIO.setup(12, GPIO.IN, pull_up_down = GPIO.PUD_UP)	#favourite

if LED:
	RED_PIN = 17
	GREEN_PIN = 27
	BLUE_PIN = 22

	GPIO.setup(RED_PIN, GPIO.OUT)       #red
	GPIO.setup(GREEN_PIN, GPIO.OUT)     #green
	GPIO.setup(BLUE_PIN, GPIO.OUT)      #blue

STOPPED = 0
PLAYING = 1
PAUSED = 2

#main global variables
intro_offset = 11   #offset in seconds of the start of the music
current_episode = 0
current_track = 0
current_position = 0
episodes = []
player_status = STOPPED
stdscr = None
main_display = None
debug_display = None
favourited_log_queue = None
event_queue = []


def getboolean(mystring):
  return mystring == "True"

def load_config():
    global DEBUG, BUTTONS, LCD, LED, KEYBOARD, SCREEN, HIDE_CURSOR, LINEWIDTH, \
        DISPLAYHEIGHT, UNPRINTABLE_CHAR, DATA_DIRECTORY, FAV_DIRECTORY, EPISODE_DIRECTORY, \
        FAST_START, FAST_START_CACHE_TIME, FAST_START_CACHE_FILE

    # Check for configuration files
    configfile = os.path.join(expanduser("~"), ".junctionbox")
    Config = ConfigParser.ConfigParser()
    if os.path.isfile(configfile):  
        Config.read(configfile)
        if 'basic' in Config.sections():
            confitems = dict(Config.items('basic'))
            if 'debug' in confitems:
                DEBUG = getboolean(confitems['debug'])
            if 'buttons' in confitems:
                BUTTONS = getboolean(confitems['buttons'])
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
                EPISODE_DIRECTORY = os.path.join(DATA_DIRECTORY, "Late_Junction")
                FAST_START_CACHE_FILE = os.path.join(DATA_DIRECTORY,"junctionbox_episodes_cache.p")
                if not('fav_directory' in confitems):
                    FAV_DIRECTORY = DATA_DIRECTORY
                    DIR_AND_FAVOURITED_LOG_FILE = (os.path.join(FAV_DIRECTORY, FAVOURITED_LOG_FILE ))
            if 'fav_directory' in confitems:
                FAV_DIRECTORY = confitems['fav_directory']
                DIR_AND_FAVOURITED_LOG_FILE = (os.path.join(FAV_DIRECTORY, FAVOURITED_LOG_FILE ))
            if 'fast_start' in confitems:
                FAST_START = getboolean(confitems['fast_start'])
            if 'fast_start_cache_time' in confitems:
                FAST_START_CACHE_TIME = int(confitems['fast_start_cache_time'])
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
       

mp = mpylayer.MPlayerControl()

def prev_episode(channel=0):
    global current_episode

    display("|<", str(current_episode + 1) + " / " + str(len(episodes)))
    if current_episode > 0:
        current_episode -= 1
        play_episode(current_episode)


def prev_track(channel=0):
    global current_track

    episode = episodes[current_episode]
  
    track_list = episode['tracks']
    display("<<", str(current_track + 1) + " / " + str(len(track_list)))

    if current_track > 0:
        current_track -= 1
        mp.time_pos = track_list[current_track]['seconds'] + intro_offset
    else:
        current_track = 0
        mp.time_pos = 0


def skip_back(SKIP_TIME):
    if mp.time_pos > SKIP_TIME:
        mp.time_pos = mp.time_pos - SKIP_TIME


def adjust_track_start():
    global current_track
    current_time = mp.time_pos
    newtime = current_time - intro_offset
    if current_track < len(episodes[current_episode]['tracks']) -1:
        # Work out which track boundary we are near:
        currtr_diff = abs( newtime - episodes[current_episode]['tracks'][current_track]['seconds'])
        nexttr_diff = abs( newtime - episodes[current_episode]['tracks'][current_track+1]['seconds'])
        if (currtr_diff < nexttr_diff):
            adjust_track = current_track
        else:
            adjust_track = current_track + 1
    else:
        adjust_track = current_track	    
    time_diff = newtime - episodes[current_episode]['tracks'][adjust_track]['seconds']
    if newtime > 0: 
        episodes[current_episode]['tracks'][adjust_track]['seconds'] = newtime
        # Needs to be made persistent:
        save_data()
	debug("Start time adjusted by "+str(time_diff)+"s, for track "+str(adjust_track+1)+", when playing track "+str(current_track+1)+". Saved to .p file." )

def play_pause(channel=0):
    play_pause()


def skip_forward(SKIP_TIME):
    # What happens when we go over the end?
    mp.time_pos = mp.time_pos + SKIP_TIME


def next_track(channel=0):
    global current_track

    episode = episodes[current_episode]
    track_list = episode['tracks']

    if current_track < len(track_list) - 1:
        current_track += 1
        
    display(">>", str(current_track + 1) + " / " + str(len(track_list)))

    try:
        mp.time_pos = track_list[current_track]['seconds'] + intro_offset
    except:
        debug("Cannot advance track. len="+str(len(track_list))+", current_track="+str(current_track)+", pid="+episode['pid']+", date="+episode['firstbcastdate'])
    

def next_episode(channel=0):
    global current_episode
    
    display(">|", str(current_episode + 1) + " / " + str(len(episodes)))
    if current_episode < len(episodes) - 1:
        current_episode += 1
        play_episode(current_episode)


def mark_favourite(channel=0):
    global favourited_log_queue

    episode = episodes[current_episode] 
    #B/tracks: This 
    track = episode['tracks'][current_track]  #B: Pass by ref vs. pass by value?
    #B/tracks: would be replaced by
    #track = tracks[current_track]
    track['favourite'] = not(track['favourite'])

    if favourited_log_queue != None:
        #if the current track has been un-favourited then take it off the log queue

        #if there is another track on the queue then write it to the log file
        if favourited_log_queue != track:
            log_favourited(favourited_log_queue, episode)


        favourited_log_queue = None
    else:
        if track['favourite']:
            favourited_log_queue = track

    show_favourite(track['favourite'])
    save_data()
    


if BUTTONS:
	GPIO.add_event_detect(4, GPIO.FALLING, callback=prev_episode, bouncetime=300)
	GPIO.add_event_detect(5, GPIO.FALLING, callback=prev_track, bouncetime=300)
	GPIO.add_event_detect(6, GPIO.FALLING, callback=play_pause, bouncetime=300)
	GPIO.add_event_detect(7, GPIO.FALLING, callback=next_track, bouncetime=300)
	GPIO.add_event_detect(8, GPIO.FALLING, callback=next_episode, bouncetime=300)
	GPIO.add_event_detect(12, GPIO.FALLING, callback=mark_favourite, bouncetime=300)


def save_data():
    episode = episodes[current_episode]
    tracks = episode['tracks']
    pid = episode['pid']
    #B/SEGMENTS: reconstructing the location of the .p file from EPISODE_DIRECTORY is not ideal, because episodes may be in several locations.
    pickle.dump(tracks, open(os.path.join(EPISODE_DIRECTORY, pid + ".p"), "wb"))


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

        episode = episodes[current_episode]
        tracks = episode['tracks']

        track_index = len(tracks) - 1
        for i in range(len(tracks)):
            if tracks[i]['seconds'] + intro_offset > pos:
                track_index = i - 1
                break

        current_track = track_index

        return True     #playing normally
    else:
        return False    #seeking


def strip_UNPRINTABLE_CHARacters(in_string):

    out_string = ""

    for s in in_string:
        if s in string.printable:
            out_string = out_string + s
        else:
            out_string = out_string + UNPRINTABLE_CHAR

    return out_string




def display(line1, line2):
    line1 = strip_UNPRINTABLE_CHARacters(line1)
    line2 = strip_UNPRINTABLE_CHARacters(line2)

    line1 = line1[0:LINEWIDTH]
    line2 = line2[0:LINEWIDTH]

 
    line1 = line1.ljust(LINEWIDTH, " ")
    line2 = line2.ljust(LINEWIDTH, " ")
    
    if LCD:
        #TODO screen code
        noop
        
    if SCREEN:
        main_display.addstr(0,0,line1)
        main_display.addstr(1,0,line2)
        main_display.refresh()


def debug(msg, value=""):
    if DEBUG and SCREEN:
        text = msg

        if value != "":
            text = text + ": %s" % value

        if debug_display != None:
            max_yx = debug_display.getmaxyx()        

            for i in range(0, len(text), max_yx[1]):
                debug_display.addstr(max_yx[0]-1,0, text[i:i + max_yx[1]])
                debug_display.scroll()

            debug_display.hline(0,0, "-", max_yx[1])
            # debug_display.refresh()
        else:
            # if debug_display doesn't (yet) exist, just print to stdout
            print text



def get_episodes():
    #Decide whether to use cache or to read from EPISODE_DIR.
    if FAST_START:
        if not(os.path.exists(FAST_START_CACHE_FILE)) or (time.time() - os.path.getmtime(FAST_START_CACHE_FILE) > FAST_START_CACHE_TIME):
            debug("Fast start: Read episodes from EPISODE_DIR ...")
            episodes = load_episodes()
            #If no episodes were loaded, should not write cache file:
            if len(episodes) > 0: 
                debug("Fast start: ... and write to cache: "+FAST_START_CACHE_FILE)
                pickle.dump(episodes, open(FAST_START_CACHE_FILE, "wb"))
            else:
                debug("Fast start: ... no episodes were loaded.")
        else:
            debug("Fast start: Read episodes from cache: "+FAST_START_CACHE_FILE)
            episodes = pickle.load(open(FAST_START_CACHE_FILE, "rb"))
    else:
        episodes = load_episodes()

    return episodes


def load_episodes():
    #open every meta data file and get the media file and a displayable name

    episodes = []
    file_pattern = (os.path.join(EPISODE_DIRECTORY, EPISODE_FILE_PATTERN))

    for metaDataFile in glob.glob(file_pattern):

        tree = ET.parse(metaDataFile)
        root = tree.getroot()

        filename = os.path.join(EPISODE_DIRECTORY,
                   root.find(NAMESPACE + 'fileprefix').text + "." +
                   root.find(NAMESPACE + 'ext').text)

        try:
            pid = root.find(NAMESPACE + 'pid').text
            # firstbcastdate is not in all xml
            firstbcastdate = root.find(NAMESPACE + 'firstbcastdate').text
            channel = root.find(NAMESPACE + 'channel').text
            # "band" is not present in older xml, and not used below, hence removed.
            # brand = root.find(NAMESPACE + 'brand').text
            episode = root.find(NAMESPACE + 'episode').text
        except:
            debug("Error parsing: "+metaDataFile)
            #exception will be raised if node is missing from xml

        #B/tracks: My suggestion is to not load tracks here.
        segment_file_name = os.path.join(EPISODE_DIRECTORY, pid + ".p")
	# The following fails if segment_file_name does not exist! Need to check!
        tracks = get_segments(segment_file_name)

        if len(tracks) == 0:
            debug("No tracks read for "+metaDataFile)

        episodes.append({'filename': filename, 'pid':pid, 'episode': episode,
                        'firstbcastdate': firstbcastdate, 'tracks': tracks})
        #B/SEGMENTS:                     , 'tracksfile': segment_file_name})
        #B/SEGMENTS: Further suggestion would be to construct the segment_file_name once, and save it within episodes.

    episodes.sort(key=lambda ep: ep['firstbcastdate'])

    return episodes        


def get_segments(filename):
    return pickle.load(open(filename, "rb"))


def play_episode(index):
    global player_status
    
    episode = episodes[index]
    #B/tracks: Suggestion is load tracks here into a global var:
    #segment_file_name = os.path.join(EPISODE_DIRECTORY, episode['pid'] + ".p")
    #tracks = get_segments(segment_file_name)
    episode_file = episode['filename']

    mp.loadfile(episode_file)
    player_status = PLAYING

    led(0,0,0)
    line1 = episode['episode']
    line2 = episode['firstbcastdate']

    display(line1, line2)


def play_pause(normal):
    global player_status

#    debug("Player status in:  "+str(player_status)+" (pl=1, pau=2)")
    if normal:
        if player_status == PLAYING:
            player_status = PAUSED
        else:
            player_status = PLAYING
    else:
        pass

#    debug("Player status out: "+str(player_status))
    mp.pause()
# If play_pause is rapidly called twice, mp doesn't keep up, hence insert a delay.
# This does cause a delay in the display too. A better way would be to check the time since this fn was last called.
    time.sleep(0.2)

    
def led(red, green, blue):
    if LED:
        GPIO.output(RED_PIN, 1 - red)
        GPIO.output(GREEN_PIN, 1 - green)
        GPIO.output(BLUE_PIN, 1 - blue)

    elif SCREEN:    #simulate LED on the screen

        colour = red + green * 2 + blue	* 4
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
        self.i = 0
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
    seconds = int(seconds)
    secs = seconds % 60
    mins = (seconds - secs) / 60

    return str(mins).rjust(2, "0") + ":" + str(secs).rjust(2, "0")

def show_favourite(favourite):
    if favourite:
        led(1, 0, 1)
    else:
        led(0, 0, 0)

def mute_unmute():
    debug("current volume: "+str(mp.volume))
    if mp.volume > 0:
        mp.volume = 0
    else:
        # This doesn't work.
        mp.volume = 99.5
    debug("New volume: "+str(mp.volume))

def handle_keypress(c):
#If you add keys, please also add them to '?'
    if c == ord('z'):
        prev_episode()
    elif c == ord('x'):
        prev_track()
    elif c == ord(','):
        skip_back(SKIP_TIME_SHORT)
    elif c == ord('<'):
        skip_back(SKIP_TIME_MEDIUM)
    elif c == ord('c'):
        play_pause(True)
    elif c == ord('C'):
        play_pause(False)
        debug("Play/pause bug fix")
    elif c == ord('v'):
        next_track()
    elif c == ord('b'):        
        next_episode()
    elif c == ord('>'):        
        skip_forward(SKIP_TIME_MEDIUM)
    elif c == ord('.'):
        skip_forward(SKIP_TIME_SHORT)
    elif c == ord('n'):
        mark_favourite()
    elif c == ord('/'):
        adjust_track_start()
    elif c == ord('m'):
        mute_unmute()
    elif c == ord('?'):
        debug("z: prev ep; x: prev tr; c: play/pause; v: next tr; b: next ep; n: fav; m: mute; q: quit; ?: this help; C: play/pause bug fix\n<,>: back/forward some secs, /: adjust track start")
    elif c == ord('q'):
        quit()

#Write a human readable log file of tracks that have been favourited.
#Note: a track is deliberately not removed from the log file if later un-favourited. 
def log_favourited(track, episode):
    f = open(os.path.join(DIR_AND_FAVOURITED_LOG_FILE), "a")
    
    data = track['track'] + "\n" + track['artist'] + "\n" + \
           episode['episode'] + "  " + episode['firstbcastdate'] + "\n" + \
	   "http://www.bbc.co.uk/programmes/" + episode['pid'] + "\n\n"

    f.write(data)
    f.close
    

def main_loop(screen):
    global current_episode, episodes, stdscr, main_display, debug_display, favourited_log_queue

    load_config()

    stdscr = screen
    main_display = curses.newwin(DISPLAYHEIGHT + 1,LINEWIDTH,1,0)    
    debug_display = curses.newwin(0, 0, DISPLAYHEIGHT + 2, 0)
    debug_display.scrollok(1)

    if HIDE_CURSOR:
        try:
            curses.curs_set(0)
        except:
            debug("Cannot hide cursor.")
    
    curses.halfdelay(4)
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)
    
    display("Junction", "Box") 
    led(0,0,0)

    episodes = get_episodes()
    
    if len(episodes) == 0:
        #TODO when episode downloading is moved to junctionbox then it should
        #wait here while downloading instead of exiting. 
        #B: Though in an ideal world it would immediately play the one it's downloading.
        sys.exit("Can't find any episodes to play in "+ DATA_DIRECTORY+ ", "+EPISODE_DIRECTORY)

    current_episode = len(episodes) - 1
    play_episode(current_episode)

    #sometimes mplayer doesn't report back length for a while.
    show_length = None
    while(show_length == None):
        show_length = mp.length

    seeking = not(update_position())
    ticker_index = 0

    last_track = -2
    last_episode = -2

    scroller1 = None
    scroller2 = None

    led_state = 0

    while(current_position < show_length):

        if (last_track != current_track) or (last_episode != current_episode):
            last_episode = current_episode
            last_track = current_track
            episode = episodes[current_episode]
            if current_track < 0:
                scroller1 = Scroller("", episode['episode'], "      ",    line_size=LINEWIDTH)
                scroller2 = Scroller("", episode['firstbcastdate'], "  ", line_size=LINEWIDTH)
            else:
                track = episode['tracks'][current_track]
                artist = track['artist']
                scroller1 = Scroller("", artist, "      ", line_size=LINEWIDTH)
                
                track_no = str(current_track + 1) + " "
                track_name =  track['track']
                scroller2 = Scroller(track_no, track_name, "  ", line_size=LINEWIDTH)

                show_favourite(track['favourite'])

                #if there is a track in the log queue when the track changes, log it.
                #tracks can be unfavourited before the track changes.
                if favourited_log_queue != None:
                    log_favourited(favourited_log_queue, episode)
                    favourited_log_queue = None                



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
            

        line2 = line2[0:LINEWIDTH-2].ljust(LINEWIDTH-2, " ") + " " + status
        line1 = line1[0:LINEWIDTH-6].ljust(LINEWIDTH-6, " ") + " " + format_time(current_position)
        
        display (line1, line2)

        if KEYBOARD:
            handle_keypress(stdscr.getch())
            #TODO do I really need this? Why does the debug window blank after getch()?
            debug_display.refresh()
        else:
            time.sleep(0.4)
            
        seeking = not(update_position())


def quit():
    global favourited_log_queue
    global current_episode, current_track, current_position

    debug("Quitting.")

    # Quit mplayer - do this first, so that there's user feedback to the keypress:
    mp.quit()

    #save anything pending in the favourited log queue before quitting
    if favourited_log_queue != None:
        log_favourited(favourited_log_queue, episodes[current_episode])
        favourited_log_queue = None

    if BUTTONS or LED or LCD:
	GPIO.cleanup()

    #B/tracks: This is needed because favourites setting modifies 'episodes'. If tracks were loaded per episode, this would not be needed:
    if FAST_START:
        debug("FAST_START: Writing cache file.")
        pickle.dump(episodes, open(FAST_START_CACHE_FILE, "wb"))

    sys.exit("JunctionBox exited normally.\nYou listened to: ep="+str(current_episode)+", tr="+str(current_track)+", pos="+format_time(current_position)+", date="+episodes[current_episode]['firstbcastdate']+".\n")


if __name__ == '__main__':
    curses.wrapper(main_loop)

