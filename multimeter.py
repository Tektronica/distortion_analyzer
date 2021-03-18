import dut_f5560A as dut
import dmm_f884xA as dmm

import time
import pandas as pd
import numpy as np
from pathlib import Path
import threading
import datetime
import os
import re
from decimal import Decimal
import csv


########################################################################################################################
def _getFilepath(directory, fname):
    Path(directory).mkdir(parents=True, exist_ok=True)
    date = datetime.date.today().strftime("%Y%m%d")
    filename = f'{fname}_{date}'
    index = 0

    while os.path.isfile(f'{directory}/{filename}_{str(index).zfill(3)}.csv'):
        index += 1
    filename = filename + "_" + str(index).zfill(3)
    return f'{directory}/{filename}.csv'


def write_to_csv(path, fname, header, *args):
    table = list(zip(*args))
    pathname = _getFilepath(path, fname)
    with open(pathname, 'w', newline='') as outfile:
        writer = csv.writer(outfile, delimiter=',')
        if header:
            writer.writerow(header)
        for row in table:
            writer.writerow(row)


########################################################################################################################
class Instruments(dut.f5560A_instrument, dmm.f884xA_instruments):
    def __init__(self, parent):
        dut.f5560A_instrument.__init__(self)
        dmm.f884xA_instruments.__init__(self)

        self.analyzer = parent
        self.measurement = []
        self.connected = False

    def connect(self, instruments):
        try:
            # ESTABLISH COMMUNICATION TO INSTRUMENTS -------------------------------------------------------------------
            f5560A_id = instruments['DUT']
            f884xA_id = instruments['DMM']

            self.connect_to_f5560A(f5560A_id)
            self.connect_to_f884xA(f884xA_id)

            if self.f5560A.healthy and self.f884xA.healthy:
                self.connected = True
                try:
                    idn_dict = {'DUT': self.f5560A_IDN, 'DMM': self.f884xA_IDN}
                    self.analyzer.frame.set_ident(idn_dict)
                    self.setup_source()
                except ValueError:
                    raise
            else:
                print('\nUnable to connect to all instruments.\n')
        except ValueError:
            raise ValueError('Could not connect. Timeout error occurred.')

    def close_instruments(self):
        time.sleep(1)
        self.close_f5560A()
        self.close_f884xA()


