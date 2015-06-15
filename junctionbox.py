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
import json

#Default Options
DEBUG = True             # enables debug print statements to screen
DEBUG_LOG = False        # enables debug print statements logged to file
UNPRINTABLE_CHAR = "#"   # character to replace unprintable characters on the display

DATA_DIRECTORY = os.path.join(expanduser("~"), "jb_data")     #Default data directory
# Note: All directories dependent on DATA_DIRECTORY need to be updated in load_config(), because DATA_DIRECTORY can be set in user preferences, see "# Update dependent directories" below.
FAV_DIRECTORY = DATA_DIRECTORY
JB_DATABASE = os.path.join(DATA_DIRECTORY, "JB_DATABASE" )
FAVOURITED_LOG_FILE = "favourited.txt"
DIR_AND_FAVOURITED_LOG_FILE = (os.path.join(FAV_DIRECTORY, FAVOURITED_LOG_FILE ))

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
PLAY_DIRECTION = - 1

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

PLAY_MODE_DEFAULT   = 0
PLAY_MODE_FAV_ONLY = 1
play_mode = PLAY_MODE_DEFAULT

#main global variables
current_episode = 0
current_track = 0
current_position = 0
# episodes = []
player_status = STOPPED
stdscr = None
main_display = None
debug_display = None
favourited_log_string = None
event_queue = []
ep = None
mp = None
mplength = None

# For use of following var, see  check_and_fix_filename_sync_bug()
fix_filename_counter = 0

def getboolean(mystring):
  return mystring == "True"

def load_config():
    global DEBUG, DEBUG_LOG, BUTTONS, LCD, LED, KEYBOARD, SCREEN, HIDE_CURSOR, LINEWIDTH, \
        DISPLAYHEIGHT, UNPRINTABLE_CHAR, DATA_DIRECTORY, FAV_DIRECTORY, \
        DIR_AND_FAVOURITED_LOG_FILE, JB_DATABASE

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


class Episodes_Database:
# Some brief documentation:

# nepisodes(): Returns number of episodes avaialble.

# title(current_episode): Returns the title of the current_episode
# pid(current_episode): Returns the pid of the current_episode
# filename(current_episode): Returns the full path/filename of the current_episode
# date(current_episode): Returns the firstbcastdate of the current_episode
# ntracks(current_episode):  Returns the number of tracks in the current_episode
# firstepisode(current_episode): True if current_episode is the first episode
# lastepisode(current_episode): True if current_episode is the last episode

# tracktitle(current_episode, current_track): Title of current_track in current_episode
# trackartist(current_episode, current_track): Artist of current_track in current_episode
# firsttrack(current_episode, current_track): True if current_track is the first track in current_episode
# lasttrack(current_episode, current_track): True if current_track is the last track in current_episode
# favourite(current_episode, current_track): Favourite status of current_track in current_episode
# start(current_episode, current_track): Start time in seconds of current_track in current_episode
# endseconds(current_episode, current_track): End time in seconds of current_track in current_episode (-1 by default)
# setfavourite(current_episode, current_track, favourite): Set favourite status of current_track in current_episode to favourite
# setstart(current_episode, current_track, seconds): Set start time of current_track in current_episode to seconds
# setend(current_episode, current_track, seconds): Set end time of current_track in current_episode to seconds

# dump_db_patch(outfile): Export user-modified data from db to outfile.
# apply_db_patch(infile): Import data from infile to db.

    # Class-level variable to stop concurrent write access.
    write_access = False

    def __init__(self, DB_Location):
        self.status = 0
        self.location = DB_Location
        self.episodes = None
        self.tracks = None
        # Check whether the given location exists:
        if not(os.path.isdir(self.location)):
            sys.exit("Exception in Episode_Database: Directory not found at " + self.location)
