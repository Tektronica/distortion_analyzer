from gui_panel_distortion_analyzer import DistortionAnalyzerTab
from gui_panel_datatable import DataTab
from gui_panel_history import HistoryTab
from gui_panel_multimeter import MultimeterTab
from gui_panel_aboutpage import AboutTab

from gui_dialog_instruments import *
from instruments_RWConfig import *

import wx
import wx.adv
import wx.html
import webbrowser

APP_VERSION = 'v2.0.2'
APP_ICON = 'images/hornet.ico'


########################################################################################################################
class TestFrame(wx.Frame):
    """"""

    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, *args, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)

        self.SetSize((1055, 640))
        # https://stackoverflow.com/a/24704039/3382269
        # Sets minimum window dimensions
        # self.SetSizeHints(1055, 640, -1, -1)

        # Menu Bar -----------------------------------------------------------------------------------------------------
        self.frame_menubar = wx.MenuBar()
        wxglade_tmp_menu = wx.Menu()
        self.menu_results = wxglade_tmp_menu.Append(wx.ID_ANY, "Open Results", "")
        self.menu_history = wxglade_tmp_menu.Append(wx.ID_ANY, "Open History", "")
        wxglade_tmp_menu.AppendSeparator()
        self.menu_export = wxglade_tmp_menu.Append(wx.ID_ANY, "Export Data", "")
        self.frame_menubar.Append(wxglade_tmp_menu, "File")

        wxglade_tmp_menu = wx.Menu()
        self.menu_config = wxglade_tmp_menu.Append(wx.ID_ANY, "Configure Instruments", "")
        self.menu_close_instruments = wxglade_tmp_menu.Append(wx.ID_ANY, "Close Instruments", "")
        self.menu_DUMMY = wxglade_tmp_menu.AppendCheckItem(wx.ID_ANY, "Use DUMMY Data?")
        # self.menu_brkpts = wxglade_tmp_menu.Append(wx.ID_ANY, "Open Breakpoints", "")
        self.frame_menubar.Append(wxglade_tmp_menu, "Settings")

        wxglade_tmp_menu = wx.Menu()
        self.menu_reset_view = wxglade_tmp_menu.Append(wx.ID_ANY, "Reset Window Size", "")
        wxglade_tmp_menu.AppendSeparator()
        self.menu_about = wxglade_tmp_menu.Append(wx.ID_ANY, '&About')
        # self.menu_brkpts = wxglade_tmp_menu.Append(wx.ID_ANY, "Open Breakpoints", "")
        self.frame_menubar.Append(wxglade_tmp_menu, "View")
        self.SetMenuBar(self.frame_menubar)

        # NOTEBOOK =====================================================================================================
        self.panel_1 = wx.Panel(self, wx.ID_ANY)
        self.notebook = wx.Notebook(self.panel_1, wx.ID_ANY)
        self.notebook_analyzer = wx.Panel(self.notebook, wx.ID_ANY)
        self.tab_analyzer = DistortionAnalyzerTab(self.notebook_analyzer, self)

        self.notebook_data = wx.Panel(self.notebook, wx.ID_ANY)
        self.tab_data = DataTab(self.notebook_data)
        self.grid_1 = self.tab_data.spreadsheet

        self.notebook_history = wx.Panel(self.notebook)
        self.tab_history = HistoryTab(self.notebook_history)

        self.notebook_multimeter = wx.Panel(self.notebook)
        self.tab_multimeter = MultimeterTab(self.notebook_multimeter)

        self.notebook_information = wx.Panel(self.notebook, wx.ID_ANY)
        self.tab_about = AboutTab(self.notebook_information)

        # BINDING EVENTS ===============================================================================================
        ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
        on_open_results_dir = lambda event: webbrowser.open('file:////' + ROOT_DIR + '/results')
        on_open_history_dir = lambda event: webbrowser.open('file:////' + ROOT_DIR + '/results/history')
        self.Bind(wx.EVT_MENU, on_open_results_dir, self.menu_results)
        self.Bind(wx.EVT_MENU, on_open_history_dir, self.menu_history)
        self.Bind(wx.EVT_MENU, self.grid_1.export, self.menu_export)
        self.Bind(wx.EVT_MENU, self.config_all_instruments, self.menu_config)
        self.Bind(wx.EVT_MENU, self.close_all_instruments, self.menu_close_instruments)
        self.Bind(wx.EVT_MENU, self.OnDummyChecked, self.menu_DUMMY)
        # self.Bind(wx.EVT_MENU, self.open_breakpoints, self.menu_brkpts)
        self.Bind(wx.EVT_MENU, self.reset_view, self.menu_reset_view)
        self.Bind(wx.EVT_MENU, self.OnAbout, self.menu_about)
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

        self.Freeze()
        self.__set_properties()
        self.__do_table_header()
        self.__do_layout()
        self.Thaw()

    def __set_properties(self):
        self.SetTitle("Distortion Analyzer")
        self.SetBackgroundColour(wx.Colour(227, 227, 227))
        self.notebook.SetBackgroundColour(wx.Colour(227, 227, 227))
        self.notebook_analyzer.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.notebook_data.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.notebook_history.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.notebook_multimeter.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.notebook_information.SetBackgroundColour(wx.Colour(255, 0, 255))

    def __do_layout(self):
        sizer_7 = wx.BoxSizer(wx.VERTICAL)
        sizer_8 = wx.BoxSizer(wx.VERTICAL)

        grid_sizer_analyzertab = wx.BoxSizer(wx.VERTICAL)
        grid_sizer_datatab = wx.BoxSizer(wx.VERTICAL)
        grid_sizer_historytab = wx.BoxSizer(wx.VERTICAL)
        grid_sizer_multimetertab = wx.BoxSizer(wx.VERTICAL)
        grid_sizer_abouttab = wx.BoxSizer(wx.VERTICAL)

        grid_sizer_analyzertab.Add(self.tab_analyzer, 1, wx.EXPAND | wx.TOP, 5)
        self.notebook_analyzer.SetSizer(grid_sizer_analyzertab)

        grid_sizer_datatab.Add(self.tab_data, 1, wx.EXPAND, 0)
        self.notebook_data.SetSizer(grid_sizer_datatab)

        grid_sizer_historytab.Add(self.tab_history, 1, wx.EXPAND, 0)
        self.notebook_history.SetSizer(grid_sizer_historytab)

        grid_sizer_multimetertab.Add(self.tab_multimeter, 1, wx.EXPAND | wx.TOP, 5)
        self.notebook_multimeter.SetSizer(grid_sizer_multimetertab)

        grid_sizer_abouttab.Add(self.tab_about, 1, wx.EXPAND, 0)
        self.notebook_information.SetSizer(grid_sizer_abouttab)

        self.notebook.AddPage(self.notebook_analyzer, "Analyzer")
        self.notebook.AddPage(self.notebook_data, "Data")
        self.notebook.AddPage(self.notebook_history, "History")
        self.notebook.AddPage(self.notebook_multimeter, "Multimeter")
        self.notebook.AddPage(self.notebook_information, "Information")

        sizer_8.Add(self.notebook, 1, wx.ALL | wx.EXPAND, 10)
        self.panel_1.SetSizer(sizer_8)

        sizer_7.Add(self.panel_1, 1, wx.EXPAND, 0)
        self.SetSizer(sizer_7)

        self.Layout()

    # ------------------------------------------------------------------------------------------------------------------
    def reset_view(self, evt):
        self.SetSize((1055, 640))

    # ------------------------------------------------------------------------------------------------------------------
    def config_all_instruments(self, evt):
        dlg = InstrumentDialog(self, ['f5560A', 'f8588A', 'f884xA'], None, wx.ID_ANY, )
        dlg.ShowModal()
        dlg.Destroy()

    def close_all_instruments(self, evt):
        print("Closing all possible remote connections to instruments:")
        self.tab_analyzer.da.close_instruments()
        print("\tremote connection to instruments used in distortion analyzer are closed.")
        self.tab_multimeter.dmm.close_instruments()
        print("\tremote connection to instruments used in multimeter are closed.")

    def OnDummyChecked(self, event):
        if self.menu_DUMMY.IsChecked():
            self.tab_analyzer.da.DUMMY_DATA = True
            self.tab_multimeter.dmm.DUMMY_DATA = True
            print('using DUMMY data.')
        else:
            self.tab_analyzer.da.DUMMY_DATA = False
            self.tab_multimeter.dmm.DUMMY_DATA = False
            print('No longer using DUMMY data.')

    # ------------------------------------------------------------------------------------------------------------------
    def __do_table_header(self):
        header = ['Amplitude', 'Frequency', 'RMS', 'THDN', 'THD', 'uARMS Noise', 'Fs', 'Samples', 'Aperture']
        self.grid_1.append_rows(header)

    def append_row(self, row):
        self.grid_1.append_rows(row)

    # ------------------------------------------------------------------------------------------------------------------
    def OnAbout(self, evt):
        info = wx.adv.AboutDialogInfo()

        description = """The distortion analyzer computes the total harmonic distortion (THD) and total harmonic 
        distortion and noise (THD+N) using time series data collected by the Fluke 8588A Digitizer. """

        info.SetIcon(wx.Icon(APP_ICON, wx.BITMAP_TYPE_ICO))
        info.SetName('Distortion Analyzer')
        info.SetVersion(APP_VERSION)
        info.SetDescription(description)
        info.SetWebSite('https://github.com/Tektronica/distortion_analyzer')
        info.AddDeveloper('Ryan Holle')

        wx.adv.AboutBox(info)

    # ------------------------------------------------------------------------------------------------------------------
    def OnCloseWindow(self, evt):
        self.tab_analyzer.da.close_instruments()
        self.tab_multimeter.dmm.close_instruments()
        self.Destroy()


########################################################################################################################
class MyApp(wx.App):
    """"""

    # ------------------------------------------------------------------------------------------------------------------
    def OnInit(self):
        self.frame = TestFrame(None, wx.ID_ANY, "")
        self.SetTopWindow(self.frame)
        self.frame.SetIcon(wx.Icon(APP_ICON))
        self.frame.Show()
        return True


# Run
if __name__ == "__main__":
    app = MyApp(0)
    app.MainLoop()
