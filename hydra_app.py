import os
import pathlib
import configparser

import dearpygui.dearpygui as dpg

import hydra.hymisc as hymisc


class HyAppState:
    """Manages Hydra's state."""
    def __init__(self):
        self.hyroot = pathlib.Path(__file__).resolve().parent
        self.cfgpath = str(self.hyroot / "hyapp.ini")
        self.icopath = str(self.hyroot / "resource" / "Icon.ico")
        
        # Load config
        try:
            with open(self.cfgpath, 'r') as configfile:
                self.config = configparser.ConfigParser()
                self.config.read_file(configfile)
        except FileNotFoundError:
            self.config = self.default_config()
            self.save_config()
            
        try:
            self.chartfolder = self.config['hydra']['chartfolder']
        except KeyError:
            self.chartfolder = None
    
    def default_config(self):
        cfg = configparser.ConfigParser()
        cfg['hydra'] = {'version': hymisc.HYDRA_VERSION}
        return cfg

    def save_config(self):
        with open(self.cfgpath, 'w') as configfile:
            self.config.write(configfile)
    
    
"""UI callbacks"""


def on_select_chartfolder():
    dpg.show_item("select_chartfolder")
        
        
def on_chartfolder_selected(sender, app_data):
    appstate.chartfolder = app_data['file_path_name']
    appstate.config['hydra']['chartfolder'] = appstate.chartfolder
    appstate.save_config()
    view_main()


def on_scan_charts():
    print("on_scan_charts()")
    
    
"""UI view controls"""


def view_main():
    """Main view with a small upper pane for chartfolder and a large lower pane
    to view discovered charts.
    
    """
    dpg.show_item("mainwindow")
    dpg.set_primary_window("mainwindow", True)

    dpg.set_value("chartfoldertext", f"Chart folder: {appstate.chartfolder}")
    dpg.configure_item("scanbutton", enabled=appstate.chartfolder is not None)
    
    # to do: Scan charts button, last scan folder and time
    
""" Main """


if __name__ == '__main__':
    # appstate is visible to the top-level functions
    appstate = HyAppState()
        
    dpg.create_context()

    # item creation - to be put into function(s) later
    dpg.add_file_dialog(
            directory_selector=True, show=False, callback=on_chartfolder_selected,
            tag="select_chartfolder", width=700 ,height=400)

    with dpg.window(label="Hydra", tag="mainwindow", show=False) as mainwindow:
        dpg.add_text(f"Chart folder: uninitialized", tag="chartfoldertext")
        with dpg.group(horizontal=True):
            dpg.add_button(label="Select folder...", callback=on_select_chartfolder)
            dpg.add_button(tag="scanbutton", label="Scan charts", callback=on_scan_charts)


    with dpg.theme() as standard_theme:
        with dpg.theme_component(dpg.mvButton, enabled_state=True):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 100, 100))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (0, 120, 120))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 200, 200))
            
        with dpg.theme_component(dpg.mvButton, enabled_state=False):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (200, 200, 200))
            dpg.add_theme_color(dpg.mvThemeCol_Button, (100, 100, 100))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (45, 45, 48))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (45, 45, 48))

    dpg.bind_theme(standard_theme)

    # Begin UI
    dpg.create_viewport(title="Hydra v0.0.1", width=1280, height=720,
                        small_icon=appstate.icopath, large_icon=appstate.icopath)

    dpg.setup_dearpygui()
    dpg.show_viewport()
    view_main()
    dpg.start_dearpygui()

    # End UI
    dpg.destroy_context()