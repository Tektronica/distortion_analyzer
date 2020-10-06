import VisaClient
import numpy as np
from scipy.signal.windows import hann, blackman, blackmanharris
from scipy.fftpack import fft
import pandas as pd
import time
import re
import wx
import matplotlib.pyplot as plt
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavigationToolbar
import threading
import matplotlib.pylab as pylab
import datetime
import os
from pathlib import Path
import yaml

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


# https://www.sjsu.edu/people/burford.furman/docs/me120/FFT_tutorial_NI.pdf

# https://www.datatranslation.eu/frontend/products/pdf/DT9862S-UnderSampling.pdf
# https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.interp1d.html
# https://docs.scipy.org/doc/scipy/reference/tutorial/fft.html

# Calculate THDN
# https://gist.github.com/endolith/246092

# Frequency detectors:
# https://gist.github.com/endolith/255291
# https://ccrma.stanford.edu/~jos/sasp/Quadratic_Interpolation_Spectral_Peaks.html

# https://dartbrains.org/features/notebooks/6_Signal_Processing.html

# https://youtu.be/aQKX3mrDFoY
# https://github.com/markjay4k/Audio-Spectrum-Analyzer-in-Python/blob/master/audio%20spectrum_pt2_spectrum_analyzer.ipynb
# https://www.renesas.com/cn/en/www/doc/application-note/an9675.pdf

# RMS in frequency domain
# https://stackoverflow.com/questions/23341935/find-rms-value-in-frequency-domain

def ReadConfig():
    if os.path.exists("instrument_config.yaml"):
        with open("instrument_config.yaml", 'r') as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
    else:
        pass


def _getFilepath():
    Path('results').mkdir(parents=True, exist_ok=True)
    date = datetime.date.today().strftime("%Y%m%d")
    filename = f'distortion_{date}'
    index = 0

    while os.path.isfile('results/' + filename + "_" + str(index).zfill(2) + '.csv'):
        index += 1
    filename = filename + "_" + str(index).zfill(2)
    return f'results/{filename}.csv'


class Measurement:
    def __init__(self, parent):
        self.parent = parent
        self.measurement = []

    def connect(self, instruments):
        # ESTABLISH COMMUNICATION TO INSTRUMENTS -----------------------------------------------------------------------
        f5560A_id = instruments['DUT']
        f8588A_id = instruments['DMM']

        self.DUT = VisaClient.VisaClient(f5560A_id)  # Fluke 5560A
        self.DMM = VisaClient.VisaClient(f8588A_id)  # Fluke 8588A

        if self.DUT.okay and self.DMM.okay:
            idn_dict = {'UUT': self.DUT.query('*IDN?'), 'DMM': self.DMM.query('*IDN?')}
            self.parent.set_ident(idn_dict)
            self.setup_source()
        else:
            print('Connection failed. Check software configuration, ensure instruments are in appropriate mode, '
                  'and consider power cycling the suspected instrument\n')

    def setup_source(self):
        self.DUT.write('*RST')
        time.sleep(1)
        self.DUT.write('wizard elbereth; ponwiz on')
        self.DUT.write('MONITOR OFF')
        print(f"\nmonitor: {self.DUT.query('MONITOR?')}")

    def setup_digitizer(self, mode, oper_range, filter_val, N, aperture):
        # DMM has a 5MHz sampled rate clock. adjusting aperture time, averages more points, which adjusts sample rate
        self.DMM.write('*RST')
        if mode in ('A', 'a'):
            self.DMM.write(':FUNC "DIGitize:CURRent" ')
            self.DMM.write(f':DIGitize:CURRent:RANGe {oper_range}')
        else:
            self.DMM.write(':FUNC "DIGitize:VOLTage" ')
            self.DMM.write(f':DIGitize:VOLTage:RANGe {oper_range}')
        self.DMM.write(f':DIGitize:FILTer {filter_val}')
        self.DMM.write(f':DIGitize:APERture {aperture}')
        self.DMM.write('TRIGger:RESet')
        self.DMM.write(f'TRIGGER:COUNT {N}')
        self.DMM.write('TRIGger:DELay:AUTO OFF')
        self.DMM.write('TRIGGER:DELay 0')

    def run_source(self, current, Ft):
        self.DUT.write(f'\nout {current}A, {Ft}Hz')
        time.sleep(2)
        print(f'\nout: {current}A, {Ft}Hz')
        # self.DUT.write('write P7P7, #hDC')  # turn COMP3 ON (distortion amp)
        self.DUT.write('Mod P7P1SEL, #h40, 0')  # turn idac fly cap inverter off in AC
        time.sleep(1)
        # if current > 1:
        #     print('turning on comp2 (22nF)')
        #     self.DUT.write('write P7P7, #hEC')  # turn COMP2 ON (distortion amp)
        #     time.sleep(2)
        # else:
        #     print('turning on comp3 (22uF)')
        #     self.DUT.write('write P7P7, #hDC')  # turn COMP3 ON (distortion amp)
        #     time.sleep(2)

        self.DUT.write('oper')
        time.sleep(5)

    def retrieve_digitize(self):
        self.DMM.write('INIT:IMM')
        time.sleep(5)
        read = self.DMM.query('FETCH?')
        buffer = [float(i) for i in read.split(',')]
        return buffer

    def standby(self):
        time.sleep(1)
        self.DUT.write('STBY')
        self.DUT.write('*WAI')
        time.sleep(1)

    def close_instruments(self):
        time.sleep(1)
        self.DUT.close()
        self.DMM.close()


