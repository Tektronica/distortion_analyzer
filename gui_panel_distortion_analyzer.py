from distortion_analyzer import DistortionAnalyzer as da
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

        self.text_error = wx.TextCtrl(self.left_panel, wx.ID_ANY, "0.1")
        self.combo_filter = wx.ComboBox(self.left_panel, wx.ID_ANY,
                                        choices=["None", "100kHz", "3MHz"],
                                        style=wx.CB_DROPDOWN | wx.CB_READONLY)

        self.label_fs_report = wx.StaticText(self.left_panel, wx.ID_ANY, "--")
        self.label_samples_report = wx.StaticText(self.left_panel, wx.ID_ANY, "--")
        self.label_aperture_report = wx.StaticText(self.left_panel, wx.ID_ANY, "--")
        self.text_rms_report = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_thdn_report = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_thd_report = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)

        self.btn_start = wx.Button(self.left_panel, wx.ID_ANY, "RUN")
        self.combo_mode = wx.ComboBox(self.left_panel, wx.ID_ANY,
                                      choices=["Single", "Sweep",
                                               "Single w/ shunt", "Sweep w/ shunt",
                                               "Continuous"],
                                      style=wx.CB_DROPDOWN)

        # PANELS =======================================================================================================
        # PLOT Panel ---------------------------------------------------------------------------------------------------
        self.figure = plt.figure(figsize=(1, 1))  # look into Figure((5, 4), 75)
        self.canvas = FigureCanvas(self.plot_panel, -1, self.figure)
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Realize()

        # instance variables -------------------------------------------------------------------------------------------
        self.flag_complete = True  # Flag indicates any active threads (False) or thread completed (True)
        self.t = threading.Thread()
        self.da = da(self)
        self.user_input = {'mode': 0,
                           'source': 0,
                           'amplitude': '',
                           'rms': 0,
                           'frequency': '',
                           'error': 0,
                           'filter': 0
                           }
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

        # Run Measurement (start subprocess) ---------------------------------------------------------------------------
        on_single_event = lambda event: self.on_run(event)
        self.Bind(wx.EVT_BUTTON, on_single_event, self.btn_start)

        on_toggle = lambda event: self.toggle_panel(event)
        self.Bind(wx.EVT_CHECKBOX, on_toggle, self.checkbox_1)

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

        self.left_panel.SetMinSize((310, 502))
        # self.left_sub_panel.SetBackgroundColour(wx.Colour(255, 0, 255))
        self.plot_panel.SetMinSize((700, 502))

        self.text_DUT_report.SetMinSize((200, 23))
        self.text_DMM_report.SetMinSize((200, 23))
        self.canvas.SetMinSize((700, 490))

        self.checkbox_1.SetValue(1)
        self.combo_rms_or_peak.SetSelection(0)
        self.combo_filter.SetSelection(1)
        self.combo_mode.SetSelection(0)
        self.combo_mode.SetMinSize((110, 23))

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
        grid_sizer_left_panel.Add(label_1, (0, 0), (1, 2), 0, 0)

        static_line_1 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_1.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_1, (1, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        # INSTRUMENT INFO  ---------------------------------------------------------------------------------------------
        label_DUT = wx.StaticText(self.left_panel, wx.ID_ANY, "DUT")
        label_DUT.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_DUT, (2, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.text_DUT_report, (2, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_DMM = wx.StaticText(self.left_panel, wx.ID_ANY, "DMM (f8588A)")
        label_DMM.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_DMM, (3, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.text_DMM_report, (3, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        grid_sizer_left_panel.Add(self.btn_connect, (4, 0), (1, 1), wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.btn_config, (4, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_source = wx.StaticText(self.left_panel, wx.ID_ANY, "5560A")
        label_source.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_source, (5, 0), (1, 1), wx.TOP, 10)
        grid_sizer_left_panel.Add(self.checkbox_1, (5, 1), (1, 1), wx.ALIGN_BOTTOM | wx.LEFT | wx.TOP, 5)

        static_line_2 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_2.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_2, (6, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        # SUB PANEL  ---------------------------------------------------------------------------------------------------
        label_amplitude = wx.StaticText(self.left_sub_panel, wx.ID_ANY, "Amplitude:")
        label_amplitude.SetMinSize((93, 16))
        grid_sizer_left_sub_panel.Add(label_amplitude, (0, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_sub_panel.Add(self.text_amplitude, (0, 1), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_left_sub_panel.Add(self.combo_rms_or_peak, (0, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT, 5)

        label_frequency = wx.StaticText(self.left_sub_panel, wx.ID_ANY, "Frequency (Ft):")
        label_frequency.SetMinSize((93, 16))
        grid_sizer_left_sub_panel.Add(label_frequency, (1, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_sub_panel.Add(self.text_frequency, (1, 1), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        label_Hz = wx.StaticText(self.left_sub_panel, wx.ID_ANY, "(Hz)")
        grid_sizer_left_sub_panel.Add(label_Hz, (1, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

        self.left_sub_panel.SetSizer(grid_sizer_left_sub_panel)
        grid_sizer_left_panel.Add(self.left_sub_panel, (7, 0), (1, 2), wx.LEFT, 0)

        # Measurement --------------------------------------------------------------------------------------------------
        label_measure = wx.StaticText(self.left_panel, wx.ID_ANY, "Measurement")
        label_measure.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_measure, (8, 0), (1, 3), wx.TOP, 10)

        static_line_3 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_3.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_3, (9, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        label_error = wx.StaticText(self.left_panel, wx.ID_ANY, "Error:")
        grid_sizer_left_panel.Add(label_error, (10, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.text_error, (10, 1), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT, 5)

        label_filter = wx.StaticText(self.left_panel, wx.ID_ANY, "Filter:")
        grid_sizer_left_panel.Add(label_filter, (11, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.combo_filter, (11, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_fs = wx.StaticText(self.left_panel, wx.ID_ANY, "Fs:")
        grid_sizer_left_panel.Add(label_fs, (12, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.label_fs_report, (12, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_samples = wx.StaticText(self.left_panel, wx.ID_ANY, "Samples:")
        grid_sizer_left_panel.Add(label_samples, (13, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.label_samples_report, (13, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_aperture = wx.StaticText(self.left_panel, wx.ID_ANY, "Aperture:")
        grid_sizer_left_panel.Add(label_aperture, (14, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.label_aperture_report, (14, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        # REPORT -------------------------------------------------------------------------------------------------------
        static_line_4 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_4.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_4, (15, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        label_rms = wx.StaticText(self.left_panel, wx.ID_ANY, "RMS:")
        grid_sizer_left_panel.Add(label_rms, (16, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.text_rms_report, (16, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_thdn = wx.StaticText(self.left_panel, wx.ID_ANY, "THD+N:")
        grid_sizer_left_panel.Add(label_thdn, (17, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.text_thdn_report, (17, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        label_thd = wx.StaticText(self.left_panel, wx.ID_ANY, "THD:")
        grid_sizer_left_panel.Add(label_thd, (18, 0), (1, 1), 0, 0)
        grid_sizer_left_panel.Add(self.text_thd_report, (18, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        # BUTTONS ------------------------------------------------------------------------------------------------------
        static_line_9 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_9.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_9, (19, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        grid_sizer_left_panel.Add(self.btn_start, (20, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        grid_sizer_left_panel.Add(self.combo_mode, (20, 1), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

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
        choice = self.combo_mode.GetSelection()
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

    # ------------------------------------------------------------------------------------------------------------------
    def get_values(self):
        mode = self.combo_mode.GetSelection()
        source = self.checkbox_1.GetValue()
        error = float(self.text_error.GetValue())
        rms = self.combo_rms_or_peak.GetSelection()

        filter = self.combo_filter.GetValue()

        amp_string = self.text_amplitude.GetValue()
        freq_string = self.text_frequency.GetValue()

        self.user_input = {'mode': mode,
                           'source': source,
                           'amplitude': amp_string,
                           'rms': rms,
                           'frequency': freq_string,
                           'error': error,
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

        elif self.t.is_alive() and self.user_input['mode'] in (1, 4):
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

        xt_start = params['xt_start']
        xt_end = params['xt_end']
        yt_start = params['yt_start']
        yt_end = params['yt_end']
        yt_tick = params['yt_tick']

        self.ax1.set_xlim([xt_start, xt_end])
        self.ax1.set_yticks(np.arange(yt_start, yt_end, yt_tick))

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
        self.ax1.autoscale()

        # UPDATE PLOT FEATURES -----------------------------------------------------------------------------------------
        self.figure.tight_layout()

        self.toolbar.update()  # Not sure why this is needed - ADS
        self.canvas.draw()
        self.canvas.flush_events()

    def results_update(self, results):
        amplitude = results['Amplitude']
        frequency = results['Frequency']

        fs = results['Fs']
        N = results['N']
        aperture = results['Aperture']
        rms = results['RMS']
        units = results['units']
        thdn = results['THDN']
        thd = results['THD']
        rms_noise = results['RMS NOISE']

        self.label_fs_report.SetLabelText(str(fs))
        self.label_samples_report.SetLabelText(str(N))
        self.label_aperture_report.SetLabelText(str(aperture))
        self.text_rms_report.SetValue(f"{'{:0.3e}'.format(rms)} {units}")
        self.text_thdn_report.SetValue(f"{round(thdn * 100, 3)}% or {round(np.log10(thdn), 1)}dB")
        self.text_thd_report.SetValue(f"{round(thd * 100, 3)}% or {round(np.log10(thd), 1)}dB")

        row = [amplitude, frequency, rms, thdn, thd, rms_noise, fs, N, aperture]
        self.frame.append_row(row)

    def error_dialog(self, error_message):
        print(error_message)
        dial = wx.MessageDialog(None, str(error_message), 'Error', wx.OK | wx.ICON_ERROR)
        dial.ShowModal()
