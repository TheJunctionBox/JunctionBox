#!/usr/bin/python

import glob
import xml.etree.ElementTree as ET
import os
import urllib
import re
import pickle

EPISODE_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                    "../jb_data/Late_Junction")
EPISODE_FILE_PATTERN = "*.xml"
SEGMENT_FILE_PATTERN = "*.html"
NAMESPACE = "{http://linuxcentre.net/xmlstuff/get_iplayer}"


def get_segment_files():
    #open every meta data file and check if the segment file has been download
    #download missing segment files

    episodes = get_episodes()

    for episode in episodes:
        pid = episode['pid']
        segment_file = os.path.join(EPISODE_DIRECTORY, pid + '.html')
        if not(os.path.isfile(segment_file)):
            segment_html = urllib.urlopen('http://www.bbc.co.uk/programmes/' + pid + '/segments').read()
            f = open(segment_file, 'w')
            f.write(segment_html)
            f.close()
            segment_data = parse_segment_html(segment_html)
            pickle.dump(segment_data, open(os.path.join(EPISODE_DIRECTORY, pid + ".p"), "wb"))



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

                data.append({'loc':loc, 'seconds':seconds, 'artist':artist, 
                             'track':track, 'favourite':False, 'heard':False})

            pickle.dump(data, open(parsed_file_name, "wb"))


                            

def get_episodes():
    episodes = []
    for metaDataFile in glob.glob(os.path.join(EPISODE_DIRECTORY, EPISODE_FILE_PATTERN)):

        tree = ET.parse(metaDataFile)
        root = tree.getroot()

        pid = root.find(NAMESPACE + 'pid').text

        episodes.append({'pid': pid})

    return episodes        


if __name__ == "__main__":

    get_segment_files()
    parse_segment_files()
