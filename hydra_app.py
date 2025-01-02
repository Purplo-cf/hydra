import os
import pathlib
import configparser
import sqlite3
import time
import json

import dearpygui.dearpygui as dpg

import hydra.hymisc as hymisc
import hydra.hyutil as hyutil
import hydra.hyrecord as hyrecord

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
    depth_value = HyAppUserSetting()
    depth_mode = HyAppUserSetting()
    
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
            ('view_bass2x', 'True'),
            ('depth_value', '5'),
            ('depth_mode', 'scores'),
        ]:
            if key not in loadedsettings:
                loadedsettings[key] = default
            
        # Save in case anything was filled in
        self.savecfg()

    def savecfg(self):
        with open(hymisc.INIPATH, 'w') as cfgfile:
            self.cfg.write(cfgfile)
            
    def chartmode_key(self):
        """A combined string to match up values of (difficulty, prodrums, bass2x)"""
        prodrums = "Pro Drums" if appstate.usettings.view_prodrums else "Drums"
        bass = "2x Bass" if appstate.usettings.view_bass2x else "1x Bass"
        return f"{appstate.usettings.view_difficulty} {prodrums}, {bass}"

class HyAppRecordBook:
    """Code-accessible collection of records that have been generated.
    
    Is saved and loaded much like usersettings.
    
    Top level organization is by hyhash.
    In each hyhash are ref values and a 'records' map of
    chartmode_key: hyrecord.
    
    hyhash: Hash of the chart file. Not comparable to other apps' song hashes.
    
    """
    def __init__(self):
        """Load existing hyrecords from file or initialize it"""
        # Initialize
        self.book = {}
        
        # Import from save file
        try:
            with open(hymisc.BOOKPATH, 'r') as jsonfile:
                book_json = json.load(jsonfile)
                for songhash, songinfo in book_json.items():
                    # Copy song info
                    self.book[songhash] = {
                        'ref_name': songinfo['ref_name'],
                        'ref_artist': songinfo['ref_artist'],
                        'ref_charter': songinfo['ref_charter'],
                        'records': {chartmode: hyrecord.HydraRecord.from_dict(record_dict) for chartmode, record_dict in songinfo['records'].items()},
                    }
        except FileNotFoundError: #():#(FileNotFoundError, json.decoder.JSONDecodeError, TypeError, KeyError):
            # To do: Errors other than FileNotFoundError should be handled
            # without nuking self.book, since when updating hydra versions it'd
            # be nice to mark records as stale rather than erasing them all.
            self.book = {}
        
        # Resave / create save file
        self.savejson()
            
    def add_song(self, hyhash, name, artist, charter):
        """Add an entry for the given hash.
        
        Multiple song library folders can have the same hyhash
        and therefore which metadata is added with the hyhash can depend on
        which gets processed first, but realistically if the hyhash is the same
        then title/artist/charter will be the same. Anyway, they're just
        reference values in case you're searching through the json manually.
        
        """
        if hyhash in self.book:
            return
        
        self.book[hyhash] = {
            # Some metadata for convenience if digging through the json
            'ref_name': name,
            'ref_artist': artist,
            'ref_charter': charter,
            'records': {},
        }
        
        self.savejson()
        
    def add_record(self, hyhash, chartmode, record):
        """Adds a HydraRecord.
        
        Requires the song to have been added beforehand.
        
        """
        self.book[hyhash]['records'][chartmode] = record
        
        self.savejson()
        
    def savejson(self):
        """Save current state to json file."""
        with open(hymisc.BOOKPATH, 'w') as jsonfile:
            json.dump(self.book, jsonfile, default=lambda r: r.__dict__, indent=4)

class HyAppState:
    """Manages Hydra's state."""
    TABLE_ROWCOUNT = 15
    TABLE_COLCOUNT = 5
    
    def __init__(self):
        self.usettings = HyAppUserSettings()
        self.hyrecordbook = HyAppRecordBook()
        self.table_viewpage = 0
        self.librarysize = 0
        self.search = None
        
        self.current_path_selectable = None
        self.selected_song_row = None
    
    def pagecount(self):
        return self.librarysize // self.TABLE_ROWCOUNT
            
            
    def get_record(self, hyhash, chartmode):
        try:
            return self.hyrecordbook.book[hyhash]['records'][chartmode]
        except KeyError:
            return None
            
    def get_selected_record(self):
        return self.get_record(self.selected_song_row[0], self.usettings.chartmode_key())
        
