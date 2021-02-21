import wx
import wx.grid
import csv
import sys

class MyGrid(wx.grid.Grid):
    def __init__(self, parent):
        """Constructor"""
        wx.grid.Grid.__init__(self, parent, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, 0)
        self.selected_rows = []
        self.selected_cols = []
        self.history = []
        self.data = {}
        self.row = 0

        self.frame_number = 1

        # test all the events
        self.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.OnCellLeftClick)
        self.Bind(wx.grid.EVT_GRID_CELL_RIGHT_CLICK, self.OnCellRightClick)
        self.Bind(wx.grid.EVT_GRID_CELL_LEFT_DCLICK, self.OnCellLeftDClick)
        self.Bind(wx.grid.EVT_GRID_CELL_RIGHT_DCLICK, self.OnCellRightDClick)
        self.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self.OnLabelLeftClick)
        self.Bind(wx.grid.EVT_GRID_LABEL_RIGHT_CLICK, self.OnLabelRightClick)
        self.Bind(wx.grid.EVT_GRID_LABEL_LEFT_DCLICK, self.OnLabelLeftDClick)
        self.Bind(wx.grid.EVT_GRID_LABEL_RIGHT_DCLICK, self.OnLabelRightDClick)
        self.Bind(wx.grid.EVT_GRID_ROW_SIZE, self.OnRowSize)
        self.Bind(wx.grid.EVT_GRID_COL_SIZE, self.OnColSize)
        self.Bind(wx.grid.EVT_GRID_RANGE_SELECT, self.OnRangeSelect)
        self.Bind(wx.grid.EVT_GRID_CELL_CHANGED, self.OnCellChange)
        self.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.OnSelectCell)
        self.Bind(wx.grid.EVT_GRID_EDITOR_SHOWN, self.OnEditorShown)
        self.Bind(wx.grid.EVT_GRID_EDITOR_HIDDEN, self.OnEditorHidden)
        self.Bind(wx.grid.EVT_GRID_EDITOR_CREATED, self.OnEditorCreated)

    def OnCellLeftClick(self, event):
        print("OnCellLeftClick: (%d,%d) %s\n" % (event.GetRow(), event.GetCol(), event.GetPosition()))
        event.Skip()

    def OnCellRightClick(self, event):
        print("OnCellRightClick: (%d,%d) %s\n" % (event.GetRow(), event.GetCol(), event.GetPosition()))
        menu_contents = [(wx.NewId(), "Cut", self.onCut),
                         (wx.NewId(), "Copy", self.onCopy),
                         (wx.NewId(), "Paste", self.onPaste),
                         None,
                         (wx.NewId(), "Plot data", self.warning("Hello! plotting hasn't been implemented yet!"))]
        popup_menu = wx.Menu()
        for menu_item in menu_contents:
            if menu_item is None:
                popup_menu.AppendSeparator()
                continue
            popup_menu.Append(menu_item[0], menu_item[1])
            self.Bind(wx.EVT_MENU, menu_item[2], id=menu_item[0])

        self.PopupMenu(popup_menu, event.GetPosition())
        popup_menu.Destroy()
        return

    def warning(self, warning):
        print(warning)

    def OnCellLeftDClick(self, evt):
        print("OnCellLeftDClick: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnCellRightDClick(self, evt):
        print("OnCellRightDClick: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnLabelLeftClick(self, evt):
        print("OnLabelLeftClick: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnLabelRightClick(self, evt):
        print("OnLabelRightClick: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnLabelLeftDClick(self, evt):
        print("OnLabelLeftDClick: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnLabelRightDClick(self, evt):
        print("OnLabelRightDClick: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnRowSize(self, evt):
        print("OnRowSize: row %d, %s\n" % (evt.GetRowOrCol(), evt.GetPosition()))
        evt.Skip()

    def OnColSize(self, evt):
        print("OnColSize: col %d, %s\n" % (evt.GetRowOrCol(), evt.GetPosition()))
        evt.Skip()

    def OnRangeSelect(self, evt):
        if evt.Selecting():
            msg = 'Selected'
        else:
            msg = 'Deselected'
        print("OnRangeSelect: %s  top-left %s, bottom-right %s\n" % (
            msg, evt.GetTopLeftCoords(), evt.GetBottomRightCoords()))
        evt.Skip()

    def OnCellChange(self, evt):
        print("OnCellChange: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        # Show how to stay in a cell that has bad data.  We can't just
        # call SetGridCursor here since we are nested inside one so it
        # won't have any effect.  Instead, set coordinates to move to in
        # idle time.
        value = self.GetCellValue(evt.GetRow(), evt.GetCol())
        if value == 'no good':
            self.moveTo = evt.GetRow(), evt.GetCol()

    def OnSelectCell(self, evt):
        if evt.Selecting():
            msg = 'Selected'
        else:
            msg = 'Deselected'
        print("OnSelectCell: %s (%d,%d) %s\n" % (msg, evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        # Another way to stay in a cell that has a bad value...
        row = self.GetGridCursorRow()
        col = self.GetGridCursorCol()
        if self.IsCellEditControlEnabled():
            self.HideCellEditControl()
            self.DisableCellEditControl()
        value = self.GetCellValue(row, col)
        if value == 'no good 2':
            return  # cancels the cell selection
        evt.Skip()

    def OnEditorShown(self, evt):
        if evt.GetRow() == 6 and evt.GetCol() == 3 and \
                wx.MessageBox("Are you sure you wish to edit this cell?",
                              "Checking", wx.YES_NO) == wx.NO:
            evt.Veto()
            return
        print("OnEditorShown: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnEditorHidden(self, evt):
        if evt.GetRow() == 6 and evt.GetCol() == 3 and \
                wx.MessageBox("Are you sure you wish to finish editing this cell?",
                              "Checking", wx.YES_NO) == wx.NO:
            evt.Veto()
            return
        print("OnEditorHidden: (%d,%d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetPosition()))
        evt.Skip()

    def OnEditorCreated(self, evt):
        print("OnEditorCreated: (%d, %d) %s\n" % (evt.GetRow(), evt.GetCol(), evt.GetControl()))

    def add_history(self, change):
        self.history.append(change)

    def get_selection(self):
        """
        Returns selected range's start_row, start_col, end_row, end_col
        If there is no selection, returns selected cell's start_row=end_row, start_col=end_col
        """
        if not len(self.GetSelectionBlockTopLeft()):
            selected_columns = self.GetSelectedCols()
            selected_rows = self.GetSelectedRows()
            if selected_columns:
                start_col = selected_columns[0]
                end_col = selected_columns[-1]
                start_row = 0
                end_row = self.GetNumberRows() - 1
            elif selected_rows:
                start_row = selected_rows[0]
                end_row = selected_rows[-1]
                start_col = 0
                end_col = self.GetNumberCols() - 1
            else:
                start_row = end_row = self.GetGridCursorRow()
                start_col = end_col = self.GetGridCursorCol()
        elif len(self.GetSelectionBlockTopLeft()) > 1:
            wx.MessageBox("Multiple selections are not supported", "Warning")
            return []
        else:
            start_row, start_col = self.GetSelectionBlockTopLeft()[0]
            end_row, end_col = self.GetSelectionBlockBottomRight()[0]

        return [start_row, start_col, end_row, end_col]

    def get_selected_cells(self):
        # returns a list of selected cells
        selection = self.get_selection()
        if not selection:
            return

        start_row, start_col, end_row, end_col = selection
        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                yield [row, col]

    def onCopy(self, event):
        """
        Copies range of selected cells to clipboard.
        """

        selection = self.get_selection()
        if not selection:
            return []
        start_row, start_col, end_row, end_col = selection

        data = u''

        rows = range(start_row, end_row + 1)
        for row in rows:
            columns = range(start_col, end_col + 1)
            for idx, column in enumerate(columns, 1):
                if idx == len(columns):
                    # if we are at the last cell of the row, add new line instead
                    data += self.GetCellValue(row, column) + "\n"
                else:
                    data += self.GetCellValue(row, column) + "\t"

        text_data_object = wx.TextDataObject()
        text_data_object.SetText(data)

        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(text_data_object)
            wx.TheClipboard.Close()
        else:
            wx.MessageBox("Can't open the clipboard", "Warning")

    def onPaste(self, event):
        if not wx.TheClipboard.Open():
            wx.MessageBox("Can't open the clipboard", "Warning")
            return False

        clipboard = wx.TextDataObject()
        wx.TheClipboard.GetData(clipboard)
        wx.TheClipboard.Close()
        data = clipboard.GetText()
        if data[-1] == "\n":
            data = data[:-1]

        try:
            cells = self.get_selected_cells()
            cell = next(cells)
        except StopIteration:
            return False

        start_row = end_row = cell[0]
        start_col = end_col = cell[1]
        max_row = self.GetNumberRows()
        max_col = self.GetNumberCols()

        history = []
        out_of_range = False

        for row, line in enumerate(data.split("\n")):
            target_row = start_row + row
            if not (0 <= target_row < max_row):
                out_of_range = True
                break

            if target_row > end_row:
                end_row = target_row

            for col, value in enumerate(line.split("\t")):
                target_col = start_col + col
                if not (0 <= target_col < max_col):
                    out_of_range = True
                    break

                if target_col > end_col:
                    end_col = target_col

                # save previous value of the cell for undo
                history.append([target_row, target_col, {"value": self.GetCellValue(target_row, target_col)}])

                self.SetCellValue(target_row, target_col, value)

        self.SelectBlock(start_row, start_col, end_row, end_col)  # select pasted range
        if out_of_range:
            wx.MessageBox("Pasted data is out of Grid range", "Warning")

        self.add_history({"type": "change", "cells": history})

    def onDelete(self, e):
        cells = []
        for row, col in self.get_selected_cells():
            attributes = {
                "value": self.GetCellValue(row, col),
                "alignment": self.GetCellAlignment(row, col)
            }
            cells.append((row, col, attributes))
            self.SetCellValue(row, col, "")

        self.add_history({"type": "delete", "cells": cells})

    def onCut(self, e):
        self.onCopy(e)
        self.onDelete(e)

    def retrieveList(self):
        """
        Copies range of selected cells to clipboard.
        """

        selection = self.get_selection()
        if not selection:
            return []
        start_row, start_col, end_row, end_col = selection

        data = u''
        list_row = []
        list_data = []
        rows = range(start_row, end_row + 1)
        for row in rows:
            columns = range(start_col, end_col + 1)
            for idx, column in enumerate(columns, 1):
                if idx == len(columns):
                    # if we are at the last cell of the row, add new line instead
                    list_row.append(self.GetCellValue(row, column))
                    list_data.append(list_row)
                    list_row = []
                else:
                    list_row.append(self.GetCellValue(row, column))

        return list_data

    def write_header(self, header):
        if isinstance(header, dict):
            print('k')
            for col, key in enumerate(header.keys()):
                self.SetCellValue(0, col, str(key))
                self.data[key] = []

        elif isinstance(header, list):
            if isinstance(header[0], list):
                head = header[0]
            else:
                head = header

            for col, key in enumerate(head):
                self.SetCellValue(0, col, str(key))
                self.data[key] = []

        self.row = 1

    def append_rows(self, rows=None):
        if rows is not None:
            if isinstance(rows, dict):
                # creates headers if empty data
                if not bool(len(self.data.keys())):
                    self.write_header(list(rows.keys()))

                if isinstance(list(rows.values())[0], list):
                    # make more rows if run out
                    rows_to_add = len(list(rows.values())[0])
                    if rows_to_add >= self.GetNumberRows() - rows_to_add:
                        self.AppendRows(10)

                    # writes data to rows
                    for col, (key, values) in enumerate(rows.items()):
                        self.data[key].extend(values)
                        for new_row, val in enumerate(values):
                            self.SetCellValue(self.row + new_row, col, str(val))
                    self.row += rows_to_add + 1
                else:
                    # make more rows if run out
                    rows_to_add = 1
                    if rows_to_add >= self.GetNumberRows() - rows_to_add:
                        self.AppendRows(10)

                    # writes data to rows
                    for col, (key, value) in enumerate(rows.items()):
                        self.data[key].append(value)
                        self.SetCellValue(self.row, col, str(value))
                    self.row += rows_to_add + 1

            elif isinstance(rows, list):
                # make more rows if run out
                rows_to_add = len(rows)
                if rows_to_add >= self.GetNumberRows() - rows_to_add:
                    self.AppendRows(10)

                if isinstance(rows[0], list):
                    # creates headers if empty data
                    if not bool(len(self.data.keys())):
                        self.write_header(rows)
                        rows = rows[1:]
                    for row, values in enumerate(rows):
                        for col, val in enumerate(values):
                            self.SetCellValue(self.row, col, str(val))
                            # TODO: don't ever implicitly populate an unordered dict this way again...
                            self.data[list(self.data.keys())[col]].append(values)
                        self.row += 1

                else:
                    # creates headers if empty data
                    if not bool(len(self.data.keys())):
                        self.write_header(rows)
                    else:
                        for col, value in enumerate(rows):
                            self.SetCellValue(self.row, col, str(value))
                            # TODO: don't ever implicitly populate an unordered dict this way again...
                            self.data[list(self.data.keys())[col]].append(value)
                        self.row += 1
            else:
                print('append list or rows only.')
                pass
        else:
            print('No row data written. data appears empty.')

    def export(self, e):
        with wx.FileDialog(self, "Save csv file", wildcard="CSV files (*.csv)|*.csv",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # save the current contents in the file
            pathname = fileDialog.GetPath()
            try:
                # https://stackoverflow.com/a/23613603/3382269
                # https://stackoverflow.com/a/3348664/3382269
                keys = self.data.keys()
                with open(pathname, 'w', newline='') as outfile:
                    writer = csv.writer(outfile, delimiter=',')
                    writer.writerow(keys)
                    writer.writerows(zip(*[self.data[key] for key in keys]))
            except IOError:
                wx.LogError("Cannot save current data in file '%s'." % pathname)


class MyGridFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        # begin wxGlade: MyFrame.__init__
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.SetSize((1028, 278))
        self.panel_1 = wx.Panel(self, wx.ID_ANY)
        self.grid_1 = MyGrid(self.panel_1)

        self.__set_properties()
        self.__do_layout()
        # end wxGlade

    def __set_properties(self):
        # begin wxGlade: MyFrame.__set_properties
        self.SetTitle("frame")
        self.grid_1.CreateGrid(16, 13)
        # end wxGlade

    def __do_layout(self):
        # begin wxGlade: MyFrame.__do_layout
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_2 = wx.BoxSizer(wx.VERTICAL)
        sizer_2.Add(self.grid_1, 1, wx.EXPAND, 0)
        self.panel_1.SetSizer(sizer_2)
        sizer_1.Add(self.panel_1, 1, wx.EXPAND, 0)
        self.SetSizer(sizer_1)
        self.Layout()
        # end wxGlade


class MyApp(wx.App):
    def OnInit(self):
        self.frame = MyGridFrame(None, wx.ID_ANY, "")
        self.SetTopWindow(self.frame)
        self.frame.Show()
        return True


if __name__ == "__main__":
    app = MyApp(0)
    app.MainLoop()