def rms_flat(a):
    """
    Return the root mean square of all the elements of *a*, flattened out.
    """
    return np.sqrt(np.mean(np.absolute(a) ** 2))


def find_range(f, x):
    """
    Find range between nearest local minima from peak at index x
    """
    lowermin = 0
    uppermin = 0
    for i in np.arange(x + 1, len(f)):
        if f[i + 1] >= f[i]:
            uppermin = i
            break
    for i in np.arange(x - 1, 0, -1):
        if f[i] <= f[i - 1]:
            lowermin = i + 1
            break
    return lowermin, uppermin


def THDN(y, fs, lpf):
    """
    Performs a windowed fft of a time-series signal y and calculate THDN.
        + Estimates fundamental frequency by finding peak value in fft
        + Skirts the fundamental by finding local minimas and throws those values away
        + Applies a Low-pass filter at fc (100kHz)
        + Calculates THD+N by calculating the rms ratio of the entire signal to the fundamental removed signal

    :returns: THD and fundamental frequency
    """
    # PERFORM FFT
    # TODO: Do this in the frequency domain, and take any skirts with it?
    y -= np.mean(y)
    w = blackman(len(y))  # TODO Kaiser?
    yf = np.fft.rfft(y * w)
    freqs = np.fft.rfftfreq(len(yf))
    yf_old = yf.copy()
    # FIND FUNDAMENTAL (peak of frequency spectrum)
    idx = np.argmax(np.abs(yf))
    freq = freqs[idx]  # no units
    f0 = freq * fs / 2  # in hertz

    # APPLY LOW PASS FILTERING
    if lpf != 0:
        fc = int(lpf * len(y) / fs)
        yf[fc:] = 1e-10

    total_rms = np.sqrt(np.sum(np.abs(yf / len(y)) ** 2))  # Parseval's Theorem

    # NOTCH REJECT FUNDAMENTAL AND MEASURE NOISE
    # Find local minimas around fundamental frequency and throw away values within boundaries of minima window.
    # TODO: create boundary w.r.thread_continuous. mainlobe width of the windowing function rather than finding local minimas
    lowermin, uppermin = find_range(abs(yf), idx)
    print(f'Boundary window: {lowermin * fs / len(y)} and {uppermin * fs / len(y)}')
    yf[lowermin:uppermin] = 1e-10
    noise_rms = np.sqrt(np.sum(np.abs(yf / len(y)) ** 2))  # Parseval's Theorem

    THDN = noise_rms / total_rms

    return THDN, f0, yf


def THD(y):
    # PERFORM FFT
    # TODO: Do this in the frequency domain, and take any skirts with it?
    # y -= np.mean(y)
    ypeak = np.max(y)
    w = blackman(len(y))  # TODO Kaiser?
    yf = np.fft.rfft(y * w)
    # FIND FUNDAMENTAL (peak of frequency spectrum)
    idx = np.argmax(np.abs(yf))
    if idx != 0:
        print(idx)
        # find harmonics up to the 9th harmonic
        n_harmonics = 9
        amplitude = np.zeros(n_harmonics)
        for h in range(n_harmonics):
            local = int(idx * (h + 1))
            amplitude[h] = np.max(np.abs(yf[local - 4:local + 4])) / ypeak
        thd = np.sqrt(np.sum(np.abs(amplitude[1:]) ** 2)) / np.abs(amplitude[0])
    else:
        print('Check the damn connection, you husk of an oat!')
        thd = 1  # bad input usually. Check connection.

    return thd