#	self.locIndex = os.path.join(self.location+"index.p")
#        if not(os.path.isfile(self.locIndex)):
#            sys.exit("Exception in Episode_Database: No db information avaialble")
#        try:
#            self.index = pickle.load(open(self.locIndex, "rb"))
#            try:
#                if not(self.index['version'] == 0):
#                    sys.exit("Exception in Episode_Database: Wrong db version")
#            except:
#                sys.exit("Exception in Episode_Database: Error with index contents")
#        except:
#            sys.exit("Exception in Episode_Database: Error reading index")
        # Check whether the main database file exists:
	self.locEpisodes = os.path.join(self.location, "episodes.p")
        if not(os.path.isfile(self.locEpisodes)):
            sys.exit("Exception in Episode_Database: No data")
        # Try to load the main database file:
        try:
            self.episodes = pickle.load(open(self.locEpisodes, "rb"))
        except:
            sys.exit("Exception in Episode_Database: Error reading data")
	self.locTracks = os.path.join(self.location, "tracks")
        # Check whether the tracks directory exists:
        if not(os.path.isdir(self.locTracks)):
            sys.exit("Exception in Episode_Database: No tracks data")
	self.loadedtrackpid = ""

    def format_time(self,seconds):
        if (seconds == -1):
            return "--:--"
        seconds = int(seconds)
        secs = seconds % 60
        mins = (seconds - secs) / 60
        return str(mins).rjust(2, "0") + ":" + str(secs).rjust(2, "0")


    def nepisodes(self):
        return len(self.episodes)

    def validepisode(self, current_episode):
        if current_episode > -1 and current_episode < self.nepisodes():
            return True
        else:
            return False

    def duration(self, current_episode):
        if self.validepisode(current_episode):
            return self.episodes[current_episode]['duration']
        else:
            return None

    def firstepisode(self, current_episode):
        if self.validepisode(current_episode):
            if current_episode == 0:
                return True
            else:
                return False
        else:
            return None

    def lastepisode(self, current_episode):
        if self.validepisode(current_episode):
            if current_episode == self.nepisodes() - 1:
                return True
            else:
                return False
        else:
            return None

    def title(self, current_episode):
        if self.validepisode(current_episode):
            return self.episodes[current_episode]['episode']    
        else:
            return None

    def pid(self, current_episode):
        if self.validepisode(current_episode):
            return self.episodes[current_episode]['pid']    
        else:
            return None

    def filename(self, current_episode):
        if self.validepisode(current_episode):
            return self.episodes[current_episode]['filename']    
        else:
            sys.exit("File name for "+str(current_episode) + " out of " + str(self.nepisodes()) + " not found.")
            return None

    def date(self, current_episode):
        if self.validepisode(current_episode):
            return self.episodes[current_episode]['firstbcastdate']    
        else:
            return None

    def _trackfile(self, current_episide):
        #return os.path.join(self.locTracks, self.pid(current_episide) + ".p")
        return os.path.join(self.locTracks, self.pid(current_episide) + ".json")

    def _loadtracks(self,  current_episode):
        if self.validepisode(current_episode):
            if not(self.loadedtrackpid == self.pid(current_episode)):
	        if os.path.isfile(self._trackfile(current_episode)):
                    #self.tracks = pickle.load(open(self._trackfile(current_episode),"rb"))
