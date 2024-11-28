import os
import sys
import json
import hydra.hypath as hypath

if __name__ == "__main__":
    
    os.makedirs("../output", exist_ok=True)
    
    with open("../output/hydra_output.json", mode='w', encoding='utf-8') as output_json:
        
        json_album = {'records': []}
        
        with open("../output/filldata_valid.txt", mode='w', encoding='utf-8') as valid_file:
            with open("../output/filldata_invalid.txt", mode='w', encoding='utf-8') as invalid_file:
                with open("../output/hydra_output.txt", mode='w', encoding='utf-8') as output:
                    print("\tOutput file: hydra_output.txt")
                    charts_root = sys.argv[1]
                    unexplored = [os.sep.join([charts_root, filename]) for filename in os.listdir(charts_root)]
                    found_charts = []
                    while len(unexplored) > 0:
                        f = unexplored.pop()
                        
                        if os.path.isfile(f):
                            # Record if this file is a chart
                            if f.endswith(".mid") or f.endswith(".chart"):
                                found_charts.append(f)
                        else:
                            # Add folder's contents to unexplored
                            unexplored += [os.sep.join([f, filename]) for filename in os.listdir(f)]
                            
                    output.write(f"Found {len(found_charts)} charts in folder '{charts_root}'.\n")

                    debug_chart = None
                    if debug_chart:
                        found_charts = [debug_chart]
                    
                    
                    for filename in found_charts:
                        print(f"{filename}")
                        output.write(f"{filename}\n")
                        if filename.endswith(".mid"):
                            song = hypath.MidiParser().parsefile(filename)
                        elif filename.endswith(".chart"):
                            song = hypath.ChartParser().parsefile(filename)
                        else:
                            print(f"\tSkipping unknown filetype.")
                            output.write(f"\tSkipping unknown filetype.\n")
                            song = None
                        
                        if song:
                            
                            song.check_activations()
                            
                            song.report(output)
                            optimizer = hypath.Optimizer()
                            optimizer.run(song)
                            optimizer.report(output)
                            
                            optimizer.report_fills(filename, valid_file, invalid_file)
                                    
                        
                        output.write("\n")
                        
                        record = hypath.HydraRecord.from_hydra(song, optimizer)
                        record.songid = filename.split(os.sep)[-2]
                        record.difficulty = "expert"
                        record.prodrums = True
                        record.bass2x = True
                        json_album['records'].append(record)
                        
        json.dump(json_album, output_json, default=lambda o: o.__dict__, indent=4)
    print("\tDone!")
