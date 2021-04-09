import dut_f5560A as dut
import dmm_f8588A as dmm

from distortion_calculator import *

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
def get_FFT_parameters(Ft, lpf, error):
    Fs = dmm.getSamplingFrequency(Ft, lpf)

    N = getWindowLength(f0=Ft, fs=Fs, windfunc='blackman', error=error)
    aperture, runtime = dmm.get_aperture(Fs, N)

    return Fs, N, aperture, runtime


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
class Instruments(dut.f5560A_instrument, dmm.f8588A_instrument):
    def __init__(self, parent):
        dut.f5560A_instrument.__init__(self)
        dmm.f8588A_instrument.__init__(self)

        self.analyzer = parent
        self.measurement = []
        self.connected = False

    def connect(self, instruments):
        try:
            # ESTABLISH COMMUNICATION TO INSTRUMENTS -------------------------------------------------------------------
            f5560A_id = instruments['f5560A']
            f8588A_id = instruments['f8588A']

            self.connect_to_f5560A(f5560A_id)
            self.connect_to_f8588A(f8588A_id)

            if self.f5560A.healthy and self.f8588A.healthy:
                self.connected = True
                try:
                    idn_dict = {'DUT': self.f5560A_IDN, 'DMM': self.f8588A_IDN}
                    self.analyzer.frame.set_ident(idn_dict)
                    self.setup_source()
                except ValueError:
                    raise
            else:
                print('Unable to connect to all instruments.\n')
        except ValueError:
            raise ValueError('Could not connect. Timeout error occurred.')

    def close_instruments(self):
        time.sleep(1)
        self.close_f5560A()
        self.close_f8588A()
        self.connected = False


