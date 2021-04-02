import dut_f5560A as dut
import dmm_f884xA as dmm1
import dmm_f8588A as dmm2

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
class Instruments(dut.f5560A_instrument, dmm1.f884xA_instrument, dmm2.f8588A_instrument):
    def __init__(self, parent):
        dut.f5560A_instrument.__init__(self)
        dmm1.f884xA_instrument.__init__(self)
        dmm2.f8588A_instrument.__init__(self)

        self.parent = parent
        self.measurement = []
        self.connected = False

    def connect(self, instruments):
        try:
            # ESTABLISH COMMUNICATION TO INSTRUMENTS -------------------------------------------------------------------
            f5560A_id = instruments['f5560A']
            DMM_id = instruments[self.parent.DMM_choice]

            self.connect_to_f5560A(f5560A_id)
            if self.parent.DMM_choice == 'f884xA':
                self.connect_to_f884xA(DMM_id)
            elif self.parent.DMM_choice == 'f8588A':
                self.connect_to_f8588A(DMM_id)
            else:
                raise ValueError("Invalid DMM choice selected!")

            if self.f5560A.healthy and (self.f884xA.healthy or self.f8588A.healthy):
                self.connected = True
                try:
                    idn_dict = {'DUT': self.f5560A_IDN, 'DMM': self.f884xA_IDN}
                    # TODO: parent.parent. --nice
                    self.parent.parent.set_ident(idn_dict)
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
        if self.parent.DMM_choice == 'f884xA':
            self.close_f884xA()
        elif self.parent.DMM_choice == 'f8588A':
            self.close_f8588A()
        else:
            raise ValueError("Failed to close DMM instrument!"
                             "\nThe DMM selected may not match what is currently in remote.")
        self.connected = False


