import numpy as np
import math

import wx

import matplotlib.pyplot as plt
import matplotlib.pylab as pylab
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavigationToolbar

CONTAINS_HARMONICS = True
CONTAINS_NOISE = False
GUI = True


def to_float(string_val):
    try:
        float_val = float(string_val)
    except ValueError:
        print('[ERROR] Measurement could not be converted to float. Possible issues with configuration.')
        raise ValueError('Prospective measurement obtained by the Fluke 8588A could not be converted to float. Suspect '
                         'null value or over-range')
    else:
        return float_val


def getWindowLength(f0=10e3, fs=2.5e6, windfunc='blackman', error=0.1, mainlobe_type='relative'):
    """
    Computes the window length of the measurement. An error is expressed since the main lobe width is directly
    proportional to the number of cycles captured. The minimum value of M correlates to the lowest detectable frequency
    by the windowing function. For instance, blackman requires a minimum of 6 period cycles of the frequency of interest
    in order to express content of that lobe in the DFT. Sampling frequency does not play a role in the width of the
    lobe, only the resolution of the lobe.

    :param mainlobe_type: Mainlobe width can be set relative to the signal frequency or as an absolute width
    independent of signal frequency

    :param f0: fundamental frequency of signal
    :param fs: sampling frequency
    :param windfunc: "Rectangular", "Bartlett", "Hanning", "Hamming", "Blackman"
    :param error: 100% error suggests the lowest detectable frequency is the fundamental
    :return: window length of integer value (number of time series
    samples collected)
    """
    # lowest detectable frequency by window
    # aka - the main lobe width
    if mainlobe_type == 'relative':
        ldf = f0 * error
    elif mainlobe_type == 'absolute':
        ldf = error
    else:
        raise ValueError('Incorrect main lobe type used!\nSelection should either be relative or absolute.')

    if windfunc == 'rectangular':
        M = int(2 * (fs / ldf))
    elif windfunc in ('bartlett', 'hanning', 'hamming'):
        M = int(4 * (fs / ldf))
    elif windfunc == 'blackman':
        M = int(6 * (fs / ldf))
    else:
        raise ValueError('Not a valid windowing function.')

    return M


def ADC(ypeak, f0, Fs, N, has_harmonics=True, has_noise=True):
    # TEMPORAL ---------------------------------------------------------------------------------------------------------
    xt = np.arange(0, N, 1) / Fs
    yt = ypeak * np.sin(2 * np.pi * f0 * xt)

    if has_harmonics:
        yt = yt + 1e-3 * ypeak * np.sin(2 * np.pi * 3 * f0 * xt) + 1e-4 * ypeak * np.sin(2 * np.pi * 5 * f0 * xt)

    if has_noise:
        yt = yt + 1e-4 * ypeak * np.random.normal(0, 1, N)

    return xt, yt


def true_signal(ypeak, N, has_harmonics=True, has_noise=True):
    signal_sum = (ypeak / np.sqrt(2))**2

    if has_harmonics:
        signal_sum += ((1e-3 * ypeak) / np.sqrt(2))**2
        signal_sum += ((1e-4 * ypeak) / np.sqrt(2))**2

    if has_noise:
        # currently researching how to determine an accurate rms value for gaussian distributed noise
        signal_sum += ((1e-4 * ypeak) / np.sqrt(2))**2

    rms_true = np.sqrt(signal_sum)

    return rms_true


def rms_flat(a):
    """
    Return the root mean square of all the elements of *a*, flattened out.
    """
    # https://stackoverflow.com/a/17463210
    # https://code.activestate.com/recipes/393090/
    # https://stackoverflow.com/a/33004170
    sqr = np.absolute(a) ** 2
    mean = math.fsum(sqr) / len(sqr)  # computed from partial sums
    return np.sqrt(mean)


class MyDemoPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY)

        self.frame = parent
        self.left_panel = wx.Panel(self, wx.ID_ANY)
        self.plot_panel = wx.Panel(self, wx.ID_ANY, style=wx.SIMPLE_BORDER)

        # PLOT Panel ---------------------------------------------------------------------------------------------------
        self.figure = plt.figure(figsize=(1, 1))  # look into Figure((5, 4), 75)
        self.canvas = FigureCanvas(self.plot_panel, -1, self.figure)
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Realize()

        self.ax1 = self.figure.add_subplot(211)
        self.ax2 = self.figure.add_subplot(212)

        self.temporal, = self.ax1.plot([], [], linestyle='-', linewidth=5, alpha=0.3)
        self.temporal_sampled, = self.ax1.plot([], [], linestyle='-', marker='x')
        self.spectral, = self.ax2.plot([], [], color='#C02942')
        self.x, self.y = [], []

        self.text_ctrl_fs = wx.TextCtrl(self.left_panel, wx.ID_ANY, style=wx.TE_PROCESS_ENTER)
        self.text_ctrl_ldf = wx.TextCtrl(self.left_panel, wx.ID_ANY, style=wx.TE_PROCESS_ENTER)
        self.text_ctrl_ldf.SetToolTip("Lowest Recoverable Frequency")

        self.text_ctrl_samples = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_rms_true = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_rms_sampled = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_rms_delta = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)

        self.text_ctrl_cycles = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_samples_per_cycle = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_aliased_freq01 = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_aliased_freq02 = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_ctrl_aliased_freq03 = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)

        on_update = lambda event: self.update(event)
        self.Bind(wx.EVT_TEXT_ENTER, on_update, self.text_ctrl_fs)
        self.Bind(wx.EVT_TEXT_ENTER, on_update, self.text_ctrl_ldf)

        self.__set_properties()
        self.__do_layout()
        self.__do_plot_layout()
        self.update(wx.Event)

    def __set_properties(self):
        self.SetBackgroundColour(wx.Colour(240, 240, 240))
        self.canvas.SetMinSize((700, 490))

        self.text_ctrl_fs.SetValue('12')
        self.text_ctrl_ldf.SetValue('100')

        # width = 200
        # self.text_ctrl_fs.SetMaxSize((width, 23))
        # self.text_ctrl_ldf.SetMaxSize((width, 23))
        #
        # self.text_ctrl_samples.SetMaxSize((width, 23))
        # self.text_ctrl_rms_true.SetMaxSize((width, 23))
        # self.text_ctrl_rms_sampled.SetMaxSize((width, 23))
        # self.text_ctrl_rms_delta.SetMaxSize((width, 23))
        #
        # self.text_ctrl_cycles.SetMaxSize((width, 23))
        # self.text_ctrl_samples_per_cycle.SetMaxSize((width, 23))
        # self.text_ctrl_aliased_freq01.SetMaxSize((width, 23))
        # self.text_ctrl_aliased_freq02.SetMaxSize((width, 23))
        # self.text_ctrl_aliased_freq03.SetMaxSize((width, 23))

    def __do_layout(self):
        sizer_2 = wx.GridSizer(1, 1, 0, 0)
        grid_sizer_1 = wx.FlexGridSizer(1, 2, 0, 0)
        grid_sizer_plot = wx.GridBagSizer(0, 0)
        grid_sizer_left_panel = wx.GridBagSizer(0, 0)

        # LEFT PANEL ---------------------------------------------------------------------------------------------------
        # TITLE --------------------------------------------------------------------------------------------------------
        row = 0
        label_1 = wx.StaticText(self.left_panel, wx.ID_ANY, "RMS && ALIASING")
        label_1.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_1, (row, 0), (1, 3), wx.LEFT | wx.RIGHT | wx.TOP, 5)

        row += 1
        static_line_1 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_1.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_1, (row, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        # SIGNAL -------------------------------------------------------------------------------------------------------
        row += 1
        lbl_signal = wx.StaticText(self.left_panel, wx.ID_ANY, "Signal Characteristics")
        lbl_signal.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(lbl_signal, (row, 0), (1, 3), wx.LEFT | wx.RIGHT, 5)

        row += 1
        lbl_signal_peak = wx.StaticText(self.left_panel, wx.ID_ANY, "Peak:")
        grid_sizer_left_panel.Add(lbl_signal_peak, (row, 0), (1, 1), wx.LEFT | wx.RIGHT, 5)
        lbl_signal_peak_val = wx.StaticText(self.left_panel, wx.ID_ANY, "1")
        grid_sizer_left_panel.Add(lbl_signal_peak_val, (row, 1), (1, 2), wx.BOTTOM, 5)

        row += 1
        lbl_signal_freq = wx.StaticText(self.left_panel, wx.ID_ANY, "Frequency (f0):")
        grid_sizer_left_panel.Add(lbl_signal_freq, (row, 0), (1, 1), wx.LEFT | wx.RIGHT, 5)
        lbl_signal_freq_val = wx.StaticText(self.left_panel, wx.ID_ANY, "1000 Hz")
        grid_sizer_left_panel.Add(lbl_signal_freq_val, (row, 1), (1, 2), wx.BOTTOM, 5)

        # SETTINGS -----------------------------------------------------------------------------------------------------
        row += 2
        lbl_settings = wx.StaticText(self.left_panel, wx.ID_ANY, "Settings")
        lbl_settings.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(lbl_settings, (row, 0), (1, 3), wx.LEFT | wx.RIGHT, 5)

        row += 1
        static_line_2 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_2.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_2, (row, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        row += 1
        lbl_fs = wx.StaticText(self.left_panel, wx.ID_ANY, "Fs:")
        grid_sizer_left_panel.Add(lbl_fs, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_left_panel.Add(self.text_ctrl_fs, (row, 1), (1, 1), wx.BOTTOM, 5)
        lbl_units_kHz = wx.StaticText(self.left_panel, wx.ID_ANY, "(kHz):")
        grid_sizer_left_panel.Add(lbl_units_kHz, (row, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)

        row += 1
        lbl_ldf = wx.StaticText(self.left_panel, wx.ID_ANY, "LDF:")
        lbl_ldf.SetToolTip("Lowest Recoverable Frequency")
        grid_sizer_left_panel.Add(lbl_ldf, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_left_panel.Add(self.text_ctrl_ldf, (row, 1), (1, 1), wx.BOTTOM, 5)
        lbl_units_hz = wx.StaticText(self.left_panel, wx.ID_ANY, "(Hz):")
        grid_sizer_left_panel.Add(lbl_units_hz, (row, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)

        # RESULTS ------------------------------------------------------------------------------------------------------
        row += 1
        lbl_results = wx.StaticText(self.left_panel, wx.ID_ANY, "Results")
        lbl_results.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(lbl_results, (row, 0), (1, 3), wx.LEFT | wx.RIGHT, 5)

        row += 1
        static_line_3 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_3.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_3, (row, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        row += 1
        lbl_samples = wx.StaticText(self.left_panel, wx.ID_ANY, "Samples (N):")
        grid_sizer_left_panel.Add(lbl_samples, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_left_panel.Add(self.text_ctrl_samples, (row, 1), (1, 2), wx.BOTTOM, 5)

        row += 1
        lbl_cycles = wx.StaticText(self.left_panel, wx.ID_ANY, "cycles:")
        grid_sizer_left_panel.Add(lbl_cycles, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_left_panel.Add(self.text_ctrl_cycles, (row, 1), (1, 2), wx.BOTTOM, 5)

        row += 1
        lbl_samples_per_cycle = wx.StaticText(self.left_panel, wx.ID_ANY, "N/cycles:")
        grid_sizer_left_panel.Add(lbl_samples_per_cycle, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_left_panel.Add(self.text_ctrl_samples_per_cycle, (row, 1), (1, 2), wx.BOTTOM, 5)

        row += 2
        lbl_rms_true = wx.StaticText(self.left_panel, wx.ID_ANY, "RMS (True):")
        grid_sizer_left_panel.Add(lbl_rms_true, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_left_panel.Add(self.text_ctrl_rms_true, (row, 1), (1, 2), wx.BOTTOM, 5)

        row += 1
        lbl_rms_sampled = wx.StaticText(self.left_panel, wx.ID_ANY, "RMS (Sampled):")
        grid_sizer_left_panel.Add(lbl_rms_sampled, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_left_panel.Add(self.text_ctrl_rms_sampled, (row, 1), (1, 2), wx.BOTTOM, 5)

        row += 1
        lbl_delta = wx.StaticText(self.left_panel, wx.ID_ANY, "Delta RMS:")
        grid_sizer_left_panel.Add(lbl_delta, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_left_panel.Add(self.text_ctrl_rms_delta, (row, 1), (1, 1), wx.BOTTOM, 5)
        lbl_units_ppm = wx.StaticText(self.left_panel, wx.ID_ANY, "(ppm):")
        grid_sizer_left_panel.Add(lbl_units_ppm, (row, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)

        row += 2
        lbl_aliased = wx.StaticText(self.left_panel, wx.ID_ANY, "Aliased Frequency:")
        lbl_aliased.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(lbl_aliased, (row, 0), (1, 3), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)

        row += 1
        lbl_h1 = wx.StaticText(self.left_panel, wx.ID_ANY, "1st Harmonic:")
        grid_sizer_left_panel.Add(lbl_h1, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_left_panel.Add(self.text_ctrl_aliased_freq01, (row, 1), (1, 1), wx.BOTTOM, 5)
        lbl_units_hz = wx.StaticText(self.left_panel, wx.ID_ANY, "(kHz):")
        grid_sizer_left_panel.Add(lbl_units_hz, (row, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)

        row += 1
        lbl_h2 = wx.StaticText(self.left_panel, wx.ID_ANY, "3rd Harmonic:")
        grid_sizer_left_panel.Add(lbl_h2, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_left_panel.Add(self.text_ctrl_aliased_freq02, (row, 1), (1, 1), wx.BOTTOM, 5)
        lbl_units_hz = wx.StaticText(self.left_panel, wx.ID_ANY, "(kHz):")
        grid_sizer_left_panel.Add(lbl_units_hz, (row, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)

        row += 1
        lbl_h3 = wx.StaticText(self.left_panel, wx.ID_ANY, "5th Harmonic:")
        grid_sizer_left_panel.Add(lbl_h3, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_left_panel.Add(self.text_ctrl_aliased_freq03, (row, 1), (1, 1), wx.BOTTOM, 5)
        lbl_units_hz = wx.StaticText(self.left_panel, wx.ID_ANY, "(kHz):")
        grid_sizer_left_panel.Add(lbl_units_hz, (row, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)

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

    def update(self, evt):
        f0 = 1000
        signal_peak = 1

        Fs = to_float(self.text_ctrl_fs.GetValue()) * 1e3
        LDF = to_float(self.text_ctrl_ldf.GetValue())

        # TEMPORAL -----------------------------------------------------------------------------------------------------
        N = getWindowLength(f0, 200e3, windfunc='blackman', error=LDF, mainlobe_type='absolute')
        self.x, self.y = ADC(signal_peak, f0, 200e3, N, CONTAINS_HARMONICS, CONTAINS_NOISE)

        N = getWindowLength(f0, Fs, windfunc='blackman', error=LDF, mainlobe_type='absolute')
        xdt, ydt = ADC(signal_peak, f0, Fs, N, CONTAINS_HARMONICS, CONTAINS_NOISE)

        rms_true = round(true_signal(signal_peak, N, CONTAINS_HARMONICS, CONTAINS_NOISE), 8)
        rms_sampled = round(rms_flat(ydt), 8)
        rms_delta = round(1e6 * (rms_true - rms_sampled), 2)

        cycles = N * f0 / Fs
        samples_per_cycles = N / cycles

        # ALIASING -----------------------------------------------------------------------------------------------------
        aliased_freq = [1.0, 3.0, 5.0]

        for idx, harmonic in enumerate(aliased_freq):
            Fn = Fs/2
            nyquist_zone = np.floor(f0*harmonic/Fn) + 1

            if nyquist_zone % 2 == 0:
                aliased_freq[idx] = (Fn - (f0*harmonic % Fn))/1000
            else:
                aliased_freq[idx] = (f0*harmonic % Fn)/1000

        # SPECTRAL -----------------------------------------------------------------------------------------------------
        xf_fft = np.linspace(0.0, Fs, N)
        w = np.blackman(N)

        # Calculate amplitude correction factor after windowing --------------------------------------------------------
        # https://stackoverflow.com/q/47904399/3382269
        amplitude_correction_factor = 1 / np.mean(w)

        # Calculate the length of the FFT ------------------------------------------------------------------------------
        if (N % 2) == 0:
            # for even values of N: FFT length is (N / 2) + 1
            fft_length = int(N / 2) + 1
        else:
            # for odd values of N: FFT length is (N + 1) / 2
            fft_length = int((N + 2) / 2)

        xf_fft = np.linspace(0.0, Fs, N)
        yf_fft = (np.fft.fft(ydt * w) / fft_length) * amplitude_correction_factor

        yf_rfft = yf_fft[:fft_length]
        xf_rfft = np.linspace(0.0, Fs / 2, fft_length)

        if aliased_freq[0] == 0:
            fh1 = f0
        else:
            fh1 = 1000 * aliased_freq[0]

        self.plot(fh1, xdt, ydt, fft_length, xf_rfft, yf_rfft)
        self.results_update(N, rms_true, rms_sampled, rms_delta, np.floor(cycles), samples_per_cycles, aliased_freq)

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

    def plot(self, f0, xt, yt, fft_length, xf, yf):
        # TEMPORAL -----------------------------------------------------------------------------------------------------
        self.temporal.set_data(self.x * 1000, self.y)
        self.temporal_sampled.set_data(xt * 1000, yt)

        xt_left = 0
        xt_right = 4 / f0  # 4 periods are displayed by default
        self.ax1.set_xlim(left=xt_left * 1000, right=xt_right * 1000)

        # SPECTRAL -----------------------------------------------------------------------------------------------------
        yf_peak = max(abs(yf))
        self.spectral.set_data(xf / 1000, 20 * np.log10(np.abs(yf / yf_peak)))
        try:
            self.ax2.relim()  # recompute the ax.dataLim
        except ValueError:
            print(f'Are the lengths of xt: {len(xf)} and yt: {len(yf)} mismatched?')
            raise
        self.ax2.autoscale()

        xf_left = 0
        xf_right = xf[fft_length - 1]
        self.ax2.set_xlim(left=xf_left / 1000, right=xf_right / 1000)

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

    def results_update(self, N, rms_true, rms_sampled, rms_delta, cycles, samples_per_cycle, aliased_freq):
        self.text_ctrl_samples.SetLabelText(str(N))
        self.text_ctrl_rms_true.SetLabelText(str(rms_true))
        self.text_ctrl_rms_sampled.SetLabelText(str(rms_sampled))
        self.text_ctrl_rms_delta.SetLabelText(str(rms_delta))

        self.text_ctrl_cycles.SetLabelText(str(cycles))
        self.text_ctrl_samples_per_cycle.SetLabelText(str(samples_per_cycle))
        self.text_ctrl_aliased_freq01.SetLabelText(str(aliased_freq[0]))
        self.text_ctrl_aliased_freq02.SetLabelText(str(aliased_freq[1]))
        self.text_ctrl_aliased_freq03.SetLabelText(str(aliased_freq[2]))


def without_gui():
    signal_peak = 1
    f0 = 1000

    Fs = to_float(input("Sampling Frequency [kHz]:")) * 1000
    LDF = to_float(input("Lowest recoverable Frequency [Hz]:"))

    # TEMPORAL -----------------------------------------------------------------------------------------------------
    N = getWindowLength(f0, Fs, windfunc='blackman', error=LDF, mainlobe_type='absolute')
    xdt, ydt = ADC(signal_peak, f0, Fs, N, CONTAINS_HARMONICS, CONTAINS_NOISE)

    rms_true = true_signal(f0, N, CONTAINS_HARMONICS, CONTAINS_NOISE)
    rms_sampled = rms_flat(ydt)
    rms_delta = round(1e6 * (rms_true - rms_sampled), 2)

    cycles = N * f0 / Fs
    samples_per_cycles = N / cycles
    aliased_freq = np.abs(f0 - Fs * round(f0 / Fs, 0))

    print()
    print('Samples (N):', N)
    print('RMS (True):', rms_true)
    print('RMS(Sampled):', rms_sampled)
    print('Delta RMS (ppm):', rms_delta)

    print()
    print('cycles:', np.floor(cycles))
    print('N/cycles:', samples_per_cycles)
    print('Aliased Frequency:', aliased_freq)


# FOR RUNNING INDEPENDENTLY ============================================================================================
class MyDemoFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.SetSize((1055, 629))
        self.panel = MyDemoPanel(self)

        self.__set_properties()
        self.__do_layout()

    def __set_properties(self):
        self.SetTitle("Aliasing")

    def __do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.panel, 1, wx.ALL | wx.EXPAND, 5)
        self.SetSizer(sizer)
        self.Layout()


class MyApp(wx.App):
    def OnInit(self):
        self.frame = MyDemoFrame(None, wx.ID_ANY, "")
        self.SetTopWindow(self.frame)
        self.frame.Show()
        return True


if __name__ == "__main__":
    if GUI:
        app = MyApp(0)
        app.MainLoop()
    else:
        without_gui()