class DistortionAnalyzer:
    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, parent):
        self.frame = parent
        self.DUMMY_DATA = False  # can be toggled by the gui
        self.amplitude_good = False  # Flag indicates user input for amplitude value is good (True)
        self.frequency_good = False  # Flag indicates user input for frequency value is good (True)

        self.params = {}
        self.results = {'Amplitude': [], 'Frequency': [], 'yrms': [],
                        'THDN': [], 'THD': [], 'RMS NOISE': [],
                        'N': [], 'Fs': [], 'Aperture': []}

        self.M = Instruments(self)

    # ##################################################################################################################
    def connect(self, instruments):
        self.M.close_instruments()
        time.sleep(2)
        try:
            self.M.connect(instruments)
        except ValueError as e:
            self.frame.error_dialog(e)

    def close_instruments(self):
        if hasattr(self.M, 'DUT') and hasattr(self.M, 'DMM'):
            self.M.close_instruments()

    # ##################################################################################################################
    def start(self, user_input):
        self.params = user_input
        selected_test = self.params['selected_test']
        source = self.params['source']
        amplitude, units, ft = self.get_string_value(user_input['amplitude'], user_input['frequency'])
        self.params['amplitude'] = amplitude
        self.params['units'] = units
        self.params['frequency'] = ft

        message = f"{amplitude} {units} @ {ft} Hz"
        print(f"\n{message} {'-' * (100 - len(message))}")

        try:
            if self.M.connected:
                # TODO: Why did I do this?
                if selected_test in (1, 3):
                    self.run_selected_function(selected_test)
                elif not source or (self.amplitude_good and self.frequency_good):
                    self.run_selected_function(selected_test)
                else:
                    self.frame.error_dialog('\nCheck amplitude and frequency values.')
            elif self.DUMMY_DATA:
                self.run_selected_function(selected_test)
            else:
                self.frame.error_dialog('\nConnect to instruments first.')
            self.frame.btn_start.SetLabel('RUN')

        except ValueError as e:
            message = 'finished with errors.'
            print(f"{message} {'-' * (100 - len(message))}")

            self.frame.flag_complete = True
            self.frame.btn_start.SetLabel('START')
            self.frame.error_dialog(e)
        else:
            message = 'done'
            print(f"{message} {'-' * (100 - len(message))}\n")
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
        headers = ['amplitude', 'frequency', 'yrms', 'THDN', 'THD', 'uARMS Noise', 'Fs', 'aperture']
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
                    self.params['units'] = 'V'
                    results[idx] = func(setup=True)
            else:
                break

        # https://stackoverflow.com/a/28356566
        # https://stackoverflow.com/a/28058264
        results_df = pd.DataFrame(results, columns=headers)
        results_df.to_csv(path_or_buf=_getFilepath('results', 'distortion'), sep=',', index=False)
        self.frame.flag_complete = True

    def run_continuous(self, func):
        print('Running a continuous run!')
        self.frame.flag_complete = False
        t = threading.currentThread()
        setup = True
        while getattr(t, "do_run", True):
            try:
                func(setup=setup)
                setup = False
                time.sleep(0.1)
            except ValueError:
                raise

        if not self.DUMMY_DATA:
            self.M.standby()
        print('Ending continuous run_source process.')

    # TEST FUNCTIONS ###################################################################################################
    def test(self, setup):
        # SOURCE -------------------------------------------------------------------------------------------------------
        amplitude = self.params['amplitude']
        coupling = self.params['coupling']
        Ft = self.params['frequency']

        if self.params['rms'] != 0:
            amplitude = amplitude / np.sqrt(2)
            print('Provided amplitude converted to RMS.')

        units = self.params['units']
        time.sleep(1)

        # DIGITIZER ----------------------------------------------------------------------------------------------------
        error = self.params['error']
        filter_val = self.params['filter']

        # DIGITIZED SIGNAL =============================================================================================
        if Ft == 0:
            lpf = 10e3
            hpf = 3  # high pass filter cutoff frequency
            Fs, N, aperture, runtime = get_FFT_parameters(Ft=10, lpf=lpf, error=error)
        else:
            if filter_val == 'None':
                lpf = 0  # low pass filter cutoff frequency
                hpf = 0
            elif filter_val == '100kHz':
                lpf = 100e3  # low pass filter cutoff frequency
                hpf = 0
            elif filter_val == '2MHz':
                lpf = 2e6  # low pass filter cutoff frequency
                hpf = 10
            elif filter_val == '2.4MHz':
                """
                If the sampling frequency is 5 MHz, the nyquist rate is 2.5 MHz.
                
                If a tangible harmonic of the signal (such as a 7th) was outside the nyquist rate, then aliasing 
                would occur. For example, a 500kHz signal has a 7th harmonic at 3.5 MHz. Sampling at 5MHz with a 2MHz 
                filter, an aliased signal at 1.5MHz would be observed. """
                lpf = 2.4e6  # low pass filter cutoff frequency
                hpf = 10
            elif filter_val == '3MHz':
                lpf = 3e6  # low pass filter cutoff frequency
                hpf = 0
            else:
                raise ValueError("Invalid filter cutoff selected!")
            Fs, N, aperture, runtime = get_FFT_parameters(Ft=Ft, lpf=lpf, error=error)

        # START DATA COLLECTION ----------------------------------------------------------------------------------------
        # TODO
        # This is for internal debugging only. Not user facing.
        if not self.DUMMY_DATA:
            # TODO: shouldn't we always want to setup digitizer for new range??
            if setup:
                self.M.setup_digitizer(units=units, ideal_range_val=amplitude, coupling=coupling,
                                       filter_val=filter_val, N=N, aperture=aperture)
            if self.params['source']:
                try:
                    self.M.run_source(units, amplitude, Ft)
                    try:
                        y = self.M.retrieve_digitize()
                    except ValueError:
                        print('error occurred while connecting to DMM. Placing 5560 in Standby.')
                        self.M.standby()
                        raise
                except ValueError:
                    print('error occurred while connecting to DUT. Exiting current measurement.')
                    raise
            else:
                y = self.M.retrieve_digitize()
        else:
            y = pd.read_csv('results/history/DUMMY.csv')['yt'].to_numpy()

        return self.fft(y, runtime, Fs, N, aperture, hpf, lpf, amplitude, Ft)

    # ------------------------------------------------------------------------------------------------------------------
    def test_analyze_shunt_voltage(self, setup):
        amplitude = self.params['amplitude']
        coupling = self.params['coupling']
        Ft = self.params['frequency']

        if self.params['rms'] != 0:
            amplitude = amplitude / np.sqrt(2)
            print('Provided amplitude converted to RMS.')

        source_units = self.params['units']
        self.M.run_source(source_units, amplitude, Ft)
        time.sleep(1)

        # METER
        self.M.setup_f8588A_meter(autorange=True, output_type='VOLT', mode='AC')
        meter_outval, meter_range, meter_ft = self.M.read_f8588A_meter()
        meter_units = 'V'

        # DIGITIZER
        error = self.params['error']
        filter_val = self.params['filter']

        # DIGITIZED SIGNAL =============================================================================================
        if Ft == 0:
            lpf = 10e3
            hpf = 3  # high pass filter cutoff frequency
            Fs, N, aperture, runtime = get_FFT_parameters(Ft=Ft, lpf=lpf, error=error)
        else:
            if filter_val == '100kHz':
                lpf = 100e3  # low pass filter cutoff frequency
            elif filter_val == '3MHz':
                lpf = 3e6  # low pass filter cutoff frequency
            else:
                lpf = 0
            hpf = 0
            Fs, N, aperture, runtime = get_FFT_parameters(Ft=Ft, lpf=lpf, error=error)

        # START DATA COLLECTION ----------------------------------------------------------------------------------------
        if setup:
            self.M.setup_digitizer(units=meter_units, ideal_range_val=meter_range, coupling=coupling,
                                   filter_val=filter_val, N=N, aperture=aperture)
        y = self.M.retrieve_digitize()

        pd.DataFrame(data=y, columns=['ydata']).to_csv('results/y_data.csv')

        return self.fft(y, runtime, Fs, N, aperture, hpf, lpf, amplitude, Ft)

    # FFT ##############################################################################################################
    def fft(self, yt, runtime, Fs, N, aperture, hpf, lpf, amplitude, Ft):
        yrms = rms_flat(yt)
        xt = np.arange(0, N, 1) / Fs

        xf_fft, yf_fft, xf_rfft, yf_rfft, main_lobe_width = windowed_fft(yt, Fs, N, 'blackman')

        # Find THD and THD+N -------------------------------------------------------------------------------------------
        try:
            thdn, f0, noise_rms = THDN_F(yf_rfft, Fs, N, main_lobe_width, hpf, lpf)
            thd = THD(yf_rfft, Fs)
            data = {'xt': xt, 'yt': yt, 'xf': xf_rfft, 'yf': yf_rfft,
                    'N': N, 'runtime': runtime, 'Fs': Fs, 'f0': f0}
        except ValueError as e:
            raise
        results_row = {'Amplitude': amplitude, 'Frequency': Ft,
                       'yrms': yrms,
                       'THDN': round(thdn, 5), 'THD': round(thd, 5), 'RMS NOISE': noise_rms,
                       'N': N, 'Fs': f'{round(Fs / 1000, 2)} kHz', 'Aperture': f'{round(aperture * 1e6, 4)}us'}

        # TODO: is this action necessary still?
        # append units column ------------------------------------------------------------------------------------------
        for key, value in results_row.items():
            self.results[key].append(value)
        results_row['units'] = self.params['units']

        # report results to main panel ---------------------------------------------------------------------------------
        self.frame.results_update(results_row)

        # save measurement to csv --------------------------------------------------------------------------------------
        header = ['xt', 'yt', 'xf', 'yf']
        write_to_csv('results/history', 'measurement', header, xt, yt, xf_fft, yf_fft)
        self.plot(data)

        return [amplitude, Ft, yrms, thdn, thd, noise_rms, Fs, aperture]

    # PLOT #############################################################################################################
    def plot(self, data):
        f0 = data['f0']
        runtime = data['runtime']

        # TEMPORAL -----------------------------------------------------------------------------------------------------
        xt = data['xt'] * 1e3
        yt = data['yt']

        ylimit = np.max(np.abs(yt)) * 1.25
        yt_tick = ylimit / 4

        xt_left = 0
        xt_right = min(4 / f0, runtime)  # 4 periods are displayed by default
        yt_btm = -ylimit
        yt_top = ylimit + yt_tick

        # SPECTRAL -----------------------------------------------------------------------------------------------------
        xf = data['xf']
        yf = data['yf']
        Fs = data['Fs']
        N = data['N']
        yf_peak = max(abs(yf))

        xf_left = np.min(xf)
        xf_right = min(10 ** (np.ceil(np.log10(f0)) + 1), Fs / 2 - Fs / N)  # Does not exceed max bin
        yf_btm = -150
        yf_top = 50

        # TODO: yf[0:N] is wrong. The actual FFT length is nearly N/2. index outside range is effectively ignored.
        params = {'xt': xt, 'yt': yt,
                  'xt_left': xt_left * 1000, 'xt_right': xt_right * 1000,
                  'yt_btm': yt_btm, 'yt_top': yt_top, 'yt_tick': yt_tick,

                  'xf': xf / 1000, 'yf': 20 * np.log10(np.abs(yf / yf_peak)),
                  'xf_left': xf_left / 1000, 'xf_right': xf_right / 1000,
                  'yf_btm': yf_btm, 'yf_top': yf_top
                  }

        self.frame.plot(params)

    # MISCELLANEOUS ####################################################################################################
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
                units = s_split[2].upper()  # example: 'V'
                self.amplitude_good = True
            elif len(s_split) == 2 and s_split[1] in units_list:
                amplitude = float(s_split[0])
                units = s_split[1].upper()  # example: 'V'
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
