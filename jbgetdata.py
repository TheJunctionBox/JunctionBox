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
import json
#from BeautifulSoup import BeautifulStoneSoup

DEBUG = True
HTML_FILE_LONG_NAME = False

DATA_DIRECTORY = os.path.join(expanduser("~"), "jb_data")     #Default data directory

#Obsolete: EPISODE_DIRECTORY = os.path.join(DATA_DIRECTORY, "Late_Junction")
EPISODE_DIRECTORY_LIST = "Late_Junction"

JB_DATABASE = os.path.join(DATA_DIRECTORY, "JB_DATABASE" )
JB_DATABASE_TRACKS = os.path.join(JB_DATABASE, "tracks" )
#JB_DATABASE_USER   = os.path.join(JB_DATABASE, "user" )

EPISODE_FILE_PATTERN = "*.xml"
SEGMENT_FILE_PATTERN = "*.html"
NAMESPACE = "{http://linuxcentre.net/xmlstuff/get_iplayer}"

# If True, the audio files are assumed to be nex to XML files, irrespective of what the XML files says about location. If False, the audio file location from the XML file is used.
COLOCATE_XML_AUDIO = True

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
        if 'colocate_xml_audio' in confitems:
            COLOCATE_XML_AUDIO = confitems['colocate_xml_audio']

EPISODE_FILE_PATTERN = "*.xml"
NAMESPACE = "{http://linuxcentre.net/xmlstuff/get_iplayer}"
ep_directories = EPISODE_DIRECTORY_LIST.split(",")

#    print "EPISODE_DIRECTORY_LIST=" + EPISODE_DIRECTORY_LIST + ", directories=" +str(len(ep_directories))

def get_segment_files(episodes):
    #open every meta data file and check if the segment file has been download
    #download missing segment files
    for episode in episodes:
        pid = episode['pid']
        duration = episode['duration']
        # segment_data_file is kept in DB, segment_file is kept alongside episodes
        segment_p_file = os.path.join(JB_DATABASE_TRACKS, pid + ".p")
        segment_data_file = os.path.join(JB_DATABASE_TRACKS, pid + ".json")
        # segment_user_file = os.path.join(JB_DATABASE_USER, pid + ".p")
        if HTML_FILE_LONG_NAME:
            segment_file = os.path.join(episode['dir'], episode['fileprefix'] + '.segments.html')
            segment_playlist_file = os.path.join(episode['dir'], episode['fileprefix'] + '.playlist.json')
        else: 
            segment_file = os.path.join(episode['dir'], episode['pid'] + '.html')
            segment_playlist_file = os.path.join(episode['dir'], episode['pid'] + '.json')
        #print segment_file + " " + episode['dir'] + " " + pid
        # Retrieve segments html file:
        if not(os.path.isfile(segment_file)):
            if DEBUG: 
                print 'Downloading to: ' + segment_file
            segment_html = urllib.urlopen('http://www.bbc.co.uk/programmes/' + pid + '/segments').read()
            # Need to check that this worked, i.e. that segment_html is not empty!
            f = open(segment_file, 'w')
            f.write(segment_html)
            f.close()
        # Retrieve segments json file:
        if not(os.path.isfile(segment_playlist_file)):
            if DEBUG: 
                print 'Downloading to: ' + segment_playlist_file
            segment_playlist_string = urllib.urlopen('http://www.bbc.co.uk/programmes/' + pid + '/playlist.json').read()
            # Need to check that this worked, i.e. that segment_html is not empty!
            f = open(segment_playlist_file, 'w')
            f.write(segment_playlist_string)
            f.close()
        UPDATE_MODE = False
        # If there is no database entry, create one:        
        if not(os.path.isfile(segment_data_file)) or UPDATE_MODE:
            # Should only save this if segments were retrieved - see comment in parse_segment_html()
            if not(os.path.isfile(segment_data_file)):
                if DEBUG: 
                    print "Creating: " + segment_data_file
                f = open(segment_file, 'r')
                segment_html = f.read()
                f.close()
                segment_data = parse_segment_html(segment_html, duration)
            else:
                with open(segment_data_file, 'r') as outfile:
                    segment_data = json.load(outfile)
                    # segment_data = pickle.load(open(segment_data_file, "rb"))
            f = open(segment_playlist_file, 'r')
            segment_playlist_string = f.read()
            f.close()
            segment_json = json.loads(segment_playlist_string)
            if 'allAvailableVersions' in segment_json:
                if len(segment_json['allAvailableVersions']) > 0:
                    if DEBUG: 
                       print "\n--- Update: " + segment_data_file
                    playlist = segment_json['allAvailableVersions'][0]['markers']
                    segment_data = data_merge(segment_data, playlist, pid)
            # Write to database:
            # pickle.dump(segment_data, open(segment_data_file, "wb"))
            with open(segment_data_file, 'w') as outfile:
                json.dump(segment_data, outfile, indent=4)