#                    with open(self._trackfile(current_episode), 'r') as infile:
#                        self.tracks = json.load(infile)
                    f = open(self._trackfile(current_episode), 'r')
                    json_playlist_string = f.read()
                    f.close()
                    self.tracks = json.loads(json_playlist_string)
                    self.loadedtrackpid = self.pid(current_episode)
                    return True
                else:
                    self.tracks = None
                    self.loadedtrackpid = None
                    return False
	    else:
                return True
        else:
           return None

    def _savetracks(self,  current_episode):
        #pickle.dump(self.tracks, open(self._trackfile(current_episode), "wb"))
        with open(self._trackfile(current_episode), 'w') as outfile:
            json.dump(self.tracks, outfile, indent=4)

    def ntracks(self,  current_episode):
        self._loadtracks(current_episode)
        return len(self.tracks)

    def firsttrack(self, current_episode, current_track):
        self._loadtracks(current_episode)
        if self.validtrack(current_episode, current_track):
            if current_track == 0:
                return True
            else:
                return False
        else:
            return None

    def lasttrack(self, current_episode, current_track):
        self._loadtracks(current_episode)
        if self.validtrack(current_episode, current_track):
            if current_track == self.ntracks(current_episode) - 1:
                return True
            else:
                return False
        else:
            return None

    def validtrack(self, current_episode, current_track):
        self._loadtracks(current_episode)
        if self.validepisode(current_episode) and current_track > -1 and current_track < self.ntracks(current_episode):
            return True
        else:
            return None

    def trackid(self, current_episode, current_track):
        self._loadtracks(current_episode)
        if self.validtrack(current_episode, current_track):
            if 'id' in self.tracks[current_track]:
                return self.tracks[current_track]['id']
            else:
                return ""
        else:
            return None

    def tracktitle(self, current_episode, current_track):
        if self.validtrack(current_episode, current_track):
            self._loadtracks(current_episode)
            if 'title' in self.tracks[current_track]:
                if self.tracks[current_track]['title'] != "":
                    return self.tracks[current_track]['title']
                else:
                    return self.tracks[current_track]['track']
            else:
                return self.tracks[current_track]['track']
        else:
            return None

    def trackartist(self, current_episode, current_track):
        if self.validtrack(current_episode, current_track):
            self._loadtracks(current_episode)
            return self.tracks[current_track]['artist']
        else:
            return None

    def trackcontributors(self, current_episode, current_track):
        if self.validtrack(current_episode, current_track):
            self._loadtracks(current_episode)
            return self.tracks[current_track]['contributors']
        else:
            return None

    def tracketc(self, current_episode, current_track):
        if self.validtrack(current_episode, current_track):
            self._loadtracks(current_episode)
            return self.tracks[current_track]['etc']
        else:
            return None

    def start(self, current_episode, current_track):
        if self.validtrack(current_episode, current_track):
            self._loadtracks(current_episode)
