# Hydra User Guide

Here's a run-through of the Hydra UI. Screens are presented, then explained from top to bottom.

## Main Screen

View your song library and quickly reference optimal paths for songs.

<p align="center"><img src="/docs/images/app_library.PNG"></p>

### Select folder...
Browse for your song folder.

This will probably be your Clone Hero song folder. Hydra will find all charts in subfolders.

In the popup you can click the 'E' to present a text box if you want to paste a path in.

### Scan charts / Refresh scan
Starts a scan and updates what songs will be viewable in Hydra.

If the selected folder was your last scan, the button will say `Refresh scan`.

Currently, songs require a valid ini file to show up. There may be a case where a song is playable in Clone Hero yet Hydra calls it invalid, but this should be very rare.

If a song fails, it'll be skipped. The progress window will list them for you when the scan completes. Once the scan is done, all successful songs will appear on
the main screen!

Songs that were scanned remain visible until the next scan, even if you did something to those chart files. If you add, remove, or edit songs, be sure to re-scan.

### View Options (Difficulty/Pro/2x Bass)
Path/scoring analysis depends on difficulty, whether it's Pro Drums, and whether 2x bass is enabled. When you analyze a song, that analysis result
is for that particular combination of options and it'll only be visible when that combination is selected.

For example, if you analyzed a song with 2x Bass enabled, but want to see what it would be with 1x bass, simply uncheck 2x Bass and
analyze the song again. Whenever you re-check 2x Bass, _that_ analysis will come back.

### Search
Filter the song library by an input string. Only songs with titles or artists that match will be shown.

### Library table
The list of songs from the latest scan. The songs are filtered by the search box. If a song has been analyzed with the current view options (difficulty/pro/2x bass), the 
top path will appear in the Path column for a quick reference.

Click on a song's row in the table to go to the details screen for that song.

### Page left/right
Down by the bottom are arrow buttons to move between pages of your song library.

## Song Details Screen

Clicking into a song will lead to this screen. This screen displays analysis for the current View Options (difficulty/pro/2x bass).

<p align="center"><img src="/docs/images/app_songdetails_analyzed.PNG"></p>

### Song Metadata (upper left)
Information pulled from the chart's ini during the latest scan: Title, Artist, Charter.

Lastly, a hash/checksum (the big hexadecimal number) is also shown here; identical chart files will have the same value. However, this comparison is only good
within Hydra. Clone Hero and other apps have their own versions of this and they probably don't align.

### Analysis Controls (upper right)
Look here to generate paths for a song (and a lot of scoring info too).
#### Depth Setting
A global setting is shown here for how many extra paths below optimal you'd like Hydra to keep during analysis. These paths are worse, but usually only by a little bit. Only a few are really necessary, in case the optimal path is unusually difficult.

Note that the more extra paths are allowed, the longer analysis will take, though a few should be no problem.

There are two depth modes. You can keep some extra paths based on a certain number of `scores` (i.e. "the next best score under optimal")
or a certain amount of `points` (i.e. "paths that are within 2000 points of optimal").
#### Analyze button
Smash this button to analyze the song and generate paths. The result will be saved and pulled up again whenever you check on this song in the future.

### Path List (lower left)
A list of the paths that were found, organized by score. Click on a path to view that path's details in the panel to the right.

### Path Details (lower right)
When it comes to getting an optimal score, following the optimal path is only part of the story. The rest is (sort of) explained here, though it's sort of an info dump at the moment.
But here's a walkthrough.
<p align="center"><img src="/docs/images/app_songdetails_details.PNG"></p>

#### Multiplier squeezes
When building up combo at the start of a song, sometimes the combo multiplier goes up on a multi-note chord. Since individual notes
are scored exactly when they're hit, in this situation you can control which notes are scored on the higher multiplier by hitting those notes *later*.
If those notes are also more valuable (cymbal and dynamic notes), then this can result in slightly more points.

If you've ever seen FC scores that seem to be identical but one is +15, this is what happened there.

This details panel will list out these multiplier squeezes if they happen in this song. `2x` means it happens when hitting 2x multiplier (10 notes into the song), and so on.

#### Activations

A list of activations in this path. The number from the path notation is shown as well as how many bars of SP you'll have at that activation. Measure number is also shown, if you happen to be referencing
an image or some other view of the chart.

If an activation has a calibration fill (the `E` notation), the timing of that calibration fill will be listed. Usually this will be `0ms`. The more negative the value, the more early you have to hit
to make the calibration fill show up.

Frontend: The chord that the activation is on. If it's a multi-note chord, perform a frontend squeeze by hitting the activation note first, so that the other notes are scored with the Star Power multiplier.

Backends: The notes surrounding the end of Star Power for this activation. There is probably a note at `0ms`, which is exactly when SP ends; the others are the notes right before and right after.

Perform a backend squeeze by hitting the `0ms` note early, so that it lands during Star Power.

The backends have a (made up by me) rating that just conveys how difficult it would be to fit that note into Star Power. If you're interested in double backend squeezes, look here for notes that are in the
`3ms` to `70ms` range. Or even higher if you're crazy. Whether these double backends are actually possible depends on some details that aren't considered by Hydra yet...

#### Score breakdown

The score that this path should get, following the same categories that Clone Hero uses in its results screen.

The score includes multiplier squeezes, frontend squeezes, and backend squeezes, so if you follow the path but your score has a bit less Star Power score than this readout,
one of those was probably missed. 

Double squeezes are currently not considered in this scoring unless they're `2ms` or less, there's a slight margin.