class DMM_Measurement:
    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, parent):
        self.panel = parent
        self.DUMMY_DATA = False  # can be toggled by the gui
        self.amplitude_good = False  # Flag indicates user input for amplitude value is good (True)
        self.frequency_good = False  # Flag indicates user input for frequency value is good (True)

        self.params = {'mode': 0, 'source': 0, 'amplitude': '', 'units': '',
                       'rms': 0, 'frequency': 0.0, 'error': 0.0,
                       'cycles': 0.0, 'filter': ''}
        self.data = {'xt': [0], 'yt': [0],
                     'xf': [0], 'yf': [0]}
        self.results = {'Amplitude': [], 'Frequency': [], 'RMS': [],
                        'THDN': [], 'THD': [], 'RMS NOISE': [],
                        'N': [], 'Fs': [], 'Aperture': []}

        self.M = Instruments(self)

    # ------------------------------------------------------------------------------------------------------------------

    def connect(self, instruments):
        self.M.close_instruments()
        time.sleep(2)
        try:
            self.M.connect(instruments)
        except ValueError as e:
            self.frame.error_dialog(e)

    # ------------------------------------------------------------------------------------------------------------------
    def start(self, user_input):
        selection = user_input['mode']
        source = user_input['source']
        amplitude, units, ft = self.get_string_value(user_input['amplitude'], user_input['frequency'])
        self.params = {'mode': user_input['mode'],
                       'source': user_input['source'],
                       'amplitude': amplitude,
                       'units': units.capitalize(),
                       'rms': user_input['rms'],
                       'frequency': ft,
                       'error': user_input['error'],

                       'filter': user_input['filter']
                       }

        message = f"{amplitude} {units} @ {ft} Hz"
        print(f"\n{message} {'-' * (100 - len(message))}")

        try:
            if self.M.connected:
                # TODO: Why did I do this?
                if selection in (1, 3):
                    self.run_selected_function(selection)
                elif not source or (self.amplitude_good and self.frequency_good):
                    self.run_selected_function(selection)
                else:
                    self.frame.error_dialog('\nCheck amplitude and frequency values.')
            elif self.DUMMY_DATA:
                self.run_selected_function(selection)
            else:
                self.frame.error_dialog('\nConnect to instruments first.')
            self.frame.btn_start.SetLabel('START')

        except ValueError as e:
            message = 'finished with errors.'
            print(f"{message} {'-' * (100 - len(message))}")

            self.frame.flag_complete = True
            self.frame.btn_start.SetLabel('START')
            self.frame.error_dialog(e)
        else:
            message = 'done'
            print(f"{message} {'-' * (100 - len(message))}")
            self.frame.flag_complete = True

    def run_selected_function(self, selection):
        try:
            # run single
            if selection == 0:
                self.run_single(self.test)

            # run sweep
            elif selection == 1:
                df = pd.read_csv('distortion_breakpoints.csv')
                self.run_sweep(df, self.test)

            # run single shunt voltage implied current measurement
            elif selection == 2:
                print('Running single measurement measuring current from shunt voltage.')
                self.run_single(self.test_analyze_shunt_voltage)

            # run swept shunt voltage implied current measurement
            elif selection == 3:
                print('Running sweep measuring current from shunt voltage.')
                df = pd.read_csv('distortion_breakpoints.csv')
                self.run_sweep(df, self.test_analyze_shunt_voltage)

            # run continuous
            elif selection == 4:
                self.run_continuous(self.test)

            # amplitude measurement only using fluke 884xA
            elif selection == 5:
                self.run_sweep(self.test_amplitude_only)

            else:
                print('Nothing happened.')

        except ValueError:
            raise

    # ------------------------------------------------------------------------------------------------------------------
    def run_single(self, func):
        print('Running Single Measurement.')
        self.frame.toggle_controls()
        self.frame.flag_complete = False
        try:
            func(setup=True)
            if not self.DUMMY_DATA:
                self.M.standby()
        except ValueError:
            self.frame.toggle_controls()
            raise

        self.frame.toggle_controls()
        self.frame.flag_complete = True

    def run_sweep(self, df, func):
        print('Running Sweep.')
        self.frame.flag_complete = False
        headers = ['amplitude', 'frequency', 'rms', 'THDN', 'THD', 'uARMS Noise', 'Fs', 'aperture']
        results = np.zeros(shape=(len(df.index), len(headers)))
        t = threading.currentThread()
        for idx, row in df.iterrows():
            if getattr(t, "do_run", True):
                if not self.DUMMY_DATA:
                    self.frame.text_amplitude.SetValue(str(row.amplitude))
                    self.frame.text_frequency.SetValue(str(row.frequency))
                    amplitude, units, ft = self.get_string_value(row.amplitude, str(row.frequency))

                    self.params['amplitude'] = amplitude
                    self.params['frequency'] = ft
                    self.params['units'] = units

                    try:
                        results[idx] = func(setup=True)
                        self.M.standby()
                    except ValueError:
                        raise
                else:
                    self.params['amplitude'] = 1
                    self.params['frequency'] = 1000
                    self.params['units'] = 'A'
                    results[idx] = func(setup=True)
            else:
                break

        # https://stackoverflow.com/a/28356566
        # https://stackoverflow.com/a/28058264
        results_df = pd.DataFrame(results, columns=headers)
        results_df.to_csv(path_or_buf=_getFilepath('results', 'distortion'), sep=',', index=False)
        self.frame.flag_complete = True

    # ------------------------------------------------------------------------------------------------------------------
    def test_amplitude_only(self, setup):
        params = self.params

        # SOURCE
        amplitude = params['amplitude']
        rms = params['rms']
        if rms != 0:
            amplitude = amplitude / np.sqrt(2)
            print('Provided amplitude converted to RMS.')

        Ft = params['frequency']
        suffix = params['units']
        time.sleep(1)

        # START DATA COLLECTION ----------------------------------------------------------------------------------------
        if setup:
            self.M.setup_meter(output='CURR', mode='AC')
        if params['source']:
            try:
                self.M.run_source(suffix, amplitude, Ft)
                try:
                    outval, freqval = self.M.read_meter()
                    data = {'x': freqval, 'y': outval}
                except ValueError:
                    print('error occurred while connecting to DMM. Placing 5560 in Standby.')
                    self.M.standby()
                    raise
            except ValueError:
                print('error occurred while connecting to DUT. Exiting current measurement.')
                raise
        else:
            outval, freqval = self.M.read_meter()

        data = {'x': freqval, 'y': outval}
        self.plot(data)

        return outval, freqval

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

        self.panel.plot(params)

    def close_instruments(self):
        if hasattr(self.M, 'DUT') and hasattr(self.M, 'DMM'):
            self.M.close_instruments()

    # ------------------------------------------------------------------------------------------------------------------
    def get_string_value(self, amp_string, freq_string):
        # https://stackoverflow.com/a/35610194
        amplitude = 0.0
        frequency = 0.0
        units = ''
        prefix = {'p': '1e-12', 'n': '1e-9', 'u': '1e-6', 'm': '1e-3'}
        units_list = ("A", "a", "V", "v")
        s_split = re.findall(r'[0-9.]+|\D', amp_string)

        # CHECK IF AMPLITUDE USER INPUT IS VALID
        try:
            if len(s_split) == 3 and s_split[1] in prefix.keys() and s_split[2] in units_list:
                amplitude = float(Decimal(s_split[0]) * Decimal(prefix[s_split[1]]))
                units = s_split[2].capitalize()
                self.amplitude_good = True
            elif len(s_split) == 2 and s_split[1] in units_list:
                amplitude = float(s_split[0])
                units = s_split[1].capitalize()
                self.amplitude_good = True

            elif len(s_split) == 2 and s_split[1]:
                self.frame.error_dialog('prefix used, but units not specified!')
                self.amplitude_good = False
            elif len(s_split) == 1:
                self.frame.error_dialog('units not specified!')
                self.amplitude_good = False
            else:
                self.frame.error_dialog('improper prefix used!')
                self.amplitude_good = False
        except ValueError:
            self.frame.error_dialog('Invalid amplitude entered!')
            self.amplitude_good = False
            pass

        # CHECK IF FREQUENCY USER INPUT IS VALID
        try:
            frequency = float(freq_string)
        except ValueError:
            self.frame.error_dialog(f"The value {freq_string} is not a valid frequency!")
            self.frequency_good = False
        else:
            self.frequency_good = True

        return amplitude, units, frequency