#            divres = divmod(self.tracks[current_track]['seconds'], 60)
#            if divres[1] != 0:
#                return self.tracks[current_track]['seconds']
            if 'mystart' in self.tracks[current_track]:
                if self.tracks[current_track]['mystart'] >= 0:
                    return self.tracks[current_track]['mystart']
            if 'start' in self.tracks[current_track]:
                if self.tracks[current_track]['start'] >= 0:
                    return self.tracks[current_track]['start']
            return self.tracks[current_track]['seconds']
        else:
            return None

    def mystart(self, current_episode, current_track):
        if self.validtrack(current_episode, current_track):
            self._loadtracks(current_episode)
            if 'mystart' in self.tracks[current_track]:
                if self.tracks[current_track]['mystart'] > -1:
                    return self.tracks[current_track]['mystart']
                else:
                    return -1
            return -1
        else:
            return None

    def starttype(self, current_episode, current_track):
        if self.validtrack(current_episode, current_track):
            self._loadtracks(current_episode)
            if 'mystart' in self.tracks[current_track]:
                if self.tracks[current_track]['mystart'] != -1:
                    return "*"
            if 'start' in self.tracks[current_track]:
                return ""
            return "~"
        else:
            return None

    def endtype(self, current_episode, current_track):
        if ep.endseconds(current_episode, current_track) > 0:
            return "*"
        else:
            return ""

    def time_info(self, current_episode, current_track):
        if self.validtrack(current_episode, current_track):
            self._loadtracks(current_episode)
            return self.format_time(self.tracks[current_track]['start']) + \
                   "/" + self.format_time(self.tracks[current_track]['mystart']) + \
                   "/" + self.format_time(self.tracks[current_track]['seconds']) + \
                  " - " + self.format_time(self.endseconds(current_episode,current_track) )
            # return self.format_time(self.tracks[current_track]['seconds']) + \
            #        "/" + self.format_time(self.tracks[current_track]['mystart']) + \
            #        "/" + self.format_time(self.tracks[current_track]['start']) + \
            #       " - " + self.format_time(self.endseconds(current_episode,current_track) )
        else:
            return "--/--"

    # Could be renamed to "end"
    def endseconds(self, current_episode, current_track):
        if self.validtrack(current_episode, current_track):
            self._loadtracks(current_episode)
            if not('ends' in self.tracks[current_track]):
                return -1
            else:
                return self.tracks[current_track]['ends']
        else:
            return None

    def favourite(self, current_episode, current_track):
        if self.validtrack(current_episode, current_track):
            self._loadtracks(current_episode)
            return self.tracks[current_track]['favourite']
        else:
            return None

    def setstart(self, current_episode, current_track, seconds):
        if self.write_access:
            sys.exit("Concurrent write to DB not supported.")
        self.write_access = True
        if self.validtrack(current_episode, current_track):
            self._loadtracks(current_episode)
            self.tracks[current_track]['mystart'] = seconds
            self._savetracks(current_episode)
            self.write_access = False
	    return True
        else:
            self.write_access = False
            return False

    def setend(self, current_episode, current_track, seconds):
        if self.write_access:
            sys.exit("Concurrent write to DB not supported.")
        self.write_access = True
        if self.validtrack(current_episode, current_track):
            self._loadtracks(current_episode)
            self.tracks[current_track]['ends'] = seconds
            self._savetracks(current_episode)
            self.write_access = False
	    return True
        else:
            self.write_access = False
            return False

    def setfavourite(self, current_episode, current_track, favourite):
        if self.write_access:
            sys.exit("Concurrent write to DB not supported.")
        self.write_access = True
        if self.validtrack(current_episode, current_track):
            self._loadtracks(current_episode)
            self.tracks[current_track]['favourite'] = favourite
            self._savetracks(current_episode)
            self.write_access = False
	    return True
        else:
            self.write_access = False
            return False

    def addtrack(self, current_episode, current_track, title, artist, seconds):
        if self.write_access:
            sys.exit("Concurrent write to DB not supported.")
        self.write_access = True
        if self.validtrack(current_episode, current_track):
            self._loadtracks(current_episode)
            self.tracks.append({'track': track, 'artist':artist, 'seconds': seconds})
	    self.tracks.sort(key=lambda tr: tr['seconds'])
            self._savetracks(current_episode)
            self.write_access = False


    def dump_db_patch(self,outfile):
        # Self-contained example to list whole database.
        updates = []
        upd = {}
        for i in range(self.nepisodes()):
            try:
                print str(i) + " " + self.title(i) + " " + self.date(i)
            except:
                print str(i) + " ENCODING_ERROR " + self.date(i)
            updates = []
            for j in range(self.ntracks(i)):
                pid = self.pid(i)
                # print "    " + str(i) + " " + str(self.mystart(i,j)) + " " +  str(self.favourite(i,j)) + " " + str(self.endseconds(i,j))
                if (self.mystart(i,j) > -1 or self.favourite(i,j) or self.endseconds(i,j) > -1):
                    update = {}
                    update['pid'] = self.pid(i)
                    update['epno'] = i
                    update['trackno'] = j
                    update['title'] =  self.tracktitle(i,j)
                    update['artist'] = self.trackartist(i,j)
                    update['id'] = self.trackid(i,j)
                    if self.mystart(i,j) > -1:
                        update['mystart'] = self.mystart(i,j)
                    if self.endseconds(i,j) > -1:
                        update['end'] = self.endseconds(i,j)
                    if self.favourite(i,j): 
                        update['favourite'] = self.favourite(i,j)
                    # update = { 'pid':  self.pid(i), 'epno': i, 'start': self.start(i,j) ,
                    #               'end': get_track_end(i,j) ,
                    #               'starttype': self.starttype(i,j) ,
                    #               'endtype': self.endtype(i,j) ,
                    #               'favourite': self.favourite(i,j),
                    #               'trackno': j,
                    #               'title': self.tracktitle(i,j) ,
                    #               'artist': self.trackartist(i,j) }
                    updates.append(update)
                    try:
                        print "  (" + str(j) + ") " + str(self.favourite(i,j)) + " " + format_time(self.start(i,j)) + self.starttype(i,j) + "-" + format_time(self.get_track_end(i,j)) + self.endtype(i,j) + " " + self.tracktitle(i,j) + " - " + self.trackartist(i,j)
                    except:
                        print "  (" + str(j) + ") " + str(self.favourite(i,j)) + " " + format_time(self.start(i,j)) + "-" + format_time(self.get_track_end(i,j)) 
	    if len(updates) > 0:
                upd[pid] =  updates 

        with open(outfile, 'w') as ofile:
            json.dump(upd, ofile, indent=4)
        print "Done."

    def apply_db_patch(self,infile):
        upd = {}
        with open(infile, 'r') as ifile:
            upd = json.load(ifile)
        for pid in upd:
            print pid
            updates = upd[pid]
            for update in updates:
                i = update['epno']
                j = update['trackno']
                try:
                    print "  " + str(self.tracktitle(i,j)) + ",  " + str(self.trackartist(i,j)) + " = " + str(update['title']) + ",  " + str(update['artist'])
                except:
                    print "  " + str(i) + ",  " + str(j) + ", title not printable"
                if not ('id' in update):
                    update['id'] = self.trackid(i,j)
                if (self.tracktitle(i,j) == update['title'] and self.trackartist(i,j) == update['artist'] and update['id'] == self.trackid(i,j) and update['pid'] == self.pid(i)):
                    if 'mystart' in update:
                        if self.mystart(i,j) == -1:
                            self.setstart(i,j, update['mystart'])
                            print "        mystart updated."
                        else:
                            if update['mystart'] != self.mystart(i,j):
                                print "        ERROR: Update of mystart failed because it was already set: " + str(self.mystart(i,j))
                            else:
                                print "        ok update of mystart: " + str(self.mystart(i,j))
                    if 'end' in update:
                        if self.endseconds(i,j) == -1:
                            self.setend(i,j, update['end'])
                            print "        mystart updated."
                        else:
                            if update['end'] != self.endseconds(i,j):
                                print "        ERROR: Update of end failed because it was already set: "  + str(self.endseconds(i,j))
                            else:
                                print "        ok update of end: " + str(self.endseconds(i,j))
                    if 'favourite' in update:
                        if self.favourite(i,j) != update['favourite']:
                            self.setfavourite(i,j, update['favourite'])
                            print "        favourite updated: " + str(update['favourite']) + " " + str(self.favourite(i,j))
                        else:
                            if update['favourite'] != self.favourite(i,j):
                                print "        ERROR: Update of favourite failed because it was already set: "  + str(self.favourite(i,j))
                            else:
                                print "        ok update of fav: " + str(self.favourite(i,j))
                else:
                    print "        ERROR: TRACK UPDATE FAILED because metadata didn't match: " + str(update['id']) + "=" + str(self.trackid(i,j)) + ", " + str(update['pid']) + "=" + str(self.pid(i))
        print "Done."

    def get_track_end(self,current_episode, current_track):
        if current_track == -1:
            return self.start(current_episode, current_track+1)
        if self.endseconds(current_episode, current_track) > 0:
            return self.endseconds(current_episode, current_track)
        if self.lasttrack(current_episode, current_track):        
            return self.duration(current_episode)
        return self.start(current_episode, current_track+1)

