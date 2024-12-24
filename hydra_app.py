import os
import pathlib
import configparser
import sqlite3
import time

import dearpygui.dearpygui as dpg

import hydra.hymisc as hymisc
import hydra.hyutil as hyutil

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
    version = HyAppUserSetting()
    chartfolder = HyAppUserSetting()
    lastscanfolder = HyAppUserSetting()
    view_difficulty = HyAppUserSetting()
    view_prodrums = HyAppUserSetting(getbool=True)
    view_bass2x = HyAppUserSetting(getbool=True)
    
    def __init__(self):
        # Load setting values from config
        self.cfg = configparser.ConfigParser()
        try:
            with open(hymisc.INIPATH, 'r') as cfgfile:
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
            ('lastscanfolder', ""),
            ('view_difficulty', 'Expert'),
            ('view_prodrums', 'True'),
            ('view_bass2x', 'True')
        ]:
            if key not in loadedsettings:
                loadedsettings[key] = default
            
        # Save in case anything was filled in
        self.savecfg()

    def savecfg(self):
        with open(hymisc.INIPATH, 'w') as cfgfile:
            self.cfg.write(cfgfile)

class HyAppState:
    """Manages Hydra's state."""
    def __init__(self):
        self.usettings = HyAppUserSettings()
    
    
"""UI callbacks"""


def on_viewport_resize():
    width = dpg.get_viewport_width() - 22 - 400
    height = 134
    dpg.configure_item("scanprogress", pos=(200, 200),
                        width=width, height=height)

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
    dpg.show_item("scanprogress")
    count = hyutil.scan_charts(appstate.usettings.chartfolder,
                       progress_discoveringcharts,
                       progress_chartsdiscoveredresult,
                       progress_libraryadd,
                       )
    
    dpg.configure_item("scanprogress_bar", overlay=f"{count}/{count}")
    dpg.show_item("scanprogress_done")
    time.sleep(1.5)
    dpg.hide_item("scanprogress")
    dpg.hide_item("scanprogress_chartsfound")
    dpg.hide_item("scanprogress_bartext")
    dpg.hide_item("scanprogress_bar")
    dpg.hide_item("scanprogress_done")
    
    appstate.usettings.lastscanfolder = appstate.usettings.chartfolder
    refresh_librarytitle()
    refresh_chartfolder()


"""Progress callbacks (reactions to processing rather than UI interactions)"""


def progress_discoveringcharts(count):
    """As charts are discovered during a scan."""
    indicator = '.' * (count//100 % 5 + 1)
    dpg.set_value("scanprogress_discovering", f"Discovering charts{indicator}")
    
def progress_chartsdiscoveredresult(count):
    """When charts have been fully discovered during a scan."""
    dpg.set_value("scanprogress_discovering", f"Discovering charts...")
    dpg.set_value("scanprogress_chartsfound", f"{count} charts found.")
    dpg.show_item("scanprogress_chartsfound")
    dpg.show_item("scanprogress_bartext")
    dpg.show_item("scanprogress_bar")
    dpg.set_value("scanprogress_bar", 0.0)
    dpg.configure_item("scanprogress_bar", overlay=f"0/{count}")

def progress_libraryadd(count, totalcount):
    """As charts are added to library during a scan."""
    dpg.set_value("scanprogress_bar", count/totalcount)
    dpg.configure_item("scanprogress_bar", overlay=f"{count}/{totalcount}")

    
"""UI view controls"""


def view_main():
    """Main view with a small upper pane for settings and a large lower pane
    to view the song library.
    
    """
    dpg.show_item("mainwindow")
    dpg.set_primary_window("mainwindow", True)
    
    dpg.configure_item("scanprogress", width=-1, height=-1)

    refresh_chartfolder()
    refresh_viewdifficulty()
    refresh_viewprodrums()
    refresh_viewbass2x()
    refresh_librarytitle()


"""UI population"""


def refresh_chartfolder():
    folder = appstate.usettings.chartfolder
    lastscan = appstate.usettings.lastscanfolder
    dpg.set_value("chartfoldertext", f"Chart folder: {folder}")
    repeat_scan = lastscan != "" and folder == lastscan
    labeltxt = "Refresh scan" if repeat_scan else "Scan charts"
    dpg.configure_item("scanbutton", enabled=folder != "", label=labeltxt)
    
    
def refresh_viewdifficulty():
    dpg.set_value("view_difficulty_combo", appstate.usettings.view_difficulty)
def refresh_viewprodrums():
    dpg.set_value("view_prodrums_check", appstate.usettings.view_prodrums)
def refresh_viewbass2x():
    dpg.set_value("view_bass2x_check", appstate.usettings.view_bass2x)


def refresh_librarytitle():
    cxn = sqlite3.connect(hymisc.DBPATH)
    cur = cxn.cursor()

    try:
        cur.execute("SELECT COUNT(*) FROM charts")
        chartcount = cur.fetchone()[0]
    except sqlite3.OperationalError:
        chartcount = 0
        
    countstr = "(1 chart)" if chartcount == 1 else f"({chartcount} charts)"
    dpg.configure_item("librarytitle", label=f"Library {countstr}")
    
    cxn.close()


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
        dpg.add_separator(label="Library", tag="librarytitle")
        with dpg.group(horizontal=True):
            dpg.add_text("View:")
            dpg.add_combo(("Expert", "Hard", "Medium", "Easy"), tag="view_difficulty_combo", callback=on_viewdifficulty)
            dpg.add_checkbox(label="Pro Drums", tag="view_prodrums_check", callback=on_viewprodrums)
            dpg.add_checkbox(label="2x Bass", tag="view_bass2x_check", callback=on_viewbass2x)

    with dpg.window(tag="scanprogress", show=False, modal=True, no_title_bar=True, no_close=True, no_resize=True, no_move=True, width=-1, height=-1,pos=(40,40)):
        dpg.add_text("Discovering charts...", tag="scanprogress_discovering")
        dpg.add_text("0 charts found.", tag="scanprogress_chartsfound", show=False)
        dpg.add_text("Adding to library...", tag="scanprogress_bartext", show=False)
        dpg.add_progress_bar(tag="scanprogress_bar", show=False, width=-1)
        dpg.add_text("Done!", tag="scanprogress_done", show=False)

    with dpg.theme() as standard_theme:
        with dpg.theme_component(dpg.mvButton, enabled_state=True):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 100, 100))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (0, 120, 120))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 200, 200))
            
        with dpg.theme_component(dpg.mvButton, enabled_state=False):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (200, 200, 200))
            dpg.add_theme_color(dpg.mvThemeCol_Button, (100, 100, 100))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (100, 100, 100))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (100, 100, 100))

    dpg.bind_theme(standard_theme)

    # Begin UI
    icopath = str(hymisc.ICOPATH)
    dpg.create_viewport(title="Hydra v0.0.1", width=1280, height=720, small_icon=icopath, large_icon=icopath)

    #demo.show_demo()
    
    dpg.set_viewport_resize_callback(on_viewport_resize)

    dpg.setup_dearpygui()
    dpg.show_viewport()
    view_main()
    dpg.start_dearpygui()

    # End UI
    dpg.destroy_context()