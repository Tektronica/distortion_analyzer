from distortion_analyzer import DistortionAnalyzer as da
from gui_grid_enhanced import MyGrid
from gui_dialog_instruments import *
from instruments_RWConfig import *

import numpy as np
import threading

import wx

import matplotlib.pyplot as plt
import matplotlib.pylab as pylab
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavigationToolbar

# https://stackoverflow.com/a/38251497
# https://matplotlib.org/3.1.1/tutorials/introductory/customizing.html
pylab_params = {'legend.fontsize': 'medium',
                'font.family': 'Segoe UI',
                'axes.titleweight': 'bold',
                'figure.figsize': (15, 5),
                'axes.labelsize': 'medium',
                'axes.titlesize': 'medium',
                'xtick.labelsize': 'medium',
                'ytick.labelsize': 'medium'}
pylab.rcParams.update(pylab_params)


class DistortionAnalyzerTab(wx.Panel):
    def __init__(self, parent, frame):
        wx.Panel.__init__(self, parent, wx.ID_ANY)

        self.parent = parent
        self.frame = frame

        self.left_panel = wx.Panel(self, wx.ID_ANY)
        self.left_sub_panel = wx.Panel(self.left_panel, wx.ID_ANY)  # amplitude/frequency panel
        self.plot_panel = wx.Panel(self, wx.ID_ANY, style=wx.SIMPLE_BORDER)

        # PANELS =======================================================================================================
        # LEFT Panel ---------------------------------------------------------------------------------------------------
        self.text_DUT_report = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_DMM_report = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.btn_connect = wx.Button(self.left_panel, wx.ID_ANY, "Connect")
        self.btn_config = wx.Button(self.left_panel, wx.ID_ANY, "Config")

        self.checkbox_1 = wx.CheckBox(self.left_panel, wx.ID_ANY, "Control Source")
        self.text_amplitude = wx.TextCtrl(self.left_sub_panel, wx.ID_ANY, "10uA")
        self.combo_rms_or_peak = wx.ComboBox(self.left_sub_panel, wx.ID_ANY,
                                             choices=["RMS", "Peak"],
                                             style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.text_frequency = wx.TextCtrl(self.left_sub_panel, wx.ID_ANY, "1000")

        self.combo_mainlobe = wx.ComboBox(self.left_panel, wx.ID_ANY,
                                          choices=["Relative", "Absolute"],
                                          style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.combo_mainlobe.SetToolTip("Mainlobe width can be set relative to the signal frequency\n"
                                       "or as an absolute width independent of signal frequency")
        self.text_mainlobe = wx.TextCtrl(self.left_panel, wx.ID_ANY, "100")
        self.label_mainlobe = wx.StaticText(self.left_panel, wx.ID_ANY, "MLW (Hz)")

        self.combo_filter = wx.ComboBox(self.left_panel, wx.ID_ANY,
                                        choices=["None", "100kHz", "2MHz", "2.4MHz", "3MHz"],
                                        style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.combo_coupling = wx.ComboBox(self.left_panel, wx.ID_ANY,
                                          choices=["AC1M", "AC10M", "DC1M", "DC10M", "DCAuto"],
                                          style=wx.CB_DROPDOWN | wx.CB_READONLY)

        self.label_fs_report = wx.StaticText(self.left_panel, wx.ID_ANY, "--")
        self.label_samples_report = wx.StaticText(self.left_panel, wx.ID_ANY, "--")
        self.label_aperture_report = wx.StaticText(self.left_panel, wx.ID_ANY, "--")
        self.text_rms_report = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_thdn_report = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_thd_report = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)

        self.btn_start = wx.Button(self.left_panel, wx.ID_ANY, "RUN")
        self.combo_selected_test = wx.ComboBox(self.left_panel, wx.ID_ANY,
                                               choices=["Single", "Sweep",
                                                        "Single w/ shunt", "Sweep w/ shunt",
                                                        "Continuous"],
                                               style=wx.CB_DROPDOWN)

        # PLOT Panel ---------------------------------------------------------------------------------------------------
        self.figure = plt.figure(figsize=(1, 1))  # look into Figure((5, 4), 75)
        self.canvas = FigureCanvas(self.plot_panel, -1, self.figure)
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Realize()

        # instance variables -------------------------------------------------------------------------------------------
        self.flag_complete = True  # Flag indicates any active threads (False) or thread completed (True)
        self.t = threading.Thread()
        self.da = da(self)
        self.user_input = {}

        self.ax1 = self.figure.add_subplot(211)
        self.ax2 = self.figure.add_subplot(212)

        self.temporal, = self.ax1.plot([], [], linestyle='-')
        self.spectral, = self.ax2.plot([], [], color='#C02942')

        # BINDINGS =====================================================================================================
        # Configure Instruments ----------------------------------------------------------------------------------------
        on_connect = lambda event: self.on_connect_instr(event)
        self.Bind(wx.EVT_BUTTON, on_connect, self.btn_connect)

        on_config = lambda event: self.config(event)
        self.Bind(wx.EVT_BUTTON, on_config, self.btn_config)

        on_mainlobe = lambda event: self.on_mainlobe_change(event)
        self.Bind(wx.EVT_COMBOBOX_CLOSEUP, on_mainlobe, self.combo_mainlobe)

        # Run Measurement (start subprocess) ---------------------------------------------------------------------------
        on_run_event = lambda event: self.on_run(event)
        self.Bind(wx.EVT_BUTTON, on_run_event, self.btn_start)

        on_toggle = lambda event: self.toggle_panel(event)
        self.Bind(wx.EVT_CHECKBOX, on_toggle, self.checkbox_1)

        on_combo_select = lambda event: self.lock_controls(event)
        self.Bind(wx.EVT_COMBOBOX_CLOSEUP, on_combo_select, self.combo_selected_test)

        self.__set_properties()
        self.__do_layout()
        self.__do_plot_layout()

    def __set_properties(self):
        self.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.canvas.SetMinSize((700, 490))

        self.left_panel.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.plot_panel.SetBackgroundColour(wx.Colour(255, 255, 255))

        self.left_panel.SetMinSize((310, 502))
        # self.left_sub_panel.SetBackgroundColour(wx.Colour(255, 0, 255))
        self.plot_panel.SetMinSize((700, 502))

        self.text_DUT_report.SetMinSize((200, 23))
        self.text_DMM_report.SetMinSize((200, 23))
        self.canvas.SetMinSize((700, 490))

        self.checkbox_1.SetValue(1)
        self.combo_rms_or_peak.SetSelection(0)

        self.combo_mainlobe.SetSelection(1)
        self.combo_mainlobe.SetMinSize((96, 23))

        self.combo_filter.SetSelection(1)
        self.combo_filter.SetMinSize((110, 23))
        self.combo_coupling.SetSelection(0)
        self.combo_coupling.SetMinSize((110, 23))

        self.combo_selected_test.SetSelection(0)
        self.combo_selected_test.SetMinSize((110, 23))

    def __do_layout(self):
        sizer_2 = wx.GridSizer(1, 1, 0, 0)
        grid_sizer_1 = wx.FlexGridSizer(1, 2, 0, 0)

        grid_sizer_left_panel = wx.GridBagSizer(0, 0)
        grid_sizer_left_sub_panel = wx.GridBagSizer(0, 0)
        grid_sizer_plot = wx.GridBagSizer(0, 0)

        # LEFT PANEL ===================================================================================================
        # TITLE --------------------------------------------------------------------------------------------------------
        label_1 = wx.StaticText(self.left_panel, wx.ID_ANY, "DISTORTION ANALYZER")
        label_1.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_1, (0, 0), (1, 3), 0, 0)

        static_line_1 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_1.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_1, (1, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        # INSTRUMENT INFO  ---------------------------------------------------------------------------------------------
        label_DUT = wx.StaticText(self.left_panel, wx.ID_ANY, "Fluke 5560A")
        label_DUT.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_DUT, (2, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.text_DUT_report, (2, 1), (1, 2), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT, 5)

        label_DMM = wx.StaticText(self.left_panel, wx.ID_ANY, "Fluke 8588A")
        label_DMM.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_DMM, (3, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.text_DMM_report, (3, 1), (1, 2), wx.BOTTOM | wx.LEFT, 5)

        grid_sizer_left_panel.Add(self.btn_connect, (4, 0), (1, 1), wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.btn_config, (4, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        # f5560A SETUP -------------------------------------------------------------------------------------------------
        label_source = wx.StaticText(self.left_panel, wx.ID_ANY, "5560A")
        label_source.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_source, (5, 0), (1, 1), wx.TOP, 10)
        grid_sizer_left_panel.Add(self.checkbox_1, (5, 1), (1, 1), wx.ALIGN_BOTTOM | wx.LEFT | wx.TOP, 5)

        static_line_2 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_2.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_2, (6, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        # SUB PANEL  ---------------------------------------------------------------------------------------------------
        label_amplitude = wx.StaticText(self.left_sub_panel, wx.ID_ANY, "Amplitude:")
        label_amplitude.SetMinSize((93, 16))
        grid_sizer_left_sub_panel.Add(label_amplitude, (0, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_sub_panel.Add(self.text_amplitude, (0, 1), (1, 1),
                                      wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_left_sub_panel.Add(self.combo_rms_or_peak, (0, 2), (1, 1),
                                      wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT, 5)

        label_frequency = wx.StaticText(self.left_sub_panel, wx.ID_ANY, "Frequency (Ft):")
        label_frequency.SetMinSize((93, 16))
        grid_sizer_left_sub_panel.Add(label_frequency, (1, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_sub_panel.Add(self.text_frequency, (1, 1), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        label_Hz = wx.StaticText(self.left_sub_panel, wx.ID_ANY, "(Hz)")
        grid_sizer_left_sub_panel.Add(label_Hz, (1, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

        self.left_sub_panel.SetSizer(grid_sizer_left_sub_panel)
        grid_sizer_left_panel.Add(self.left_sub_panel, (7, 0), (1, 3), wx.LEFT, 0)

        # Measurement --------------------------------------------------------------------------------------------------
        label_measure = wx.StaticText(self.left_panel, wx.ID_ANY, "Measurement")
        label_measure.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_measure, (8, 0), (1, 3), wx.TOP, 10)

        static_line_3 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_3.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_3, (9, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        # label_error = wx.StaticText(self.left_panel, wx.ID_ANY, "Lobe Error:")
        # grid_sizer_left_panel.Add(label_error, (10, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.combo_mainlobe, (10, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.text_mainlobe, (10, 1), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_left_panel.Add(self.label_mainlobe, (10, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT, 5)

        label_filter = wx.StaticText(self.left_panel, wx.ID_ANY, "Filter:")
        grid_sizer_left_panel.Add(label_filter, (11, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.combo_filter, (11, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_coupling = wx.StaticText(self.left_panel, wx.ID_ANY, "Coupling:")
        grid_sizer_left_panel.Add(label_coupling, (12, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.combo_coupling, (12, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_fs = wx.StaticText(self.left_panel, wx.ID_ANY, "Fs:")
        grid_sizer_left_panel.Add(label_fs, (13, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.label_fs_report, (13, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_samples = wx.StaticText(self.left_panel, wx.ID_ANY, "Samples:")
        grid_sizer_left_panel.Add(label_samples, (14, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.label_samples_report, (14, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_aperture = wx.StaticText(self.left_panel, wx.ID_ANY, "Aperture:")
        grid_sizer_left_panel.Add(label_aperture, (15, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.label_aperture_report, (15, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        # REPORT -------------------------------------------------------------------------------------------------------
        static_line_4 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_4.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_4, (16, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        label_rms = wx.StaticText(self.left_panel, wx.ID_ANY, "RMS:")
        grid_sizer_left_panel.Add(label_rms, (17, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.text_rms_report, (17, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_thdn = wx.StaticText(self.left_panel, wx.ID_ANY, "THD+N:")
        grid_sizer_left_panel.Add(label_thdn, (18, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.text_thdn_report, (18, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_thd = wx.StaticText(self.left_panel, wx.ID_ANY, "THD:")
        grid_sizer_left_panel.Add(label_thd, (19, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.text_thd_report, (19, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        # BUTTONS ------------------------------------------------------------------------------------------------------
        static_line_9 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_9.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_9, (20, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        grid_sizer_left_panel.Add(self.btn_start, (21, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        grid_sizer_left_panel.Add(self.combo_selected_test, (21, 1), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

        self.left_panel.SetSizer(grid_sizer_left_panel)

        # PLOT PANEL ===================================================================================================
        grid_sizer_plot.Add(self.canvas, (0, 0), (1, 1), wx.ALL | wx.EXPAND)
        grid_sizer_plot.Add(self.toolbar, (1, 0), (1, 1), wx.ALL | wx.EXPAND)
        grid_sizer_plot.AddGrowableRow(0)
        grid_sizer_plot.AddGrowableCol(0)
        self.plot_panel.SetSizer(grid_sizer_plot)

        # add to main panel --------------------------------------------------------------------------------------------
        grid_sizer_1.Add(self.left_panel, 0, wx.EXPAND | wx.RIGHT, 0)
        grid_sizer_1.Add(self.plot_panel, 1, wx.EXPAND, 5)
        grid_sizer_1.AddGrowableRow(0)
        grid_sizer_1.AddGrowableCol(1)

        sizer_2.Add(grid_sizer_1, 0, wx.EXPAND, 0)

        self.SetSizer(sizer_2)
        self.Layout()

    # ------------------------------------------------------------------------------------------------------------------
    def config(self, evt):
        dlg = InstrumentDialog(self, ['f5560A', 'f8588A'], None, wx.ID_ANY, )
        dlg.ShowModal()
        dlg.Destroy()

    def get_instruments(self):
        config_dict = ReadConfig()

        f5560A = config_dict['f5560A']
        f8588A = config_dict['f8588A']

        instruments = {'f5560A': {'address': f5560A['address'], 'port': f5560A['port'],
                                  'gpib': f5560A['gpib'], 'mode': f5560A['mode']},
                       'f8588A': {'address': f8588A['address'], 'port': f8588A['port'],
                                  'gpib': f8588A['gpib'], 'mode': f8588A['mode']}}

        return instruments

    def set_ident(self, idn_dict):
        self.text_DUT_report.SetValue(idn_dict['DUT'])  # DUT
        self.text_DMM_report.SetValue(idn_dict['DMM'])  # current DMM

    def on_connect_instr(self, evt):
        print('\nResetting connection. Closing communication with any connected instruments')
        self.text_DUT_report.Clear()
        self.text_DMM_report.Clear()
        self.thread_this(self.da.connect, (self.get_instruments(),))

    # ------------------------------------------------------------------------------------------------------------------
    def toggle_panel(self, evt):
        if self.checkbox_1.GetValue():
            if not self.left_sub_panel.IsShown():
                self.left_sub_panel.Show()
        else:
            self.left_sub_panel.Hide()

    def lock_controls(self, evt):
        choice = self.combo_selected_test.GetSelection()
        if choice in (1, 3):
            if self.checkbox_1.GetValue() == 0:
                self.checkbox_1.SetValue(1)
                self.toggle_panel(evt)
            self.checkbox_1.Disable()
            self.text_amplitude.Disable()
            self.combo_rms_or_peak.Disable()
            self.text_frequency.Disable()
        else:
            self.checkbox_1.Enable()
            self.text_amplitude.Enable()
            self.combo_rms_or_peak.Enable()
            self.text_frequency.Enable()

    def toggle_controls(self):
        if self.text_amplitude.Enabled:
            self.checkbox_1.Disable()
            self.text_amplitude.Disable()
            self.combo_rms_or_peak.Disable()
            self.text_frequency.Disable()
        else:
            self.checkbox_1.Enable()
            self.text_amplitude.Enable()
            self.combo_rms_or_peak.Enable()
            self.text_frequency.Enable()

    def on_mainlobe_change(self, evt):
        value = self.combo_mainlobe.GetValue()
        if value == 'Relative':
            self.text_mainlobe.SetValue('0.1')
            self.label_mainlobe.SetLabelText('(MLW/f0)')
        else:
            self.text_mainlobe.SetValue('100')
            self.label_mainlobe.SetLabelText('MLW (Hz)')

    # ------------------------------------------------------------------------------------------------------------------
    def get_values(self):
        selected_test = self.combo_selected_test.GetSelection()
        source = self.checkbox_1.GetValue()
        mainlobe_type = self.combo_mainlobe.GetValue().lower()
        mainlobe_value = float(self.text_mainlobe.GetValue())
        rms = self.combo_rms_or_peak.GetSelection()

        coupling = self.combo_coupling.GetValue()
        filter = self.combo_filter.GetValue()

        amp_string = self.text_amplitude.GetValue()
        freq_string = self.text_frequency.GetValue()

        self.user_input = {'selected_test': selected_test,
                           'source': source,
                           'amplitude': amp_string,
                           'frequency': freq_string,
                           'rms': rms,
                           'coupling': coupling,
                           'mainlobe_type': mainlobe_type,
                           'mainlobe_value': mainlobe_value,
                           'filter': filter
                           }

    # ------------------------------------------------------------------------------------------------------------------
    def thread_this(self, func, arg=()):
        self.t = threading.Thread(target=func, args=arg, daemon=True)
        self.t.start()

    # ------------------------------------------------------------------------------------------------------------------
    def on_run(self, evt):
        self.get_values()
        if not self.t.is_alive() and self.flag_complete:
            # start new thread
            self.thread_this(self.da.start, (self.user_input,))
            self.btn_start.SetLabel('STOP')

        elif self.t.is_alive() and self.user_input['selected_test'] in (1, 4):
            # stop continuous
            # https://stackoverflow.com/a/36499538
            self.t.do_run = False
            self.btn_start.SetLabel('RUN')
        else:
            print('thread already running.')

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

    def update_plot(self, x, y, std):
        self.results_update([x, y, std])
        # TODO: np.NaN is always index 0. Should this be fixed?
        self.x = np.append(self.x, x)
        self.y = np.append(self.y, y)
        self.std = np.append(self.std, std)

        yerr = self.std / np.sqrt(self.x.size)

        self.plot(yerr)

    def plot(self, params):
        # TEMPORAL -----------------------------------------------------------------------------------------------------
        xt = params['xt']
        yt = params['yt']

        self.temporal.set_data(xt, yt)

        xt_left = params['xt_left']
        xt_right = params['xt_right']
        yt_btm = params['yt_btm']
        yt_top = params['yt_top']
        yt_tick = params['yt_tick']

        self.ax1.set_xlim(left=xt_left, right=xt_right)
        self.ax1.set_yticks(np.arange(yt_btm, yt_top, yt_tick))

        # SPECTRAL -----------------------------------------------------------------------------------------------------
        xf = params['xf']
        yf = params['yf']

        self.spectral.set_data(xf, yf)

        xf_left = params['xf_left']
        xf_right = params['xf_right']
        yf_btm = params['yf_btm']
        yf_top = params['yf_top']

        self.ax2.set_xlim(left=xf_left, right=xf_right)
        self.ax2.set_ylim(bottom=yf_btm, top=yf_top)

        # REDRAW PLOT --------------------------------------------------------------------------------------------------
        self.plot_redraw()

    def plot_redraw(self):
        try:
            self.ax1.relim()  # recompute the ax.dataLim
        except ValueError:
            xt_length = len(self.ax1.get_xdata())
            yt_length = len(self.ax1.get_ydata())
            print(f'Are the lengths of xt: {xt_length} and yt: {yt_length} mismatched?')
            raise
        self.ax1.margins(x=0)
        self.ax1.autoscale(axis='y')

        # UPDATE PLOT FEATURES -----------------------------------------------------------------------------------------
        self.figure.tight_layout()

        self.toolbar.update()  # Not sure why this is needed - ADS
        self.canvas.draw()
        self.canvas.flush_events()

    def results_update(self, results):
        amplitude = results['Amplitude']
        freq_ideal = results['freq_ideal']
        freq_fudged = results['freq_fudged']
        freq_actual = results['freq_actual']

        fs = results['Fs']
        N = results['N']
        aperture = results['Aperture']
        yrms = results['yrms']
        units = results['units']
        thdn = results['THDN']
        thd = results['THD']
        rms_noise = results['RMS NOISE']

        self.label_fs_report.SetLabelText(str(fs))
        self.label_samples_report.SetLabelText(str(N))
        self.label_aperture_report.SetLabelText(str(aperture))
        self.text_rms_report.SetValue(f"{'{:0.3e}'.format(yrms)} {units}")
        self.text_thdn_report.SetValue(f"{round(thdn * 100, 3)}% or {round(np.log10(thdn), 1)}dB")
        self.text_thd_report.SetValue(f"{round(thd * 100, 3)}% or {round(np.log10(thd), 1)}dB")

        row = [amplitude, freq_ideal, freq_fudged, freq_actual, yrms, thdn, thd, rms_noise, fs, N, aperture]
        self.frame.append_row(row)

    def error_dialog(self, error_message):
        print(error_message)
        dial = wx.MessageDialog(None, str(error_message), 'Error', wx.OK | wx.ICON_ERROR)
        dial.ShowModal()


# FOR RUNNING INDEPENDENTLY ============================================================================================
class MyDistortionAnalyzerFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.SetSize((1055, 1000))

        self.splitter = wx.SplitterWindow(self)
        self.panel = DistortionAnalyzerTab(self.splitter, self)
        self.spreadsheet = MyGrid(self.splitter)

        self.splitter.SplitHorizontally(window1=self.panel, window2=self.spreadsheet, sashPosition=0)

        self.__set_properties()
        self.__do_table_header()
        self.__do_layout()

    def __set_properties(self):
        self.SetTitle("Distortion Analyzer")
        self.panel.da.DUMMY_DATA = True
        self.panel.SetMinSize((1055, 525))
        self.spreadsheet.CreateGrid(100, 60)

    def __do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.splitter, 1, wx.EXPAND, 0)
        self.SetSizer(sizer)
        self.Layout()

    # ------------------------------------------------------------------------------------------------------------------
    def OnCloseWindow(self, evt):
        self.panel.da.close_instruments()
        self.Destroy()

    # ------------------------------------------------------------------------------------------------------------------
    def __do_table_header(self):
        header = ['Amplitude', 'Frequency', 'RMS', 'THDN', 'THD', 'uARMS Noise', 'Fs', 'Samples', 'Aperture']
        self.spreadsheet.append_rows(header)

    def append_row(self, row):
        self.spreadsheet.append_rows(row)


class MyApp(wx.App):
    def OnInit(self):
        self.frame = MyDistortionAnalyzerFrame(None, wx.ID_ANY, "")
        self.SetTopWindow(self.frame)
        self.frame.Show()
        return True


if __name__ == "__main__":
    app = MyApp(0)
    app.MainLoop()