def prev_episode(channel=0):
    global current_episode

    display("|<", str(current_episode + 1) + " / " + str(ep.nepisodes()))
    if not(ep.firstepisode(current_episode)):
        current_episode -= 1
        play_episode(current_episode)

def prev_track(channel=0):
    global current_track

    display("<<", str(current_track + 1) + " / " + str(ep.ntracks(current_episode)))

    if not(ep.firsttrack(current_episode,current_track)):
        current_track -= 1
        mp.time_pos = ep.start(current_episode, current_track) 
    else:
        current_track = 0
        mp.time_pos = 0


def skip_back(SKIP_TIME):
    if mp.time_pos > SKIP_TIME:
        mp.time_pos = mp.time_pos - SKIP_TIME


def adjust_track_start():
    global current_track
    current_time = mp.time_pos
    newtime = current_time 
    if current_track == - 1:
        adjust_track = current_track + 1
    else: 
        if current_track == ep.ntracks(current_episode) - 1:
            adjust_track = current_track
        else:
            # Work out which track boundary we are near:
            currtr_diff = abs( newtime - ep.start(current_episode, current_track))
            nexttr_diff = abs( newtime - ep.start(current_episode, current_track+1))
            if (currtr_diff < nexttr_diff):
                adjust_track = current_track
            else:
                adjust_track = current_track + 1
    time_diff = newtime - ep.start(current_episode, adjust_track)
    oldtime = ep.start(current_episode, adjust_track)
    if newtime > 0: 
        ep.setstart(current_episode, adjust_track, newtime)
	debug("    Start time adjusted by "+str(time_diff)+"s, from "+format_time(oldtime) + " to " + format_time(newtime) + ", for track "+str(adjust_track+1)+", when playing track "+str(current_track+1)+". Saved to db." )