def segment_data_merge(segment_data, segment_data2):
    if len(segment_data) != len(segment_data2):
        print "ERROR: len(segment_data) != len(segment_data2)"
    # Copy fields from segment_data2 to segment_data as needed.
    for i in range(len(segment_data)):
        pass
    return segment_data

def data_merge(segment_data, playlist,pid):
    if len(playlist) != len(segment_data):
        print "ERROR: len(playlist) != len(segment_data)"
        print str(len(playlist))+ " " + str(len(segment_data))
        # for i in range(len(playlist)):
        #     print segment_data[i]['track'] + " --- " + playlist[i]['text']
        # print segment_data[len(segment_data)-1]['track']
    if playlist != None:
        for i in range(len(segment_data)):
            if i < len(playlist):
                offset = 0
                # Fixing an episode specific track counting issue:
                if pid == 'b05w82wf' and i > 2:
                    offset = 2
                if i + offset < len(segment_data):
                    if len(playlist) != len(segment_data):
                        try:
                            print segment_data[i+offset]['track'] + " --- " + playlist[i]['text']
                        except:
                            pass
                    segment_data[i+offset]['start'] = playlist[i]['start']
                    segment_data[i+offset]['title'] = playlist[i]['text'] 
                    segment_data[i+offset]['id']    = playlist[i]['id'] 
            else:
                if pid != 'b05w82wf':
                    print "No playlist data for index: "+str(i)
                    print segment_data[i]['track']
#             if (playlist[i]['text'] == segment_data[i]['track']):
#                 try:
#                     print str(i) + " OK " + format_time(playlist[i]['start'])+" "+ playlist[i]['text'].encode('utf-8').strip() + " = " + segment_data[i]['track'] 
#                 except:
#                     print str(i)+ "  FAIL =="
#             else:
#                 try:
#                     print str(i) + " !! " + format_time(playlist[i]['start'])+" "+ playlist[i]['text'].encode('utf-8').strip() + " = " + segment_data[i]['track'] 
#                 except:
#                     print str(i)+ "  FAIL !!"
# #                   print format_time(playlist[i]['start'])+" "+ playlist[i]['text'].encode('utf-8').strip() + "; " + format_time(segment_data[i]['seconds']) + " " + \
# #                         segment_data[i]['track'] + ", " + segment_data[i]['artist']
    return segment_data

def format_time(seconds):
    seconds = int(seconds)
    secs = seconds % 60
    mins = (seconds - secs) / 60

    return str(mins).rjust(2, "0") + ":" + str(secs).rjust(2, "0")

