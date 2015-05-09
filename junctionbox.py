#!/usr/bin/python
DEBUG = True        #enables debug print statements

#Hardware Options
BUTTONS = False 	#set to True if buttons are present
SCREEN = False 	#set to True if there is an LCD screen present
LED = False 		#set to True if there is an RGB LED present

if BUTTONS or LED:
	import RPi.GPIO as GPIO

import curses
import mpylayer
import time
import os
import glob
import xml.etree.ElementTree as ET
import re
import pickle
from subprocess import call


EPISODE_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                    "../jb_data/Late_Junction")
                    
DATA_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "../jb_data")
EPISODE_FILE_PATTERN = "*.xml"
NAMESPACE = "{http://linuxcentre.net/xmlstuff/get_iplayer}"
TICKER = ['-','\\','|','/']

if BUTTONS or LED:
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




intro_offset = 11   #offset in seconds of the start of the music
current_episode = 0
current_track = 0
current_position = 0
episodes = []
player_status = STOPPED
stdscr = None

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


def play_pause(channel=0):
    play_pause()


def next_track(channel=0):
    global current_track

    episode = episodes[current_episode]

    if current_track < len(episode['tracks']):
        current_track += 1
        
    track_list = episode['tracks']
    display(">>", str(current_track + 1) + " / " + str(len(track_list)))

    mp.time_pos = track_list[current_track]['seconds'] + intro_offset

    

def next_episode(channel=0):
    global current_episode
    
    display(">|", str(current_episode + 1) + " / " + str(len(episodes)))
    if current_episode < len(episodes) - 1:
        current_episode += 1
        play_episode(current_episode)


def mark_favourite(channel=0):
    track = episodes[current_episode]['tracks'][current_track]
    track['favourite'] = not(track['favourite'])
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
    pickle.dump(tracks, open(os.path.join(EPISODE_DIRECTORY, pid + ".p"), "wb"))


def update_position():
    global current_position, current_track

    if player_status == PAUSED:
        return True     #playing normally (not seeking), paused so don't ask for position
    
    debug("here updpos 0")
    pos = mp.time_pos
    debug("here updpos 1")

    if isinstance(pos, float):
        current_position = pos

        episode = episodes[current_episode]
        tracks = episode['tracks']
    
        for i in range(len(tracks)):
            if tracks[i]['seconds'] + intro_offset > pos:
                break

        current_track = i - 1
        return True     #playing normally
    else:
        return False    #seeking



def display(line1, line2):
    line1 = line1[0:16]
    line2 = line2[0:16] 
    display_line1 = line1.ljust(16, " ")
    display_line2 = line2.ljust(16, " ")
    
    if SCREEN:
        #TODO screen code
        noop
    else:
        stdscr.addstr(1,4,line1)
        stdscr.addstr(2,4,line2)
        stdscr.refresh()


def debug(msg, value=""):
    if DEBUG:
        text = msg + ": %s" % value
        stdscr.addstr(6,0, "DEBUG:")
        stdscr.addstr(7,0, text)
        stdscr.refresh()


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
        
        pid = root.find(NAMESPACE + 'pid').text
        firstbcastdate = root.find(NAMESPACE + 'firstbcastdate').text
        channel = root.find(NAMESPACE + 'channel').text
        brand = root.find(NAMESPACE + 'brand').text
        episode = root.find(NAMESPACE + 'episode').text

        segment_file_name = os.path.join(EPISODE_DIRECTORY, pid + ".p")
        tracks = get_segments(segment_file_name)

        episodes.append({'filename': filename, 'pid':pid, 'episode': episode,
                         'firstbcastdate': firstbcastdate, 'tracks': tracks})

        episodes.sort(key=lambda ep: ep['firstbcastdate'])

    return episodes        


def get_segments(filename):
    return pickle.load(open(filename, "rb"))


def play_episode(index):
    global player_status
    
    episode = episodes[index]
    episode_file = episode['filename']

    mp.loadfile(episode_file)
    player_status = PLAYING

    led(0,0,0)
    line1 = episode['episode']
    line2 = episode['firstbcastdate']
    display(line1, line2)


def play_pause():
    global player_status
    
    if player_status == PLAYING:
        player_status = PAUSED
    else:
        player_status = PLAYING

    mp.pause()
    

    
def led(red, green, blue):
	if LED:
		GPIO.output(RED_PIN, 1 - red)
		GPIO.output(GREEN_PIN, 1 - green)
		GPIO.output(BLUE_PIN, 1 - blue)
	else:
	    colour = red + green * 2 + blue	* 4
	    if colour == 0:
	        char = " "
	    else:
	        char = "*"    
	    stdscr.addstr(1,22, char, curses.color_pair(colour))

class Scroller:
    def __init__(self, left_text, centre_text, right_text, line_size=16):
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


def handle_keypress(c):
    if c == ord('z'):
        prev_episode()
    elif c == ord('x'):
        prev_track()
    elif c == ord('c'):
        play_pause()
    elif c == ord('v'):
        next_track()
    elif c == ord('b'):        
        next_episode()
    elif c == ord('n'):
        mark_favourite()
    elif c == ord('q'):
        raise           #if q is pressed then quit

def main_loop(screen):
    global current_episode, episodes, stdscr

    stdscr = screen    
    curses.curs_set(0)
    curses.halfdelay(4)
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)



    
    display("Late", "Junction")
    led(0,0,0)

    episodes = load_episodes()
    
    current_episode = len(episodes) - 1
    play_episode(current_episode)


    time.sleep(2)
    
    show_length = mp.length

    seeking = not(update_position())
    ticker_index = 0

    last_track = -2

    scroller1 = None
    scroller2 = None

    led_state = 0
    debug("here 5")    
    while(current_position < show_length):
        if last_track != current_track:
            last_track = current_track
            if current_track < 0:
                scroller1 = Scroller("", episodes[current_episode]['episode'], "      ")
                scroller2 = Scroller("", episodes[current_episode]['firstbcastdate'], "  ")
            else:
                track = episodes[current_episode]['tracks'][current_track]
                artist = track['artist']
                scroller1 = Scroller("", artist, "      ")
                
                track_no = str(current_track + 1) + " "
                track_name =  track['track']
                scroller2 = Scroller(track_no, track_name, "  ")

                show_favourite(track['favourite'])
                

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
            
        line2 = line2[0:14].ljust(14, " ") + " " + status
        line1 = line1[0:10] + " " + format_time(current_position)
        
        display (line1, line2)

        if not(SCREEN):
            handle_keypress(stdscr.getch())
        else:
            time.sleep(0.4)
            
        seeking = not(update_position())

        


if __name__ == '__main__':
    curses.wrapper(main_loop)

