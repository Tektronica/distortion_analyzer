from dmm_f8588A import *
from dut_f5560A import *
from distortion_calculator import *

import time
import pandas as pd
import numpy as np
from pathlib import Path
import threading
import datetime
import os

DUMMY_DATA = True


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


class DistortionAnalyzer:
    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, parent):
        super().__init__()
        self.user_input = {'mode': 0, 'source': 0, 'amplitude': '',
                           'rms': 0, 'frequency': 0.0, 'samples': 0,
                           'cycles': 0.0, 'filter': ''}
        self.params = {'mode': 0, 'source': 0, 'amplitude': '', 'units': '',
                       'rms': 0, 'ft': 0.0, 'samples': 0,
                       'cycles': 0.0, 'filter': ''}
        self.data = {'xt': [0], 'yt': [0],
                     'xf': [0], 'yf': [0]}
        self.results = {'Amplitude': [], 'Frequency': [], 'RMS': [], 'THDN': [], 'THD': [], 'Fs': [], 'Aperture': []}

        self.frame = parent
        self.M = Instruments(self)

    # ------------------------------------------------------------------------------------------------------------------

    def connect(self, instruments):
        self.M.close_instruments()
        time.sleep(2)
        self.M.connect(instruments)

    # ------------------------------------------------------------------------------------------------------------------
    def start(self, params):
        self.params = params
        selection = self.params['mode']
        source = self.params['source']
        if self.M.connected:
            # TODO: Why did I do this?
            if selection in (1, 3):
                self.run_selected_function(selection)
            elif not source or (self.frame.amplitude_good and self.frame.frequency_good):
                self.run_selected_function(selection)
            else:
                self.frame.error_dialog('\nCheck amplitude and frequency values.')
        elif DUMMY_DATA:
            self.run_selected_function(selection)
        else:
            self.frame.error_dialog('\nFirst connect to instruments.')

        self.frame.btn_start.SetLabel('START')

    def run_selected_function(self, selection):
        # run single
        if selection == 0:
            print('Running single')
            self.run_single(self.test)

        # run sweep
        elif selection == 1:
            print('Running sweep')
            df = pd.read_csv('distortion_breakpoints.csv')
            self.run_sweep(df, self.test)

        # run single shunt voltage implied current measurement
        elif selection == 2:
            print('Running single measurement measuring current from shunt voltage')
            self.run_single(self.test_analyze_shunt_voltage)

        # run swept shunt voltage implied current measurement
        elif selection == 3:
            print('Running sweep measuring current from shunt voltage')
            df = pd.read_csv('distortion_breakpoints.csv')
            self.run_sweep(df, self.test_analyze_shunt_voltage)

        # run continuous
        elif selection == 4:
            self.run_continuous(self.test)

        else:
            print('Nothing happened.')

    # ------------------------------------------------------------------------------------------------------------------
    def run_single(self, func):
        print('\nrun_single!')
        self.frame.toggle_controls()
        self.flag_complete = False
        func(setup=True)
        if not DUMMY_DATA:
            self.M.standby()
        self.frame.toggle_controls()
        self.flag_complete = True

    def run_sweep(self, df, func):
        self.flag_complete = False

        headers = ['amplitude', 'frequency', 'rms', 'THDN', 'THD', 'Fs', 'aperture']
        results = np.zeros(shape=(len(df.index), len(headers)))
        for idx, row in df.iterrows():
            self.frame.text_amplitude.SetValue(str(row.amplitude))
            self.frame.text_frequency.SetValue(str(row.frequency))

            self.params['amplitude'] = row.amplitude
            self.params['frequency'] = row.frequency
            results[idx] = func(setup=True)
            self.M.standby()

        # https://stackoverflow.com/a/28356566
        # https://stackoverflow.com/a/28058264
        results_df = pd.DataFrame(results, columns=headers)
        results_df.to_csv(path_or_buf=_getFilepath(), sep=',', index=False)

    def run_continuous(self, func):
        print('\nrun_continuous!')
        self.flag_complete = False
        t = threading.currentThread()
        setup = True
        while getattr(t, "do_run", True):
            func(setup=True)
            setup = False
            time.sleep(0.1)

        if not DUMMY_DATA:
            self.M.standby()
        print('Ending continuous run_source process.')

    # ------------------------------------------------------------------------------------------------------------------
    def test(self, setup):
        params = self.params
        # SOURCE
        amplitude = params['amplitude']
        rms = params['rms']
        if rms != 0:
            amplitude = amplitude / np.sqrt(2)
            print('Provided amplitude converted to RMS.')

        Ft = params['ft']
        suffix = params['units']
        time.sleep(1)

        # DIGITIZER
        N = params['samples']
        cycles = params['cycles']
        filter_val = params['filter']

        # SIGNAL SOURCE ================================================================================================
        if suffix in ('A', 'a'):
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

        # START DATA COLLECTION ----------------------------------------------------------------------------------------
        # TODO
        # This is for internal debugging only. Not user facing.
        if not DUMMY_DATA:
            if setup:
                self.M.setup_digitizer(suffix, oper_range, filter_val, N, aperture)
            if params['source']:
                self.M.run_source(suffix, amplitude, Ft)
                y = self.M.retrieve_digitize()
            else:
                y = self.M.retrieve_digitize()
            pd.DataFrame(data=y, columns=['ydata']).to_csv('results/y_data.csv')
        else:
            y = pd.read_csv('results/y_data.csv')['ydata'].to_numpy()

        return self.fft(y, runtime, Fs, N, aperture, lpf, amplitude, Ft)

    # ------------------------------------------------------------------------------------------------------------------
    def test_analyze_shunt_voltage(self, setup):
        params = self.params
        # SOURCE
        amplitude = params['amplitude']
        rms = params['rms']
        if rms != 0:
            amplitude = amplitude / np.sqrt(2)
            print('Provided amplitude converted to RMS.')

        Ft = params['ft']
        suffix = params['units']
        self.M.run_source(suffix, amplitude, Ft)
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

        # START DATA COLLECTION ----------------------------------------------------------------------------------------
        if setup:
            self.M.setup_digitizer(meter_mode, meter_range, filter_val, N, aperture)
        y = self.M.retrieve_digitize()

        pd.DataFrame(data=y, columns=['ydata']).to_csv('results/y_data.csv')

        return self.fft(y, runtime, Fs, N, aperture, lpf, amplitude, Ft)

    def fft(self, y, runtime, Fs, N, aperture, lpf, amplitude, Ft):
        yrms = rms_flat(y)

        # FFT ==========================================================================================================
        x = np.arange(0.0, runtime, aperture + 200e-9)
        # xf = np.linspace(0.0, Fs / 2, int(N / 2 + 1))
        xf = np.linspace(0.0, Fs, N)
        ywf = windowed_fft(y, N, 'blackman')

        # Find %THD+N
        thdn, f0, yf = THDN(y, Fs, lpf)
        thd = THD(y, Fs)
        data = {'x': x, 'y': y, 'xf': xf, 'ywf': ywf, 'RMS': yrms, 'N': N, 'runtime': runtime, 'Fs': Fs, 'f0': f0}

        results_row = {'Amplitude': amplitude, 'Frequency': Ft, 'RMS': round(yrms, 4),
                       'THDN': round(thdn, 4), 'THD': round(thd, 4),
                       'Fs': round(Fs, 2), 'Aperture': f'{round(aperture * 1e6, 4)}us'}

        for key, value in results_row.items():
            self.results[key].append(value)
        results_row['units'] = self.params['units']

        self.frame.results_update(results_row)
        self.plot(data)

        return [amplitude, Ft, yrms, thdn, thd, Fs, aperture]

    def plot(self, data):
        F0 = data['f0']
        runtime = data['runtime']

        # TEMPORAL -----------------------------------------------------------------------------------------------------
        xt = data['x'] * 1e3
        yt = data['y']

        x_periods = 4
        xt_end = min(x_periods / F0, runtime)
        ylimit = np.max(np.abs(yt)) * 1.25
        yt_tick = ylimit / 4

        # SPECTRAL -----------------------------------------------------------------------------------------------------
        xf = data['xf']
        yf = data['ywf']
        Fs = data['Fs']
        N = data['N']
        yrms = data['RMS']

        xf_end = min(10 ** (np.ceil(np.log10(F0)) + 1), Fs / 2 - Fs / N)  # Does not exceed max bin

        params = {'xt': xt, 'yt': yt,
                  'xt_start': 0, 'xt_end': 1e3 * xt_end,
                  'yt_start': -ylimit, 'yt_end': ylimit + yt_tick, 'yt_tick': yt_tick,

                  'xf': xf[0:N] / 1000, 'yf': 20 * np.log10(2 * np.abs(yf[0:N] / (yrms * N))),
                  'xf_start': np.min(xf) / 1000, 'xf_end': xf_end / 1000,
                  'yf_start': -150, 'yf_end': 0
                  }

        self.frame.plot(params)

    def close_instruments(self):
        if hasattr(self.M, 'DUT') and hasattr(self.M, 'DMM'):
            self.M.close_instruments()