def parse_segment_html(html, duration):
    # expression needs to be improved to capture additional data (cf. todo.txt). Also note that sometimes times aren't present, in which case <div[^>]*>(\d\d):(\d\d)<\/div> is missing.
    # Should maybe add "(?:....)?" but need to make sure that this doesn't cause problems down the line. Most likely problem with older episodes only.
    expression = r'<div class="segment__track">\s*(?:<div[^>]*>(\d\d):(\d\d)<\/div>)?.*?<span class="artist" [^>]*>([^<>]*)<\/span>.*?(?:<span|<p class="no-margin") property="name">([^<>]*)<\/(?:span|p)>(?:(?:\s*<\/p>)?\s*(<ul.*?<\/ul>)?(\s*<ul.*?<\/ul>)?)?'

    p = re.compile(expression)

    data = []

    trackno = -1
    for m in p.finditer(html):    
        trackno = trackno + 1
        if m.group(1) != None:
            loc = str(m.group(1)) + ":" + str(m.group(2))
            seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60
        else:
            loc = ""
            seconds = -1
        artist = m.group(3)
        track = m.group(4)
        contributors = str(m.group(5))
        etc = str(m.group(6))

        if etc == "" and re.match( r'contributor' , contributors):
            etc = contributors
            contributors = ""
        contributors = re.sub(r'<.*?>', '', contributors)
        etc = re.sub(r'<.*?>', '', etc)

        # try:
        #     artist = unescape(artist) 
        #     track = unescape(track) 
        #     contributors = unescape(contributors) 
        #     etc = unescape(etc) 
        # except:
        #     print "art="+ artist
        #     print "art="+ track
        #     sys.exit()
        
        # data stores: (1) The extracted information, (2) Empty fields for inf appended from playlist.json, (3) user data
        data.append({'number': trackno, 'loc':loc, 'seconds':seconds, 'artist':artist, 'track':track, 'contributors': contributors, 'etc': etc, 'sectype': '',
                     'start' : -1, 'title': "", 'id': "",
                     'ends': -1, 'mystart': -1, 'favourite':False, 'favourited':False, 'heard':False})

    # data now needs checking - sometimes the time on tracks is zero, and needs to be interpolated.
    pos = []
    if (len(data) > 0):
        ntr = len(data)
        if data[0]['seconds'] == 0:
            data[0]['seconds'] = 11
        if data[0]['seconds'] == -1:
            data[0]['seconds'] = 11
        for i in range(len(data)):
            pos.append(data[i]['seconds'])
        pos.append(int(duration))
        for i in range(len(data)):
            if (pos[i] == -1):
                j = i
                while (pos[j] == -1):
                    j = j + 1
                step = (pos[j] - pos[i-1])/(j-(i-1))
                for k in range(i,j):
                    if pos[k] != -1:
                        print "WARNING! pos[k]"
                    pos[k] = pos[i-1] + (k-i+1)*step
                    print "Adjusting position for "+str(k)+ " to " + str(pos[k])
                    data[k]['seconds'] = pos[k]
                    data[k]['sectype'] = 'interp'
        for i in range(len(data)):
            data[i]['seconds'] = pos[i]
    return data

# def unescape(s):
#     return BeautifulStoneSoup(s, convertEntities=BeautifulStoneSoup.HTML_ENTITIES)

def get_episodes_audio():
    # call get_iplayer
    pass

def get_episodes_metadata():
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
                    duration = root.find(NAMESPACE + 'durations').text

                    #If the meta data files are moved then they contain the wrong paths.
                    #This code assumes the metadata files are in the same directory as 
                    #the audio files and ignores the path in the metadata file.
                    # if DEBUG:
                    #     print "file_base: " + file_base
                    #     print "filename: " + filename
                    #     print "filedir: " + filedir
                    #     print "fileprefix: " + fileprefix
                    if COLOCATE_XML_AUDIO:
                        file_base = os.path.basename(filename)
                        filename = os.path.join(DATA_DIRECTORY, metaDataDir, file_base)
                        filedir = os.path.join(DATA_DIRECTORY, metaDataDir)

                    if (os.path.isdir(filedir)  and os.path.isfile(filename)):
                        episodes.append({'filename': filename, 'pid':pid, 'episode': episode,
                                         'firstbcastdate': firstbcastdate, 'fileprefix': fileprefix, 'dir': filedir , 'ext': fileext, 'duration':duration })
                    else:
                        # print "Error for " + filename + " " + pid + " " + " " + fileprefix + " " + filedir + " " + fileext
                        print "  Error: No audio file for " + filename + " " + firstbcastdate
                except:
                    #exception will be raised if node is missing from xml
                    print "  Error finding tags in xml file: " + metaDataFile

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

    get_episodes_audio()

    if DEBUG: 
        print 'Getting episodes' 
    episodes = get_episodes_metadata()
# To skip episode parsing when developing:
#    episodes = pickle.load(open(os.path.join(JB_DATABASE,"episodes.p"), "rb"))

    if DEBUG: 
        print 'Getting segments'
    get_segment_files(episodes)
    if DEBUG: 
        print 'Done.'

