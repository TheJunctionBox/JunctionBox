#!/usr/bin/python

import glob
import xml.etree.ElementTree as ET
import os
import urllib
import re
import pickle
import ConfigParser
from os.path import expanduser
import os.path
import sys

DEBUG = False
HTML_FILE_LONG_NAME = False

DATA_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "../jb_data")
#Obsolete: EPISODE_DIRECTORY = os.path.join(DATA_DIRECTORY, "Late_Junction")
EPISODE_DIRECTORY_LIST = "Late_Junction"

JB_DATABASE = os.path.join(DATA_DIRECTORY, "JB_DATABASE" )
JB_DATABASE_TRACKS = os.path.join(JB_DATABASE, "tracks" )

EPISODE_FILE_PATTERN = "*.xml"
SEGMENT_FILE_PATTERN = "*.html"
NAMESPACE = "{http://linuxcentre.net/xmlstuff/get_iplayer}"

def getboolean(mystring):
  return mystring == "True"

# Check for configuration files
configfile = os.path.join( expanduser("~"), ".junctionbox")
Config = ConfigParser.ConfigParser()


if os.path.isfile(configfile):  
    Config.read(configfile)
    if 'basic' in Config.sections():
        confitems = dict(Config.items('basic'))
        if 'data_directory' in confitems:
            DATA_DIRECTORY = confitems['data_directory']
            if not('jb_database' in confitems):
                JB_DATABASE = os.path.join(DATA_DIRECTORY, "JB_DATABASE" )
                JB_DATABASE_TRACKS = os.path.join(JB_DATABASE, "tracks" )
        if 'debug' in confitems:
            DEBUG = getboolean(confitems['debug'])
        if 'html_file_long_name' in confitems:
            HTML_FILE_LONG_NAME = getboolean(confitems['html_file_long_name'])
        if 'jb_database' in confitems:
            JB_DATABASE = confitems['jb_database']
            JB_DATABASE_TRACKS = os.path.join(JB_DATABASE, "tracks" )
        if 'episode_directory_list' in confitems:
            EPISODE_DIRECTORY_LIST = confitems['episode_directory_list']

EPISODE_FILE_PATTERN = "*.xml"
NAMESPACE = "{http://linuxcentre.net/xmlstuff/get_iplayer}"
ep_directories = EPISODE_DIRECTORY_LIST.split(",")

#    print "EPISODE_DIRECTORY_LIST=" + EPISODE_DIRECTORY_LIST + ", directories=" +str(len(ep_directories))

def get_segment_files(episodes):
    #open every meta data file and check if the segment file has been download
    #download missing segment files
    for episode in episodes:
        pid = episode['pid']
        # segment_data_file is kept in DB, segment_file is kept alongside episodes
        segment_data_file = os.path.join(JB_DATABASE_TRACKS, pid + ".p")
        if HTML_FILE_LONG_NAME:
            segment_file = os.path.join(episode['dir'], episode['fileprefix'] + '.segments.html')
        else: 
            segment_file = os.path.join(episode['dir'], episode['pid'] + '.html')
        #print segment_file + " " + episode['dir'] + " " + pid
        if not(os.path.isfile(segment_file)):
            if DEBUG: 
                print 'Downloading to: ' + segment_file
            segment_html = urllib.urlopen('http://www.bbc.co.uk/programmes/' + pid + '/segments').read()
            # Need to check that this worked, i.e. that segment_html is not empty!
            f = open(segment_file, 'w')
            f.write(segment_html)
            f.close()
        else:
            #if DEBUG: 
            #    print 'Reusing: ' + segment_file
            f = open(segment_file, 'r')
            segment_html = f.read()
            f.close()
        if not(os.path.isfile(segment_data_file)):
            if DEBUG: 
                print "Creating: " + segment_data_file
            segment_data = parse_segment_html(segment_html)
            # Should only save this if segments were retrieved - see comment in parse_segment_html()
            pickle.dump(segment_data, open(segment_data_file, "wb"))


def parse_segment_html(html):
    # expression needs to be improved to capture additional data (cf. todo.txt). Also note that sometimes times aren't present, in which case <div[^>]*>(\d\d):(\d\d)<\/div> is missing.
    # Should maybe add "(?:....)?" but need to make sure that this doesn't cause problems down the line. Most likely problem with older episodes only.
    expression = r'<div class="segment__track">\s*<div[^>]*>(\d\d):(\d\d)<\/div>.*?<span class="artist" [^>]*>([^<>]*)<\/span>.*?<span property="name">([^<>]*)<\/span>'

    p = re.compile(expression)

    data = []

    for m in p.finditer(html):    
        loc = m.group(1) + ":" + m.group(2)
        seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60
        artist = m.group(3)
        track = m.group(4)
        
        #B: Tracks should have end-times. 
        data.append({'loc':loc, 'seconds':seconds, 'artist':artist, 'track':track,'ends': -1,
                     'favourite':False, 'favourited':False, 'heard':False})

    return data

