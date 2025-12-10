# ZSimView

A lightweight viewer for **ZSim periodic HDF5 statistics**.

ZSim generates periodic statistics in HDF5 format, but inspecting these
files manually is inconvenient.\
**ZSimView** provides an easy way to load, browse, and visualize these
statistics without requiring custom scripts.

------------------------------------------------------------------------

## Features

- Loads `zsim.h5`, `zsim-ev.h5`, and `zsim-cmp.h5`
- Snapshot list with phase/time preview
- Automatic listing of fields inside each snapshot
- Displays scalar, compound, and array-of-compound records
- Table-based visualization of per-core and per-module statistics
- Preserves field selection when switching snapshots
- Optional dark mode (future extension)

------------------------------------------------------------------------

## Requirements

-   Python 3
-   PyQt5
-   h5py
-   numpy

------------------------------------------------------------------------

## Running From the Command Line

If your environment sets `LD_LIBRARY_PATH` for zsim, you **must unset
it** before running:

``` bash
unset LD_LIBRARY_PATH
python3 zsimview.py
```
------------------------------------------------------------------------

## Installing and Creating Launcher Icon (Optional)

You can install ZSimView so it appears in your system application menu.

Run:

``` bash
./INSTALL
```

This script:

-   Creates `/usr/local/bin/zsimview`
-   Writes a `.desktop` entry to\
    `~/.local/share/applications/zsimview.desktop`
-   Installs the provided icon `icon.png`
-   Ensures the GUI launches without a terminal

After installation, you can start the application by:

    zsimview

Or by selecting **ZSimView** from your desktop environment's
applications menu.

------------------------------------------------------------------------

## Common Issue: LD_LIBRARY_PATH

If you use zsim, you may have exported:

    LD_LIBRARY_PATH=<zsim build>

This breaks GUI applications that depend on the system HDF5 libraries.

Fix:

    unset LD_LIBRARY_PATH

ZSimView does not depend on zsim libraries and must use the system ones.

------------------------------------------------------------------------

