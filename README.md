# Hydra
Score optimizer / path viewer for Clone Hero drums!
 
Featuring a song browsing UI to make information convenient to access even for large song libraries.

## Quick-start guide

1. Download the [latest release](https://github.com/DragonDelgar/hydra/releases).
2. Extract the Hydra folder to any location and run Hydra.exe.
3. Click **Select folder...** and then pick your Clone Hero songs folder (or whichever folder contains the songs you want to browse).
4. Click **Scan charts**.
5. Once it's done, songs should appear in a table. Search for or find the page of the song you want to get the path for, then click the song.
6. Click the big  **Analyze paths!** button.
7. Once it's done, paths should appear on the left side. The first path is optimal. There may be other paths tied for optimal, listed under the same score. Below that there  may be some additional paths on slightly lower scores, which could come in handy if the optimal path is unusually difficult.
8. Click a path on the left side to show its details on the right side.
9. You can return to browsing songs by X-ing out of the Song Details window.

<p align="center"><img src="/resource/icon_app.png" width="200"></p>

## Path notation guide

I want to get around to a more complete guide on paths and optimal scoring mechanics, but for now here's a primer on the pathing notation Hydra uses. It's based on skip counting notation that's been around for a long time.

### Skips

Since drum SP is activated at set activation points, and controlling where you activate boils down to skipping activations until you reach the one you want, a path is mainly just a list of how many to skip each time.

Examples:
| Path | Meaning |
| --- | --- |
| `1 2 0` | Skip 1, then activate. Skip 2, then activate. Skip 0 (activate right away without skipping). |
| `0 0 0 0` | Activate without skipping for the whole song. (For clarity reasons, Hydra doesn't leave out trailing 0s.) |

### Squeeze In / Squeeze Out (+/-)

If another SP phrase comes along while you're in active Star Power, and you hit it, that bar of SP immediately goes into your active SP, which you might call chaining or extending SP. In some cases, though, this SP phrase might come right when your active SP is running out, in which case you can actually _control_ whether the SP chains or not by hitting that SP phrase early or late.

**A skip with a minus on it** means squeeze out: There will be an SP phrase right when your active SP ends and it needs to not chain. This can be achieved by activating early (so your SP ends earlier), or hitting the last note in the SP phrase late. Or both.

**A skip with a plus on it** means squeeze in: There will be an SP phrase right when your active SP ends and it needs to chain. This can be achieved by activating late (so your SP ends later), or hitting the last note in the SP phrase early. Or both.

Examples:
| Path | Meaning |
| --- | --- |
| `1 2+` | Skip 1, then activate. Skip 2, then activate, and when the activation is about to run out make sure to chain the SP phrase. |
| `1- 1` | Skip 1, then activate, and when the activation is about to run out make sure to not chain the SP phrase. Skip 1, then activate. |

### Calibration Fills (E)

When you gain your second bar of SP, the game makes sure that even though you can activate SP now, if an activation is already coming up (in the next measure or two), it won't suddenly appear and surprise you. One quirk of the Clone Hero engine, though, is that this timing condition is based not on the charted positions of notes, but on real time. So in some charts, whether you hit that second bar of SP early or late can control whether an activation appears or not. Even if that fill is just skipped anyway, it could throw off your counting to have a fill that's only there sometimes.

**A skip with E on it** means that this situation will happen when you gain the 2nd bar of SP, and that the skip count assumes the early fill happened:

If you trigger the early fill, either by chance or purposefully by hitting the SP-granting note with early timing, then the skip count is the one that's listed.

If you don't trigger the early fill, either by chance or purposefully by hitting the SP-granting note with late timing, then skip count will be 1 less than what's listed. Note that in Clone Hero, drum activations don't cause you to miss out on any points, so it's OK to trigger E fills just to skip them.

Another way to think about it is that if the skip has an E on it, then you know the first skip is right after gaining SP and you can count it even if it doesn't appear. Either way, this notation should cue you in to adjust your skip counting whichever way makes sense.

Lastly, this timing is _also_ offset by your calibration. If your calibration is not zero, it's likely that all of these E fills will either occur or not occur by default.

Examples:
| Path | Meaning |
| --- | --- |
| `E2` | When you gain the 2nd bar of SP, if an early fill occurred, treat this as a 2. If the early fill didn't occur, treat this as a 1. |
| `E0` | The activation is *on* the early fill, so in order to not miss this activation, triggering the early fill (by hitting the SP early) is required. |
