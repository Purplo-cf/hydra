import os
import json
import sqlite3
import configparser
import pathlib
import hashlib
import time

from . import hypath
from . import hydata
from . import hysong
from . import hymisc

    
def discover_charts(rootname, cb_progress=None):
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
                    if cb_progress:
                        cb_progress(len(found_by_dirname))
            elif f.endswith("song.ini"):
                try:
                    # Add to entry for this dir
                    found_by_dirname[dir][1] = f
                except KeyError:
                    # Create new entry for this dir
                    found_by_dirname[dir] = [None, f, dir]
                    if cb_progress:
                        cb_progress(len(found_by_dirname))
        else:
            # Handle a folder - add subfolders to the search
            unexplored += [os.sep.join([f, name]) for name in os.listdir(f)]
            
    return [tuple(info) for info in found_by_dirname.values() if all(info)]


def get_rowvalues(chartfile, inifile, path, rootfolder):
    config = configparser.ConfigParser(
        strict=False, allow_no_value=True, interpolation=None
    )
    # utf-8 should work but try to do other encodings if it doesn't
    for codec in ['utf-8', 'utf-8-sig', 'ansi']:
        try:
            config.read(inifile, encoding=codec)
            break
        except (configparser.MissingSectionHeaderError, UnicodeDecodeError):
            continue
   
    # Song inis have one section
    if 'Song' in config:
        metadata = config['Song']
    elif 'song' in config:
        metadata = config['song']
    else:
        raise hymisc.ChartFileError("Invalid ini format.")
    
    # Hash the chart file
    with open(chartfile, 'rb') as f:
        hyhash = hashlib.file_digest(f, "md5").hexdigest()
    
    # Grab our desired metadata
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

    folder = os.path.relpath(pathlib.Path(path).parent, rootfolder)
    return (hyhash, name, artist, charter, path, folder)

def analyze_chart(
    filepath,
    m_difficulty, m_pro, m_bass2x,
    d_mode, d_value,
    cb_parsecomplete=None, cb_pathsprogress=None
):
    """The full process to go from chart file to hydata.
    
    It's more or less a chain: Chart --> Song --> Graph --> Record.
    
    """
    # Parse chart file and make a song object
    if filepath.endswith(".mid"):
        parser = hysong.MidiParser()
    elif filepath.endswith(".chart"):
        parser = hysong.ChartParser()
    else:
        raise hymisc.ChartFileError("Unexpected chart filetype")
    
    parser.parsefile(filepath, m_difficulty, m_pro, m_bass2x)
    
    if cb_parsecomplete:
        cb_parsecomplete()
    
    # Use song object to make a score graph
    graph = hypath.ScoreGraph(parser.song)
    
    # Use score graph to run the paths
    pather = hypath.GraphPather()
    pather.read(graph, d_mode, d_value, cb_pathsprogress)

    return pather.record
