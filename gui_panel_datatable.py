import wx
from gui_grid_enhanced import MyGrid


class DataTab(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY)

        # Data panel for displaying raw output -------------------------------------------------------------------------
        self.spreadsheet = MyGrid(self)
        self.btn_export = wx.Button(self, wx.ID_ANY, "Export")

        # export grid data ---------------------------------------------------------------------------------------------
        self.Bind(wx.EVT_BUTTON, self.spreadsheet.export, self.btn_export)

        self.__set_properties()
        self.__do_layout()

    def __set_properties(self):
        # self.SetBackgroundColour(wx.Colour(127, 255, 0))
        self.spreadsheet.CreateGrid(100, 60)
        self.spreadsheet.SetMinSize((1024, 50))

    def __do_layout(self):
        sizer_2 = wx.GridSizer(1, 1, 0, 0)
        grid_sizer_1 = wx.FlexGridSizer(2, 1, 0, 0)

        grid_sizer_1.Add(self.spreadsheet, 1, wx.EXPAND, 0)
        grid_sizer_1.Add(self.btn_export, 0, 0, 0)
        grid_sizer_1.AddGrowableRow(0)
        grid_sizer_1.AddGrowableCol(0)
        sizer_2.Add(grid_sizer_1, 0, wx.EXPAND, 0)
        self.SetSizer(sizer_2)
        self.Layout()