def adjust_track_end():
    global current_track
    current_time = mp.time_pos
    newtime = current_time 
    if current_track > -1 and current_track < ep.ntracks(current_episode):
        if current_track == ep.ntracks(current_episode) - 1:
            adjust_track = current_track
        else:
            if current_track == - 1:
                adjust_track = current_track + 1
            else:
                # If we are just into the next track, still adjust the previous track...
                if newtime + 5 < ep.start(current_episode, current_track+1):
                    adjust_track = current_track
                else:
                    adjust_track = current_track + 1
        time_diff = newtime - ep.endseconds(current_episode, adjust_track)
        oldtime_raw = ep.endseconds(current_episode, adjust_track)
        oldtime = ep.get_track_end(current_episode, adjust_track)
	if oldtime_raw == oldtime:
            infostr = "*"
        if newtime > 0: 
            ep.setend(current_episode, adjust_track, newtime)
	    debug("    End time adjusted by "+str(time_diff)+"s, from "+format_time(oldtime) + " to " + format_time(newtime) + ", for track "+str(adjust_track)+". Saved to db." )


def play_pause(channel=0):
    play_pause()


def skip_forward(SKIP_TIME):
    # What happens when we go over the end?
    global current_episode
    get_show_length(current_episode)
    if mp.time_pos + SKIP_TIME < get_show_length(current_episode):
        mp.time_pos = mp.time_pos + SKIP_TIME


def next_track(channel=0):
    global current_track

    if not(ep.lasttrack(current_episode, current_track)):
        current_track += 1

    #debug(">>" + str(current_track + 1) + " / " +  str(ep.ntracks(current_episode)))
    display(">>", str(current_track + 1) + " / " +  str(ep.ntracks(current_episode)))

    try:
        mp.time_pos = ep.start(current_episode, current_track) 
    except:
        debug("Cannot advance track. len="+str(ep.ntracks(current_episode))+", current_track="+str(current_track)+", pid="+ep.pid(current_episode)+", date="+ep.date(current_episode))

def this_track(channel=0):
    global current_track

    if not(ep.validtrack(current_episode, current_track)):
        current_track = -1
    else:       
        display("><", str(current_track + 1) + " / " +  str(ep.ntracks(current_episode)))
        try:
            mp.time_pos = ep.start(current_episode, current_track) 
        except:
            debug("Cannot seek to track. len="+str(ep.ntracks(current_episode))+", current_track="+str(current_track)+", pid="+ep.pid(current_episode)+", date="+ep.date(current_episode))
    

def next_episode(channel=0):
    global current_episode
    
    display(">|", str(current_episode + 1) + " / " + str(ep.nepisodes()))
    if not(ep.lastepisode(current_episode)):
        current_episode += 1
        play_episode(current_episode)


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


if BUTTONS:
	GPIO.add_event_detect(4, GPIO.FALLING, callback=prev_episode, bouncetime=300)
	GPIO.add_event_detect(5, GPIO.FALLING, callback=prev_track, bouncetime=300)
	GPIO.add_event_detect(6, GPIO.FALLING, callback=play_pause, bouncetime=300)
	GPIO.add_event_detect(7, GPIO.FALLING, callback=next_track, bouncetime=300)
	GPIO.add_event_detect(8, GPIO.FALLING, callback=next_episode, bouncetime=300)
	GPIO.add_event_detect(12, GPIO.FALLING, callback=mark_favourite, bouncetime=300)


