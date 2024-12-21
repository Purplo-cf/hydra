import os
import pathlib
import configparser

import dearpygui.dearpygui as dpg

import hydra.hymisc as hymisc

import dearpygui.demo as demo


"""Settings"""


class HyAppUserSetting:
    """Streamlines editing runtime state and the underlying config file
    at the same time.
    
    """
    def __init__(self, getbool=False):
        self.getbool = getbool
        
    def __set_name__(self, owner, name):
        self.key = name
    
    def __get__(self, obj, objtype=None):
        if self.getbool:
            return obj.cfg['hydra'].getboolean(self.key)
        else:
            return obj.cfg['hydra'][self.key]
        
    def __set__(self, obj, value):
        obj.cfg['hydra'][self.key] = str(value)
        obj.savecfg()

class HyAppUserSettings:
    """Interface for hydra's saveable settings.
    
    Automatically loads from config on init.
    
    HyApp reads setting values from here.
    
    Changing settings in HyApp changes variables in here and simultaneously
    updates the config.
    
    """
    CFGPATH = str(pathlib.Path(__file__).resolve().parent / "hyapp.ini")
    
    version = HyAppUserSetting()
    chartfolder = HyAppUserSetting()
    view_difficulty = HyAppUserSetting()
    view_prodrums = HyAppUserSetting(getbool=True)
    view_bass2x = HyAppUserSetting(getbool=True)
    
    def __init__(self):
        # Load setting values from config
        self.cfg = configparser.ConfigParser()
        try:
            with open(self.CFGPATH, 'r') as cfgfile:
                self.cfg.read_file(cfgfile)
        except FileNotFoundError:
            pass
        
        # Bootstrap the cfg if it was essentially empty
        if 'hydra' not in self.cfg:
            self.cfg['hydra'] = {}
        
        loadedsettings = self.cfg['hydra']
        
        # Always override version number
        loadedsettings['version'] = str(hymisc.HYDRA_VERSION)
        
        # Fill in any missing values manually with defaults
        for key, default in [
            ('chartfolder', ""),
            ('view_difficulty', 'Expert'),
            ('view_prodrums', 'True'),
            ('view_bass2x', 'True')
        ]:
            if key not in loadedsettings:
                loadedsettings[key] = default
            
        # Save in case anything was filled in
        self.savecfg()

    def savecfg(self):
        with open(self.CFGPATH, 'w') as cfgfile:
            self.cfg.write(cfgfile)

class HyAppState:
    """Manages Hydra's state."""
    def __init__(self):
        # Paths - may move to a more utility location
        self.hyroot = pathlib.Path(__file__).resolve().parent
        self.icopath = str(self.hyroot / "resource" / "Icon.ico")
        
        self.usettings = HyAppUserSettings()
        
    
    
"""UI callbacks"""


def on_select_chartfolder():
    dpg.show_item("select_chartfolder")
        
def on_chartfolder_selected(sender, app_data):
    appstate.usettings.chartfolder = app_data['file_path_name']
    refresh_chartfolder()

def on_viewdifficulty(sender, app_data):
    appstate.usettings.view_difficulty = app_data
    refresh_viewdifficulty()

def on_viewprodrums(sender, app_data):
    appstate.usettings.view_prodrums = app_data
    refresh_viewprodrums()
    
def on_viewbass2x(sender, app_data):
    appstate.usettings.view_bass2x = app_data
    refresh_viewbass2x()

def on_scan_charts():
    print("on_scan_charts()")
    
    
"""UI view controls"""


def view_main():
    """Main view with a small upper pane for chartfolder and a large lower pane
    to view discovered charts.
    
    """
    dpg.show_item("mainwindow")
    dpg.set_primary_window("mainwindow", True)

    refresh_chartfolder()
    refresh_viewdifficulty()
    refresh_viewprodrums()
    refresh_viewbass2x()
    
    
"""UI population"""


def refresh_chartfolder():
    folder = appstate.usettings.chartfolder
    dpg.set_value("chartfoldertext", f"Chart folder: {folder}")
    dpg.configure_item("scanbutton", enabled=folder != "")
    
    
def refresh_viewdifficulty():
    dpg.set_value("view_difficulty_combo", appstate.usettings.view_difficulty)
def refresh_viewprodrums():
    dpg.set_value("view_prodrums_check", appstate.usettings.view_prodrums)
def refresh_viewbass2x():
    dpg.set_value("view_bass2x_check", appstate.usettings.view_bass2x)
    
    
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
        dpg.add_separator(label="Settings")
        dpg.add_text(f"Chart folder: uninitialized", tag="chartfoldertext")
        with dpg.group(horizontal=True):
            dpg.add_button(label="Select folder...", callback=on_select_chartfolder)
            dpg.add_button(tag="scanbutton", label="Scan charts", callback=on_scan_charts)
        dpg.add_separator(label="Library")
        with dpg.group(horizontal=True):
            dpg.add_text("View:")
            dpg.add_combo(("Expert", "Hard", "Medium", "Easy"), tag="view_difficulty_combo", callback=on_viewdifficulty)
            dpg.add_checkbox(label="Pro Drums", tag="view_prodrums_check", callback=on_viewprodrums)
            dpg.add_checkbox(label="2x Bass", tag="view_bass2x_check", callback=on_viewbass2x)


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

    #demo.show_demo()

    dpg.setup_dearpygui()
    dpg.show_viewport()
    view_main()
    dpg.start_dearpygui()

    # End UI
    dpg.destroy_context()