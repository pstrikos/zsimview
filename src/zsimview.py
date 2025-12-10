#!/usr/bin/env python3
import sys
import os
import argparse

import numpy as np
import h5py

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QListWidget,
    QTableWidget, QTableWidgetItem, QLabel,
    QFileDialog, QMessageBox, QAction
)
from PyQt5.QtCore import Qt


class ZSimHDFViewer(QMainWindow):
    def __init__(self, h5_path=None):
        super().__init__()
        self.setWindowTitle("ZSim HDF5 Viewer")
        self.resize(1200, 700)

        self.h5_file = None
        self.dset = None  # /stats dataset
        self.current_snapshot_index = None
        self.current_record = None  # stats[i]['root']

        self._build_ui()
        self._build_menu()

        if h5_path:
            self.open_file(h5_path)

    # ---------- UI ----------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout()
        central.setLayout(main_layout)

        # Left: snapshot list
        left_layout = QVBoxLayout()
        self.snapshot_list = QListWidget()
        self.snapshot_list.currentRowChanged.connect(self.on_snapshot_selected)
        left_layout.addWidget(QLabel("Snapshots"))
        left_layout.addWidget(self.snapshot_list)

        # Middle: field list
        mid_layout = QVBoxLayout()
        self.field_list = QListWidget()
        self.field_list.currentRowChanged.connect(self.on_field_selected)
        mid_layout.addWidget(QLabel("Fields in snapshot"))
        mid_layout.addWidget(self.field_list)

        # Right: table + info
        right_layout = QVBoxLayout()
        self.info_label = QLabel("Select a snapshot and a field.")
        self.info_label.setWordWrap(True)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        right_layout.addWidget(self.info_label)
        right_layout.addWidget(self.table)

        main_layout.addLayout(left_layout, 1)
        main_layout.addLayout(mid_layout, 1)
        main_layout.addLayout(right_layout, 3)

    def _build_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open HDF5...", self)
        open_action.triggered.connect(self.open_dialog)
        file_menu.addAction(open_action)

        quit_action = QAction("&Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    # ---------- File handling ----------

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open HDF5 file",
            os.getcwd(),
            "HDF5 files (*.h5 *.hdf5);;All files (*)"
        )
        if path:
            self.open_file(path)

    def open_file(self, path):
        # Close previous
        if self.h5_file is not None:
            try:
                self.h5_file.close()
            except Exception:
                pass
            self.h5_file = None
            self.dset = None

        try:
            self.h5_file = h5py.File(path, "r")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")
            return

        if "stats" not in self.h5_file:
            QMessageBox.critical(self, "Error", "File does not contain a 'stats' dataset.")
            self.h5_file.close()
            self.h5_file = None
            return

        self.dset = self.h5_file["stats"]

        # Basic sanity check: compound with 'root' field
        dt = self.dset.dtype
        if "root" not in dt.fields:
            QMessageBox.critical(self, "Error", "Dataset 'stats' does not contain a 'root' field.\n"
                                                "This viewer is tailored to ZSim/BZSim files.")
            self.h5_file.close()
            self.h5_file = None
            self.dset = None
            return

        # Populate snapshot list
        self.snapshot_list.clear()
        self.field_list.clear()
        self.table.clear()

        num_snapshots = self.dset.shape[0]
        for i in range(num_snapshots):
            # Try to get some metadata: phase or time
            try:
                rec = self.dset[i]["root"]
                phase = int(rec["phase"])
                # time is an array[4]; we show the last element as "time"
                time_arr = rec["time"]
                time_val = int(time_arr[-1]) if hasattr(time_arr, "__len__") else int(time_arr)
                label = f"{i}: phase={phase}, time={time_val}"
            except Exception:
                label = f"{i}"
            self.snapshot_list.addItem(label)

        self.setWindowTitle(f"ZSim HDF5 Viewer - {os.path.basename(path)}")
        self.info_label.setText("Select a snapshot on the left, then a field in the middle.")
        self.current_snapshot_index = None
        self.current_record = None

    # ---------- Snapshot / field selection ----------

    def on_snapshot_selected(self, row):
        if row < 0 or self.dset is None:
            return

        # remember previously selected field name (if any)
        prev_field = None
        if self.field_list.currentRow() >= 0:
            prev_field = self.field_list.currentItem().text()

        self.current_snapshot_index = row

        try:
            rec = self.dset[row]["root"]
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read snapshot {row}:\n{e}")
            return

        self.current_record = rec
        self.field_list.clear()
        self.table.clear()

        # populate new field list
        field_names = list(rec.dtype.names)
        self.field_list.addItems(field_names)

        # try to reselect previous field if still present
        if prev_field in field_names:
            idx = field_names.index(prev_field)
            self.field_list.setCurrentRow(idx)
            # explicitly trigger loading
            self.on_field_selected(idx)
        else:
            self.info_label.setText(
                f"Snapshot {row} selected. Field list updated.\n"
                f"Select a field to view values."
            )


    def on_field_selected(self, row):
        if self.current_record is None or row < 0:
            return

        field_name = self.field_list.item(row).text()
        try:
            value = self.current_record[field_name]
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read field '{field_name}':\n{e}")
            return

        self.display_value(field_name, value)

    # ---------- Display logic ----------

    def display_value(self, field_name, value):
        """
        value can be:
        - scalar (int-like)
        - scalar compound (np.void with .dtype.names)
        - array of scalar numbers
        - array of compound (np.ndarray with dtype.names)
        """
        self.table.clear()

        # Scalar non-compound
        if not isinstance(value, np.ndarray) and not hasattr(value, "dtype"):
            self.table.setRowCount(1)
            self.table.setColumnCount(1)
            self.table.setHorizontalHeaderLabels(["value"])
            self.table.setVerticalHeaderLabels(["0"])
            self.table.setItem(0, 0, QTableWidgetItem(str(value)))
            self.info_label.setText(f"Field '{field_name}': scalar value")
            return

        # If it's a numpy scalar or np.void
        if not isinstance(value, np.ndarray):
            # Could be scalar compound or scalar number
            if hasattr(value.dtype, "names") and value.dtype.names is not None:
                # scalar compound
                names = list(value.dtype.names)
                self.table.setRowCount(1)
                self.table.setColumnCount(len(names))
                self.table.setHorizontalHeaderLabels(names)
                self.table.setVerticalHeaderLabels(["0"])
                for j, n in enumerate(names):
                    self.table.setItem(0, j, QTableWidgetItem(str(value[n])))
                self.info_label.setText(f"Field '{field_name}': scalar compound with {len(names)} fields")
                return
            else:
                # scalar numeric
                self.table.setRowCount(1)
                self.table.setColumnCount(1)
                self.table.setHorizontalHeaderLabels(["value"])
                self.table.setVerticalHeaderLabels(["0"])
                self.table.setItem(0, 0, QTableWidgetItem(str(value)))
                self.info_label.setText(f"Field '{field_name}': scalar value")
                return

        # Now we have an ndarray
        arr = np.array(value)

        # Array of compound
        if hasattr(arr.dtype, "names") and arr.dtype.names is not None:
            names = list(arr.dtype.names)
            rows = arr.shape[0] if arr.ndim > 0 else 1

            # We add one extra row for the SUM
            self.table.setRowCount(rows + 1)
            self.table.setColumnCount(len(names))

            # Vertical labels: SUM, 0, 1, 2, ...
            vert_labels = ["SUM"] + [str(i) for i in range(rows)]
            self.table.setVerticalHeaderLabels(vert_labels)
            self.table.setHorizontalHeaderLabels(names)

            # ---- Compute SUM row (index 0) ----
            for col, name in enumerate(names):
                col_data = arr[name]          # shape: (rows,) or (rows, k)
                summed = np.sum(col_data, axis=0)
                self.table.setItem(0, col, QTableWidgetItem(str(summed)))

            # ---- Fill normal rows starting at index 1 ----
            if arr.ndim == 0:
                rec = arr
                for j, n in enumerate(names):
                    self.table.setItem(1, j, QTableWidgetItem(str(rec[n])))
            else:
                for i in range(rows):
                    rec = arr[i]
                    for j, n in enumerate(names):
                        self.table.setItem(i + 1, j, QTableWidgetItem(str(rec[n])))

            self.info_label.setText(
                f"Field '{field_name}': SUM row + {rows} entries"
            )
            return


        # Plain numeric array
        if arr.ndim == 1:
            rows = arr.shape[0]
            self.table.setRowCount(rows)
            self.table.setColumnCount(1)
            self.table.setHorizontalHeaderLabels(["value"])
            self.table.setVerticalHeaderLabels([str(i) for i in range(rows)])
            for i in range(rows):
                self.table.setItem(i, 0, QTableWidgetItem(str(arr[i])))
            self.info_label.setText(
                f"Field '{field_name}': 1D array of length {rows}"
            )
        else:
            # For higher dimensions, flatten
            flat = arr.reshape(-1)
            rows = flat.shape[0]
            self.table.setRowCount(rows)
            self.table.setColumnCount(1)
            self.table.setHorizontalHeaderLabels(["value"])
            self.table.setVerticalHeaderLabels([str(i) for i in range(rows)])
            for i in range(rows):
                self.table.setItem(i, 0, QTableWidgetItem(str(flat[i])))
            self.info_label.setText(
                f"Field '{field_name}': {arr.ndim}D array, flattened to length {rows}"
            )


def main():
    parser = argparse.ArgumentParser(description="ZSim/BZSim HDF5 GUI viewer")
    parser.add_argument("file", nargs="?", help="Path to zsim.h5 or zsim-ev.h5")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    viewer = ZSimHDFViewer(args.file)
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

