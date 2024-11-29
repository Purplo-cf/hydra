import os
import sys
import json
import hydra.hypath as hypath
import hydra.hyutil as hyutil

if __name__ == "__main__":
    
    os.makedirs(os.sep.join(['..','output']), exist_ok=True)
    
    with open(os.sep.join(['..','output','hydra_output.json']), mode='w', encoding='utf-8') as output_json:
        
        json_album = {'records': []}
        
        charts_root = sys.argv[1]
        names_to_chartfiles = hyutil.discover_charts(charts_root)
        
        print(f"\nFound {len(names_to_chartfiles)} charts in root folder '{charts_root}'.\n")
        
        for name, chartfile in names_to_chartfiles.items():
            print(f"{chartfile}")
            
            json_album['records'].append(hyutil.run_chart(chartfile))
            
            # Temp
            json_album['records'][-1].songid = name
                        
        json.dump(json_album, output_json, default=lambda o: o.__dict__, indent=4)
        
        print(f"\nFinished saving {len(json_album['records'])} records to hydra_output.json")
