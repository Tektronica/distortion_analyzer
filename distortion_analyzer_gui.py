from dmm_f8588A import *
from dut_f5560A import *
from distortion_calculator import *
from instruments_dialog_gui import *
from instruments_RWConfig import *

import wx
import re
import time
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.pylab as pylab
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavigationToolbar
import numpy as np
from pathlib import Path
import threading
import datetime
import os

DUMMY = False

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
def _getFilepath():
    Path('results').mkdir(parents=True, exist_ok=True)
    date = datetime.date.today().strftime("%Y%m%d")
    filename = f'distortion_{date}'
    index = 0

    while os.path.isfile('results/' + filename + "_" + str(index).zfill(2) + '.csv'):
        index += 1
    filename = filename + "_" + str(index).zfill(2)
    return f'results/{filename}.csv'


########################################################################################################################
class Instruments(f5560A_instrument, f8588A_instrument):
    def __init__(self, parent):
        f5560A_instrument.__init__(self)
        f8588A_instrument.__init__(self)
        self.parent = parent
        self.measurement = []
        self.connected = False

    def connect(self, instruments):
        # ESTABLISH COMMUNICATION TO INSTRUMENTS -----------------------------------------------------------------------
        f5560A_id = instruments['DUT']
        f8588A_id = instruments['DMM']
        self.connect_to_f5560A(f5560A_id)
        self.connect_to_f8588A(f8588A_id)

        if self.f5560A.okay and self.f8588A.okay:
            self.connected = True
            idn_dict = {'DUT': self.f5560A_IDN, 'DMM': self.f8588A_IDN}
            self.parent.set_ident(idn_dict)
            self.setup_source()
        else:
            print('\nUnable to connect to all instruments.\n')

    def close_instruments(self):
        time.sleep(1)
        self.close_f5560A()
        self.close_f8588A()


