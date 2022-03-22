from distortion_calculator import *

import numpy as np
import pandas as pd
from pathlib import Path

import wx

import matplotlib.pyplot as plt
import matplotlib.pylab as pylab
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavigationToolbar


class HistoryTab(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY)

        self.parent = parent
        self.plot_panel = wx.Panel(self, wx.ID_ANY, style=wx.SIMPLE_BORDER)

        # PLOT Panel ---------------------------------------------------------------------------------------------------
        self.figure = plt.figure(figsize=(1, 1))  # look into Figure((5, 4), 75)
        self.canvas = FigureCanvas(self.plot_panel, -1, self.figure)
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Realize()

        self.ax1 = self.figure.add_subplot(211)
        self.ax2 = self.figure.add_subplot(212)

        self.temporal, = self.ax1.plot([], [], linestyle='-')
        self.spectral, = self.ax2.plot([], [], color='#C02942')

        # Open history dialog ------------------------------------------------------------------------------------------
        self.btn_openHistory = wx.Button(self, wx.ID_ANY, "Open History")
        self.Bind(wx.EVT_BUTTON, self.OnOpen, self.btn_openHistory)

        self.text_ctrl_fs = wx.TextCtrl(self, wx.ID_ANY, "")
        self.text_ctrl_samples = wx.TextCtrl(self, wx.ID_ANY, "")
        self.text_ctrl_rms = wx.TextCtrl(self, wx.ID_ANY, "")
        self.text_ctrl_thdn = wx.TextCtrl(self, wx.ID_ANY, "")
        self.text_ctrl_thd = wx.TextCtrl(self, wx.ID_ANY, "")

        self.__set_properties()
        self.__do_layout()
        self.__do_plot_layout()

    def __set_properties(self):
        self.SetBackgroundColour(wx.Colour(240, 240, 240))
        self.canvas.SetMinSize((700, 490))

    def __do_layout(self):
        sizer_2 = wx.GridSizer(1, 1, 0, 0)
        grid_sizer_1 = wx.FlexGridSizer(1, 2, 0, 0)
        grid_sizer_plot = wx.GridBagSizer(0, 0)
        grid_sizer_report = wx.GridBagSizer(0, 0)

        # LEFT PANEL ---------------------------------------------------------------------------------------------------
        lbl_fs = wx.StaticText(self, wx.ID_ANY, "Fs:")
        lbl_samples = wx.StaticText(self, wx.ID_ANY, "Samples:")
        lbl_rms = wx.StaticText(self, wx.ID_ANY, "RMS:")
        lbl_thdn = wx.StaticText(self, wx.ID_ANY, "THD+N:")
        lbl_THD = wx.StaticText(self, wx.ID_ANY, "THD:")

        static_line_1 = wx.StaticLine(self, wx.ID_ANY)
        static_line_1.SetMinSize((180, 2))
        static_line_2 = wx.StaticLine(self, wx.ID_ANY)
        static_line_2.SetMinSize((180, 2))

        grid_sizer_report.Add(self.btn_openHistory, (0, 0), (1, 2), wx.LEFT | wx.TOP, 5)
        grid_sizer_report.Add(static_line_2, (1, 0), (1, 2), wx.ALL, 5)
        grid_sizer_report.Add(lbl_fs, (2, 0), (1, 1), wx.LEFT | wx.RIGHT, 5)
        grid_sizer_report.Add(self.text_ctrl_fs, (2, 1), (1, 1), wx.BOTTOM, 5)
        grid_sizer_report.Add(lbl_samples, (3, 0), (1, 1), wx.LEFT | wx.RIGHT, 5)
        grid_sizer_report.Add(self.text_ctrl_samples, (3, 1), (1, 1), wx.BOTTOM, 5)
        grid_sizer_report.Add(static_line_1, (4, 0), (1, 2), wx.ALL, 5)
        grid_sizer_report.Add(lbl_rms, (5, 0), (1, 1), wx.LEFT | wx.RIGHT, 5)
        grid_sizer_report.Add(self.text_ctrl_rms, (5, 1), (1, 1), wx.BOTTOM, 5)
        grid_sizer_report.Add(lbl_thdn, (6, 0), (1, 1), wx.LEFT | wx.RIGHT, 5)
        grid_sizer_report.Add(self.text_ctrl_thdn, (6, 1), (1, 1), wx.BOTTOM, 5)
        grid_sizer_report.Add(lbl_THD, (7, 0), (1, 1), wx.LEFT | wx.RIGHT, 5)
        grid_sizer_report.Add(self.text_ctrl_thd, (7, 1), (1, 1), 0, 0)
        grid_sizer_1.Add(grid_sizer_report, 1, wx.EXPAND, 0)

        # PLOT PANEL ---------------------------------------------------------------------------------------------------
        grid_sizer_plot.Add(self.canvas, (0, 0), (1, 1), wx.ALL | wx.EXPAND)
        grid_sizer_plot.Add(self.toolbar, (1, 0), (1, 1), wx.ALL | wx.EXPAND)
        grid_sizer_plot.AddGrowableRow(0)
        grid_sizer_plot.AddGrowableCol(0)
        self.plot_panel.SetSizer(grid_sizer_plot)
        grid_sizer_1.Add(self.plot_panel, 1, wx.EXPAND, 5)

        grid_sizer_1.AddGrowableRow(0)
        grid_sizer_1.AddGrowableCol(1)

        sizer_2.Add(grid_sizer_1, 0, wx.EXPAND, 0)

        self.SetSizer(sizer_2)
        self.Layout()

    def error_dialog(self, error_message):
        print(error_message)
        dial = wx.MessageDialog(None, str(error_message), 'Error', wx.OK | wx.ICON_ERROR)
        dial.ShowModal()

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

        self.process_raw_input(xt, yt, xf, yf)

    def process_raw_input(self, xt, yt, xf, yf):
        yrms = np.sqrt(np.mean(np.abs(yt) ** 2))
        N = len(xt)
        Fs = round(1 / (xt[1] - xt[0]), 2)

        # SPECTRAL -----------------------------------------------------------------------------------------------------
        main_lobe_width = 6 * (Fs / N)

        if (N % 2) == 0:
            # for even values of N: length is (N / 2) + 1
            fft_length = int(N / 2) + 1
        else:
            # for odd values of N: length is (N + 1) / 2
            fft_length = int((N + 2) / 2)

        yf_rfft = yf[:fft_length]
        xf_rfft = np.round(np.fft.rfftfreq(N, d=1. / Fs), 6)  # one-sided

        thdn, *_ = THDN_F(xf_rfft, yf_rfft, Fs, N, main_lobe_width, hpf=0, lpf=100e3)
        thd = THD(xf_rfft, yf_rfft, Fs, N, main_lobe_width)

        self.plot(xt, yt, fft_length, xf_rfft, yf_rfft)
        self.results_update(Fs, N, yrms, thdn, thd)

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

    def plot(self, xt, yt, fft_length, xf, yf):
        # TEMPORAL -----------------------------------------------------------------------------------------------------
        self.temporal.set_data(xt, yt)

        try:
            self.ax1.relim()  # recompute the ax.dataLim
        except ValueError:
            print(f'Are the lengths of xt: {len(xt)} and yt: {len(yt)} mismatched?')
            raise
        self.ax1.margins(x=0)
        self.ax1.autoscale()

        # SPECTRAL -----------------------------------------------------------------------------------------------------
        yf_peak = max(abs(yf))
        self.spectral.set_data(xf/1000, 20 * np.log10(np.abs(yf / yf_peak)))
        try:
            self.ax2.relim()  # recompute the ax.dataLim
        except ValueError:
            print(f'Are the lengths of xt: {len(xf)} and yt: {len(yf)} mismatched?')
            raise
        self.ax2.autoscale()

        xf_left = 0
        xf_right = xf[fft_length - 1]
        self.ax2.set_xlim(left=xf_left/1000, right=xf_right/1000)

        # UPDATE PLOT FEATURES -----------------------------------------------------------------------------------------
        self.figure.tight_layout()

        self.toolbar.update()  # Not sure why this is needed - ADS
        self.canvas.draw()
        self.canvas.flush_events()

    def results_update(self, Fs, N, yrms, thdn, thd):
        self.text_ctrl_fs.SetLabelText(str(Fs))
        self.text_ctrl_samples.SetLabelText(str(N))
        self.text_ctrl_rms.SetValue(f"{'{:0.3e}'.format(yrms)}")
        self.text_ctrl_thdn.SetValue(f"{round(thdn * 100, 3)}% or {round(np.log10(thdn), 1)}dB")
        self.text_ctrl_thd.SetValue(f"{round(thd * 100, 3)}% or {round(np.log10(thd), 1)}dB")
