import os
import sys
import hydra.hypath as hypath

if __name__ == "__main__":
    with open("../output/filldata_valid.txt", mode='w', encoding='utf-8') as valid_file:
        with open("../output/filldata_invalid.txt", mode='w', encoding='utf-8') as invalid_file:
            with open("../output/hydra_output.txt", mode='w', encoding='utf-8') as output:
                print("\tOutput file: hydra_output.txt")
                charts_root = sys.argv[1]
                unexplored = [f"{charts_root}/" + filename for filename in os.listdir(charts_root)]
                found_charts = []
                while len(unexplored) > 0:
                    f = unexplored.pop()
                    
                    if os.path.isfile(f):
                        # Record if this file is a chart
                        if f.endswith(".mid") or f.endswith(".chart"):
                            found_charts.append(f)
                    else:
                        # Add folder's contents to unexplored
                        unexplored += [f + "/" + filename for filename in os.listdir(f)]
                        
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
    print("\tDone!")
