from multimeter import DMM_Measurement as dmm
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

def open_breakpoints():
    import subprocess, os, platform
    wkdir = os.getcwd()
    filename = "distortion_breakpoints.csv"
    path_to_file = wkdir + '\\' + filename

    print(f'opening breakpoints file at: {path_to_file}')

    if platform.system() == 'Darwin':       # macOS
        subprocess.call(('open', path_to_file))

    elif platform.system() == 'Windows':    # Windows
        print(os.path.normcase(path_to_file))
        os.startfile(filename)

    else:                                   # linux variants
        subprocess.call(('xdg-open', path_to_file))


class MultimeterTab(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY)

        # instance variables -------------------------------------------------------------------------------------------
        self.DUT_choice = 'f5560A'
        self.DMM_choice = 'f8588A'
        self.dmm = dmm(self)

        self.t = threading.Thread()
        self.flag_complete = True  # Flag indicates any active threads (False) or thread completed (True)
        self.user_input = {'autorange': True,
                           'always_voltage': True,
                           'mode': 0,
                           'amplitude': '',
                           'rms': 0,
                           'frequency': '',
                           }

        self.frame = parent
        self.left_panel = wx.Panel(self, wx.ID_ANY)
        self.plot_panel = wx.Panel(self, wx.ID_ANY, style=wx.SIMPLE_BORDER)

        # LEFT Panel ---------------------------------------------------------------------------------------------------
        self.combo_DUT_choice = wx.ComboBox(self.left_panel, wx.ID_ANY,
                                            choices=["Fluke 5560A", "Fluke 5730A"],
                                            style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.combo_DMM_choice = wx.ComboBox(self.left_panel, wx.ID_ANY,
                                            choices=["Fluke 884xA", "Fluke 8588A"],
                                            style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.text_DUT_report = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.text_DMM_report = wx.TextCtrl(self.left_panel, wx.ID_ANY, "", style=wx.TE_READONLY)
        self.label_source = wx.StaticText(self.left_panel, wx.ID_ANY, "Fluke 5560A")

        self.btn_connect = wx.Button(self.left_panel, wx.ID_ANY, "Connect")
        self.btn_config = wx.Button(self.left_panel, wx.ID_ANY, "Config")
        self.checkbox_autorange = wx.CheckBox(self.left_panel, wx.ID_ANY, "Auto Range")

        self.text_amplitude = wx.TextCtrl(self.left_panel, wx.ID_ANY, "10uA")
        self.combo_rms_or_peak = wx.ComboBox(self.left_panel, wx.ID_ANY,
                                             choices=["RMS", "Peak"],
                                             style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self.text_frequency = wx.TextCtrl(self.left_panel, wx.ID_ANY, "1000")

        self.checkbox_always_voltage = wx.CheckBox(self.left_panel, wx.ID_ANY, "Always Voltage")
        self.spreadsheet = MyGrid(self.left_panel)
        self.btn_cleardata = wx.Button(self.left_panel, wx.ID_ANY, "Clear Data")
        self.checkbox_errorbar = wx.CheckBox(self.left_panel, wx.ID_ANY, "Error Bars")

        self.btn_start = wx.Button(self.left_panel, wx.ID_ANY, "RUN")
        self.combo_mode = wx.ComboBox(self.left_panel, wx.ID_ANY, choices=["Single", "Sweep"], style=wx.CB_DROPDOWN)
        self.btn_breakpoints = wx.Button(self.left_panel, wx.ID_ANY, "Breakpoints")

        # PLOT Panel ---------------------------------------------------------------------------------------------------
        self.figure = plt.figure(figsize=(1, 1))  # look into Figure((5, 4), 75)
        self.canvas = FigureCanvas(self.plot_panel, -1, self.figure)
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Realize()

        self.x, self.y, self.std = np.NaN, np.NaN, np.NaN
        self.errorbars = False
        self.ax1 = self.figure.add_subplot(111)
        self.line, (self.err_top, self.err_btm), (self.bars,) = self.ax1.errorbar(np.zeros(1), np.zeros(1), yerr=np.zeros(1), fmt='o',
                                                                                  ecolor='red', capsize=4)
        # BINDINGS =====================================================================================================
        # Configure Instruments ----------------------------------------------------------------------------------------
        on_DUT_selection = lambda event: self._get_DUT_choice(event)
        self.Bind(wx.EVT_COMBOBOX_CLOSEUP, on_DUT_selection, self.combo_DUT_choice)

        on_DMM_selection = lambda event: self._get_DMM_choice(event)
        self.Bind(wx.EVT_COMBOBOX_CLOSEUP, on_DMM_selection, self.combo_DMM_choice)

        on_connect = lambda event: self.on_connect_instr(event)
        self.Bind(wx.EVT_BUTTON, on_connect, self.btn_connect)

        on_config = lambda event: self.config(event)
        self.Bind(wx.EVT_BUTTON, on_config, self.btn_config)

        on_toggle_autorange = lambda event: self.toggle_autorange(event)
        self.Bind(wx.EVT_CHECKBOX, on_toggle_autorange, self.checkbox_autorange)

        on_toggle_always_voltage = lambda event: self.toggle_always_voltage(event)
        self.Bind(wx.EVT_CHECKBOX, on_toggle_always_voltage, self.checkbox_always_voltage)

        on_cleardata = lambda event: self.cleardata(event)
        self.Bind(wx.EVT_BUTTON, on_cleardata, self.btn_cleardata)

        on_toggle_errorbar = lambda event: self.toggle_errorbar(event)
        self.Bind(wx.EVT_CHECKBOX, on_toggle_errorbar, self.checkbox_errorbar)

        # Run Measurement (start subprocess) ---------------------------------------------------------------------------
        on_run_event = lambda event: self.on_run(event)
        self.Bind(wx.EVT_BUTTON, on_run_event, self.btn_start)

        on_open_breakpoints = lambda event: open_breakpoints()
        self.Bind(wx.EVT_BUTTON, on_open_breakpoints, self.btn_breakpoints)

        on_combo_select = lambda event: self.lock_controls(event)
        self.Bind(wx.EVT_COMBOBOX_CLOSEUP, on_combo_select, self.combo_mode)

        self.__set_properties()
        self.__do_layout()
        self.__do_plot_layout()
        self.__do_table_header()
        self.cleardata(wx.Event)

    def __set_properties(self):
        self.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.canvas.SetMinSize((700, 490))

        self.left_panel.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.plot_panel.SetBackgroundColour(wx.Colour(255, 255, 255))

        self.text_DUT_report.SetMinSize((200, 23))
        self.text_DMM_report.SetMinSize((200, 23))
        self.checkbox_autorange.SetValue(1)

        self.combo_DUT_choice.SetSelection(0)
        self.combo_DUT_choice.SetMinSize((87, 23))
        self.combo_DMM_choice.SetSelection(1)
        self.combo_DMM_choice.SetMinSize((87, 23))
        self.btn_connect.SetMinSize((87, 23))
        self.btn_start.SetMinSize((87, 23))
        self.btn_breakpoints.SetMinSize((87, 23))

        self.combo_rms_or_peak.SetSelection(0)
        self.combo_mode.SetSelection(0)
        self.checkbox_always_voltage.SetValue(0)
        self.checkbox_errorbar.SetValue(0)

        self.spreadsheet.CreateGrid(60, 3)
        self.spreadsheet.SetRowLabelSize(40)
        self.spreadsheet.SetColLabelValue(0, 'Frequency')
        self.spreadsheet.SetColLabelValue(1, 'Value')
        self.spreadsheet.SetColLabelValue(2, 'STD')
        self.spreadsheet.SetMinSize((300, 215))

        self.combo_mode.SetMinSize((110, 23))

    def __do_layout(self):
        sizer_2 = wx.GridSizer(1, 1, 0, 0)
        grid_sizer_1 = wx.FlexGridSizer(1, 2, 0, 0)
        grid_sizer_left_panel = wx.GridBagSizer(0, 0)
        grid_sizer_left_sub_btn_row = wx.GridBagSizer(0, 0)
        grid_sizer_plot = wx.GridBagSizer(0, 0)

        # LEFT PANEL ===================================================================================================
        # TITLE --------------------------------------------------------------------------------------------------------
        row = 0
        label_1 = wx.StaticText(self.left_panel, wx.ID_ANY, "MULTIMETER")
        label_1.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_1, (row, 0), (1, 2), 0, 0)

        row += 1
        static_line_1 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_1.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_1, (row, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        # INSTRUMENT INFO  ---------------------------------------------------------------------------------------------
        row += 1
        grid_sizer_left_panel.Add(self.combo_DUT_choice, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.text_DUT_report, (row, 1), (1, 2), wx.BOTTOM | wx.LEFT, 5)

        row += 1
        grid_sizer_left_panel.Add(self.combo_DMM_choice, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.text_DMM_report, (row, 1), (1, 2), wx.BOTTOM | wx.LEFT, 5)

        row += 1
        grid_sizer_left_panel.Add(self.btn_connect, (row, 0), (1, 1), wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.btn_config, (row, 1), (1, 1), wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        grid_sizer_left_panel.Add(self.checkbox_autorange, (row, 2), (1, 1), wx.ALIGN_CENTRE_VERTICAL | wx.BOTTOM, 5)

        # f5560A SETUP -------------------------------------------------------------------------------------------------
        row += 1
        self.label_source.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(self.label_source, (row, 0), (1, 2), wx.TOP, 10)

        row += 1
        static_line_2 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_2.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_2, (row, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        row += 1
        label_amplitude = wx.StaticText(self.left_panel, wx.ID_ANY, "Amplitude:")
        grid_sizer_left_panel.Add(label_amplitude, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.text_amplitude, (row, 1), (1, 1), wx.BOTTOM | wx.LEFT, 5)
        grid_sizer_left_panel.Add(self.combo_rms_or_peak, (row, 2), (1, 1), wx.BOTTOM | wx.LEFT, 5)

        row += 1
        label_frequency = wx.StaticText(self.left_panel, wx.ID_ANY, "Frequency (Ft):")
        grid_sizer_left_panel.Add(label_frequency, (row, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 5)
        grid_sizer_left_panel.Add(self.text_frequency, (row, 1), (1, 1), wx.LEFT, 5)
        label_Hz = wx.StaticText(self.left_panel, wx.ID_ANY, "(Hz)")
        grid_sizer_left_panel.Add(label_Hz, (row, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

        row += 1
        label_measure = wx.StaticText(self.left_panel, wx.ID_ANY, "Measure")
        label_measure.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_left_panel.Add(label_measure, (row, 0), (1, 1), wx.TOP, 10)
        grid_sizer_left_panel.Add(self.checkbox_always_voltage, (row, 1), (1, 3), wx.ALIGN_BOTTOM | wx.LEFT, 10)

        # RESULTS ------------------------------------------------------------------------------------------------------
        row += 1
        static_line_3 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_3.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_3, (row, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        row += 1
        grid_sizer_left_panel.Add(self.spreadsheet, (row, 0), (1, 3), wx.ALIGN_LEFT | wx.RIGHT | wx.EXPAND, 5)

        row += 1
        grid_sizer_left_panel.Add(self.btn_cleardata, (row, 0), (1, 1), wx.LEFT | wx.TOP, 5)
        grid_sizer_left_panel.Add(self.checkbox_errorbar, (row, 1), (1, 1), wx.LEFT | wx.TOP, 5)
        grid_sizer_left_panel.AddGrowableRow(11)

        # BUTTONS ------------------------------------------------------------------------------------------------------
        row += 1
        static_line_4 = wx.StaticLine(self.left_panel, wx.ID_ANY)
        static_line_4.SetMinSize((300, 2))
        grid_sizer_left_panel.Add(static_line_4, (row, 0), (1, 3), wx.BOTTOM | wx.RIGHT | wx.TOP, 5)

        row += 1
        grid_sizer_left_sub_btn_row.Add(self.btn_start, (0, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL)
        grid_sizer_left_sub_btn_row.Add(self.combo_mode, (0, 1), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        grid_sizer_left_sub_btn_row.Add(self.btn_breakpoints, (0, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        grid_sizer_left_panel.Add(grid_sizer_left_sub_btn_row, (row, 0), (1, 3), wx.ALIGN_TOP | wx.BOTTOM, 13)

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

    # GET SELECTED INSTRUMENTS =========================================================================================
    def _get_instr_choice(self, type, selection, text_ctrl):
        # Get [NEW] instr choice ---------------------------------------------------------------------------------------
        print(f"The {selection} has been selected.")
        new_choice = 'f' + selection.strip('Fluke ')

        # Get [PREVIOUS] instr choice ----------------------------------------------------------------------------------
        if type.lower() == 'dut':
            current_choice = self.dmm.DUT_choice
        elif type.lower() == 'dmm':
            current_choice = self.dmm.DMM_choice
        else:
            raise ValueError("invalid instrument type. Please specify whether 'dut' or 'dmm'.")

        # Conditionally refresh GUI ------------------------------------------------------------------------------------
        if not self.dmm.M.connected:
            # if instruments are not connected, then user is free to change the DMM choice
            pass

        elif self.dmm.DUMMY_DATA:
            # if using dummy data, then we only need to set DMM choice to True before running
            self.dmm.DMM_choice = self.DMM_choice

        elif new_choice != current_choice and self.dmm.M.connected:
            # if the selected instrument does not currently match the remote instrument connected, there's a problem.
            self.dmm.M.connected = False
            print(f"[WARNING] the {selection} is NOT the current remote instrument connected!")
            # set text box color to red (chantilly: #EAB9C1)
            text_ctrl.SetBackgroundColour(wx.Colour(234, 185, 193))
            self.left_panel.Refresh()

        elif new_choice == self.dmm.DMM_choice:
            # if the selected instrument does match the remote instrument connected, reset the color if necessary
            self.dmm.M.connected = True
            # Reset color (white smoke: #F0F0F0)
            text_ctrl.SetBackgroundColour(wx.Colour(240, 240, 240))
            self.left_panel.Refresh()

        return new_choice

    def _get_DUT_choice(self, evt):
        selection = self.combo_DUT_choice.GetValue()
        self.DUT_choice = self._get_instr_choice(type='dut', selection=selection, text_ctrl=self.text_DUT_report)
        self.label_source.SetLabelText(str(selection))

        return self.DUT_choice

    def _get_DMM_choice(self, evt):
        selection = self.combo_DMM_choice.GetValue()
        self.DMM_choice = self._get_instr_choice(type='dmm', selection=selection, text_ctrl=self.text_DMM_report)

        return self.DMM_choice

    # CONFIGURE INSTR FOR MEASUREMENT ==================================================================================
    def config(self, evt):
        dlg = InstrumentDialog(self, [self.DUT_choice, self.DMM_choice], None, wx.ID_ANY, )
        dlg.ShowModal()
        dlg.Destroy()

    def get_instruments(self):
        config_dict = ReadConfig()

        dut = config_dict[self.DUT_choice]
        dmm = config_dict[self.DMM_choice]

        instruments = {self.DUT_choice: {'address': dut['address'], 'port': dut['port'],
                                         'gpib': dut['gpib'], 'mode': dut['mode']},
                       self.DMM_choice: {'address': dmm['address'], 'port': dmm['port'],
                                         'gpib': dmm['gpib'], 'mode': dmm['mode']}}

        return instruments

    def set_ident(self, idn_dict):
        self.text_DUT_report.SetValue(idn_dict['DUT'])  # DUT
        self.text_DMM_report.SetValue(idn_dict['DMM'])  # current DMM

    def on_connect_instr(self, evt):
        wait = wx.BusyCursor()
        msg = "Establishing remote connections to instruments."
        busyDlg = wx.BusyInfo(msg, parent=self)

        print('\nResetting connection. Closing communication with any connected instruments')
        self.text_DUT_report.Clear()
        self.text_DMM_report.Clear()
        self.dmm.DUT_choice = self.DUT_choice
        self.dmm.DMM_choice = self.DMM_choice
        # self.thread_this(self.dmm.connect, (self.get_instruments(),))
        self.dmm.connect(self.get_instruments(),)

        busyDlg = None
        del wait

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

    def toggle_controls(self):
        if self.text_amplitude.IsEnabled():
            self.text_amplitude.Disable()
            self.combo_rms_or_peak.Disable()
            self.text_frequency.Disable()
        else:
            self.text_amplitude.Enable()
            self.combo_rms_or_peak.Enable()
            self.text_frequency.Enable()

    def toggle_autorange(self, evt):
        if self.checkbox_autorange.IsChecked():
            print("[Update] Auto Ranging turned ON for Fluke 884xA.")
        else:
            print("[Update] Auto Ranging turned OFF for Fluke 884xA.")

    def toggle_always_voltage(self, evt):
        DMM_choice = {self.DMM_choice}

        if self.checkbox_always_voltage.IsChecked():
            print(f"[Update] {DMM_choice} will always measure voltage. Use external shunt if sourcing current.")
        else:
            print(f"[Update] {DMM_choice} will perform direct measurement of the DUT.")

    # ------------------------------------------------------------------------------------------------------------------
    def get_values(self):
        autorange = bool(self.checkbox_autorange.GetValue())
        always_voltage = bool(self.checkbox_always_voltage.GetValue())
        mode = self.combo_mode.GetSelection()
        rms = self.combo_rms_or_peak.GetSelection()

        amp_string = self.text_amplitude.GetValue()
        freq_string = self.text_frequency.GetValue()

        self.user_input = {'autorange': autorange,
                           'always_voltage': always_voltage,
                           'mode': mode,
                           'amplitude': amp_string,
                           'rms': rms,
                           'frequency': freq_string,
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
            self.thread_this(self.dmm.start, (self.user_input,))
            self.checkbox_autorange.Disable()
            self.checkbox_always_voltage.Disable()
            self.btn_start.SetLabel('STOP')

        elif self.t.is_alive() and self.user_input['mode'] == 1:
            # stop sweep
            # https://stackoverflow.com/a/36499538
            self.t.do_run = False
            self.checkbox_autorange.Enable()
            self.checkbox_always_voltage.Enable()
            self.btn_start.SetLabel('RUN')
        else:
            print('thread already running.')

    # ------------------------------------------------------------------------------------------------------------------
    def __do_plot_layout(self):
        self.ax1.set_title('MULTIMETER')
        self.ax1.set_xlabel('FREQUENCY (kHz)')
        self.ax1.set_ylabel('AMPLITUDE')
        self.ax1.grid(True)
        self.figure.tight_layout()

    def toggle_errorbar(self, evt):
        if self.errorbars:
            self.errorbars = False
            print("[Update] Error bars have been turned OFF")
        else:
            self.errorbars = True
            print("[Update] Error bars have been turned ON")

        if hasattr(self.x, 'size'):
            y_err = self.std / np.sqrt(self.x.size)
            self.plot(yerr=y_err)

    def update_plot(self, x, y, std):
        self.results_update([x, y, std])
        # TODO: np.NaN is always index 0. Should this be fixed?
        self.x = np.append(self.x, x)
        self.y = np.append(self.y, y)
        self.std = np.append(self.std, std)

        yerr = self.std / np.sqrt(self.x.size)

        self.plot(yerr)

    def plot(self, yerr=None):
        if self.errorbars and yerr is not None:
            yerr_top = self.y + yerr
            yerr_btm = self.y - yerr

            self.line.set_data(self.x, self.y)
            self.err_top.set_data(self.x, yerr_top)
            self.err_btm.set_data(self.x, yerr_btm)

            new_segments = [np.array([[x, yt], [x, yb]]) for x, yt, yb in zip(self.x, yerr_top, yerr_btm)]
            self.bars.set_segments(new_segments)
        else:
            self.line.set_data(self.x, self.y)
            self.err_top.set_ydata(None)
            self.err_btm.set_ydata(None)

            new_segments = []
            self.bars.set_segments(new_segments)

        self.plot_redraw()

    def plot_redraw(self):
        try:
            self.ax1.relim()  # recompute the ax.dataLim
        except ValueError:
            yerr = self.err_top.get_ydata()
            print(f'Are the lengths of x: {len(self.x)}, y: {len(self.y)}, and yerr: {len(yerr)} mismatched?')
            raise
        self.ax1.autoscale()

        # UPDATE PLOT FEATURES -----------------------------------------------------------------------------------------
        self.figure.tight_layout()

        self.toolbar.update()  # Not sure why this is needed - ADS
        self.canvas.draw()
        self.canvas.flush_events()

    def cleardata(self, evt):
        self.x, self.y, self.std = np.NaN, np.NaN, np.NaN
        self.spreadsheet.cleardata()

        self.plot()

    def __do_table_header(self):
        header = ['frequency', 'value', 'std']
        self.spreadsheet.append_rows(header)

    def results_update(self, row):
        """
        :param row: of type list
        :return: True iff rows successfully appended to spreadsheet (grid)
        """
        # self.text_rms_report.SetLabelText(str(y))
        # self.text_frequency_report.SetLabelText(str(x))
        if isinstance(row, list):
            self.spreadsheet.append_rows(row)
            return True
        else:
            raise ValueError('Row to be appended not of type list.')

    def error_dialog(self, error_message):
        print(error_message)
        dial = wx.MessageDialog(None, str(error_message), 'Error', wx.OK | wx.ICON_ERROR)
        dial.ShowModal()


# FOR RUNNING INDEPENDENTLY ============================================================================================
class MyMultimeterFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.SetSize((1055, 564))
        self.panel = MultimeterTab(self)

        self.__set_properties()
        self.__do_layout()

    def __set_properties(self):
        self.SetTitle("Multimeter")
        self.panel.dmm.DUMMY_DATA = True

    def __do_layout(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.panel, 1, wx.EXPAND, 0)
        self.SetSizer(sizer)
        self.Layout()

    # ------------------------------------------------------------------------------------------------------------------
    def OnCloseWindow(self, evt):
        self.panel.dmm.close_instruments()
        self.Destroy()


class MyApp(wx.App):
    def OnInit(self):
        self.frame = MyMultimeterFrame(None, wx.ID_ANY, "")
        self.SetTopWindow(self.frame)
        self.frame.Show()
        return True


if __name__ == "__main__":
    app = MyApp(0)
    app.MainLoop()
