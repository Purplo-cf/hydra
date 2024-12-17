import os
import sys
import json
import configparser

import hydra.hypath as hypath
import hydra.hyutil as hyutil

if __name__ == "__main__":
    
    os.makedirs(os.sep.join(['..','output']), exist_ok=True)
    outfile = os.sep.join(['..','output','hydra_output.json'])
    
    with open(outfile, mode='w', encoding='utf-8') as output_json:
        
        json_album = {'records': []}
        
        charts_root = sys.argv[1]
        charts = hyutil.discover_charts(charts_root)
        
        print(f"\nFound {len(charts)} charts in '{charts_root}'.\n")
        
        for notesfile, inifile in charts:
            print(f"{notesfile}")
            
            json_album['records'].append(hyutil.run_chart(notesfile))
            
            config = configparser.ConfigParser()
            config.read(inifile)
            
            if 'Song' in config:
                name = config['Song']['name']
                artist = config['Song']['artist']
            elif 'song' in config:
                name = config['song']['name']
                artist = config['song']['artist']
            else:
                raise hymisc.ChartFileError()
            
            json_album['records'][-1].ref_songname = name
            json_album['records'][-1].ref_artistname = artist
                        
        json.dump(json_album, output_json, default=lambda r: r.__dict__, indent=4)
        
        print(f"\nFinished saving {len(json_album['records'])} records to hydra_output.json")
