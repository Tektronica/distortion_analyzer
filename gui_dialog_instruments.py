import wx
from instruments_RWConfig import *


########################################################################################################################
class InstrumentDialog(wx.Dialog):
    """"""

    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, parent, instrs, *args, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_DIALOG_STYLE
        super(InstrumentDialog, self).__init__(parent, title='Configure Instruments')
        wx.Dialog.__init__(self, *args, **kwds)
        self.Center()

        self.panel = wx.Panel(self, wx.ID_ANY)

        # DYNAMIC DATA ENTRY PANELS ------------------------------------------------------------------------------------
        self.instr_list = instrs
        self.panels = []

        # BUTTONS ------------------------------------------------------------------------------------------------------
        self.btn_save = wx.Button(self.panel, wx.ID_ANY, "Save")
        self.btn_save.Bind(wx.EVT_BUTTON, self.on_save)

        self.__load_config()
        self.__set_properties()
        self.__do_layout()

    # ------------------------------------------------------------------------------------------------------------------
    def __set_properties(self):
        self.SetTitle("Configure Instruments")

    # ------------------------------------------------------------------------------------------------------------------
    def __load_config(self):
        config_dict = ReadConfig()
        # load config file into settings if available
        if isinstance(config_dict, dict):
            config = config_dict

            for idx, key in enumerate(config_dict.keys()):
                mode = config[key]['mode']

                self.panels.append(DataEntryPanel(self.panel, wx.ID_ANY, key))
                self.panels[idx].setValues(mode=mode, address=config[key]['address'], port=config[key]['port'],
                                           gpib=config[key]['gpib'])
                self.panels[idx].toggle_panel(mode)
        else:
            print('no config')

    # ------------------------------------------------------------------------------------------------------------------
    def __do_layout(self):
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        grid_sizer = wx.GridBagSizer(0, 0)
        grid_dynamic_sizer = wx.GridBagSizer(0, 0)

        # TITLE --------------------------------------------------------------------------------------------------------
        title_Instruments = wx.StaticText(self.panel, wx.ID_ANY, "INSTRUMENTS")
        title_Instruments.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer.Add(title_Instruments, (0, 0), (1, 3), wx.BOTTOM, 10)

        static_line_1 = wx.StaticLine(self.panel, wx.ID_ANY)
        static_line_1.SetMinSize((292, 2))
        grid_sizer.Add(static_line_1, (1, 0), (1, 3), wx.BOTTOM | wx.TOP, 5)

        # ADD DYNAMIC PANELS -------------------------------------------------------------------------------------------
        for idx, panel in enumerate(self.panels):
            if panel.key in self.instr_list:
                header = wx.StaticText(self.panel, wx.ID_ANY, panel.key)
                header.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
                grid_dynamic_sizer.Add(header, (idx, 0), (1, 1), wx.BOTTOM | wx.RIGHT, 5)
                grid_dynamic_sizer.Add(panel, (idx, 1), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer.Add(grid_dynamic_sizer, (2, 0), (1, 3), wx.BOTTOM | wx.TOP, 5)

        # ADD BUTTONS --------------------------------------------------------------------------------------------------
        static_line_2 = wx.StaticLine(self.panel, wx.ID_ANY)
        static_line_2.SetMinSize((292, 2))
        grid_sizer.Add(static_line_2, (3, 0), (1, 3), wx.BOTTOM | wx.TOP, 5)

        grid_sizer.Add(self.btn_save, (4, 0), (1, 3), wx.ALIGN_RIGHT, 0)
        self.panel.SetSizer(grid_sizer)

        # ADD MAIN PANEL TO SIZER --------------------------------------------------------------------------------------
        sizer_1.Add(self.panel, 1, wx.ALL | wx.EXPAND, 10)
        self.SetSizer(sizer_1)
        sizer_1.Fit(self)

    # ------------------------------------------------------------------------------------------------------------------
    def toggle_panel(self, mode, panel, panel_gpib):
        if mode in ('SOCKET', 'SERIAL'):
            if not panel.IsShown():
                panel_gpib.Hide()
                panel.Show()
        else:
            if not panel_gpib.IsShown():
                panel.Hide()
                panel_gpib.Show()
        self.Layout()

    # ------------------------------------------------------------------------------------------------------------------
    def on_save(self, evt):
        # Merging dictionaries: https://stackoverflow.com/a/26853961

        config = {panel.key: panel.get_text() for panel in self.panels}
        SaveConfig(config)

        if self.IsModal():
            self.EndModal(wx.ID_OK)
            evt.Skip()
        else:
            self.Close()


class DataEntryPanel(wx.Panel):
    def __init__(self, parent, wxid, key):
        super(DataEntryPanel, self).__init__(parent)
        self.panel_base = wx.Panel(self, wxid)
        self.panel_1 = wx.Panel(self.panel_base, wx.ID_ANY)
        self.panel_2 = wx.Panel(self.panel_base, wx.ID_ANY)

        self.key = key
        self.mode = wx.ComboBox(self.panel_base, wx.ID_ANY, choices=["SOCKET", "GPIB", "SERIAL"], style=wx.CB_DROPDOWN)
        self.address = wx.TextCtrl(self.panel_1, wx.ID_ANY, "")
        self.port = wx.TextCtrl(self.panel_1, wx.ID_ANY, "3490")
        self.gpib = wx.TextCtrl(self.panel_2, wx.ID_ANY, "")

        on_combo_00 = lambda event: self.on_combo(event, self.mode.GetValue(), self.key)
        self.Bind(wx.EVT_COMBOBOX_CLOSEUP, on_combo_00, self.mode)

        self.Freeze()
        self.__set_properties()
        self.__do_layout()
        self.Thaw()

    def __set_properties(self):
        self.mode.SetSelection(0)
        self.port.SetMinSize((50, 23))
        self.gpib.SetMinSize((50, 23))
        self.panel_1.SetMinSize((176, 51))
        self.panel_2.SetMinSize((176, 51))

    def __do_layout(self):
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_2 = wx.BoxSizer(wx.HORIZONTAL)
        grid_sizer_1 = wx.GridBagSizer(0, 0)
        grid_sizer_2 = wx.GridBagSizer(0, 0)

        # SOCKET/SERIAL PANEL ------------------------------------------------------------------------------------------
        label_address = wx.StaticText(self.panel_1, wx.ID_ANY, "ADDRESS")
        label_colon = wx.StaticText(self.panel_1, wx.ID_ANY, ":")
        label_port = wx.StaticText(self.panel_1, wx.ID_ANY, "PORT")

        label_colon.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))

        grid_sizer_1.Add(label_address, (0, 0), (1, 2), wx.BOTTOM, 5)
        grid_sizer_1.Add(label_port, (0, 2), (1, 1), wx.BOTTOM, 5)
        grid_sizer_1.Add(self.address, (1, 0), (1, 1), 0, 0)
        grid_sizer_1.Add(label_colon, (1, 1), (1, 1), wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_1.Add(self.port, (1, 2), (1, 1), 0, 0)
        self.panel_1.SetSizer(grid_sizer_1)

        # GPIB PANEL ---------------------------------------------------------------------------------------------------
        label_gpibaddress = wx.StaticText(self.panel_2, wx.ID_ANY, "GPIB ADDRESS")
        grid_sizer_2.Add(label_gpibaddress, (0, 0), (1, 2), wx.BOTTOM, 5)
        grid_sizer_2.Add(self.gpib, (1, 0), (1, 1), 0, 0)
        self.panel_2.SetSizer(grid_sizer_2)
        self.panel_2.Hide()

        sizer_2.Add(self.panel_1, 1, wx.EXPAND, 0)
        sizer_2.Add(self.panel_2, 1, wx.EXPAND, 0)
        sizer_2.Add(self.mode, 0, wx.ALIGN_BOTTOM | wx.BOTTOM | wx.LEFT, 7)
        self.panel_base.SetSizer(sizer_2)

        sizer_1.Add(self.panel_base, 1, wx.EXPAND, 0)
        self.SetSizer(sizer_1)

    # ------------------------------------------------------------------------------------------------------------------
    def setValues(self, mode='SOCKET', address='', port='', gpib=''):
        self.mode.SetValue(mode)
        self.address.SetValue(address)
        self.port.SetValue(port)
        self.gpib.SetValue(gpib)

    # ------------------------------------------------------------------------------------------------------------------
    def on_combo(self, evt, mode, instr):
        if instr == 'DUT':
            self.toggle_panel(mode)
        else:
            self.toggle_panel(mode)

    # ------------------------------------------------------------------------------------------------------------------
    def toggle_panel(self, mode):
        self.Freeze()
        if mode in ('SOCKET', 'SERIAL'):
            if not self.panel_1.IsShown():
                self.panel_2.Hide()
                self.panel_1.Show()
        else:
            if not self.panel_2.IsShown():
                self.panel_1.Hide()
                self.panel_2.Show()
        self.Layout()
        self.Thaw()

    def get_text(self):
        return {'mode': self.mode.GetValue(),
                'address': self.address.GetValue(),
                'port': self.port.GetValue(),
                'gpib': self.gpib.GetValue()}


########################################################################################################################
class MyApp(wx.App):
    """"""

    # ------------------------------------------------------------------------------------------------------------------
    def OnInit(self):
        dlg = InstrumentDialog(None, None, wx.ID_ANY, "")
        dlg.ShowModal()
        dlg.Destroy()
        return True


# Run
if __name__ == "__main__":
    app = MyApp(0)