########################################################################################################################
class TestFrame(wx.Frame):
    """"""

    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, *args, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_FRAME_STYLE ^ wx.RESIZE_BORDER
        wx.Frame.__init__(self, *args, **kwds)
        self.SetSize((1041, 605))

        self.t = threading.Thread()
        self.flag_complete = True

        self.panel_1 = wx.Panel(self, wx.ID_ANY)
        self.panel_2 = wx.Panel(self.panel_1, wx.ID_ANY)
        self.panel_4 = wx.Panel(self.panel_2, wx.ID_ANY, style=wx.SIMPLE_BORDER)

        self.figure = plt.figure(figsize=(1, 1))  # look into Figure((5, 4), 75)
        self.canvas = FigureCanvas(self.panel_4, -1, self.figure)
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Realize()

        self.ax1 = self.figure.add_subplot(211)
        self.ax2 = self.figure.add_subplot(212)

        self.temporal, = self.ax1.plot([], [], linestyle='-')
        self.spectral, = self.ax2.plot([], [], color='red')

        self.text_ctrl_1 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_2 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.btn_connect = wx.Button(self.panel_2, wx.ID_ANY, "Connect")
        self.btn_config = wx.Button(self.panel_2, wx.ID_ANY, "Config")

        self.checkbox_1 = wx.CheckBox(self.panel_2, wx.ID_ANY, "Control Source")
        self.panel_3 = wx.Panel(self.panel_2, wx.ID_ANY)
        self.text_ctrl_3 = wx.TextCtrl(self.panel_3, wx.ID_ANY, "1.2A")
        self.combo_box_1 = wx.ComboBox(self.panel_3, wx.ID_ANY, choices=["RMS", "Peak"],
                                       style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.text_ctrl_4 = wx.TextCtrl(self.panel_3, wx.ID_ANY, "5000")
        self.text_ctrl_5 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "10000")
        self.text_ctrl_6 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "70")
        self.combo_box_2 = wx.ComboBox(self.panel_2, wx.ID_ANY, choices=["None", "100kHz", "3MHz"],
                                       style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.label_13 = wx.StaticText(self.panel_2, wx.ID_ANY, "--")
        self.label_14 = wx.StaticText(self.panel_2, wx.ID_ANY, "--")
        self.text_ctrl_7 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_8 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_9 = wx.TextCtrl(self.panel_2, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.btn_single = wx.Button(self.panel_2, wx.ID_ANY, "RUN")
        self.combo_box_3 = wx.ComboBox(self.panel_2, wx.ID_ANY, choices=["Single Run", "Sweep", "Continuous Run"],
                                       style=wx.CB_DROPDOWN)

        # Menu Bar
        self.frame_menubar = wx.MenuBar()
        wxglade_tmp_menu = wx.Menu()
        wxglade_tmp_menu.Append(wx.ID_ANY, "Export Data", "")
        self.frame_menubar.Append(wxglade_tmp_menu, "File")
        wxglade_tmp_menu = wx.Menu()
        wxglade_tmp_menu.Append(wx.ID_ANY, "configure instruments", "")
        self.frame_menubar.Append(wxglade_tmp_menu, "Instruments")
        self.SetMenuBar(self.frame_menubar)

        # Configure Instruments
        on_connect = lambda event: self.connect(event)
        self.Bind(wx.EVT_BUTTON, on_connect, self.btn_connect)

        on_config = lambda event: self.config(event)
        self.Bind(wx.EVT_BUTTON, on_config, self.btn_config)

        # Run Measurement (start subprocess)
        on_single_event = lambda event: self.on_run(event)
        self.Bind(wx.EVT_BUTTON, on_single_event, self.btn_single)

        on_toggle = lambda event: self.toggle_panel(event)
        self.Bind(wx.EVT_CHECKBOX, on_toggle, self.checkbox_1)

        on_combo_select = lambda event: self.lock_controls(event)
        self.Bind(wx.EVT_COMBOBOX_CLOSEUP, on_combo_select, self.combo_box_3)

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

        self.__set_properties()
        self.__do_layout()
        self.__do_plot_layout()
        self.M = Measurement(self)

    def __set_properties(self):
        self.SetTitle("Dual Output")
        self.text_ctrl_1.SetMinSize((200, 23))
        self.text_ctrl_2.SetMinSize((200, 23))
        self.canvas.SetMinSize((700, 490))
        self.panel_4.SetMinSize((700, 502))
        self.checkbox_1.SetValue(1)
        self.combo_box_1.SetSelection(0)
        self.combo_box_2.SetSelection(1)
        self.combo_box_3.SetSelection(0)

    def __do_layout(self):
        sizer_7 = wx.BoxSizer(wx.VERTICAL)
        sizer_8 = wx.BoxSizer(wx.VERTICAL)
        grid_sizer_1 = wx.GridBagSizer(0, 0)
        grid_sizer_2 = wx.GridBagSizer(0, 0)
        grid_sizer_3 = wx.GridBagSizer(0, 0)
        label_1 = wx.StaticText(self.panel_2, wx.ID_ANY, "DISTORTION ANALYZER")
        label_1.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_1, (0, 0), (1, 2), 0, 0)

        grid_sizer_3.Add(self.canvas, (0, 0), (1, 1), wx.ALL | wx.EXPAND)
        grid_sizer_3.Add(self.toolbar, (1, 0), (1, 1), wx.ALL | wx.EXPAND)

        self.panel_4.SetSizer(grid_sizer_3)
        grid_sizer_1.Add(self.panel_4, (0, 2), (21, 1), wx.EXPAND, 0)
        static_line_5 = wx.StaticLine(self.panel_2, wx.ID_ANY)
        static_line_5.SetMinSize((300, 2))
        grid_sizer_1.Add(static_line_5, (1, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)
        label_2 = wx.StaticText(self.panel_2, wx.ID_ANY, "UUT")
        label_2.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_2, (2, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_1.Add(self.text_ctrl_1, (2, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        label_3 = wx.StaticText(self.panel_2, wx.ID_ANY, "DMM (Digitizer)")
        label_3.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_3, (3, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_1.Add(self.text_ctrl_2, (3, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_1.Add(self.btn_connect, (4, 0), (1, 1), wx.BOTTOM, 5)
        grid_sizer_1.Add(self.btn_config, (4, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        label_4 = wx.StaticText(self.panel_2, wx.ID_ANY, "Source")
        label_4.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_4, (5, 0), (1, 1), wx.TOP, 10)
        grid_sizer_1.Add(self.checkbox_1, (5, 1), (1, 1), wx.ALIGN_BOTTOM | wx.LEFT | wx.TOP, 5)
        static_line_6 = wx.StaticLine(self.panel_2, wx.ID_ANY)
        static_line_6.SetMinSize((300, 2))
        grid_sizer_1.Add(static_line_6, (6, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)
        label_5 = wx.StaticText(self.panel_3, wx.ID_ANY, "Amplitude:")
        grid_sizer_2.Add(label_5, (0, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_2.Add(self.text_ctrl_3, (0, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_2.Add(self.combo_box_1, (0, 2), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        label_6 = wx.StaticText(self.panel_3, wx.ID_ANY, "Frequency (Ft):")
        label_6.SetMinSize((95, 16))
        grid_sizer_2.Add(label_6, (1, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_2.Add(self.text_ctrl_4, (1, 1), (1, 1), wx.LEFT, 5)
        label_7 = wx.StaticText(self.panel_3, wx.ID_ANY, "(Hz)")
        grid_sizer_2.Add(label_7, (1, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        self.panel_3.SetSizer(grid_sizer_2)
        grid_sizer_1.Add(self.panel_3, (7, 0), (1, 2), wx.EXPAND, 0)
        label_8 = wx.StaticText(self.panel_2, wx.ID_ANY, "Measure")
        label_8.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_8, (8, 0), (1, 2), wx.TOP, 10)
        static_line_7 = wx.StaticLine(self.panel_2, wx.ID_ANY)
        static_line_7.SetMinSize((300, 2))
        grid_sizer_1.Add(static_line_7, (9, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)
        label_9 = wx.StaticText(self.panel_2, wx.ID_ANY, "Samples (N):")
        grid_sizer_1.Add(label_9, (10, 0), (1, 1), 0, 0)
        grid_sizer_1.Add(self.text_ctrl_5, (10, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        label_10 = wx.StaticText(self.panel_2, wx.ID_ANY, "Cycles:")
        grid_sizer_1.Add(label_10, (11, 0), (1, 1), 0, 0)
        grid_sizer_1.Add(self.text_ctrl_6, (11, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        label_19 = wx.StaticText(self.panel_2, wx.ID_ANY, "Filter:")
        grid_sizer_1.Add(label_19, (12, 0), (1, 1), 0, 0)
        grid_sizer_1.Add(self.combo_box_2, (12, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        label_11 = wx.StaticText(self.panel_2, wx.ID_ANY, "Fs:")
        grid_sizer_1.Add(label_11, (13, 0), (1, 1), 0, 0)
        grid_sizer_1.Add(self.label_13, (13, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        label_12 = wx.StaticText(self.panel_2, wx.ID_ANY, "Aperture:")
        grid_sizer_1.Add(label_12, (14, 0), (1, 1), 0, 0)
        grid_sizer_1.Add(self.label_14, (14, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        static_line_8 = wx.StaticLine(self.panel_2, wx.ID_ANY)
        static_line_8.SetMinSize((300, 2))
        grid_sizer_1.Add(static_line_8, (15, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)
        label_15 = wx.StaticText(self.panel_2, wx.ID_ANY, "RMS:")
        grid_sizer_1.Add(label_15, (16, 0), (1, 1), 0, 0)
        grid_sizer_1.Add(self.text_ctrl_7, (16, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        label_16 = wx.StaticText(self.panel_2, wx.ID_ANY, "THD+N:")
        grid_sizer_1.Add(label_16, (17, 0), (1, 1), 0, 0)
        grid_sizer_1.Add(self.text_ctrl_8, (17, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        label_17 = wx.StaticText(self.panel_2, wx.ID_ANY, "THD:")
        grid_sizer_1.Add(label_17, (18, 0), (1, 1), 0, 0)
        grid_sizer_1.Add(self.text_ctrl_9, (18, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        static_line_9 = wx.StaticLine(self.panel_2, wx.ID_ANY)
        static_line_9.SetMinSize((300, 2))
        grid_sizer_1.Add(static_line_9, (19, 0), (1, 2), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)
        grid_sizer_1.Add(self.btn_single, (20, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        grid_sizer_1.Add(self.combo_box_3, (20, 1), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        self.panel_2.SetSizer(grid_sizer_1)
        sizer_8.Add(self.panel_2, 1, wx.ALL | wx.EXPAND, 10)
        self.panel_1.SetSizer(sizer_8)
        sizer_7.Add(self.panel_1, 1, wx.EXPAND, 0)
        self.SetSizer(sizer_7)
        self.Layout()

    # ------------------------------------------------------------------------------------------------------------------
    def connect(self, evt):
        if hasattr(self.M, 'DUT') and hasattr(self.M, 'DMM'):
            self.M.close_instruments()
            time.sleep(2)
        self.thread_this(self.M.connect, (self.get_instruments(), ))

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
        self.text_ctrl_1.SetValue(idn_dict['UUT'])  # UUT
        self.text_ctrl_2.SetValue(idn_dict['DMM'])  # current DMM

    # ------------------------------------------------------------------------------------------------------------------
    def on_run(self, evt):
        choice = self.combo_box_3.GetSelection()
        if not self.t.is_alive() and self.flag_complete:
            # run single
            if choice == 0:
                self.thread_this(self.run_single)
            # run sweep
            elif choice == 1:
                df = pd.read_csv('distortion_breakpoints.csv')
                self.thread_this(self.run_series, (df,))
            # run continuous
            else:
                self.btn_single.SetLabel('STOP')
                self.thread_this(self.run_continuous)
        # stop continuous
        elif self.t.is_alive():
            # https://stackoverflow.com/a/36499538
            self.t.do_run = False
            self.btn_single.SetLabel('RUN')
        else:
            print('A thread is currently running and will not be interrupted.')

    def thread_this(self, func, arg=()):
        self.t = threading.Thread(target=func, args=arg, daemon=True)
        self.t.start()

    # ------------------------------------------------------------------------------------------------------------------
    def run_single(self):
        print('\nrun_single!')
        self.flag_complete = False
        self.test(self.get_values(), setup=True)
        self.M.standby()
        self.flag_complete = True

    def run_continuous(self):
        print('\nrun_continuous!')
        self.flag_complete = False
        t = threading.currentThread()
        setup = True
        while getattr(t, "do_run", True):
            self.test(self.get_values(), setup)
            setup = False
            time.sleep(0.1)
        self.M.standby()
        print('Ending continuous run_source process.')
        self.flag_complete = True

    def run_series(self, df):
        self.flag_complete = False

        headers = ['amplitude', 'frequency', 'yrms', 'THDN', 'THD', 'Fs', 'aperture']
        results = np.zeros(shape=(len(df.index), len(headers)))

        for idx, row in df.iterrows():
            self.text_ctrl_3.SetValue(str(row.amplitude))
            self.text_ctrl_4.SetValue(str(row.frequency))
            results[idx] = self.test(self.get_values(), setup=True)
            self.M.standby()

        self.flag_complete = True
        # https://stackoverflow.com/a/28356566
        # https://stackoverflow.com/a/28058264
        results_df = pd.DataFrame(results, columns=headers)
        results_df.to_csv(path_or_buf=_getFilepath(), sep=',', index=False)

    # ------------------------------------------------------------------------------------------------------------------
    def test(self, params, setup):
        amplitude = params['amplitude']
        ft = params['ft']
        rms = params['rms']
        mode = params['mode']
        Ft = params['ft']
        N = params['samples']
        cycles = params['cycles']
        filter_val = params['filter']

        if rms != 0:
            amplitude = amplitude / np.sqrt(2)
            print('Provided amplitude converted to RMS.')

        # SIGNAL SOURCE ================================================================================================
        if mode in ('A', 'a'):
            if amplitude <= 1.5:
                oper_range = 10 ** round(np.log10(amplitude))
            elif 1.5 <= amplitude <= 10:
                oper_range = 10
            else:
                oper_range = 30
        else:
            oper_range = 10 ** round(np.log10(amplitude))
            if oper_range < 0.1:
                oper_range = 0.1

        # DIGITIZED SIGNAL =============================================================================================
        if filter_val == '100kHz':
            lpf = 100e3  # low pass filter cutoff frequency
        elif filter_val == '3MHz':
            lpf = 3e6  # low pass filter cutoff frequency
        else:
            lpf = 0

        Fs = 5e6 / (2 ** round(np.log2(5e6 / ((N * Ft) / cycles))))  # Hz
        aperture = 200e-9 * round(((1 / Fs) - 200e-9) / 200e-9)
        runtime = N * (aperture + 200e-9)

        '''
        The entire process for one reading is 200 ns, which gives a maximum trigger rate of 5 MHz. The aperture can be
        set from 0 ns to 3 ms in 200 ns increments up to 1 ms, and 100 μs increments from 1 ms to 3 ms. Aperture length
        increases sample rate. 
            Fs = 5MHz
            Ts = 200ns
            Aperture = 600ns --> 4 points averaged for each sample since:200ns + 3 * (200ns)
            Apparent sample time: 200ns + 600ns
            Apparent sample rate: 1/(800ns) = 1.25MHz

        Aperture is the time difference between the occurrence of the trigger and time when the tracking value is held.
          + with an Fs an apparent sample rate of 156.250 kHz, an aperture length of 6.2us averages 32 points per sample
          + with an Fs an apparent sample rate of 625.000 kHz, an aperture length of 1.4us averages 8 points per sample
          + with an Fs an apparent sample rate of 1.25 MHz, an aperture length of 600ns averages 4 points per sample
        '''

        # START DATA COLLECTION ----------------------------------------------------------------------------------------
        # TODO
        # This is for internal debugging only. Not user facing.
        if not DUMMY:
            if setup:
                self.M.setup_digitizer(mode, oper_range, filter_val, N, aperture)
            if params['source']:
                y = self.run_with_source(amplitude, Ft)
            else:
                y = self.run_without_source()
            pd.DataFrame(data=y, columns=['ydata']).to_csv('results/y_data.csv')
        else:
            y = self.dummy()

        yrms = rms_flat(y)

        # FFT ==========================================================================================================
        x = np.arange(0.0, runtime, aperture + 200e-9)
        xf = np.linspace(0.0, Fs, N)
        w = blackman(N)
        ywf = fft(y * w)

        # Find %THD+N
        thdn, f0, yf = THDN(y, Fs, lpf)
        thd = THD(y)
        data = {'x': x, 'y': y, 'xf': xf, 'ywf': ywf, 'yrms': yrms, 'N': N, 'runtime': runtime, 'Fs': Fs, 'f0': f0}

        self.label_13.SetLabel(f'{round(Fs / 1000, 2)}kHz')
        self.label_14.SetLabel(f'{round(aperture * 1e6, 4)}us')
        self.text_ctrl_7.SetValue(f'{round(yrms, 6)}A')
        self.text_ctrl_8.SetValue(f"{round(thdn * 100, 4)}% or {round(20 * np.log10(thdn), 1)}dB")
        self.text_ctrl_9.SetValue(f"{round(thd * 100, 4)}% or {round(20 * np.log10(thd), 1)}dB")
        self.plot(data)

        return [amplitude, ft, yrms, thdn, thd, Fs, aperture]

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
        x = data['x']
        y = data['y']
        xf = data['xf']
        ywf = data['ywf']
        f0 = data['f0']
        runtime = data['runtime']
        yrms = data['yrms']
        N = data['N']
        ylimit = np.max(np.abs(y)) * 1.25
        increment = ylimit / 4

        self.temporal.set_data(x * 1e3, y)
        # divide by number of samples to keep the scaling.
        self.spectral.set_data(xf[0:N] / 1000, 20 * np.log10(2 * np.abs(ywf[0:N] / (yrms * N))))

        self.ax1.set_xlim([0, 1e3 * runtime])
        self.ax1.set_yticks(np.arange(-ylimit, ylimit + increment, increment))
        self.ax2.set_xlim(100 / 1000, 10 ** (np.ceil(np.log10(f0)) + 1) / 1000)
        self.ax2.set_ylim(-150, 0)

        self.toolbar.update()  # Not sure why this is needed - ADS
        self.canvas.draw()
        self.canvas.flush_events()

    # ------------------------------------------------------------------------------------------------------------------
    def run_with_source(self, current, Ft):
        self.M.run_source(current, Ft)
        return self.M.retrieve_digitize()

    def run_without_source(self):
        return self.M.retrieve_digitize()

    def dummy(self):
        return pd.read_csv('results/y_data.csv')['ydata'].to_numpy()

    # ------------------------------------------------------------------------------------------------------------------
    def lock_controls(self, evt):
        choice = self.combo_box_3.GetSelection()
        if choice == 1:
            if self.checkbox_1.GetValue() == 0:
                self.checkbox_1.SetValue(1)
                self.toggle_panel(evt)
            self.checkbox_1.Disable()
            self.text_ctrl_3.Disable()
            self.combo_box_1.Disable()
            self.text_ctrl_4.Disable()
        else:
            self.checkbox_1.Enable()
            self.text_ctrl_3.Enable()
            self.combo_box_1.Enable()
            self.text_ctrl_4.Enable()

    # ------------------------------------------------------------------------------------------------------------------
    def toggle_panel(self, evt):
        if self.checkbox_1.GetValue():
            if not self.panel_3.IsShown():
                self.panel_3.Show()
        else:
            self.panel_3.Hide()

    # ------------------------------------------------------------------------------------------------------------------
    def get_values(self):
        amplitude, units = self.get_string_value(self.text_ctrl_3.GetValue())
        return {'source': self.checkbox_1.GetValue(), 'amplitude': amplitude, 'mode': units,
                'rms': self.combo_box_1.GetSelection(), 'ft': float(self.text_ctrl_4.GetValue()),
                'samples': int(self.text_ctrl_5.GetValue()), 'cycles': float(self.text_ctrl_6.GetValue()),
                'filter': self.combo_box_2.GetStringSelection()}

    # ------------------------------------------------------------------------------------------------------------------
    def get_string_value(self, s):
        # https://stackoverflow.com/a/35610194
        value = 0
        unit = None
        prefix = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3}
        s_split = re.findall(r'[0-9.]+|\D', s)
        try:
            if len(s_split) == 3 and s_split[1] in prefix.keys() and s_split[2] in ("A", "a", "V", "v"):
                value = float(s_split[0]) * prefix[s_split[1]]
                unit = s_split[2].capitalize()
            elif len(s_split) == 2 and s_split[1] in ("A", "a", "V", "v"):
                value = float(s_split[0])
                unit = s_split[1].capitalize()
            elif len(s_split) == 2 and s_split[1] in prefix.keys():
                print('units not specified!')
            else:
                print('improper prefix used!')
        except ValueError:
            pass

        return value, unit

    def OnCloseWindow(self, evt):
        if hasattr(self.M, 'DUT') and hasattr(self.M, 'DMM'):
            self.M.close_instruments()
        self.Destroy()


########################################################################################################################
class InstrumentDialog(wx.Dialog):
    """"""

    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, parent, *args, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_DIALOG_STYLE
        super(InstrumentDialog, self).__init__(parent, title='Configure Instruments')
        wx.Dialog.__init__(self, *args, **kwds)

        self.dut_mode = ''
        self.dut_address = ''
        self.dut_port = ''
        self.dut_gpib = ''

        self.dmm_mode = ''
        self.dmm_address = ''
        self.dmm_port = ''
        self.dmm_gpib = ''

        self.panel_5 = wx.Panel(self, wx.ID_ANY)
        self.dut_mode = wx.ComboBox(self.panel_5, wx.ID_ANY, choices=["SOCKET", "GPIB", "SERIAL"], style=wx.CB_DROPDOWN)
        self.dmm_mode = wx.ComboBox(self.panel_5, wx.ID_ANY, choices=["SOCKET", "GPIB", "SERIAL"], style=wx.CB_DROPDOWN)

        self.panel_6 = wx.Panel(self.panel_5, wx.ID_ANY)
        self.dut_address = wx.TextCtrl(self.panel_6, wx.ID_ANY, "")
        self.dut_port = wx.TextCtrl(self.panel_6, wx.ID_ANY, "3490")

        self.panel_7 = wx.Panel(self.panel_5, wx.ID_ANY)
        self.dmm_address = wx.TextCtrl(self.panel_7, wx.ID_ANY, "")
        self.dmm_port = wx.TextCtrl(self.panel_7, wx.ID_ANY, "3490")

        self.panel_8 = wx.Panel(self.panel_5, wx.ID_ANY)
        self.dut_gpib = wx.TextCtrl(self.panel_8, wx.ID_ANY, "")

        self.panel_9 = wx.Panel(self.panel_5, wx.ID_ANY)
        self.dmm_gpib = wx.TextCtrl(self.panel_9, wx.ID_ANY, "")

        self.btn_save = wx.Button(self.panel_5, wx.ID_ANY, "Save")
        self.btn_save.Bind(wx.EVT_BUTTON, self.on_save)

        on_combo_00 = lambda event: self.on_combo(event, self.dut_mode.GetValue(), 'DUT')
        self.Bind(wx.EVT_COMBOBOX_CLOSEUP, on_combo_00, self.dut_mode)
        on_combo_01 = lambda event: self.on_combo(event, self.dmm_mode.GetValue(), 'DMM')
        self.Bind(wx.EVT_COMBOBOX_CLOSEUP, on_combo_01, self.dmm_mode)

        self.__set_properties()
        self.__do_layout()

    # ------------------------------------------------------------------------------------------------------------------
    def __set_properties(self):
        self.SetTitle("Configure Instruments")
        self.dut_port.SetMinSize((50, 23))
        self.dut_gpib.SetMinSize((50, 23))
        self.panel_6.SetMinSize((176, 51))
        self.panel_8.SetMinSize((176, 51))
        self.dut_mode.SetSelection(0)

        self.dmm_port.SetMinSize((50, 23))
        self.dmm_gpib.SetMinSize((50, 23))
        self.panel_7.SetMinSize((176, 51))
        self.panel_9.SetMinSize((176, 51))
        self.dmm_mode.SetSelection(0)

    # ------------------------------------------------------------------------------------------------------------------
    def __do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        grid_sizer_4 = wx.GridBagSizer(0, 0)
        sizer_1 = wx.BoxSizer()
        sizer_2 = wx.BoxSizer()
        grid_sizer_5 = wx.GridBagSizer(0, 0)
        grid_sizer_6 = wx.GridBagSizer(0, 0)
        grid_sizer_7 = wx.GridBagSizer(0, 0)
        grid_sizer_8 = wx.GridBagSizer(0, 0)

        label_18 = wx.StaticText(self.panel_5, wx.ID_ANY, "INSTRUMENTS")
        label_18.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_4.Add(label_18, (0, 0), (1, 3), wx.BOTTOM, 10)

        static_line_1 = wx.StaticLine(self.panel_5, wx.ID_ANY)
        static_line_1.SetMinSize((292, 2))
        grid_sizer_4.Add(static_line_1, (1, 0), (1, 3), wx.BOTTOM | wx.TOP, 5)

        label_19 = wx.StaticText(self.panel_5, wx.ID_ANY, "DUT")
        label_19.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_4.Add(label_19, (2, 0), (1, 1), wx.BOTTOM, 5)
        label_21 = wx.StaticText(self.panel_6, wx.ID_ANY, "ADDRESS")
        grid_sizer_5.Add(label_21, (0, 0), (1, 2), wx.BOTTOM, 5)
        label_22 = wx.StaticText(self.panel_6, wx.ID_ANY, "PORT")
        grid_sizer_5.Add(label_22, (0, 2), (1, 1), wx.BOTTOM, 5)
        grid_sizer_5.Add(self.dut_address, (1, 0), (1, 1), 0, 0)
        label_23 = wx.StaticText(self.panel_6, wx.ID_ANY, ":")
        label_23.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_5.Add(label_23, (1, 1), (1, 1), wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_5.Add(self.dut_port, (1, 2), (1, 1), 0, 0)
        self.panel_6.SetSizer(grid_sizer_5)
        sizer_1.Add(self.panel_6, 1, wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)

        label_20 = wx.StaticText(self.panel_5, wx.ID_ANY, "DMM")
        label_20.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_4.Add(label_20, (3, 0), (1, 1), wx.BOTTOM, 5)
        label_24 = wx.StaticText(self.panel_7, wx.ID_ANY, "ADDRESS")
        grid_sizer_6.Add(label_24, (0, 0), (1, 2), wx.BOTTOM, 5)
        label_25 = wx.StaticText(self.panel_7, wx.ID_ANY, "PORT")
        grid_sizer_6.Add(label_25, (0, 2), (1, 1), wx.BOTTOM, 5)
        grid_sizer_6.Add(self.dmm_address, (1, 0), (1, 1), 0, 0)
        label_26 = wx.StaticText(self.panel_7, wx.ID_ANY, ":")
        label_26.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_6.Add(label_26, (1, 1), (1, 1), wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_6.Add(self.dmm_port, (1, 2), (1, 1), 0, 0)
        self.panel_7.SetSizer(grid_sizer_6)
        sizer_2.Add(self.panel_7, 1, wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)

        label_27 = wx.StaticText(self.panel_8, wx.ID_ANY, "GPIB ADDRESS")
        grid_sizer_7.Add(label_27, (0, 0), (1, 2), wx.BOTTOM, 5)
        grid_sizer_7.Add(self.dut_gpib, (1, 0), (1, 1), 0, 0)
        self.panel_8.SetSizer(grid_sizer_7)
        self.panel_8.Hide()
        sizer_1.Add(self.panel_8, 1, wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)

        label_28 = wx.StaticText(self.panel_9, wx.ID_ANY, "GPIB ADDRESS")
        grid_sizer_8.Add(label_28, (0, 0), (1, 2), wx.BOTTOM, 5)
        grid_sizer_8.Add(self.dmm_gpib, (1, 0), (1, 1), 0, 0)
        self.panel_9.SetSizer(grid_sizer_8)
        self.panel_9.Hide()
        sizer_2.Add(self.panel_9, 1, wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)

        grid_sizer_4.Add(sizer_1, (2, 1), (1, 1), wx.ALIGN_BOTTOM | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_4.Add(sizer_2, (3, 1), (1, 1), wx.ALIGN_BOTTOM | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)

        grid_sizer_4.Add(self.dut_mode, (2, 2), (1, 1), wx.ALIGN_BOTTOM | wx.BOTTOM, 17)
        grid_sizer_4.Add(self.dmm_mode, (3, 2), (1, 1), wx.ALIGN_BOTTOM | wx.BOTTOM, 17)

        static_line_2 = wx.StaticLine(self.panel_5, wx.ID_ANY)
        static_line_2.SetMinSize((292, 2))
        grid_sizer_4.Add(static_line_2, (4, 0), (1, 3), wx.BOTTOM | wx.TOP, 5)

        grid_sizer_4.Add(self.btn_save, (5, 0), (1, 3), wx.ALIGN_RIGHT, 0)
        self.panel_5.SetSizer(grid_sizer_4)
        sizer.Add(self.panel_5, 1, wx.ALL | wx.EXPAND, 10)

        self.SetSizer(sizer)
        sizer.Fit(self)

        self.LoadConfig()

    # ------------------------------------------------------------------------------------------------------------------
    def LoadConfig(self):
        config_dict = ReadConfig()
        # load config file into settings if available
        if isinstance(config_dict, dict):
            config = config_dict

            self.dut_mode.SetValue(config['DUT']['mode'])
            self.dut_address.SetValue(config['DUT']['address'])
            self.dut_port.SetValue(config['DUT']['port'])
            self.dut_gpib.SetValue(config['DUT']['gpib'])

            self.dmm_mode.SetValue(config['DMM']['mode'])
            self.dmm_address.SetValue(config['DMM']['address'])
            self.dmm_port.SetValue(config['DMM']['port'])
            self.dmm_gpib.SetValue(config['DMM']['gpib'])

            self.toggle_panel(config['DUT']['mode'], self.panel_6, self.panel_8)
            self.toggle_panel(config['DMM']['mode'], self.panel_7, self.panel_9)
        else:
            print('no config')

    # ------------------------------------------------------------------------------------------------------------------
    def on_combo(self, evt, mode, instr):
        if instr == 'DUT':
            self.toggle_panel(mode, self.panel_6, self.panel_8)
        else:
            self.toggle_panel(mode, self.panel_7, self.panel_9)

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
        config = {'DUT': {'mode': self.dut_mode.GetStringSelection(),
                          'address': self.dut_address.GetValue(),
                          'port': self.dut_port.GetValue(),
                          'gpib': self.dut_gpib.GetValue()},
                  'DMM': {'mode': self.dmm_mode.GetStringSelection(),
                          'address': self.dmm_address.GetValue(),
                          'port': self.dmm_port.GetValue(),
                          'gpib': self.dmm_gpib.GetValue()}}

        with open('instrument_config.yaml', 'w') as f:
            yaml.dump(config, f, sort_keys=False)

        if self.IsModal():
            self.EndModal(wx.ID_OK)
            evt.Skip()
        else:
            self.Close()


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
