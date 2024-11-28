import os
import json
from . import hypath

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
        records = [hypath.HydraRecord.from_dict(r_raw) for r_raw in album["records"]]
            
    if not map_names:
        return records
    
    unique_ids = set([r.songid for r in records])
    return {id: set([r for r in records if r.songid == id]) for id in unique_ids}