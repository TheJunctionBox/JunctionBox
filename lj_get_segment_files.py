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

DEBUG = False
HTML_FILE_LONG_NAME = False

DATA_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "../jb_data")
EPISODE_DIRECTORY = os.path.join(DATA_DIRECTORY, "Late_Junction")

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
        if 'debug' in confitems:
            DEBUG = getboolean(confitems['debug'])
        if 'html_file_long_name' in confitems:
            HTML_FILE_LONG_NAME = getboolean(confitems['html_file_long_name'])

#TODO remove and search for subdirs instead
EPISODE_DIRECTORY = os.path.join(DATA_DIRECTORY, "Late_Junction")


def get_segment_files():
    #open every meta data file and check if the segment file has been download
    #download missing segment files

    episodes = get_episodes()

    for episode in episodes:
        pid = episode['pid']
        if HTML_FILE_LONG_NAME:
            fileprefix = episode['fileprefix']
            segment_file = os.path.join(EPISODE_DIRECTORY, fileprefix + '.segments.html')
        else: 
            segment_file = os.path.join(EPISODE_DIRECTORY, pid + '.html')
        segment_data_file = os.path.join(EPISODE_DIRECTORY, pid + ".p")
        if not(os.path.isfile(segment_file)):
            if DEBUG: 
                print 'Downloading to: ' + segment_file
            segment_html = urllib.urlopen('http://www.bbc.co.uk/programmes/' + pid + '/segments').read()
            f = open(segment_file, 'w')
            f.write(segment_html)
            f.close()
        else:
            if DEBUG: 
                print 'Reusing: ' + segment_file
            f = open(segment_file, 'r')
            segment_html = f.read()
            f.close()
        if not(os.path.isfile(segment_data_file)):
            if DEBUG: 
                print "Creating: " + segment_data_file
            segment_data = parse_segment_html(segment_html)
            pickle.dump(segment_data, open(segment_data_file, "wb"))


def parse_segment_html(html):
    # expression needs to be improved to capture additional data (cf. todo.txt). Also note that sometimes times aren't present, in which case <div[^>]*>(\d\d):(\d\d)<\/div> is missing.
    # Should maybe add (?:....) but need to make sure that this doesn't cause problems down the line.
    expression = r'<div class="segment__track">\s*<div[^>]*>(\d\d):(\d\d)<\/div>.*?<span class="artist" [^>]*>([^<>]*)<\/span>.*?<span property="name">([^<>]*)<\/span>'

    p = re.compile(expression)

    data = []

    for m in p.finditer(html):    
        loc = m.group(1) + ":" + m.group(2)
        seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60
        artist = m.group(3)
        track = m.group(4)
        
        data.append({'loc':loc, 'seconds':seconds, 'artist':artist, 'track':track,
                     'favourite':False, 'favourited':False, 'heard':False})

    return data



def parse_segment_files():
    expression = r'<div class="segment__track">\s*<div[^>]*>(\d\d):(\d\d)<\/div>.*?<span class="artist" [^>]*>([^<>]*)<\/span>.*?<span property="name">([^<>]*)<\/span>'

    p = re.compile(expression)

    for segment_file in glob.glob(os.path.join(EPISODE_DIRECTORY, SEGMENT_FILE_PATTERN)):

        pid = os.path.splitext(os.path.basename(segment_file))[0]
        parsed_file_name = os.path.join(EPISODE_DIRECTORY, pid + ".p")

        if not(os.path.exists(parsed_file_name)):

            f = open(segment_file, "r")
            html = f.read()
            f.close()

            data = []

            for m in p.finditer(html):    
                loc = m.group(1) + ":" + m.group(2)
                seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60
                artist = m.group(3)
                track = m.group(4)

                data.append({'loc':loc, 'seconds':seconds, 'artist':artist, 'track':track,
                             'favourite':False, 'favourited':False, 'heard':False})

            pickle.dump(data, open(parsed_file_name, "wb"))


def get_episodes():
    episodes = []
    for metaDataFile in glob.glob(os.path.join(EPISODE_DIRECTORY, EPISODE_FILE_PATTERN)):

        tree = ET.parse(metaDataFile)
        root = tree.getroot()

        pid = root.find(NAMESPACE + 'pid').text
        fileprefix = root.find(NAMESPACE + 'fileprefix').text

        episodes.append({'pid': pid, 'fileprefix': fileprefix})

    return episodes        


if __name__ == "__main__":

    get_segment_files()

# This is obsole now!
#    parse_segment_files()
