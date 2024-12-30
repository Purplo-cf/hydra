import os
import json
import sqlite3
import hashlib
import configparser
import pathlib

from . import hypath
from . import hyrecord
from . import hysong
from . import hymisc


def scan_charts(chartfolder,
                cb_chartfound, cb_allchartsfound, cb_libraryadded):
    """Makes a database out of the charts found in the given root folder.
    Replaces the current one if it's already there.
    
    """
    # Map out the file locations first
    chartfiles = discover_charts(chartfolder, cb_chartfound)
    cb_allchartsfound(len(chartfiles))
    
    cxn = sqlite3.connect(hymisc.DBPATH)
    cur = cxn.cursor()
    
    # Initialize db
    chartrow = TABLE_COL_INFO.keys()
    cur.execute("DROP TABLE IF EXISTS charts")
    cur.execute(f"CREATE TABLE charts{chartrow}")
    
    # Copy info from each ini to the db
    for i, (chartfile, inifile, path) in enumerate(chartfiles):        
        config = configparser.ConfigParser(strict=False, allow_no_value=True)
        # utf-8 should work but try to do other encodings if it doesn't
        for codec in ['utf-8', 'utf-8-sig', 'ansi']:
            try:
                config.read(inifile, encoding=codec)
                break
            except (configparser.MissingSectionHeaderError, UnicodeDecodeError):
                continue
       
        # Grab what we wanted from the ini file
        if 'Song' in config:
            metadata = config['Song']
        elif 'song' in config:
            metadata = config['song']
        else:
            raise hymisc.ChartFileError("Invalid ini format.")
        
        # Hash the chart file
        with open(chartfile, 'rb') as f:
            hyhash = hashlib.file_digest(f, "md5").hexdigest()
        
        # Grab those values
        try:
            name = metadata['name']
        except KeyError:
            name = "<unknown name>"
            
        try:
            artist = metadata['artist']
        except KeyError:
            artist = "<unknown artist>"
            
        try:
            charter = metadata['charter']
        except KeyError:
            charter = "<unknown charter>"

        folder = os.path.relpath(pathlib.Path(path).parent, chartfolder)

        # Insert into db
        rowvalues = (hyhash, name, artist, charter, path, folder)
        cur.execute(f"INSERT INTO charts VALUES (?, ?, ?, ?, ?, ?)", rowvalues)
        cb_libraryadded(i+1, len(chartfiles))
    
    cxn.commit()
    cxn.close()
    
    return len(chartfiles)
    
def discover_charts(rootname, cb_chartfound=None):
    """Returns a list of tuples (notesfile, inifile, folder).
    
    Looks for charts in the given root folder.
    
    """
    # Use input root folder to initialize search paths
    try:
        rootdir = os.listdir(rootname)
    except FileNotFoundError:
        return []
    unexplored = [os.sep.join([rootname, name]) for name in rootdir]
    
    # Search subfolders and group chart/ini files by their parent folder
    # {dirname: [chartfile, inifile, dirname]}
    found_by_dirname = {}
    while unexplored:
        f = unexplored.pop()
        dir = os.path.dirname(f)
        
        if os.path.isfile(f):
            # Handle a file - chartfile or inifile
            if f.endswith(".mid") or f.endswith(".chart"):
                try:
                    # Add to entry for this dir
                    found_by_dirname[dir][0] = f
                except KeyError:
                    # Create new entry for this dir
                    found_by_dirname[dir] = [f, None, dir]
                    if cb_chartfound:
                        cb_chartfound(len(found_by_dirname))
            elif f.endswith("song.ini"):
                try:
                    # Add to entry for this dir
                    found_by_dirname[dir][1] = f
                except KeyError:
                    # Create new entry for this dir
                    found_by_dirname[dir] = [None, f, dir]
                    if cb_chartfound:
                        cb_chartfound(len(found_by_dirname))
        else:
            # Handle a folder - add subfolders to the search
            unexplored += [os.sep.join([f, name]) for name in os.listdir(f)]
            
    return [tuple(info) for info in found_by_dirname.values() if all(info)]

def load_records(filepath):
    """Loads hyrecords from a json file."""
    records = []
    
    with open(filepath, mode='r', encoding='utf-8') as recordfile:
        records_json = json.load(recordfile)['records']
        records = [hyrecord.HydraRecord.from_dict(r) for r in records_json]
            
    return records
    
def run_chart(filepath):
    """Current chain to go from chart file to hyrecord.
    
    First parses either chart format to a Song object,
    then uses that to create a ScoreGraph, then
    feeds that into a GraphPather.
    
    """
    if filepath.endswith(".mid"):
        song = hysong.MidiParser().parsefile(filepath)
    elif filepath.endswith(".chart"):
        song = hysong.ChartParser().parsefile(filepath)
    else:
        raise hymisc.ChartFileError("Unexpected chart filetype")
    
    graph = hypath.ScoreGraph(song)
    
    pather = hypath.GraphPather()
    pather.read(graph)
    
    return pather.record
