import os
import json

from . import hypath
from . import hyrecord
from . import hysong
from . import hymisc

    
def discover_charts(rootname):
    """Returns a list of tuples (notesfile, inifile).
    
    Looks for charts in the given root folder.
    
    """
    try:
        rootdir = os.listdir(rootname)
    except FileNotFoundError:
        return []
        
    unexplored = [os.sep.join([rootname, name]) for name in rootdir]
    
    found_by_dirname = {}
    while unexplored:
        f = unexplored.pop()
        
        if os.path.isfile(f):
            # Handle a file
            if f.endswith(".mid") or f.endswith(".chart"):
                try:
                    found_by_dirname[os.path.dirname(f)][0] = f
                except KeyError:
                    found_by_dirname[os.path.dirname(f)] = [f, None]
            elif f.endswith(".ini"):
                try:
                    found_by_dirname[os.path.dirname(f)][1] = f
                except KeyError:
                    found_by_dirname[os.path.dirname(f)] = [None, f]
        else:
            # Handle a folder
            unexplored += [os.sep.join([f, name]) for name in os.listdir(f)]
            
    return [tuple(files) for files in found_by_dirname.values() if all(files)]

def load_records(filepath):
    """Loads hyrecords from a json file."""
    records = []
    
    with open(filepath, mode='r', encoding='utf-8') as recordfile:
        records_json = json.load(recordfile)['records']
        records = [hyrecord.HydraRecord.from_dict(r) for r in records_json]
            
    return records
    
def run_chart(filepath):
    """Current procedure to go from chart file to hyrecord.
    
    First parses either chart format to a Song object,
    then uses that to create a ScoreGraph, then
    feeds that into a GraphPather.
    
    To do: replace HydraRecord.from_graph with something in GraphPather
    
    """
    if filepath.endswith(".mid"):
        song = hysong.MidiParser().parsefile(filepath)
    elif filepath.endswith(".chart"):
        song = hysong.ChartParser().parsefile(filepath)
    else:
        raise hymisc.ChartFileError("Unexpected chart filetype")
    
    graph = hypath.ScoreGraph(song)
    
    pather = hypath.GraphPather()
    pather.run(graph)
    
    return hyrecord.HydraRecord.from_graph(song, pather)