########################################################################################################################
class TestFrame(wx.Frame):
    """"""

    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, *args, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.SetSize((1049, 605))

        self.t = threading.Thread()
        self.flag_complete = True  # Flag indicates any active threads (False) or thread completed (True)
        self.amplitude_good = False  # Flag indicates user input for amplitude value is good (True)
        self.frequency_good = False  # Flag indicates user input for frequency value is good (True)

        self.panel_1 = wx.Panel(self, wx.ID_ANY)
        self.panel_2 = wx.Panel(self.panel_1, wx.ID_ANY)
        self.panel_3 = wx.Panel(self.panel_2, wx.ID_ANY)  # left panel
        self.panel_4 = wx.Panel(self.panel_3, wx.ID_ANY)  # amplitude/frequency panel
        self.panel_5 = wx.Panel(self.panel_2, wx.ID_ANY, style=wx.SIMPLE_BORDER)  # plot panel

        # PLOT Panel ---------------------------------------------------------------------------------------------------
        self.figure = plt.figure(figsize=(1, 1))  # look into Figure((5, 4), 75)
        self.canvas = FigureCanvas(self.panel_5, -1, self.figure)
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Realize()

        self.ax1 = self.figure.add_subplot(211)
        self.ax2 = self.figure.add_subplot(212)

        self.temporal, = self.ax1.plot([], [], linestyle='-')
        self.spectral, = self.ax2.plot([], [], color='red')

        # LEFT TOOL PANEL ----------------------------------------------------------------------------------------------
        self.text_DUT_report = wx.TextCtrl(self.panel_3, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_DMM_report = wx.TextCtrl(self.panel_3, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.btn_connect = wx.Button(self.panel_3, wx.ID_ANY, "Connect")
        self.btn_config = wx.Button(self.panel_3, wx.ID_ANY, "Config")

        self.checkbox_1 = wx.CheckBox(self.panel_3, wx.ID_ANY, "Control Source")
        self.text_amplitude = wx.TextCtrl(self.panel_4, wx.ID_ANY, "1.2A")
        self.combo_box_1 = wx.ComboBox(self.panel_4, wx.ID_ANY, choices=["RMS", "Peak"],
                                       style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.text_frequency = wx.TextCtrl(self.panel_4, wx.ID_ANY, "5000")
        self.text_samples = wx.TextCtrl(self.panel_3, wx.ID_ANY, "20000")
        self.text_cycles = wx.TextCtrl(self.panel_3, wx.ID_ANY, "70")
        self.combo_filter = wx.ComboBox(self.panel_3, wx.ID_ANY, choices=["None", "100kHz", "3MHz"],
                                        style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.label_fs_report = wx.StaticText(self.panel_3, wx.ID_ANY, "--")
        self.label_rms_report = wx.StaticText(self.panel_3, wx.ID_ANY, "--")
        self.text_rms_report = wx.TextCtrl(self.panel_3, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_thdn_report = wx.TextCtrl(self.panel_3, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_thd_report = wx.TextCtrl(self.panel_3, wx.ID_ANY, "", style=wx.TE_READONLY)

        self.btn_single = wx.Button(self.panel_3, wx.ID_ANY, "RUN")
        self.combo_box_3 = wx.ComboBox(self.panel_3, wx.ID_ANY,
                                       choices=["Single", "Sweep", "Single w/ shunt", "Sweep w/ shunt", "~Continuous"],
                                       style=wx.CB_DROPDOWN)

        # Menu Bar -----------------------------------------------------------------------------------------------------
        self.frame_menubar = wx.MenuBar()
        wxglade_tmp_menu = wx.Menu()
        wxglade_tmp_menu.Append(wx.ID_ANY, "Export Data", "")
        self.frame_menubar.Append(wxglade_tmp_menu, "File")
        wxglade_tmp_menu = wx.Menu()
        wxglade_tmp_menu.Append(wx.ID_ANY, "configure instruments", "")
        self.frame_menubar.Append(wxglade_tmp_menu, "Instruments")
        self.SetMenuBar(self.frame_menubar)

        # Configure Instruments ----------------------------------------------------------------------------------------
        on_connect = lambda event: self.connect(event)
        self.Bind(wx.EVT_BUTTON, on_connect, self.btn_connect)

        on_config = lambda event: self.config(event)
        self.Bind(wx.EVT_BUTTON, on_config, self.btn_config)

        # Run Measurement (start subprocess) ---------------------------------------------------------------------------
        on_single_event = lambda event: self.on_run(event)
        self.Bind(wx.EVT_BUTTON, on_single_event, self.btn_single)

        on_toggle = lambda event: self.toggle_panel(event)
        self.Bind(wx.EVT_CHECKBOX, on_toggle, self.checkbox_1)

        on_combo_select = lambda event: self.lock_controls(event)
        self.Bind(wx.EVT_COMBOBOX_CLOSEUP, on_combo_select, self.combo_box_3)

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

        self.Freeze()
        self.__set_properties()
        self.__do_layout()
        self.__do_plot_layout()
        self.Thaw()

        self.M = Instruments(self)

    def __set_properties(self):
        self.SetTitle("Distortion Analyzer")
        self.text_DUT_report.SetMinSize((200, 23))
        self.text_DMM_report.SetMinSize((200, 23))
        self.canvas.SetMinSize((700, 490))
        self.panel_3.SetMinSize((310, 502))
        self.panel_5.SetMinSize((700, 502))
        self.checkbox_1.SetValue(1)
        self.combo_box_1.SetSelection(0)
        self.combo_filter.SetSelection(1)
        self.combo_box_3.SetSelection(0)

    def __do_layout(self):
        sizer_7 = wx.BoxSizer(wx.VERTICAL)
        sizer_8 = wx.BoxSizer(wx.VERTICAL)

        grid_sizer_1 = wx.GridBagSizer(0, 0)
        grid_sizer_2 = wx.GridBagSizer(0, 0)
        grid_sizer_3 = wx.GridBagSizer(0, 0)
        grid_sizer_4 = wx.GridBagSizer(0, 0)

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
        grid_sizer_2.Add(self.label_rms_report, (14, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

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
        grid_sizer_2.Add(self.btn_single, (20, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        grid_sizer_2.Add(self.combo_box_3, (20, 1), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

        self.panel_3.SetSizer(grid_sizer_2)
        grid_sizer_1.Add(self.panel_3, (0, 0), (1, 1), wx.EXPAND, 0)
        grid_sizer_1.Add(self.panel_5, (0, 1), (1, 1), wx.EXPAND, 0)
        self.panel_2.SetSizer(grid_sizer_1)
        grid_sizer_1.AddGrowableRow(0)
        grid_sizer_1.AddGrowableCol(1)
        grid_sizer_4.AddGrowableRow(0)
        grid_sizer_4.AddGrowableCol(0)
        sizer_8.Add(self.panel_2, 1, wx.ALL | wx.EXPAND, 10)
        self.panel_1.SetSizer(sizer_8)
        sizer_7.Add(self.panel_1, 1, wx.EXPAND, 0)
        self.SetSizer(sizer_7)
        self.Layout()

    # ------------------------------------------------------------------------------------------------------------------
    def connect(self, evt):
        print('\nResetting connection. Closing communication with any connected instruments')
        self.text_DUT_report.Clear()
        self.text_DMM_report.Clear()
        self.M.close_instruments()
        time.sleep(2)
        self.thread_this(self.M.connect, (self.get_instruments(),))

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
    def on_run(self, evt):
        selection = self.combo_box_3.GetSelection()
        if self.M.connected:
            params = self.get_values()
            # TODO: Why did I do this?
            if selection in (1, 3):
                self.run_selected_function(selection)
            elif not self.checkbox_1.GetValue() or (self.amplitude_good and self.frequency_good):
                self.run_selected_function(selection)
            else:
                self.error_dialog('\nCheck amplitude and frequency values.')
        else:
            self.error_dialog('\nFirst connect to instruments.')

    def run_selected_function(self, selection):
        if not self.t.is_alive() and self.flag_complete:
            # run single
            if selection == 0:
                print('Running single')
                self.thread_this(self.run_single, (self.test,))

            # run sweep
            elif selection == 1:
                print('Running sweep')
                df = pd.read_csv('distortion_breakpoints.csv')
                self.thread_this(self.run_sweep, (df, self.test,))

            # run single shunt voltage implied current measurement
            elif selection == 2:
                print('Running single measurement measuring current from shunt voltage')
                self.thread_this(self.run_single, (self.test_analyze_shunt_voltage,))

            # run swept shunt voltage implied current measurement
            elif selection == 3:
                print('Running sweep measuring current from shunt voltage')
                df = pd.read_csv('distortion_breakpoints.csv')
                self.thread_this(self.run_sweep, (df, self.test_analyze_shunt_voltage,))

            # run continuous
            elif selection == 4:
                self.btn_single.SetLabel('STOP')
                self.thread_this(self.run_continuous)

            else:
                print('Nothing happened.')

        # stop continuous
        elif self.t.is_alive() and selection == 4:
            # https://stackoverflow.com/a/36499538
            self.t.do_run = False
            self.btn_single.SetLabel('RUN')
        else:
            self.error_dialog('A thread is currently running and will not be interrupted.')

    def thread_this(self, func, arg=()):
        self.t = threading.Thread(target=func, args=arg, daemon=True)
        self.t.start()

    # ------------------------------------------------------------------------------------------------------------------
    def run_single(self, func):
        print('\nrun_single!')
        self.toggle_controls()
        self.flag_complete = False
        func(self.get_values(), setup=True)
        self.M.standby()
        self.toggle_controls()
        self.flag_complete = True

    def run_sweep(self, df, func):
        self.flag_complete = False

        headers = ['amplitude', 'frequency', 'yrms', 'THDN', 'THD', 'Fs', 'aperture']
        results = np.zeros(shape=(len(df.index), len(headers)))
        for idx, row in df.iterrows():
            self.text_amplitude.SetValue(str(row.amplitude))
            self.text_frequency.SetValue(str(row.frequency))
            results[idx] = func(self.get_values(), setup=True)
            self.M.standby()

        self.flag_complete = True
        # https://stackoverflow.com/a/28356566
        # https://stackoverflow.com/a/28058264
        results_df = pd.DataFrame(results, columns=headers)
        results_df.to_csv(path_or_buf=_getFilepath(), sep=',', index=False)

    def run_continuous(self):
        print('\nrun_continuous!')
        self.flag_complete = False
        t = threading.currentThread()
        setup = True
        while getattr(t, "do_run", True):
            params = self.get_values()
            self.test(params, setup)
            setup = False
            time.sleep(0.1)
        self.M.standby()
        print('Ending continuous run_source process.')
        self.flag_complete = True

    # ------------------------------------------------------------------------------------------------------------------
    def test(self, params, setup):
        # SOURCE
        amplitude = params['amplitude']
        rms = params['rms']
        if rms != 0:
            amplitude = amplitude / np.sqrt(2)
            print('Provided amplitude converted to RMS.')

        Ft = params['ft']
        mode = params['mode']
        time.sleep(1)

        # DIGITIZER
        N = params['samples']
        cycles = params['cycles']
        filter_val = params['filter']

        # SIGNAL SOURCE ================================================================================================
        if mode in ('A', 'a'):
            if amplitude <= 1.5:
                oper_range = 10 ** round(np.log10(amplitude))
            elif 1.5 <= amplitude <= 10:
                oper_range = 10
            else:
                oper_range = 30
        else:
            if amplitude <= 0.12:
                oper_range = 0.1
            elif amplitude <= 1.2:
                oper_range = 1
            elif amplitude <= 12:
                oper_range = 10
            elif amplitude <= 120:
                oper_range = 100
            else:
                oper_range = 1000

        # DIGITIZED SIGNAL =============================================================================================
        if filter_val == '100kHz':
            lpf = 100e3  # low pass filter cutoff frequency
        elif filter_val == '3MHz':
            lpf = 3e6  # low pass filter cutoff frequency
        else:
            lpf = 0

        aperture, Fs, runtime = get_aperture(Ft, N, cycles)
        self.label_fs_report.SetLabel(f'{round(Fs / 1000, 2)}kHz')
        self.label_rms_report.SetLabel(f'{round(aperture * 1e6, 4)}us')

        # START DATA COLLECTION ----------------------------------------------------------------------------------------
        # TODO
        # This is for internal debugging only. Not user facing.
        if not DUMMY:
            if setup:
                self.M.setup_digitizer(mode, oper_range, filter_val, N, aperture)
            if params['source']:
                self.M.run_source(mode, amplitude, Ft)
                y = self.M.retrieve_digitize()
            else:
                y = self.M.retrieve_digitize()
            pd.DataFrame(data=y, columns=['ydata']).to_csv('results/y_data.csv')
        else:
            y = pd.read_csv('results/y_data.csv')['ydata'].to_numpy()

        yrms = rms_flat(y)

        # FFT ==========================================================================================================
        x = np.arange(0.0, runtime, aperture + 200e-9)
        xf = np.linspace(0.0, Fs, N)
        ywf = windowed_fft(y, N, 'blackman')

        # Find %THD+N
        thdn, f0, yf = THDN(y, Fs, lpf)
        thd = THD(y, Fs)
        data = {'x': x, 'y': y, 'xf': xf, 'ywf': ywf, 'yrms': yrms, 'N': N, 'runtime': runtime, 'Fs': Fs, 'f0': f0}

        self.text_rms_report.SetValue(f'{round(yrms, 6)}{mode.capitalize()}')
        self.text_thdn_report.SetValue(f"{round(thdn * 100, 4)}% or {round(20 * np.log10(thdn), 1)}dB")
        self.text_thd_report.SetValue(f"{round(thd * 100, 4)}% or {round(20 * np.log10(thd), 1)}dB")
        self.plot(data)

        return [amplitude, Ft, yrms, thdn, thd, Fs, aperture]

    # ------------------------------------------------------------------------------------------------------------------
    def test_analyze_shunt_voltage(self, params, setup):
        # SOURCE
        amplitude = params['amplitude']
        rms = params['rms']
        if rms != 0:
            amplitude = amplitude / np.sqrt(2)
            print('Provided amplitude converted to RMS.')

        Ft = params['ft']
        mode = params['mode']
        self.M.run_source(mode, amplitude, Ft)
        time.sleep(1)

        # METER
        self.M.setup_meter('VOLT', 'AC')
        meter_outval, meter_range, meter_ft = self.M.read_meter('VOLT', 'AC')
        meter_mode = 'V'

        # DIGITIZER
        N = params['samples']
        cycles = params['cycles']
        filter_val = params['filter']

        # SIGNAL SOURCE ================================================================================================
        # CURRENT
        if meter_mode in ('A', 'a'):
            if meter_outval <= 1.5:
                meter_range = 10 ** round(np.log10(meter_outval))
            elif 1.5 <= meter_outval <= 10:
                meter_range = 10
            else:
                meter_range = 30
        # VOLTAGE
        else:
            if meter_range <= 0.1:
                meter_range = 0.1
            else:
                pass

        # DIGITIZED SIGNAL =============================================================================================
        if filter_val == '100kHz':
            lpf = 100e3  # low pass filter cutoff frequency
        elif filter_val == '3MHz':
            lpf = 3e6  # low pass filter cutoff frequency
        else:
            lpf = 0

        aperture, Fs, runtime = get_aperture(Ft, N, cycles)
        self.label_fs_report.SetLabel(f'{round(Fs / 1000, 2)}kHz')
        self.label_rms_report.SetLabel(f'{round(aperture * 1e6, 4)}us')

        # START DATA COLLECTION ----------------------------------------------------------------------------------------
        if setup:
            self.M.setup_digitizer(meter_mode, meter_range, filter_val, N, aperture)
        y = self.M.retrieve_digitize()

        pd.DataFrame(data=y, columns=['ydata']).to_csv('results/y_data.csv')

        yrms = rms_flat(y)

        # FFT ==========================================================================================================
        x = np.arange(0.0, runtime, aperture + 200e-9)
        # xf = np.linspace(0.0, Fs / 2, int(N / 2 + 1))
        xf = np.linspace(0.0, Fs, N)
        ywf = windowed_fft(y, N, 'blackman')

        # Find %THD+N
        thdn, f0, yf = THDN(y, Fs, lpf)
        thd = THD(y, Fs)
        data = {'x': x, 'y': y, 'xf': xf, 'ywf': ywf, 'yrms': yrms, 'N': N, 'runtime': runtime, 'Fs': Fs, 'f0': f0}

        self.text_rms_report.SetValue(f'{round(yrms, 6)}V')
        self.text_thdn_report.SetValue(f"{round(thdn * 100, 4)}% or {round(20 * np.log10(thdn), 1)}dB")
        self.text_thd_report.SetValue(f"{round(thd * 100, 4)}% or {round(20 * np.log10(thd), 1)}dB")
        self.plot(data)

        return [amplitude, Ft, yrms, thdn, thd, Fs, aperture]

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

    def plot(self, data):

        F0 = data['f0']

        # TEMPORAL -----------------------------------------------------------------------------------------------------
        x = data['x']
        y = data['y']
        runtime = data['runtime']

        self.temporal.set_data(x * 1e3, y)
        x_periods = 4
        x_max = min(x_periods / F0, runtime)
        ylimit = np.max(np.abs(y)) * 1.25
        increment = ylimit / 4
        self.ax1.set_yticks(np.arange(-ylimit, ylimit + increment, increment))
        self.ax1.relim()  # recompute the ax.dataLim
        self.ax1.autoscale()
        self.ax1.set_xlim([0, 1e3 * x_max])

        # SPECTRAL -----------------------------------------------------------------------------------------------------
        xf = data['xf']
        ywf = data['ywf']
        Fs = data['Fs']
        N = data['N']
        yrms = data['yrms']

        # divide by number of samples to keep the scaling.
        self.spectral.set_data(xf[0:N] / 1000, 20 * np.log10(2 * np.abs(ywf[0:N] / (yrms * N))))

        xf_max = min(10 ** (np.ceil(np.log10(F0)) + 1), Fs / 2 - Fs / N)  # Does not exceed max bin
        self.ax2.set_xlim(np.min(xf) / 1000, xf_max / 1000)
        self.ax2.set_ylim(-150, 0)

        # UPDATE PLOT FEATURES -----------------------------------------------------------------------------------------
        self.figure.tight_layout()

        self.toolbar.update()  # Not sure why this is needed - ADS
        self.canvas.draw()
        self.canvas.flush_events()

    # ------------------------------------------------------------------------------------------------------------------
    def lock_controls(self, evt):
        choice = self.combo_box_3.GetSelection()
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
        amp_string = self.text_amplitude.GetValue()
        freq_string = self.text_frequency.GetValue()
        amplitude, units, ft = self.get_string_value(amp_string, freq_string)

        return {'source': self.checkbox_1.GetValue(), 'amplitude': amplitude, 'mode': units.capitalize(),
                'rms': self.combo_box_1.GetSelection(), 'ft': ft, 'samples': int(self.text_samples.GetValue()),
                'cycles': float(self.text_cycles.GetValue()), 'filter': self.combo_filter.GetStringSelection()}

    def get_string_value(self, amp_string, freq_string):
        # https://stackoverflow.com/a/35610194
        amplitude = 0.0
        frequency = 0.0
        units = ''
        prefix = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3}
        units_list = ("A", "a", "V", "v")
        s_split = re.findall(r'[0-9.]+|\D', amp_string)

        # CHECK IF AMPLITUDE USER INPUT IS VALID
        try:
            if len(s_split) == 3 and s_split[1] in prefix.keys() and s_split[2] in units_list:
                amplitude = float(s_split[0]) * prefix[s_split[1]]
                units = s_split[2].capitalize()
                self.amplitude_good = True
            elif len(s_split) == 2 and s_split[1] in units_list:
                amplitude = float(s_split[0])
                units = s_split[1].capitalize()
                self.amplitude_good = True

            elif len(s_split) == 2 and s_split[1]:
                self.error_dialog('prefix used, but units not specified!')
                self.amplitude_good = False
            elif len(s_split) == 1:
                self.error_dialog('units not specified!')
                self.amplitude_good = False
            else:
                self.error_dialog('improper prefix used!')
                self.amplitude_good = False
        except ValueError:
            self.error_dialog('Invalid amplitude entered!')
            self.amplitude_good = False
            pass

        # CHECK IF FREQUENCY USER INPUT IS VALID
        try:
            frequency = float(freq_string)
        except ValueError:
            self.error_dialog(f"The value {self.text_frequency.GetValue()} is not a valid frequency!")
            self.frequency_good = False
        else:
            self.frequency_good = True

        return amplitude, units, frequency

    def error_dialog(self, error_message):
        print(error_message)
        dial = wx.MessageDialog(None, error_message, 'Error', wx.OK | wx.ICON_ERROR)
        dial.ShowModal()

    def OnCloseWindow(self, evt):
        if hasattr(self.M, 'DUT') and hasattr(self.M, 'DMM'):
            self.M.close_instruments()
        self.Destroy()


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
