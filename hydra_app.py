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
    TABLE_ROWCOUNT = 15
    TABLE_COLCOUNT = 5
    
    def __init__(self):
        self.usettings = HyAppUserSettings()
        self.table_viewpage = 0
        self.librarysize = 0
        self.search = None
    
    def pagecount(self):
        return self.librarysize // self.TABLE_ROWCOUNT
            
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
    
    cache_librarysize()
    
    refresh_librarytitle()
    refresh_chartfolder()
    refresh_tableview()

def on_search_text(sender, app_data):
    appstate.search = None if app_data == "" else app_data
    appstate.table_viewpage = 0
    refresh_tableview()

def on_library_rowclick(sender, app_data):
    print(f"Library song clicked: {sender}, {app_data}")
    for s in all_table_row_selectables():
        if s != sender:
            dpg.set_value(s, False)

def on_pageleft(sender, app_data):
    appstate.table_viewpage = max(appstate.table_viewpage - 1, 0)
    refresh_tableview()
   
def on_pageright(sender, app_data):
    appstate.table_viewpage = min(appstate.table_viewpage + 1, appstate.pagecount())
    refresh_tableview()


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
    
    cache_librarysize()
    
    refresh_chartfolder()
    refresh_viewdifficulty()
    refresh_viewprodrums()
    refresh_viewbass2x()
    refresh_librarytitle()
    refresh_tableview()
    
    
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

def refresh_tableview():
    """Display a particular page of the song library.
    
    Other info like the size of the library is already known and doesn't need
    the db to be accessed.
    
    """    
    cxn = sqlite3.connect(hymisc.DBPATH)
    cur = cxn.cursor()

    try:
        colnames = (("name", "Name"), ("artist", "Artist"), ("charter", "Charter"), ("folder", "Folder"))
        if appstate.search:
            searchparam = f"%{appstate.search}%"
            where = "WHERE name LIKE ? OR artist LIKE ?"
            fullcount = cur.execute(f"SELECT COUNT(*) FROM charts {where}", (searchparam, searchparam)).fetchone()[0]
            entries = cur.execute(f"SELECT {','.join([t[0] for t in colnames])} FROM charts {where} ORDER BY name LIMIT {appstate.TABLE_ROWCOUNT} OFFSET {appstate.table_viewpage * appstate.TABLE_ROWCOUNT}", (searchparam,searchparam)).fetchall()
        else:
            fullcount = appstate.librarysize
            entries = cur.execute(f"SELECT {','.join([t[0] for t in colnames])} FROM charts ORDER BY name LIMIT {appstate.TABLE_ROWCOUNT} OFFSET {appstate.table_viewpage * appstate.TABLE_ROWCOUNT}").fetchall()
        cxn.close()
    except sqlite3.OperationalError:
        cxn.close()
        return
            
    # Assign library-based header names
    for i, t in enumerate(colnames):
        dpg.configure_item(f"table_header{i}", label=t[1])    
    
    # Assign record-based header name
    dpg.configure_item(f"table_header{len(colnames)}", label="Path")
    
    for r in range(appstate.TABLE_ROWCOUNT):
        # Fill library-based cells
        for c in range(len(colnames)):
            try:
                dpg.set_value(f"table[{r}, {c}]", entries[r][c])
            except IndexError:
                dpg.set_value(f"table[{r}, {c}]", "-----")
                
        # Fill record-based cell
        dpg.configure_item(f"table[{r}, {len(colnames)}]", label="Coming Soon")
        
        
    lastpage = fullcount//appstate.TABLE_ROWCOUNT
    dpg.set_value("librarypagelabel", f"{appstate.table_viewpage + 1}/{lastpage + 1}")
        
    dpg.configure_item("pageleftbutton", enabled=appstate.table_viewpage > 0)
    dpg.configure_item("pagerightbutton", enabled=appstate.table_viewpage < lastpage)
    
    if appstate.librarysize > 0:
        dpg.hide_item("libraryempty")    
        dpg.show_item("librarypopulated")
    else:
        dpg.hide_item("librarypopulated")        
        dpg.show_item("libraryempty")        
        
    

def refresh_librarytitle():
    chartcount = appstate.librarysize    
    countstr = "(1 chart)" if chartcount == 1 else f"({chartcount} charts)"
    dpg.configure_item("librarytitle", label=f"Library {countstr}")
    

""" Utility"""

def cache_librarysize():
    cxn = sqlite3.connect(hymisc.DBPATH)
    cur = cxn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM charts")
        appstate.librarysize = cur.fetchone()[0]
    except sqlite3.OperationalError:
        appstate.librarysize = 0
    cxn.close()

