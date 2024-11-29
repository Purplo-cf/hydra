import os
import json
from . import hypath
from . import hyrecord
from . import hysong

class ChartFileError(Exception):
    pass
    
# to do: look for nearby song info and pull metadata 
def discover_charts(root, map_names=True):
    charts = []
    
    try:
        unexplored = [os.sep.join([root, filename]) for filename in os.listdir(root)]
    except FileNotFoundError:
        return []
    
    while len(unexplored) > 0:
        f = unexplored.pop()
        
        if os.path.isfile(f):
            # Handle a file
            if f.endswith(".mid") or f.endswith(".chart"):
                charts.append(f)
        else:
            # Handle a folder
            unexplored += [os.sep.join([f, filename]) for filename in os.listdir(f)]
            
    return {c.split(os.sep)[-2]: c for c in charts} if map_names else charts

def load_records(filepath, map_names=True):
    records = []
    
    with open(filepath, mode='r', encoding='utf-8') as recordfile:
        album = json.load(recordfile)
        records = [hyrecord.HydraRecord.from_dict(r_raw) for r_raw in album["records"]]
            
    if not map_names:
        return records
    
    unique_ids = set([r.songid for r in records])
    return {id: set([r for r in records if r.songid == id]) for id in unique_ids}
    
def run_chart(filepath):
    if filepath.endswith(".mid"):
        song = hysong.MidiParser().parsefile(filepath)
    elif filepath.endswith(".chart"):
        song = hysong.ChartParser().parsefile(filepath)
    else:
        raise ChartFileError("Unexpected chart filetype")
    
    optimizer = hypath.Optimizer()
    optimizer.run(song)
    
    return hyrecord.HydraRecord.from_hydra(song, optimizer)