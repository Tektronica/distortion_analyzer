from multimeter import DMM_Measurement as dmm
from gui_dialog_instruments import *
from instruments_RWConfig import *

import numpy as np
import pandas as pd
from pathlib import Path
import threading

import wx

import matplotlib.pyplot as plt
import matplotlib.pylab as pylab
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavigationToolbar


class MultimeterTab(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY)

        self.parent = parent
        self.left_panel = wx.Panel(self, wx.ID_ANY)
        self.plot_panel = wx.Panel(self, wx.ID_ANY, style=wx.SIMPLE_BORDER)

        # LEFT Panel ---------------------------------------------------------------------------------------------------
        self.text_DUT_report = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_DMM_report = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.btn_connect = wx.Button(self.left_panel, wx.ID_ANY, "Connect")
        self.btn_config = wx.Button(self.left_panel, wx.ID_ANY, "Config")

        self.text_amplitude = wx.TextCtrl(self.left_panel, wx.ID_ANY, "10uA")
        self.combo_rms_or_peak = wx.ComboBox(self.left_panel, wx.ID_ANY,
                                             choices=["RMS", "Peak"],
                                             style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.text_frequency = wx.TextCtrl(self.left_panel, wx.ID_ANY, "1000")

        self.text_rms_report = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_frequency_report = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)

        self.btn_start = wx.Button(self.left_panel, wx.ID_ANY, "RUN")
        self.combo_mode = wx.ComboBox(self.left_panel, wx.ID_ANY, choices=["Single", "Sweep"], style=wx.CB_DROPDOWN)

        # PLOT Panel ---------------------------------------------------------------------------------------------------
        self.figure = plt.figure(figsize=(1, 1))  # look into Figure((5, 4), 75)
        self.canvas = FigureCanvas(self.plot_panel, -1, self.figure)
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Realize()

        self.ax1 = self.figure.add_subplot(111)

        self.temporal, = self.ax1.plot([], [], linestyle='-')

        # instance variables -------------------------------------------------------------------------------------------
        self.dmm = dmm(self)
        self.flag_complete = True  # Flag indicates any active threads (False) or thread completed (True)
        self.user_input = {'mode': 0,
                           'amplitude': '',
                           'rms': 0,
                           'frequency': '',
                           }

        # Open history dialog ------------------------------------------------------------------------------------------
        self.btn_openHistory = wx.Button(self, wx.ID_ANY, "Open History")
        self.Bind(wx.EVT_BUTTON, self.OnOpen, self.btn_openHistory)

        # Configure Instruments ----------------------------------------------------------------------------------------
        on_connect = lambda event: self.on_connect_instr(event)
        self.Bind(wx.EVT_BUTTON, on_connect, self.btn_connect)

        on_config = lambda event: self.config(event)
        self.Bind(wx.EVT_BUTTON, on_config, self.btn_config)

        # Run Measurement (start subprocess) ---------------------------------------------------------------------------
        on_single_event = lambda event: self.on_run(event)
        self.Bind(wx.EVT_BUTTON, on_single_event, self.btn_start)

        on_combo_select = lambda event: self.lock_controls(event)
        self.Bind(wx.EVT_COMBOBOX_CLOSEUP, on_combo_select, self.combo_mode)

        self.__set_properties()
        self.__do_layout()
        self.__do_plot_layout()

    def __set_properties(self):
        self.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.canvas.SetMinSize((700, 490))

        self.left_panel.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.plot_panel.SetBackgroundColour(wx.Colour(255, 255, 255))

        self.text_DUT_report.SetMinSize((200, 23))
        self.text_DMM_report.SetMinSize((200, 23))
        self.combo_rms_or_peak.SetSelection(0)
        self.combo_mode.SetSelection(0)

    def __do_layout(self):
        sizer_2 = wx.GridSizer(1, 1, 0, 0)
        grid_sizer_1 = wx.FlexGridSizer(1, 2, 0, 0)
        grid_sizer_left_panel = wx.GridBagSizer(0, 0)
        grid_sizer_plot = wx.GridBagSizer(0, 0)

        # LEFT PANEL ===================================================================================================
        # TITLE --------------------------------------------------------------------------------------------------------
        label_1 = wx.StaticText(self.left_panel, wx.ID_ANY, "MULTIMETER")
        label_1.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_1, (0, 0), (1, 2), 0, 0)

        static_line_1 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_1.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_1, (1, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        # INSTRUMENT INFO  ---------------------------------------------------------------------------------------------
        label_DUT = wx.StaticText(self.left_panel, wx.ID_ANY, "DUT")
        label_DUT.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_DUT, (2, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.text_DUT_report, (2, 1), (1, 2), wx.BOTTOM | wx.LEFT, 5)

        label_DMM = wx.StaticText(self.left_panel, wx.ID_ANY, "DMM (f884xA)")
        label_DMM.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_DMM, (3, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.text_DMM_report, (3, 1), (1, 2), wx.BOTTOM | wx.LEFT, 5)

        grid_sizer_left_panel.Add(self.btn_connect, (4, 0), (1, 1), wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.btn_config, (4, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_source = wx.StaticText(self.left_panel, wx.ID_ANY, "Source")
        label_source.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_source, (5, 0), (1, 1), wx.TOP, 10)

        static_line_2 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_2.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_2, (6, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        label_amplitude = wx.StaticText(self.left_panel, wx.ID_ANY, "Amplitude:")
        grid_sizer_left_panel.Add(label_amplitude, (7, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.text_amplitude, (7, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_left_panel.Add(self.combo_rms_or_peak, (7, 2), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_frequency = wx.StaticText(self.left_panel, wx.ID_ANY, "Frequency (Ft):")
        grid_sizer_left_panel.Add(label_frequency, (8, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.text_frequency, (8, 1), (1, 1), wx.LEFT, 5)
        label_Hz = wx.StaticText(self.left_panel, wx.ID_ANY, "(Hz)")
        grid_sizer_left_panel.Add(label_Hz, (8, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

        label_measure = wx.StaticText(self.left_panel, wx.ID_ANY, "Measurement")
        label_measure.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_measure, (9, 0), (1, 2), wx.TOP, 10)

        # RESULTS ------------------------------------------------------------------------------------------------------
        static_line_3 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_3.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_3, (10, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        label_rms_report = wx.StaticText(self.left_panel, wx.ID_ANY, "RMS:")
        label_frequency_report = wx.StaticText(self.left_panel, wx.ID_ANY, "Frequency:")

        grid_sizer_left_panel.Add(label_rms_report, (11, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.text_rms_report, (11, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_left_panel.Add(label_frequency_report, (12, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.text_frequency_report, (12, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        # BUTTONS ------------------------------------------------------------------------------------------------------
        static_line_4 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_4.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_4, (13, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        grid_sizer_left_panel.Add(self.btn_start, (14, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        grid_sizer_left_panel.Add(self.combo_mode, (14, 1), (1, 1), wx.EXPAND | wx.LEFT, 5)

        self.left_panel.SetSizer(grid_sizer_left_panel)

        # PLOT PANEL ===================================================================================================
        grid_sizer_plot.Add(self.canvas, (0, 0), (1, 1), wx.ALL | wx.EXPAND)
        grid_sizer_plot.Add(self.toolbar, (1, 0), (1, 1), wx.ALL | wx.EXPAND)
        grid_sizer_plot.AddGrowableRow(0)
        grid_sizer_plot.AddGrowableCol(0)
        self.plot_panel.SetSizer(grid_sizer_plot)

        # add to main panel --------------------------------------------------------------------------------------------
        grid_sizer_1.Add(self.left_panel, 0, wx.EXPAND | wx.RIGHT, 5)
        grid_sizer_1.Add(self.plot_panel, 1, wx.EXPAND, 5)
        grid_sizer_1.AddGrowableRow(0)
        grid_sizer_1.AddGrowableCol(1)

        sizer_2.Add(grid_sizer_1, 0, wx.EXPAND, 0)

        self.SetSizer(sizer_2)
        self.Layout()

    # ------------------------------------------------------------------------------------------------------------------
    def config(self, evt):
        dlg = InstrumentDialog(self, None, wx.ID_ANY, "")
        dlg.ShowModal()
        dlg.Destroy()

    # ------------------------------------------------------------------------------------------------------------------
    def lock_controls(self, evt):
        choice = self.combo_mode.GetSelection()
        if choice == 1:
            self.text_amplitude.Disable()
            self.combo_rms_or_peak.Disable()
            self.text_frequency.Disable()
        else:
            self.text_amplitude.Enable()
            self.combo_rms_or_peak.Enable()
            self.text_frequency.Enable()

    # ------------------------------------------------------------------------------------------------------------------
    def get_values(self):
        mode = self.combo_mode.GetSelection()
        rms = self.combo_rms_or_peak.GetSelection()

        amp_string = self.text_amplitude.GetValue()
        freq_string = self.text_frequency.GetValue()

        self.user_input = {'mode': mode,
                           'amplitude': amp_string,
                           'rms': rms,
                           'frequency': freq_string,
                           }

    # ------------------------------------------------------------------------------------------------------------------
    def thread_this(self, func, arg=()):
        self.t = threading.Thread(target=func, args=arg, daemon=True)
        self.t.start()

    def get_instruments(self):
        config_dict = ReadConfig()

        instruments = {'DUT': {'address': config_dict['DUT']['address'], 'port': config_dict['DUT']['port'],
                               'gpib': config_dict['DUT']['gpib'], 'mode': config_dict['DUT']['mode']},
                       'f884xA': {'address': config_dict['DMM']['address'], 'port': config_dict['DMM']['port'],
                                  'gpib': config_dict['DMM']['gpib'], 'mode': config_dict['DMM']['mode']}}
        return instruments

    def on_connect_instr(self, evt):
        print('\nResetting connection. Closing communication with any connected instruments')
        self.text_DUT_report.Clear()
        self.text_DMM_report.Clear()
        self.thread_this(self.dmm.connect, (self.get_instruments(),))

    # ------------------------------------------------------------------------------------------------------------------
    def on_run(self, evt):
        self.get_values()
        if not self.t.is_alive() and self.flag_complete:
            # start new thread
            self.thread_this(self.dmm.start, (self.user_input,))
            self.btn_start.SetLabel('STOP')

        elif self.t.is_alive() and self.user_input['mode'] in (1, 4):
            # stop continuous
            # https://stackoverflow.com/a/36499538
            self.t.do_run = False
            self.btn_start.SetLabel('RUN')
        else:
            print('thread already running.')

    def OnOpen(self, event):
        Path("results/history").mkdir(parents=True, exist_ok=True)
        with wx.FileDialog(self, "Open previous measurement:", wildcard="CSV files (*.csv)|*.csv",
                           defaultDir="results/history",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return  # the user changed their mind

            # Proceed loading the file chosen by the user
            pathname = fileDialog.GetPath()
            try:
                with open(pathname, 'r') as file:
                    self.open_history(file)
            except (IOError, ValueError) as e:
                wx.LogError("Cannot open file '%s'." % pathname)
                self.error_dialog(e)

    def open_history(self, file):
        df = pd.read_csv(file)

        try:
            xt = df['xt'].to_numpy()
            yt = df['yt'].to_numpy()
            xf = df['xf'].to_numpy()

            # https://stackoverflow.com/a/18919965/3382269
            # https://stackoverflow.com/a/51725795/3382269
            df['yf'] = df['yf'].str.replace('i', 'j').apply(lambda x: np.complex(x))
            yf = df['yf'].to_numpy()
        except KeyError:
            raise ValueError('Incorrect file attempted to be opened. '
                             '\nCheck data headers. xt, yt, xf, yf should be present')

    # ------------------------------------------------------------------------------------------------------------------
    def __do_plot_layout(self):
        self.ax1.set_title('SAMPLED TIMED SERIES DATA')
        self.ax1.set_xlabel('FREQUENCY (kHz)')
        self.ax1.set_ylabel('AMPLITUDE')
        self.figure.tight_layout()

    def plot(self, x, y):
        self.temporal.set_data(x, y)

        try:
            self.ax1.relim()  # recompute the ax.dataLim
        except ValueError:
            print(f'Are the lengths of xt: {len(x)} and yt: {len(y)} mismatched?')
            raise
        self.ax1.autoscale()

        # UPDATE PLOT FEATURES -----------------------------------------------------------------------------------------
        self.figure.tight_layout()

        self.toolbar.update()  # Not sure why this is needed - ADS
        self.canvas.draw()
        self.canvas.flush_events()

    def results_update(self, x, y):
        self.text_rms_report.SetLabelText(str(y))
        self.text_frequency_report.SetLabelText(str(x))

    def error_dialog(self, error_message):
        print(error_message)
        dial = wx.MessageDialog(None, str(error_message), 'Error', wx.OK | wx.ICON_ERROR)
        dial.ShowModal()
