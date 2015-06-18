import os
import sys
import pickle
import json

class EpisodeDatabase:
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
                        print "  (" + str(j) + ") " + str(self.favourite(i,j)) + " " + self.format_time(self.start(i,j)) + self.starttype(i,j) + "-" + self.format_time(self.get_track_end(i,j)) + self.endtype(i,j) + " " + self.tracktitle(i,j) + " - " + self.trackartist(i,j)
                    except:
                        print "  (" + str(j) + ") " + str(self.favourite(i,j)) + " " + self.format_time(self.start(i,j)) + "-" + self.format_time(self.get_track_end(i,j)) 
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
                                print "        ok - mystart: " + str(self.mystart(i,j))
                    if 'end' in update:
                        if self.endseconds(i,j) == -1:
                            self.setend(i,j, update['end'])
                            print "        mystart updated."
                        else:
                            if update['end'] != self.endseconds(i,j):
                                print "        ERROR: Update of end failed because it was already set: "  + str(self.endseconds(i,j))
                            else:
                                print "        ok - end: " + str(self.endseconds(i,j))
                    if 'favourite' in update:
                        if self.favourite(i,j) != update['favourite']:
                            self.setfavourite(i,j, update['favourite'])
                            print "        favourite updated: " + str(update['favourite']) + " " + str(self.favourite(i,j))
                        else:
                            if update['favourite'] != self.favourite(i,j):
                                print "        ERROR: Update of favourite failed because it was already set: "  + str(self.favourite(i,j))
                            else:
                                print "        ok - fav: " + str(self.favourite(i,j))
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

# Should remove track end if track start is set to earlier than track end.
# Shoudl allow setting end track if near start of next track.

    def adjust_track_start(self,current_episode, current_track, current_time):
        newtime = current_time 
        if current_track == - 1:
            adjust_track = current_track + 1
        else: 
            if current_track == self.ntracks(current_episode) - 1:
                adjust_track = current_track
            else:
                # Work out which track boundary we are near:
                currtr_diff = abs( newtime - self.start(current_episode, current_track))
                nexttr_diff = abs( newtime - self.start(current_episode, current_track+1))
                if (currtr_diff < nexttr_diff):
                    adjust_track = current_track
                else:
                    adjust_track = current_track + 1
        time_diff = newtime - self.start(current_episode, adjust_track)
        oldtime = self.start(current_episode, adjust_track)
        if newtime > 0: 
            self.setstart(current_episode, adjust_track, newtime)
            return "    Start time adjusted by "+str(time_diff)+"s, from "+self.format_time(oldtime) + " to " + self.format_time(newtime) + ", for track "+str(adjust_track+1)+", when playing track "+str(current_track+1)+". Saved to db."
        else:
            return ""

    def adjust_track_end(self,current_episode, current_track, current_time):
        newtime = current_time 
        if current_track > -1 and current_track < self.ntracks(current_episode):
            if current_track == self.ntracks(current_episode) - 1:
                adjust_track = current_track
            else:
                if current_track == - 1:
                    adjust_track = current_track + 1
                else:
                    # If we are just into the next track, still adjust the previous track...
                    if newtime + 5 < self.start(current_episode, current_track+1):
                        adjust_track = current_track
                    else:
                        adjust_track = current_track + 1
            time_diff = newtime - self.endseconds(current_episode, adjust_track)
            oldtime_raw = self.endseconds(current_episode, adjust_track)
            oldtime = self.get_track_end(current_episode, adjust_track)
            if oldtime_raw == oldtime:
                infostr = "*"
            if newtime > 0: 
                self.setend(current_episode, adjust_track, newtime)
                return "    End time adjusted by "+str(time_diff)+"s, from "+self.format_time(oldtime) + " to " + self.format_time(newtime) + ", for track "+str(adjust_track)+". Saved to db." 
            else:
                return ""
