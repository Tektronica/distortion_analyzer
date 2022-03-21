from gui_panel_distortion_analyzer import DistortionAnalyzerTab
from gui_panel_datatable import DataTab
from gui_panel_history import HistoryTab
from gui_panel_multimeter import MultimeterTab
from gui_panel_aboutpage import AboutTab

from gui_dialog_instruments import *
from instruments_RWConfig import *

from gui_dialog_specwizard import *

import wx
import wx.adv
import wx.html
import webbrowser
import warnings

APP_VERSION = 'v2.5'
APP_ICON = 'images/hornet.ico'


########################################################################################################################
class TestFrame(wx.Frame):
    """"""

    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, *args, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)

        self.SetSize((1055, 663))
        self.Center()
        # https://stackoverflow.com/a/24704039/3382269
        # Sets minimum window dimensions
        # self.SetSizeHints(1055, 640, -1, -1)

        # TOP MENU BAR =================================================================================================
        self.frame_menubar = wx.MenuBar()

        # FILE menu tab ------------------------------------------------------------------------------------------------
        menu_tree_file_tab = wx.Menu()
        self.menu_results = menu_tree_file_tab.Append(wx.ID_ANY, "Open Results", "")
        self.menu_history = menu_tree_file_tab.Append(wx.ID_ANY, "Open History", "")
        menu_tree_file_tab.AppendSeparator()
        self.menu_export = menu_tree_file_tab.Append(wx.ID_ANY, "Export Data", "")
        self.frame_menubar.Append(menu_tree_file_tab, "File")

        # SETTINGS menu tab --------------------------------------------------------------------------------------------
        menu_tree_settings_tab = wx.Menu()
        self.menu_config = menu_tree_settings_tab.Append(wx.ID_ANY, "Configure Instruments", "")
        self.menu_close_instruments = menu_tree_settings_tab.Append(wx.ID_ANY, "Close Instruments", "")
        menu_tree_settings_tab.AppendSeparator()

        self.radio_menu_windowing = wx.Menu()  # submenu
        self.menu_windowing_rect = self.radio_menu_windowing.AppendRadioItem(wx.ID_ANY, 'Rectangular', '1')
        self.menu_windowing_bart = self.radio_menu_windowing.AppendRadioItem(wx.ID_ANY, 'Bartlett', '2')
        self.menu_windowing_hann = self.radio_menu_windowing.AppendRadioItem(wx.ID_ANY, 'Hanning', '3')
        self.menu_windowing_hann = self.radio_menu_windowing.AppendRadioItem(wx.ID_ANY, 'Hamming', '3')
        self.menu_windowing_blac = self.radio_menu_windowing.AppendRadioItem(wx.ID_ANY, 'Blackman', '4')
        menu_tree_settings_tab.AppendSubMenu(self.radio_menu_windowing, 'W&indowing')

        self.radio_menu_trigger = wx.Menu()  # submenu
        self.menu_trigger_aperture = self.radio_menu_trigger.AppendRadioItem(wx.ID_ANY, 'Aperture', '1')
        self.menu_trigger_timer = self.radio_menu_trigger.AppendRadioItem(wx.ID_ANY, 'Timer', '2')
        menu_tree_settings_tab.AppendSubMenu(self.radio_menu_trigger, 'T&rigger')
        menu_tree_settings_tab.AppendSeparator()

        self.menu_DUMMY = menu_tree_settings_tab.AppendCheckItem(wx.ID_ANY, "Use DUMMY Data?")
        # self.menu_brkpts = wxglade_tmp_menu.Append(wx.ID_ANY, "Open Breakpoints", "")
        self.frame_menubar.Append(menu_tree_settings_tab, "Settings")

        # VIEW menu tab ------------------------------------------------------------------------------------------------
        menu_tree_view_tab = wx.Menu()
        self.menu_reset_view = menu_tree_view_tab.Append(wx.ID_ANY, "Reset Window Size", "")
        menu_tree_view_tab.AppendSeparator()
        self.menu_about = menu_tree_view_tab.Append(wx.ID_ANY, '&About')
        # self.menu_brkpts = wxglade_tmp_menu.Append(wx.ID_ANY, "Open Breakpoints", "")
        self.frame_menubar.Append(menu_tree_view_tab, "View")

        # UTILITIES menu tab -------------------------------------------------------------------------------------------
        menu_tree_utilities_tab = wx.Menu()
        self.menu_spec_wizard = menu_tree_utilities_tab.Append(wx.ID_ANY, "Specification Wizard", "")
        self.frame_menubar.Append(menu_tree_utilities_tab, "Utilities")

        # Add tabs to bar ----------------------------------------------------------------------------------------------
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
        self.Bind(wx.EVT_MENU, self.OnCloseInstruments, self.menu_close_instruments)
        self.Bind(wx.EVT_MENU, self.OnWindowSelection, self.menu_windowing_rect)
        self.Bind(wx.EVT_MENU, self.OnWindowSelection, self.menu_windowing_bart)
        self.Bind(wx.EVT_MENU, self.OnWindowSelection, self.menu_windowing_hann)
        self.Bind(wx.EVT_MENU, self.OnWindowSelection, self.menu_windowing_blac)
        self.Bind(wx.EVT_MENU, self.OnTriggerSelection, self.menu_trigger_aperture)
        self.Bind(wx.EVT_MENU, self.OnTriggerSelection, self.menu_trigger_timer)
        self.Bind(wx.EVT_MENU, self.OnDummyChecked, self.menu_DUMMY)
        # self.Bind(wx.EVT_MENU, self.open_breakpoints, self.menu_brkpts)
        self.Bind(wx.EVT_MENU, self.reset_view, self.menu_reset_view)
        self.Bind(wx.EVT_MENU, self.open_spec_wizard, self.menu_spec_wizard)
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

        # Set default window selection in the appended submenu radio list
        self.radio_menu_windowing.Check(id=self.menu_windowing_blac.GetId(), check=True)

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
        self.SetSize((1055, 663))

    def popup_dialog(self, error_message):
        print(str(error_message) + '\n')
        dial = wx.MessageDialog(None, str(error_message), 'Error', wx.OK | wx.ICON_ERROR)
        dial.ShowModal()

    def open_spec_wizard(self, evt):
        # https://docs.wxpython.org/wx.Dialog.html#phoenix-title-modal-and-modeless
        dlg = SpecWizardDialog(self, None, wx.ID_ANY, )
        dlg.Show()  # ShowModal() method displays dialog frame in the modal manner, while Show() makes it modeless.

        # with SpecWizardDialog(self, None, wx.ID_ANY, ) as dlg:
        #     if dlg.Show() == wx.ID_OK:
        #         # do something here
        #         print('Hello')
        #     else:
        #         pass

    # ------------------------------------------------------------------------------------------------------------------
    def config_all_instruments(self, evt):
        # dlg = InstrumentDialog(self, ['f5560A', 'f8588A', 'f884xA'], None, wx.ID_ANY, )
        # dlg.ShowModal()
        # dlg.Destroy()
        with InstrumentDialog(self, ['f5560A', 'f8588A', 'f884xA'], None, wx.ID_ANY, ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                # do something here
                print('Hello')
            else:
                pass

    def close_all_instruments(self):
        wait = wx.BusyCursor()
        msg = "Closing all remote connections to instruments"
        busyDlg = wx.BusyInfo(msg, parent=self)

        try:
            print("Closing all possible remote connections to instruments:")
            self.tab_analyzer.da.close_instruments()
            self.tab_multimeter.dmm.close_instruments()

        except ValueError as e:
            error = str(e)
            print(error)
            if error.split()[0] == "VI_ERROR_CONN_LOST":
                print("[ERROR] Connection was lost before closing remote connection.")
                pass
            else:
                raise

        busyDlg = None
        del wait

    def OnCloseInstruments(self, evt):
        self.close_all_instruments()
        self.popup_dialog('All instruments have been closed.')

    def OnCloseWindow(self, evt):
        self.close_all_instruments()
        self.Destroy()

    def OnWindowSelection(self, evt):
        window_value = "rectangular"
        for item in self.radio_menu_windowing.GetMenuItems():
            if item.IsChecked():
                window_value = item.GetItemLabelText().lower()

        self.tab_analyzer.da.WINDOW_SELECTION = window_value
        print(f"[{window_value}] Selected as the windowing function.")

    def OnTriggerSelection(self, evt):
        trigger_value = "aperture"
        for item in self.radio_menu_trigger.GetMenuItems():
            if item.IsChecked():
                trigger_value = item.GetItemLabelText().lower()

        self.tab_analyzer.da.USE_APERTURE = trigger_value
        print(f"[{trigger_value}] Selected as the trigger method.")

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
        header = ['Amplitude', 'freq_ideal', 'freq_sampled',
                  'RMS', 'THDN', 'THD', 'uARMS Noise', 'Fs', 'Samples', 'Aperture']
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
    # https://stackoverflow.com/a/16237927
    warnings.simplefilter('error', UserWarning)
    app = MyApp(0)
    app.MainLoop()