def update_position():
    global current_position, current_track

    if player_status == PAUSED:
        #debug("Paused.")
        return True     #playing normally (not seeking), paused so don't ask for position

    #debug("Not Paused.")
    pos = mp.time_pos
    
    #really hacky bit but it seems sometimes mplayer only responds every second call
    if not(isinstance(pos, float)):
        pos = mp.time_pos

    if isinstance(pos, float):

        current_position = pos

        track_index = ep.ntracks(current_episode) - 1
        for i in range(ep.ntracks(current_episode)):
            if ep.start(current_episode, i ) > pos:
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
    if DEBUG_LOG:
        f = open("logfile.txt","a")
        try:
            f.write(msg+"\n")
            f.write(value+"\n")
        except:
            f.write("OOOPS"+"\n")
        f.close
    if DEBUG and SCREEN:
        text = msg

        if value != "":
            text = text + ": %s" % value

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


def play_episode(index):
    global player_status, show_length, mplength
    
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

    show_length = get_show_length(index)


def get_show_length(index):
    global ep, mplength
    if mplength == None:
        mplength = mp.length
        #debug("mplength: "+str(mplength))
    if mplength == None:
        return ep.duration(index)
    else:
        return mplength
    #sometimes mplayer doesn't report back length for a while.
#    while(show_length == None):
#        show_length = mp.length

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
                this_track()
        else:
            pass
            # debug("Current track while seeking: " + str(current_track))
        # if fix_filename_counter > 3:
        #     debug("filename_sync_bug. hit="+str(fix_filename_counter))
        #     debug("-->"+mpfile)
        #     debug("-->"+episode_file)
        # fix_filename_counter += 1
        # if fix_filename_counter > 5:
        #     debug("Wrong file playing. Loading episode: "+str(current_episode))
        #     play_episode(current_episode)
        #     fix_filename_counter = 0
    else:
        fix_filename_counter = 0


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

def change_mode():
    global play_mode
    if play_mode == PLAY_MODE_DEFAULT:
        debug("PLAY_MODE_FAV_ONLY")
        play_mode = PLAY_MODE_FAV_ONLY
    else:
        debug("PLAY_MODE_DEFAULT")
        play_mode = PLAY_MODE_DEFAULT

def seek_next_fav():
    global current_track
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
                    this_track()
            else:
                debug("Favourite mode: Skip track to "+ str(i) + ", in "+str(current_episode))
                current_track = i
                this_track()
        else:
            debug("Favourite mode: go to prev/next episode")
            if PLAY_DIRECTION == -1:
                prev_episode()
            else:
                next_episode()
            time.sleep(1.0)

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
    elif c == ord('m'):
        change_mode()
    elif c == ord('/'):
        adjust_track_start()
    elif c == ord('\\'):
        adjust_track_end()
    elif c == ord('V'):
        mute_unmute()
    elif c == ord('?'):
        debug("z: prev ep; x: prev tr; c: play/pause; v: next tr; b: next ep; n: fav; V: mute; q: quit; ?: this help; C: play/pause bug fix\n<,>: back/forward some secs, /: adjust track startm \\: adjust track end, m: play mode")
    elif c == ord('q'):
        quit()

#Write a human readable log file of tracks that have been favourited.
#Note: a track is deliberately not removed from the log file if later un-favourited. 
def log_favourited(data):
    f = open(os.path.join(DIR_AND_FAVOURITED_LOG_FILE), "a")
    try:
        f.write(data)
    except:
        debug("Could not write favourite data to logfile!")
    f.close

    

def main_loop(screen):
    global current_episode, stdscr, main_display, debug_display, favourited_log_string, show_length
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

    ep = Episodes_Database(JB_DATABASE)
    
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
        play_and_display(launch_track)
        current_episode =  current_episode + PLAY_DIRECTION
    quit()