def all_table_row_selectables():
    return [f"table[{r}, {appstate.TABLE_COLCOUNT - 1}]" for r in range(appstate.TABLE_ROWCOUNT)]

""" Main """


if __name__ == '__main__':
    # appstate is visible to the top-level functions
    appstate = HyAppState()
            
    dpg.create_context()

    # Fonts
    with dpg.font_registry():
        with dpg.font(hymisc.FONTPATH_ANTQ, 18, tag="MainFont"):
            dpg.add_font_range_hint(dpg.mvFontRangeHint_Japanese)
    dpg.bind_font("MainFont")
    
    # Main window
    with dpg.window(label="Hydra", tag="mainwindow", show=False) as mainwindow:
        dpg.add_separator(label="Settings")
        dpg.add_text(f"Chart folder: uninitialized", tag="chartfoldertext")
        with dpg.group(horizontal=True):
            dpg.add_button(label="Select folder...", callback=on_select_chartfolder)
            dpg.add_button(tag="scanbutton", label="Scan charts", callback=on_scan_charts)
        dpg.add_spacer(height=2)
        dpg.add_separator(label="Library", tag="librarytitle")
        
        with dpg.group(tag="librarypopulated"):
            dpg.add_spacer(height=2)
            with dpg.group(horizontal=True, tag="libraryviewcontrols"):
                dpg.add_text("View:")
                dpg.add_combo(("Expert", "Hard", "Medium", "Easy"), tag="view_difficulty_combo", width=120, callback=on_viewdifficulty)
                dpg.add_checkbox(label="Pro Drums", tag="view_prodrums_check", callback=on_viewprodrums)
                dpg.add_checkbox(label="2x Bass", tag="view_bass2x_check", callback=on_viewbass2x)
            
            dpg.add_spacer(height=2)
            with dpg.group(horizontal=True, tag="librarysearch"):
                dpg.add_text("Search:")
                dpg.add_input_text(callback=on_search_text, width=282)
            
            dpg.add_spacer(height=2)
            with dpg.table(tag="librarytable"):
                for i in range(appstate.TABLE_COLCOUNT):
                    dpg.add_table_column(label=f"table_header{i}", tag=f"table_header{i}")
                for r in range(appstate.TABLE_ROWCOUNT):
                    with dpg.table_row(tag=f"table_row{r}"):
                        for c in range(appstate.TABLE_COLCOUNT - 1):
                            dpg.add_text(f"table[{r}, {c}]", tag=f"table[{r}, {c}]")
                            
                        dpg.add_selectable(tag=f"table[{r}, {appstate.TABLE_COLCOUNT - 1}]", label=f"table[{r}, {appstate.TABLE_COLCOUNT - 1}]", span_columns=True, callback=on_library_rowclick, user_data="Row Click")
                            
            dpg.configure_item("table_header0", init_width_or_weight=1)
            dpg.configure_item("table_header1", init_width_or_weight=.75)
            dpg.configure_item("table_header2", init_width_or_weight=.5)
            dpg.configure_item("table_header3", init_width_or_weight=.75)                
            dpg.configure_item("table_header4", init_width_or_weight=1)

            with dpg.group(horizontal=True, tag="librarytablecontrols"):
                dpg.add_button(tag="pageleftbutton", arrow=True, direction=dpg.mvDir_Left, callback=on_pageleft)
                dpg.add_text("0/0", tag= "librarypagelabel")
                dpg.add_button(tag="pagerightbutton", arrow=True, direction=dpg.mvDir_Right, callback=on_pageright)
        
        dpg.add_text("No songs scanned. Set a folder and scan songs to get started!", tag="libraryempty", show=False)
        
    # Showable
    dpg.add_file_dialog(
            directory_selector=True, show=False, callback=on_chartfolder_selected,
            tag="select_chartfolder", width=700 ,height=400)

    with dpg.window(tag="scanprogress", show=False, modal=True, no_title_bar=True, no_close=True, no_resize=True, no_move=True, width=-1, height=-1,pos=(40,40)):
        dpg.add_text("Discovering charts...", tag="scanprogress_discovering")
        dpg.add_text("0 charts found.", tag="scanprogress_chartsfound", show=False)
        dpg.add_text("Adding to library...", tag="scanprogress_bartext", show=False)
        dpg.add_progress_bar(tag="scanprogress_bar", show=False, width=-1)
        dpg.add_text("Done!", tag="scanprogress_done", show=False)

    # Theme
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
    #dpg.show_font_manager()
    
    dpg.set_viewport_resize_callback(on_viewport_resize)

    dpg.setup_dearpygui()
    dpg.show_viewport()
    view_main()
    dpg.start_dearpygui()

    # End UI
    dpg.destroy_context()