class DMM_Measurement:
    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, parent):
        self.parent = parent
        self.DUMMY_DATA = False  # can be toggled by the gui
        self.amplitude_good = False  # Flag indicates user input for amplitude value is good (True)
        self.frequency_good = False  # Flag indicates user input for frequency value is good (True)

        self.DMM_choice = 'f8588A'
        self.params = {}
        self.results = {'Amplitude': [], 'Frequency': [], 'RMS': [],
                        'THDN': [], 'THD': [], 'RMS NOISE': [],
                        'N': [], 'Fs': [], 'Aperture': []}

        # Saving the last state of Ft (operating frequency) helps determine if we have switched between AC and DC
        self._Ft = 0.0

        self.M = Instruments(self)

    # ##################################################################################################################
    def connect(self, instruments):
        self.M.close_instruments()
        time.sleep(2)
        try:
            self.M.connect(instruments)
        except ValueError as e:
            self.parent.error_dialog(e)

    def close_instruments(self):
        if hasattr(self.M, 'DUT') and hasattr(self.M, 'DMM'):
            self.M.close_instruments()

    # ##################################################################################################################
    def start(self, user_input):
        selection = user_input['mode']
        amplitude, units, ft = self.get_string_value(user_input['amplitude'], user_input['frequency'])
        self.params = {'autorange': user_input['autorange'],
                       'always_voltage': user_input['always_voltage'],
                       'mode': user_input['mode'],
                       'amplitude': amplitude,
                       'units': units.capitalize(),
                       'rms': user_input['rms'],
                       'frequency': ft,
                       }

        message = f"{amplitude} {units} @ {ft} Hz"
        print(f"\n{message} {'-' * (100 - len(message))}")

        try:
            if self.M.connected:
                if selection == 1:
                    self.run_selected_function(selection)
                elif self.amplitude_good and self.frequency_good:
                    self.run_selected_function(selection)
                else:
                    self.parent.error_dialog('\nCheck amplitude and frequency values.')
            elif self.DUMMY_DATA:
                self.run_selected_function(selection)
            else:
                self.parent.error_dialog('\nConnect to instruments first.')
            self.parent.btn_start.SetLabel('START')
            self.parent.checkbox_autorange.Enable()
            self.parent.checkbox_always_voltage.Enable()

        except ValueError as e:
            message = 'finished with errors.'
            print(f"{message} {'-' * (100 - len(message))}")

            self.parent.flag_complete = True
            self.parent.btn_start.SetLabel('START')
            self.parent.error_dialog(e)
        else:
            message = 'done'
            print(f"{message} {'-' * (100 - len(message))}\n")
            self.parent.flag_complete = True

    def run_selected_function(self, selection):
        try:
            # run single
            if selection == 0:
                self.run_single(self.test_multimeter)

            # run sweep
            elif selection == 1:
                df = pd.read_csv('distortion_breakpoints.csv')
                self.run_sweep(df, self.test_multimeter)

            else:
                print('Nothing happened.')

        except ValueError:
            raise

    # ------------------------------------------------------------------------------------------------------------------
    def run_single(self, func):
        print('Running Single Measurement with Multimeter.')
        self.parent.toggle_controls()
        self.parent.flag_complete = False
        try:
            func(setup=True)
            if not self.DUMMY_DATA:
                self.M.standby()
        except ValueError:
            self.parent.toggle_controls()
            raise

        self.parent.toggle_controls()
        self.parent.flag_complete = True

    def run_sweep(self, df, func):
        print('Running Sweep.')
        self.parent.flag_complete = False
        headers = ['amplitude', 'frequency', 'measured', 'freq_meas', 'std']
        results = np.zeros(shape=(len(df.index), len(headers)))
        t = threading.currentThread()
        for idx, row in df.iterrows():
            if getattr(t, "do_run", True):
                if not self.DUMMY_DATA:
                    self.parent.text_amplitude.SetValue(str(row.amplitude))
                    self.parent.text_frequency.SetValue(str(row.frequency))
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
                    amplitude, units, ft = self.get_string_value(str(row.amplitude), str(row.frequency))

                    self.params['amplitude'] = amplitude
                    self.params['frequency'] = ft
                    self.params['units'] = units
                    results[idx] = func(setup=True)
            else:
                break

        # https://stackoverflow.com/a/28356566
        # https://stackoverflow.com/a/28058264
        results_df = pd.DataFrame(results, columns=headers)
        results_df.to_csv(path_or_buf=_getFilepath('results', 'multimeter'), sep=',', index=False)
        self.parent.flag_complete = True

    # TEST FUNCTIONS ###################################################################################################
    def test_multimeter(self, setup):
        params = self.params

        # SOURCE
        amplitude = params['amplitude']
        rms = params['rms']
        if rms != 0:
            amplitude = amplitude / np.sqrt(2)
            print('Provided amplitude converted to RMS.')

        Ft = params['frequency']
        units = params['units']

        # In transimpedance situations where voltage is being measured across a load -----------------------------------
        if params['always_voltage']:
            dmm_units = 'V'
        else:
            dmm_units = units

        time.sleep(1)

        # START DATA COLLECTION ----------------------------------------------------------------------------------------
        if not self.DUMMY_DATA:
            autorange = params['autorange']

            # Usually enters on each new measurement, but only once for each loop (measurement sweep) ------------------
            if setup:
                self.M.setup_f884xA_meter(autorange=autorange, units=dmm_units, frequency=Ft)
                self._Ft = Ft

            # During a loop (measurement sweep) we want to catch changes from either AC to DC or vice-versa ------------
            elif (Ft * self._Ft) == 0 and Ft != self._Ft:
                self.M.setup_f884xA_meter(autorange=autorange, units=dmm_units, frequency=Ft)
                self._Ft = Ft

            try:
                if not autorange:
                    if self.DMM_choice == 'f884xA':
                        self.M.set_f884xA_range(ideal_range_val=amplitude, units=units, frequency=Ft)
                    elif self.DMM_choice == 'f8588A':
                        self.M.set_f8588A_range(ideal_range_val=amplitude, units=units, frequency=Ft)
                    else:
                        raise ValueError("Invalid DMM selection made!")

                    time.sleep(1)
                self.M.run_source(units, amplitude, Ft)

                try:
                    if self.DMM_choice == 'f884xA':
                        outval, freqval, std = self.M.average_f884xA_reading(10)
                    elif self.DMM_choice == 'f8588A':
                        outval, freqval, std = self.M.average_f8588A_reading(10)
                    else:
                        raise ValueError("Invalid DMM selection made!")

                except ValueError:
                    print('error occurred while connecting to DMM. Placing Fluke 5560A in Standby.')
                    self.M.standby()
                    raise

            except ValueError:
                print('error occurred while connecting to Fluke 5560A. Exiting current measurement.')
                raise
        else:
            # DUMMY_DATA for random number generation
            freqval, outval, std = Ft, (7 + 1 * np.random.random(1))[0], (0.25 + np.random.random(1))[0]
            if self.DMM_choice == 'f884xA':
                M = dmm1.f884xA_instrument()
            elif self.DMM_choice == 'f8588A':
                M = dmm2.f8588A_instrument()
            else:
                raise ValueError("Invalid DMM selection made!")

            print(f"Fluke 5560A operating units: {units}")
            print(f"Retrieve function parameters for DMM: {M._get_function_params(frequency=freqval, units='A')}")
            print(f"Measured units: {dmm_units}")

        self.parent.update_plot(freqval, outval, std)
        return amplitude, Ft, outval, freqval, std

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
                units = s_split[2].capitalize()
                self.amplitude_good = True
            elif len(s_split) == 2 and s_split[1] in units_list:
                amplitude = float(s_split[0])
                units = s_split[1].capitalize()
                self.amplitude_good = True

            elif len(s_split) == 2 and s_split[1]:
                self.parent.error_dialog('prefix used, but units not specified!')
                self.amplitude_good = False
            elif len(s_split) == 1:
                self.parent.error_dialog('units not specified!')
                self.amplitude_good = False
            else:
                self.parent.error_dialog('improper prefix used!')
                self.amplitude_good = False
        except ValueError:
            self.parent.error_dialog('Invalid amplitude entered!')
            self.amplitude_good = False
            pass

        # CHECK IF FREQUENCY USER INPUT IS VALID
        try:
            frequency = float(freq_string)
        except ValueError:
            self.parent.error_dialog(f"The value {freq_string} is not a valid frequency!")
            self.frequency_good = False
        else:
            self.frequency_good = True

        return amplitude, units, frequency