def play_and_display(launch_track):
    global current_episode,stdscr, main_display, debug_display, favourited_log_string, show_length
    global current_track, current_position
    global ep

    play_episode(current_episode)
    show_length = get_show_length(current_episode)

    seeking = not(update_position())
    ticker_index = 0

    last_track = -2
    last_episode = -2

    scroller1 = None
    scroller2 = None

    led_state = 0

    # Added "-2" here because of "end of track" bug:
    while(current_position < int(show_length) - 2):

        check_and_fix_filename_sync_bug()
        show_length = get_show_length(current_episode)
        if launch_track > -1 and current_position > 0:
            current_track = launch_track
            launch_track = -1
            this_track()
        if play_mode == PLAY_MODE_FAV_ONLY:
            seek_next_fav()
            #debug("Last track "+str(last_track) + ", " + str(current_track))
        if (last_track != current_track) or (last_episode != current_episode):
            last_track = current_track
            #B: Inserted this, because of issue below, see next try/except block:
	    if last_episode != current_episode:
                last_track = -2
                current_track = -1
                debug("\nNew episode: "+str(current_episode) + ", pid=" + ep.pid(current_episode)+", date="+ep.date(current_episode))
            last_episode = current_episode
            #episode = episodes[current_episode]
            if current_track < 0:
                scroller1 = Scroller("", ep.title(current_episode), "      ",    line_size=LINEWIDTH)
                scroller2 = Scroller("", ep.date(current_episode), "  ", line_size=LINEWIDTH)
            else:
                track_name = ep.tracktitle(current_episode,current_track)
                artist = ep.trackartist(current_episode,current_track)
                track_no  = str(current_track + 1) + " "
                try:
                    scroller1 = Scroller("", artist, "      ", line_size=LINEWIDTH)                
                    scroller2 = Scroller(track_no, track_name, "  ", line_size=LINEWIDTH)
                except:
                    debug("Episode change / track change: Error setting track. current_track="+str(current_track)+", current_episode"+
                          str(current_episode)+", ep.ntracks="+str(ep.ntracks(current_episode)))
                try:
                    debug("- Playing track " + str(current_track) + ", in ep=" + str(current_episode)  +  " (" + track_name  + ") "
                          + format_time(ep.start(current_episode,current_track)) + ep.starttype(current_episode,current_track)  
                          + "-" + format_time(ep.get_track_end(current_episode,current_track))+ ep.endtype(current_episode,current_track) )
                          #+ "; " + ep.time_info(current_episode,current_track))
                except:
                   debug("- Playing track " + str(track_no))

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
    
    debug("Showlength " + str(show_length) + " reached")
    current_position = 0
    # Rather than quit, should go to previous episode...
    # quit()


def quit():
    global favourited_log_string
    global current_episode, current_track, current_position

    debug("Quitting.")

    # Quit mplayer - do this first, so that there's user feedback to the keypress:
    mp.quit()

    #save anything pending in the favourited log queue before quitting
    if favourited_log_string != None:
        log_favourited(favourited_log_string)
        favourited_log_string = None

    if BUTTONS or LED or LCD:
	GPIO.cleanup()

    sys.exit("JunctionBox exited normally.\nYou listened to: ep="+str(current_episode)+", tr="+str(current_track)+", pos="+format_time(current_position)+", date="+ep.date(current_episode)+"\n"+
             "Continue listening like this: "+ sys.argv[0] + " " + str(current_episode)+" "+str(current_track))


if __name__ == '__main__':    
    load_config()
    if len(sys.argv) > 1 and sys.argv[1] == "dumppatch":
        ep = Episodes_Database(JB_DATABASE)
        ep.dump_db_patch(sys.argv[2])
        sys.exit("Exitting normally after db operation.")
    if len(sys.argv) > 1 and sys.argv[1] == "applypatch":
        ep = Episodes_Database(JB_DATABASE)
        ep.apply_db_patch(sys.argv[2])
        sys.exit("Exitting normally after db operation.")
    curses.wrapper(main_loop)