# def parse_segment_files():
#     expression = r'<div class="segment__track">\s*<div[^>]*>(\d\d):(\d\d)<\/div>.*?<span class="artist" [^>]*>([^<>]*)<\/span>.*?<span property="name">([^<>]*)<\/span>'

#     p = re.compile(expression)

#     for segment_file in glob.glob(os.path.join(EPISODE_DIRECTORY, SEGMENT_FILE_PATTERN)):

#         pid = os.path.splitext(os.path.basename(segment_file))[0]
#         parsed_file_name = os.path.join(EPISODE_DIRECTORY, pid + ".p")

#         if not(os.path.exists(parsed_file_name)):

#             f = open(segment_file, "r")
#             html = f.read()
#             f.close()

#             data = []

#             for m in p.finditer(html):    
#                 loc = m.group(1) + ":" + m.group(2)
#                 seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60
#                 artist = m.group(3)
#                 track = m.group(4)

#                 data.append({'loc':loc, 'seconds':seconds, 'artist':artist, 'track':track,
#                              'favourite':False, 'favourited':False, 'heard':False})

#             pickle.dump(data, open(parsed_file_name, "wb"))


def get_episodes():
    #open every meta data file and get the media file and a displayable name

    episodes = []

    for metaDataDir in ep_directories:
        if DEBUG:
            print "Examining "+str(metaDataDir)
        file_pattern = (os.path.join(DATA_DIRECTORY, metaDataDir, EPISODE_FILE_PATTERN))
        for metaDataFile in glob.glob(file_pattern):

            try:
                tree = ET.parse(metaDataFile)
                root = tree.getroot()
                try:
                    filename = root.find(NAMESPACE + 'filename').text
                    # filename = filedir + fireprefix + fileext
                    filedir = root.find(NAMESPACE + 'dir').text
                    fileprefix = root.find(NAMESPACE + 'fileprefix').text
                    fileext = root.find(NAMESPACE + 'ext').text
                    pid = root.find(NAMESPACE + 'pid').text
                    # firstbcastdate is not in all xml
                    firstbcastdate = root.find(NAMESPACE + 'firstbcastdate').text
                    channel = root.find(NAMESPACE + 'channel').text
                    # "band" is not present in older xml, and not used below, hence removed.
                    # brand = root.find(NAMESPACE + 'brand').text
                    episode = root.find(NAMESPACE + 'episode').text
                    if (os.path.isdir(filedir)  and os.path.isfile(filename)):
                        episodes.append({'filename': filename, 'pid':pid, 'episode': episode,
                                         'firstbcastdate': firstbcastdate, 'fileprefix': fileprefix, 'dir': filedir , 'ext': fileext })
                    else:
                        # print "Error for " + filename + " " + pid + " " + " " + fileprefix + " " + filedir + " " + fileext
                        print "  Error: No audio file for " + filename + " " + firstbcastdate
                except:
                    #exception will be raised if node is missing from xml
                    print "  Error finding tags in xml file: "+metaDataFile

            except:
                print "  Error parsing xml file: "+metaDataFile

    episodes.sort(key=lambda ep: ep['firstbcastdate'])
    pickle.dump(episodes, open(os.path.join(JB_DATABASE,"episodes.p"), "wb"))

    return episodes        


if __name__ == "__main__":
    try:
        if not( os.path.isdir(JB_DATABASE)):
            os.mkdir(JB_DATABASE)
        if not( os.path.isdir(JB_DATABASE_TRACKS)):
            os.mkdir(JB_DATABASE_TRACKS)
    except:
        sys.exit("Failed to create directories: "+JB_DATABASE)

    if DEBUG: 
        print 'Getting episodes' 
    episodes = get_episodes()
#    episodes = pickle.load(open(os.path.join(JB_DATABASE,"episodes.p"), "rb"))

    if DEBUG: 
        print 'Getting segments'
    get_segment_files(episodes)
    if DEBUG: 
        print 'Done.'

# This is obsole now!
#    parse_segment_files()