"""UI callbacks"""


def on_viewport_resize():
    width = dpg.get_viewport_width() - 22 - 400
    height = 158
    dpg.configure_item("scanprogress", pos=(200, 200),
                        width=width, height=height)
    
    width = dpg.get_viewport_width() - 22 - 80
    height = dpg.get_viewport_height() - 22 - 80
    dpg.configure_item("songdetails", pos=(40, 40),
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

def on_depth_value(sender, app_data):
    appstate.usettings.depth_value = app_data

def on_depth_mode(sender, app_data):
    appstate.usettings.depth_mode = app_data
    
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

def on_library_rowclick(sender, app_data, user_data):
    # Cancel out selected states (we just want button functionality)
    for s in all_table_row_selectables():
        dpg.set_value(s, False)
        
    # Do nothing for empty rows
    if user_data is None:
        return
        
    # Update selected row and update UI
    appstate.selected_song_row = user_data
    view_showsongdetails()

def on_path_selected(sender, app_data, record):
    """
    
    user_data: HyRecordPath.
    
    """
    print(f"{sender}, {app_data}, {record}")
    
    # "Unlock" the previous selectable
    if appstate.current_path_selectable:
        dpg.set_value(appstate.current_path_selectable, False)
        dpg.configure_item(appstate.current_path_selectable, enabled=True)
    
    appstate.current_path_selectable = sender
    
    # "Lock" the new selected path: only deselectable by selecting another.
    dpg.configure_item(sender, enabled=False)
    
    # Rebuild path details panel
    dpg.delete_item("songdetails_pathdetails", children_only=True)
    
    with dpg.tree_node(label="Multiplier squeezes", parent="songdetails_pathdetails", default_open=True):
        dpg.bind_item_font(dpg.last_item(), "MainFont24")
        if record.multsqueezes:
            for msq in record.multsqueezes:
                with dpg.tree_node(label=f"{msq.notationstr()}  ({msq.chord.rowstr()})", default_open=False):
                    dpg.bind_item_font(dpg.last_item(), "MonoFont")
                    dpg.add_text(f"Hit {msq.squeezecount} high-value note{'' if msq.squeezecount == 1 else 's'} last for +{msq.points}.")
        else:
            dpg.add_text("None.")
            dpg.bind_item_font(dpg.last_item(), "MonoFont")
        
#    with dpg.tree_node(label="Activations", parent="songdetails_pathdetails", default_open=True):
    
    with dpg.tree_node(label="Score breakdown", parent="songdetails_pathdetails", default_open=True):
        dpg.bind_item_font(dpg.last_item(), "MainFont24")
        nums = [
            record.score_base, record.score_combo, record.score_sp,
            record.score_solo, record.score_accents, record.score_ghosts,
            record.totalscore()
        ]
        numwidth = max([len(str(n)) for n in nums])
        numstrs = [' '*(numwidth - len(str(n))) + str(n) for n in nums]
        dpg.add_text(f"Notes:            {numstrs[0]}")
        dpg.bind_item_font(dpg.last_item(), "MonoFont")
        dpg.add_text(f"Combo Bonus:      {numstrs[1]}")
        dpg.bind_item_font(dpg.last_item(), "MonoFont")
        dpg.add_text(f"Star Power:       {numstrs[2]}")
        dpg.bind_item_font(dpg.last_item(), "MonoFont")
        dpg.add_text(f"Solo Bonus:       {numstrs[3]}")
        dpg.bind_item_font(dpg.last_item(), "MonoFont")
        dpg.add_text(f"Accent Notes:     {numstrs[4]}")
        dpg.bind_item_font(dpg.last_item(), "MonoFont")
        dpg.add_text(f"Ghost Notes:      {numstrs[5]}")
        dpg.bind_item_font(dpg.last_item(), "MonoFont")
        dpg.add_text(f"\nTotal Score:      {numstrs[6]}")
        dpg.bind_item_font(dpg.last_item(), "MonoFont")

def on_pageleft(sender, app_data):
    appstate.table_viewpage = max(appstate.table_viewpage - 1, 0)
    refresh_tableview()
   
def on_pageright(sender, app_data):
    appstate.table_viewpage = min(appstate.table_viewpage + 1, appstate.pagecount())
    refresh_tableview()

def on_run_chart(sender, app_data, user_data):
    # Show modal
    dpg.configure_item("songdetails", no_title_bar=True, no_close=True)
    dpg.hide_item("songdetails_upperpanel")
    dpg.hide_item("songdetails_lowerpanel")
    dpg.show_item("songdetails_progresspanel")
    # run chart
    chartfile = hyutil.discover_charts(appstate.selected_song_row[4])[0][0]
    record = hyutil.run_chart(chartfile)
    
    appstate.hyrecordbook.add_song(appstate.selected_song_row[0], appstate.selected_song_row[1], appstate.selected_song_row[2], appstate.selected_song_row[3])
    
    appstate.hyrecordbook.add_record(appstate.selected_song_row[0], appstate.usettings.chartmode_key(), record)
    # pause
    time.sleep(1.5)
    # update record displays
    refresh_tableview()
    refresh_songdetails()
    
    # hide modal
    dpg.show_item("songdetails_upperpanel")
    dpg.show_item("songdetails_lowerpanel")
    dpg.hide_item("songdetails_progresspanel")
    dpg.configure_item("songdetails", no_title_bar=False, no_close=False)

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
    
    refresh_depthvalue()
    refresh_depthmode()
    
    
def view_showsongdetails():
    """Shows the song details window and necessarily updates the info.
    
    Closing the song details window is just via close button.
    
    """
    dpg.show_item("songdetails")
    refresh_songdetails()
    
    
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

def refresh_depthvalue():
    dpg.set_value("inp_depthvalue", int(appstate.usettings.depth_value))
def refresh_depthmode():
    dpg.set_value("inp_depthmode", appstate.usettings.depth_mode)

def refresh_tableview():
    """Display a particular page of the song library.
    
    Other info like the size of the library is already known and doesn't need
    the db to be accessed.
    
    """    
    cxn = sqlite3.connect(hymisc.DBPATH)
    cur = cxn.cursor()

    try:
        if appstate.search:
            searchparam = f"%{appstate.search}%"
            where = "WHERE name LIKE ? OR artist LIKE ?"
            fullcount = cur.execute(f"SELECT COUNT(*) FROM charts {where}", (searchparam, searchparam)).fetchone()[0]
            entries = cur.execute(f"SELECT * FROM charts {where} ORDER BY name LIMIT {appstate.TABLE_ROWCOUNT} OFFSET {appstate.table_viewpage * appstate.TABLE_ROWCOUNT}", (searchparam,searchparam)).fetchall()
        else:
            fullcount = appstate.librarysize
            entries = cur.execute(f"SELECT * FROM charts ORDER BY name LIMIT {appstate.TABLE_ROWCOUNT} OFFSET {appstate.table_viewpage * appstate.TABLE_ROWCOUNT}").fetchall()
        cxn.close()
    except sqlite3.OperationalError:
        entries = []
        cxn.close()
            
    # subset of db columns shown on the table
    colkeys = ['name', 'artist', 'charter', 'folder']
            
    # Assign library-based header names
    for i, s in enumerate([hymisc.TABLE_COL_INFO[k][1] for k in colkeys]):
        dpg.configure_item(f"table_header{i}", label=s)    
    
    # Assign record-based header name
    dpg.configure_item(f"table_header{appstate.TABLE_COLCOUNT - 1}", label="Path")
    
    for r in range(appstate.TABLE_ROWCOUNT):
        # Fill library-based cells
        for c, colkey in enumerate(colkeys):
            try:
                dpg.set_value(f"table[{r}, {c}]", entries[r][hymisc.TABLE_COL_INFO[colkey][0]])
                dpg.bind_item_font(f"table[{r}, {c}]", "MainFont")
            except IndexError:
                dpg.set_value(f"table[{r}, {c}]", "-----")
                dpg.bind_item_font(f"table[{r}, {c}]", "MonoFont")
                
        # Fill record-based cell
        try:
            record = appstate.get_record(entries[r][0], appstate.usettings.chartmode_key())
            if record:
                dpg.configure_item(f"table[{r}, {appstate.TABLE_COLCOUNT - 1}]", label=record.paths[0].pathstring(), user_data=entries[r])
                dpg.bind_item_theme(f"table[{r}, {appstate.TABLE_COLCOUNT - 1}]", "bestpath_theme")
                dpg.bind_item_font(f"table[{r}, {appstate.TABLE_COLCOUNT - 1}]", "MonoFont")
            else:
                dpg.configure_item(f"table[{r}, {appstate.TABLE_COLCOUNT - 1}]", label="(New...)", user_data=entries[r])
                dpg.bind_item_theme(f"table[{r}, {appstate.TABLE_COLCOUNT - 1}]", "newsong_theme")
                dpg.bind_item_font(f"table[{r}, {appstate.TABLE_COLCOUNT - 1}]", "MainFont")
        except IndexError:
            dpg.configure_item(f"table[{r}, {appstate.TABLE_COLCOUNT - 1}]", label="-----", user_data=None)
            dpg.bind_item_theme(f"table[{r}, {appstate.TABLE_COLCOUNT - 1}]", "newsong_theme")
            dpg.bind_item_font(f"table[{r}, {appstate.TABLE_COLCOUNT - 1}]", "MonoFont")
    
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
    
def refresh_songdetails():
    dpg.set_value("songdetails_songtitle", appstate.selected_song_row[1])
    dpg.set_value("songdetails_songartist", appstate.selected_song_row[2])
    dpg.set_value("songdetails_songcharter", appstate.selected_song_row[3])
    dpg.set_value("songdetails_songhash", appstate.selected_song_row[0])
    
    dpg.configure_item("songdetails", label=f"Song Details - {appstate.usettings.chartmode_key()}")
        
    viewed_record = appstate.get_selected_record()
    
    # Lower Panel - or quit if this row has no record yet
    
    if not viewed_record:
        dpg.hide_item("songdetails_pathpanel")
        dpg.hide_item("songdetails_pathdetails")
        dpg.hide_item("songdetails_pathdivider")
        dpg.show_item("songdetails_nopathsyet")
        return
    
    dpg.show_item("songdetails_pathpanel")
    dpg.show_item("songdetails_pathdetails")
    dpg.show_item("songdetails_pathdivider")
    dpg.hide_item("songdetails_nopathsyet")
    
    def scorestr(score):
        s = str(score)
        r = ""
        digits_left = len(s)
        for c in s:
            r += c
            digits_left -= 1

            if digits_left % 3 == 0 and digits_left != 0:
                r += ','
        return r
    
    # Rebuild path list
    
    dpg.delete_item("songdetails_pathpanel", children_only=True)
    appstate.current_path_selectable = None
        
    current_score = None 
    current_treenode = None
    for i, p in enumerate(viewed_record.paths):
        if current_score != p.totalscore():
            current_score = p.totalscore()
            current_treenode = dpg.add_tree_node(label=scorestr(current_score), parent="songdetails_pathpanel", default_open=True)
            dpg.bind_item_font(current_treenode, "MonoFont")
        
        pathselectable = dpg.add_selectable(label=p.pathstring(), parent=current_treenode, callback=on_path_selected, user_data=p, default_value=i==0)
        if i == 0:
            autoselect = pathselectable
        
    # Auto select the first path
    on_path_selected(autoselect, True, viewed_record.paths[0])
    
    
    
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

    # Textures
    with dpg.texture_registry():
        w, h, c, d = dpg.load_image(str(hymisc.ICOPATH_NOTE))
        dpg.add_static_texture(width=w, height=h, default_value=d, tag="icon_note")
        w, h, c, d = dpg.load_image(str(hymisc.ICOPATH_SNAKE))
        dpg.add_static_texture(width=w, height=h, default_value=d, tag="icon_snake")
        
    # Fonts
    with dpg.font_registry():
        with dpg.font(hymisc.FONTPATH_ANTQ, 18, tag="MainFont"):
            dpg.add_font_range_hint(dpg.mvFontRangeHint_Japanese)
        with dpg.font(hymisc.FONTPATH_ANTQ, 24, tag="MainFont24"):
            dpg.add_font_range_hint(dpg.mvFontRangeHint_Japanese)
        dpg.add_font(hymisc.FONTPATH_MONO, 18, tag="MonoFont")
        
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
                            
                        dpg.add_selectable(tag=f"table[{r}, {appstate.TABLE_COLCOUNT - 1}]", label=f"table[{r}, {appstate.TABLE_COLCOUNT - 1}]", span_columns=True, callback=on_library_rowclick)
                        
                            
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

    with dpg.window(tag="scanprogress", show=False, modal=True, no_title_bar=True, no_close=True, no_resize=True, no_move=True):
        dpg.add_text("Discovering charts...", tag="scanprogress_discovering")
        dpg.add_text("0 charts found.", tag="scanprogress_chartsfound", show=False)
        dpg.add_text("Adding to library...", tag="scanprogress_bartext", show=False)
        dpg.add_progress_bar(tag="scanprogress_bar", show=False, width=-1)
        dpg.add_text("Done!", tag="scanprogress_done", show=False)
    
    
    with dpg.window(label="Song Details", tag="songdetails", show=False, modal=True, no_title_bar=False, no_close=False, no_resize=True, no_move=True):
        with dpg.group(tag="songdetails_upperpanel", horizontal=True, height=170):
            with dpg.child_window(tag="songdetails_songinfo", width=390, horizontal_scrollbar=True):
                with dpg.group(horizontal=True):
                    dpg.add_image("icon_note")
                    dpg.add_text("Song Title", tag="songdetails_songtitle")
                    dpg.bind_item_font(dpg.last_item(), "MainFont24")
                with dpg.group(horizontal=True):
                    dpg.add_image("icon_snake")
                    dpg.add_text("Song Artist", tag="songdetails_songartist")
                    dpg.bind_item_font(dpg.last_item(), "MainFont24")
                with dpg.group(horizontal=True):
                    dpg.add_image("icon_note")
                    dpg.add_text("Charter", tag="songdetails_songcharter")
                    dpg.bind_item_font(dpg.last_item(), "MainFont24")
                with dpg.group(horizontal=True):
                    dpg.add_image("icon_snake")
                    dpg.add_text("Hash", tag="songdetails_songhash", color=(180,180,180,255))
                    dpg.bind_item_font(dpg.last_item(), "MonoFont")
            with dpg.child_window(tag="songdetails_songanalysis", width=340):
                dpg.add_text("/// Space for future stuff! ///") # Song Traits?
            with dpg.child_window(tag="songdetails_controls", width=-1):
                with dpg.group(horizontal=True):
                    dpg.add_text("Extra depth below optimal:")
                    dpg.add_input_int(tag="inp_depthvalue", width=140, default_value=1, callback=on_depth_value)
                    dpg.add_combo(("scores", "points"), tag="inp_depthmode", default_value="scores", width=80, callback=on_depth_mode)
                dpg.add_spacer(height=0)
                dpg.add_button(tag="runbutton", label="Analyze paths!", width=-1,height=-1, callback=on_run_chart)
                dpg.bind_item_font(dpg.last_item(), "MainFont24")
                    
                    #dpg.add_text("???")
        with dpg.group(tag="songdetails_lowerpanel", horizontal=True, height=-1):
            dpg.add_text("No paths generated yet.", tag="songdetails_nopathsyet", show=False)
            dpg.add_child_window(tag="songdetails_pathpanel", border=False, width=540)
            with dpg.child_window(tag="songdetails_pathdivider", border=False, width=40, frame_style=True):
                dpg.add_text(" >>>", pos=(5,0))
                
            with dpg.child_window(tag="songdetails_pathdetails", border=False, width=-1):
                dpg.add_text("Filler - Path Details")
        #dpg.add_text("Song Name", tag="songdetails_name")
        with dpg.group(tag="songdetails_progresspanel", show=False):
            dpg.add_text("Test")

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
            
    with dpg.theme(tag="bestpath_theme"):
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (250,210,0))
            
    with dpg.theme(tag="newsong_theme"):
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Text, (100,100,100))

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