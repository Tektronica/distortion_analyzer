from distortion_analyzer import DistortionAnalyzer as da

from instruments_dialog_gui import *
from instruments_RWConfig import *
from grid_enhanced import MyGrid

import wx
import re
import time
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.pylab as pylab
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavigationToolbar

import threading

# https://stackoverflow.com/a/38251497
# https://matplotlib.org/3.1.1/tutorials/introductory/customizing.html
params = {'legend.fontsize': 'medium',
          'font.family': 'Segoe UI',
          'axes.titleweight': 'bold',
          'figure.figsize': (15, 5),
          'axes.labelsize': 'medium',
          'axes.titlesize': 'medium',
          'xtick.labelsize': 'medium',
          'ytick.labelsize': 'medium'}
pylab.rcParams.update(params)


########################################################################################################################
class TestFrame(wx.Frame):
    """"""

    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, *args, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.SetSize((1055, 640))
        # https://stackoverflow.com/a/24704039/3382269
        self.SetSizeHints(1055, 640, -1, -1)
        self.flag_complete = True  # Flag indicates any active threads (False) or thread completed (True)
        self.t = threading.Thread()
        self.da = da(self)
        self.user_input = {'mode': 0,
                           'source': 0,
                           'amplitude': '',
                           'rms': 0,
                           'frequency': '',
                           'samples': 0,
                           'cycles': 0,
                           'filter': 0
                           }
        self.panel_1 = wx.Panel(self, wx.ID_ANY)
        self.notebook = wx.Notebook(self.panel_1, wx.ID_ANY)
        self.notebook_analyzer = wx.Panel(self.notebook, wx.ID_ANY)
        self.notebook_data = wx.Panel(self.notebook, wx.ID_ANY)
        self.panel_3 = wx.Panel(self.notebook_analyzer, wx.ID_ANY)  # left panel
        self.panel_4 = wx.Panel(self.panel_3, wx.ID_ANY)  # amplitude/frequency panel
        self.panel_5 = wx.Panel(self.notebook_analyzer, wx.ID_ANY, style=wx.SIMPLE_BORDER)  # plot panel

        # PLOT Panel ---------------------------------------------------------------------------------------------------
        self.figure = plt.figure(figsize=(1, 1))  # look into Figure((5, 4), 75)
        self.canvas = FigureCanvas(self.panel_5, -1, self.figure)
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Realize()

        self.ax1 = self.figure.add_subplot(211)
        self.ax2 = self.figure.add_subplot(212)

        self.temporal, = self.ax1.plot([], [], linestyle='-')
        self.spectral, = self.ax2.plot([], [], color='#C02942')

        # LEFT TOOL PANEL ----------------------------------------------------------------------------------------------
        self.text_DUT_report = wx.TextCtrl(self.panel_3, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_DMM_report = wx.TextCtrl(self.panel_3, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.btn_connect = wx.Button(self.panel_3, wx.ID_ANY, "Connect")
        self.btn_config = wx.Button(self.panel_3, wx.ID_ANY, "Config")

        self.checkbox_1 = wx.CheckBox(self.panel_3, wx.ID_ANY, "Control Source")
        self.text_amplitude = wx.TextCtrl(self.panel_4, wx.ID_ANY, "10uA")
        self.combo_box_1 = wx.ComboBox(self.panel_4, wx.ID_ANY, choices=["RMS", "Peak"],
                                       style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.text_frequency = wx.TextCtrl(self.panel_4, wx.ID_ANY, "1000")
        self.text_samples = wx.TextCtrl(self.panel_3, wx.ID_ANY, "40000")
        self.text_cycles = wx.TextCtrl(self.panel_3, wx.ID_ANY, "70")
        self.combo_filter = wx.ComboBox(self.panel_3, wx.ID_ANY, choices=["None", "100kHz", "3MHz"],
                                        style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.label_fs_report = wx.StaticText(self.panel_3, wx.ID_ANY, "--")
        self.label_aperture_report = wx.StaticText(self.panel_3, wx.ID_ANY, "--")
        self.text_rms_report = wx.TextCtrl(self.panel_3, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_thdn_report = wx.TextCtrl(self.panel_3, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_thd_report = wx.TextCtrl(self.panel_3, wx.ID_ANY, "", style=wx.TE_READONLY)

        self.btn_start = wx.Button(self.panel_3, wx.ID_ANY, "RUN")
        self.combo_mode = wx.ComboBox(self.panel_3, wx.ID_ANY,
                                      choices=["Single", "Sweep", "Single w/ shunt", "Sweep w/ shunt", "~Continuous"],
                                      style=wx.CB_DROPDOWN)

        # Data panel for displaying raw output -------------------------------------------------------------------------
        self.grid_1 = MyGrid(self.notebook_data)
        self.btn_export = wx.Button(self.notebook_data, wx.ID_ANY, "Export")

        # Menu Bar -----------------------------------------------------------------------------------------------------
        self.frame_menubar = wx.MenuBar()
        wxglade_tmp_menu = wx.Menu()
        self.menu_export = wxglade_tmp_menu.Append(wx.ID_ANY, "Export Data", "")
        self.frame_menubar.Append(wxglade_tmp_menu, "File")
        wxglade_tmp_menu = wx.Menu()
        self.menu_config = wxglade_tmp_menu.Append(wx.ID_ANY, "Configure instruments", "")
        # self.menu_brkpts = wxglade_tmp_menu.Append(wx.ID_ANY, "Open Breakpoints", "")
        self.frame_menubar.Append(wxglade_tmp_menu, "Settings")
        self.SetMenuBar(self.frame_menubar)

        # Menu Bar Bind Events -----------------------------------------------------------------------------------------
        self.Bind(wx.EVT_MENU, self.grid_1.export, self.menu_export)
        self.Bind(wx.EVT_MENU, self.config, self.menu_config)
        # self.Bind(wx.EVT_MENU, self.open_breakpoints, self.menu_brkpts)

        # Configure Instruments ----------------------------------------------------------------------------------------
        on_connect = lambda event: self.on_connect_instr(event)
        self.Bind(wx.EVT_BUTTON, on_connect, self.btn_connect)

        on_config = lambda event: self.config(event)
        self.Bind(wx.EVT_BUTTON, on_config, self.btn_config)

        # Run Measurement (start subprocess) ---------------------------------------------------------------------------
        on_single_event = lambda event: self.on_run(event)
        self.Bind(wx.EVT_BUTTON, on_single_event, self.btn_start)

        on_toggle = lambda event: self.toggle_panel(event)
        self.Bind(wx.EVT_CHECKBOX, on_toggle, self.checkbox_1)

        on_combo_select = lambda event: self.lock_controls(event)
        self.Bind(wx.EVT_COMBOBOX_CLOSEUP, on_combo_select, self.combo_mode)

        # export grid data ---------------------------------------------------------------------------------------------
        self.Bind(wx.EVT_BUTTON, self.grid_1.export, self.btn_export)

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

        self.Freeze()
        self.__set_properties()
        self.__do_layout()
        self.__do_plot_layout()
        self.__do_table_header()
        self.Thaw()

    def __set_properties(self):
        self.SetTitle("Distortion Analyzer")
        self.SetBackgroundColour(wx.Colour(227, 227, 227))
        self.notebook.SetBackgroundColour(wx.Colour(227, 227, 227))
        self.notebook_analyzer.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.notebook_data.SetBackgroundColour(wx.Colour(255, 255, 255))

        self.text_DUT_report.SetMinSize((200, 23))
        self.text_DMM_report.SetMinSize((200, 23))
        self.canvas.SetMinSize((700, 490))
        self.panel_3.SetMinSize((310, 502))
        self.panel_5.SetMinSize((700, 502))
        self.checkbox_1.SetValue(1)
        self.combo_box_1.SetSelection(0)
        self.combo_filter.SetSelection(1)
        self.combo_mode.SetSelection(0)

        self.grid_1.CreateGrid(100, 60)
        self.grid_1.SetMinSize((1024, 50))

    def __do_layout(self):
        sizer_7 = wx.BoxSizer(wx.VERTICAL)
        sizer_8 = wx.BoxSizer(wx.VERTICAL)

        grid_sizer_1 = wx.GridBagSizer(0, 0)
        grid_sizer_2 = wx.GridBagSizer(0, 0)
        grid_sizer_3 = wx.GridBagSizer(0, 0)
        grid_sizer_4 = wx.GridBagSizer(0, 0)
        grid_sizer_5 = wx.FlexGridSizer(2, 1, 0, 0)
        grid_sizer_6 = wx.GridSizer(1, 3, 0, 0)

        # TITLE --------------------------------------------------------------------------------------------------------
        label_1 = wx.StaticText(self.panel_3, wx.ID_ANY, "DISTORTION ANALYZER")
        label_1.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_2.Add(label_1, (0, 0), (1, 2), 0, 0)

        static_line_5 = wx.StaticLine(self.panel_3, wx.ID_ANY)
        static_line_5.SetMinSize((300, 2))
        grid_sizer_2.Add(static_line_5, (1, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        # PLOT PANEL ---------------------------------------------------------------------------------------------------
        grid_sizer_4.Add(self.canvas, (0, 0), (1, 1), wx.ALL | wx.EXPAND)
        grid_sizer_4.Add(self.toolbar, (1, 0), (1, 1), wx.ALL | wx.EXPAND)
        self.panel_5.SetSizer(grid_sizer_4)

        # LEFT TOOL PANEL ==============================================================================================
        # INSTRUMENT INFO  ---------------------------------------------------------------------------------------------
        label_DUT = wx.StaticText(self.panel_3, wx.ID_ANY, "DUT")
        label_DMM = wx.StaticText(self.panel_3, wx.ID_ANY, "DMM (Digitizer)")

        label_DUT.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        label_DMM.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))

        grid_sizer_2.Add(label_DUT, (2, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_2.Add(label_DMM, (3, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_2.Add(self.btn_connect, (4, 0), (1, 1), wx.BOTTOM, 5)
        grid_sizer_2.Add(self.text_DUT_report, (2, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_2.Add(self.text_DMM_report, (3, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_2.Add(self.btn_config, (4, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        static_line_6 = wx.StaticLine(self.panel_3, wx.ID_ANY)
        static_line_6.SetMinSize((300, 2))
        grid_sizer_2.Add(static_line_6, (6, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        # SOURCE -------------------------------------------------------------------------------------------------------
        label_source = wx.StaticText(self.panel_3, wx.ID_ANY, "Source")
        label_source.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_2.Add(label_source, (5, 0), (1, 1), wx.TOP, 10)
        grid_sizer_2.Add(self.checkbox_1, (5, 1), (1, 1), wx.ALIGN_BOTTOM | wx.LEFT | wx.TOP, 5)

        label_amplitude = wx.StaticText(self.panel_4, wx.ID_ANY, "Amplitude:")
        label_frequency = wx.StaticText(self.panel_4, wx.ID_ANY, "Frequency (Ft):")
        label_Hz = wx.StaticText(self.panel_4, wx.ID_ANY, "(Hz)")
        label_measure = wx.StaticText(self.panel_3, wx.ID_ANY, "Measure")

        label_frequency.SetMinSize((95, 16))

        grid_sizer_3.Add(label_amplitude, (0, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_3.Add(self.text_amplitude, (0, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_3.Add(self.combo_box_1, (0, 2), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_3.Add(label_frequency, (1, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_3.Add(self.text_frequency, (1, 1), (1, 1), wx.LEFT, 5)
        grid_sizer_3.Add(label_Hz, (1, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        self.panel_4.SetSizer(grid_sizer_3)
        grid_sizer_2.Add(self.panel_4, (7, 0), (1, 2), wx.EXPAND, 0)

        # MEASURE ------------------------------------------------------------------------------------------------------
        label_samples = wx.StaticText(self.panel_3, wx.ID_ANY, "Samples (N):")
        label_cycles = wx.StaticText(self.panel_3, wx.ID_ANY, "Cycles:")
        label_filter = wx.StaticText(self.panel_3, wx.ID_ANY, "Filter:")
        label_fs = wx.StaticText(self.panel_3, wx.ID_ANY, "Fs:")
        label_aperture = wx.StaticText(self.panel_3, wx.ID_ANY, "Aperture:")

        label_measure.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_2.Add(label_measure, (8, 0), (1, 2), wx.TOP, 10)
        static_line_7 = wx.StaticLine(self.panel_3, wx.ID_ANY)

        static_line_7.SetMinSize((300, 2))
        grid_sizer_2.Add(static_line_7, (9, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)
        grid_sizer_2.Add(label_samples, (10, 0), (1, 1), 0, 0)
        grid_sizer_2.Add(self.text_samples, (10, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_2.Add(label_cycles, (11, 0), (1, 1), 0, 0)
        grid_sizer_2.Add(self.text_cycles, (11, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_2.Add(label_filter, (12, 0), (1, 1), 0, 0)
        grid_sizer_2.Add(self.combo_filter, (12, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_2.Add(label_fs, (13, 0), (1, 1), 0, 0)
        grid_sizer_2.Add(self.label_fs_report, (13, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_2.Add(label_aperture, (14, 0), (1, 1), 0, 0)
        grid_sizer_2.Add(self.label_aperture_report, (14, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        # RESULTS ------------------------------------------------------------------------------------------------------
        static_line_8 = wx.StaticLine(self.panel_3, wx.ID_ANY)
        static_line_8.SetMinSize((300, 2))
        grid_sizer_2.Add(static_line_8, (15, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        label_rms = wx.StaticText(self.panel_3, wx.ID_ANY, "RMS:")
        label_thdn = wx.StaticText(self.panel_3, wx.ID_ANY, "THD+N:")
        label_thd = wx.StaticText(self.panel_3, wx.ID_ANY, "THD:")

        grid_sizer_2.Add(label_rms, (16, 0), (1, 1), 0, 0)
        grid_sizer_2.Add(self.text_rms_report, (16, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_2.Add(label_thdn, (17, 0), (1, 1), 0, 0)
        grid_sizer_2.Add(self.text_thdn_report, (17, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_2.Add(label_thd, (18, 0), (1, 1), 0, 0)
        grid_sizer_2.Add(self.text_thd_report, (18, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        static_line_9 = wx.StaticLine(self.panel_3, wx.ID_ANY)
        static_line_9.SetMinSize((300, 2))
        grid_sizer_2.Add(static_line_9, (19, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        # BUTTONS ------------------------------------------------------------------------------------------------------
        grid_sizer_2.Add(self.btn_start, (20, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        grid_sizer_2.Add(self.combo_mode, (20, 1), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

        self.panel_3.SetSizer(grid_sizer_2)
        grid_sizer_1.Add(self.panel_3, (0, 0), (1, 1), wx.EXPAND, 0)
        grid_sizer_1.Add(self.panel_5, (0, 1), (1, 1), wx.EXPAND, 0)
        self.notebook_analyzer.SetSizer(grid_sizer_1)

        grid_sizer_6.Add(self.btn_export, 0, wx.ALL, 5)
        grid_sizer_6.Add((0, 0), 0, 0, 0)
        grid_sizer_6.Add((0, 0), 0, 0, 0)
        grid_sizer_5.Add(self.grid_1, 0, wx.EXPAND, 0)
        grid_sizer_5.Add(grid_sizer_6, 1, wx.EXPAND, 0)
        self.notebook_data.SetSizer(grid_sizer_5)
        grid_sizer_5.AddGrowableRow(0)
        grid_sizer_5.AddGrowableCol(0)

        grid_sizer_1.AddGrowableRow(0)
        grid_sizer_1.AddGrowableCol(1)
        grid_sizer_4.AddGrowableRow(0)
        grid_sizer_4.AddGrowableCol(0)
        self.notebook.AddPage(self.notebook_analyzer, "Analyzer")
        self.notebook.AddPage(self.notebook_data, "Data")
        sizer_8.Add(self.notebook, 1, wx.ALL | wx.EXPAND, 10)
        self.panel_1.SetSizer(sizer_8)
        sizer_7.Add(self.panel_1, 1, wx.EXPAND, 0)
        self.SetSizer(sizer_7)
        self.Layout()

    # ------------------------------------------------------------------------------------------------------------------
    def thread_this(self, func, arg=()):
        self.t = threading.Thread(target=func, args=arg, daemon=True)
        self.t.start()

    def on_connect_instr(self, evt):
        print('\nResetting connection. Closing communication with any connected instruments')
        self.text_DUT_report.Clear()
        self.text_DMM_report.Clear()
        self.thread_this(self.da.connect, (self.get_instruments(),))

    # ------------------------------------------------------------------------------------------------------------------
    def on_run(self, evt):
        self.get_values()
        if not self.t.is_alive() and self.flag_complete:
            # start new thread
            self.thread_this(self.da.start, (self.user_input,))
            self.btn_start.SetLabel('STOP')

        elif self.t.is_alive() and self.user_input['mode'] == 4:
            # stop continuous
            # https://stackoverflow.com/a/36499538
            self.t.do_run = False
            self.btn_start.SetLabel('RUN')
        else:
            print('thread already running.')

    def config(self, evt):
        dlg = InstrumentDialog(self, None, wx.ID_ANY, "")
        dlg.ShowModal()
        dlg.Destroy()

    def get_instruments(self):
        config_dict = ReadConfig()

        instruments = {'DUT': {'address': config_dict['DUT']['address'], 'port': config_dict['DUT']['port'],
                               'gpib': config_dict['DUT']['gpib'], 'mode': config_dict['DUT']['mode']},
                       'DMM': {'address': config_dict['DMM']['address'], 'port': config_dict['DMM']['port'],
                               'gpib': config_dict['DMM']['gpib'], 'mode': config_dict['DMM']['mode']}}
        return instruments

    def set_ident(self, idn_dict):
        self.text_DUT_report.SetValue(idn_dict['DUT'])  # DUT
        self.text_DMM_report.SetValue(idn_dict['DMM'])  # current DMM

    # ------------------------------------------------------------------------------------------------------------------
    def lock_controls(self, evt):
        choice = self.combo_mode.GetSelection()
        if choice in (1, 3):
            if self.checkbox_1.GetValue() == 0:
                self.checkbox_1.SetValue(1)
                self.toggle_panel(evt)
            self.checkbox_1.Disable()
            self.text_amplitude.Disable()
            self.combo_box_1.Disable()
            self.text_frequency.Disable()
        else:
            self.checkbox_1.Enable()
            self.text_amplitude.Enable()
            self.combo_box_1.Enable()
            self.text_frequency.Enable()

    def toggle_controls(self):
        if self.text_amplitude.Enabled:
            self.checkbox_1.Disable()
            self.text_amplitude.Disable()
            self.combo_box_1.Disable()
            self.text_frequency.Disable()
        else:
            self.checkbox_1.Enable()
            self.text_amplitude.Enable()
            self.combo_box_1.Enable()
            self.text_frequency.Enable()

    # ------------------------------------------------------------------------------------------------------------------
    def toggle_panel(self, evt):
        if self.checkbox_1.GetValue():
            if not self.panel_4.IsShown():
                self.panel_4.Show()
        else:
            self.panel_4.Hide()

    # ------------------------------------------------------------------------------------------------------------------
    def get_values(self):
        mode = self.combo_mode.GetSelection()
        source = self.checkbox_1.GetValue()
        samples = int(self.text_samples.GetValue())
        rms = self.combo_box_1.GetSelection()
        cycles = int(self.text_cycles.GetValue())
        filter = self.combo_filter.GetStringSelection()

        amp_string = self.text_amplitude.GetValue()
        freq_string = self.text_frequency.GetValue()

        self.user_input = {'mode': mode,
                           'source': source,
                           'amplitude': amp_string,
                           'rms': rms,
                           'frequency': freq_string,
                           'samples': samples,
                           'cycles': cycles,
                           'filter': filter
                           }

    # def open_breakpoints(self, evt):
    #     fileName = 'distortion_breakpoints.csv'
    #     os.system("notepad.exe " + fileName)

    def error_dialog(self, error_message):
        print(error_message)
        dial = wx.MessageDialog(None, str(error_message), 'Error', wx.OK | wx.ICON_ERROR)
        dial.ShowModal()

    def OnCloseWindow(self, evt):
        self.da.close_instruments()
        self.Destroy()

    def __do_table_header(self):
        header = [['Amplitude', 'Frequency', 'RMS', 'THDN', 'THD', 'uARMS Noise', 'Fs', 'Aperture']]
        self.grid_1.append_rows(header)

    def results_update(self, results):
        amplitude = results['Amplitude']
        frequency = results['Frequency']

        fs = results['Fs']
        aperture = results['Aperture']
        rms = results['RMS']
        units = results['units']
        thdn = results['THDN']
        thd = results['THD']
        rms_noise = results['RMS NOISE']

        self.label_fs_report.SetLabelText(str(fs))
        self.label_aperture_report.SetLabelText(str(aperture))
        self.text_rms_report.SetValue(f"{rms}{units}")
        self.text_thdn_report.SetValue(f"{round(thdn * 100, 3)}% or {round(np.log10(thdn), 1)}dB")
        self.text_thd_report.SetValue(f"{round(thd * 100, 3)}% or {round(np.log10(thd), 1)}dB")

        # self.grid_1.append_rows({k: results[k] for k in set(list(results.keys())) - {'units'}})
        self.grid_1.append_rows([[amplitude, frequency, rms, thdn, thd, rms_noise, fs, aperture]])

    # ------------------------------------------------------------------------------------------------------------------
    def __do_plot_layout(self):
        self.ax1.set_title('SAMPLED TIMED SERIES DATA')
        self.ax1.set_xlabel('TIME (ms)')
        self.ax1.set_ylabel('AMPLITUDE')
        self.ax2.set_title('DIGITIZED WAVEFORM SPECTRAL RESPONSE')
        self.ax2.set_xlabel('FREQUENCY (kHz)')
        self.ax2.set_ylabel('MAGNITUDE (dB)')
        self.ax2.grid()
        self.figure.align_ylabels([self.ax1, self.ax2])
        self.figure.tight_layout()

    def plot(self, params):
        # TEMPORAL -----------------------------------------------------------------------------------------------------
        xt = params['xt']
        yt = params['yt']

        self.temporal.set_data(xt, yt)

        xt_start = params['xt_start']
        xt_end = params['xt_end']
        yt_start = params['yt_start']
        yt_end = params['yt_end']
        yt_tick = params['yt_tick']

        self.ax1.set_yticks(np.arange(yt_start, yt_end, yt_tick))
        self.ax1.relim()  # recompute the ax.dataLim
        self.ax1.autoscale()
        self.ax1.set_xlim([xt_start, xt_end])

        # SPECTRAL -----------------------------------------------------------------------------------------------------
        xf = params['xf']
        yf = params['yf']

        self.spectral.set_data(xf, yf)

        xf_start = params['xf_start']
        xf_end = params['xf_end']
        yf_start = params['yf_start']
        yf_end = params['yf_end']

        self.ax2.set_xlim(xf_start, xf_end)
        self.ax2.set_ylim(yf_start, yf_end)

        # UPDATE PLOT FEATURES -----------------------------------------------------------------------------------------
        self.figure.tight_layout()

        self.toolbar.update()  # Not sure why this is needed - ADS
        self.canvas.draw()
        self.canvas.flush_events()


########################################################################################################################
class MyApp(wx.App):
    """"""

    # ------------------------------------------------------------------------------------------------------------------
    def OnInit(self):
        self.frame = TestFrame(None, wx.ID_ANY, "")
        self.SetTopWindow(self.frame)
        self.frame.SetIcon(wx.Icon('images/hornet.ico'))
        self.frame.Show()
        return True


# Run
if __name__ == "__main__":
    app = MyApp(0)
    app.MainLoop()
