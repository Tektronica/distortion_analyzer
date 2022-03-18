import dut_f5560A as dut1
import dut_f5730A as dut2
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
class Instruments(dut1.f5560A_instrument, dut2.f5730A_instrument, dmm1.f884xA_instrument, dmm2.f8588A_instrument):
    def __init__(self, parent):
        dut1.f5560A_instrument.__init__(self)
        dut2.f5730A_instrument.__init__(self)
        dmm1.f884xA_instrument.__init__(self)
        dmm2.f8588A_instrument.__init__(self)

        self.multimeter = parent
        self.measurement = []
        self.connected = False

    def connect(self, instruments):
        try:
            DUT_choice = self.multimeter.DUT_choice
            DMM_choice = self.multimeter.DMM_choice

            # ESTABLISH COMMUNICATION TO INSTRUMENTS -------------------------------------------------------------------
            DUT_id = instruments[DUT_choice]
            DMM_id = instruments[DMM_choice]

            # Connect to the dut ---------------------------------------------------------------------------------------
            if DUT_choice == 'f5730A':
                self.connect_to_f5730A(DUT_id)
                dut = self.f5730A
                dut_idn = self.f5730A_IDN

            elif DUT_choice == 'f5560A':
                self.connect_to_f5560A(DUT_id)
                dut = self.f5560A
                dut_idn = self.f5560A_IDN

            else:
                raise ValueError("Invalid DUT choice selected!")

            # Connect to the dmm ---------------------------------------------------------------------------------------
            if DMM_choice == 'f884xA':
                self.connect_to_f884xA(DMM_id)
                dmm = self.f884xA
                dmm_idn = self.f884xA_IDN

            elif DMM_choice == 'f8588A':
                self.connect_to_f8588A(DMM_id)
                dmm = self.f8588A
                dmm_idn = self.f8588A_IDN

            else:
                raise ValueError('Invalid DMM choice selected!')

            # Are all instruments connected? ---------------------------------------------------------------------------
            if dut.healthy and dmm.healthy:
                self.connected = True

                # Set *IDN? labels in text boxes of parent gui ---------------------------------------------------------
                try:
                    idn_dict = {'DUT': dut_idn, 'DMM': dmm_idn}
                    self.multimeter.panel.set_ident(idn_dict)

                    # Setup Source -------------------------------------------------------------------------------------
                    if DUT_choice == 'f5560A':
                        self.setup_f5560A_source()
                    elif DUT_choice == 'f5730A':
                        self.setup_f5730A_source()
                    else:
                        raise ValueError("Invalid DUT selection made!")
                except ValueError:
                    raise
            else:
                raise ValueError('Unable to connect to all instruments.\n')

        except ValueError:
            raise ValueError('Could not connect. Timeout error occurred.')

    def close_instruments(self):
        time.sleep(1)
        self.close_f5560A()
        if self.multimeter.DMM_choice == 'f884xA':
            self.close_f884xA()
        elif self.multimeter.DMM_choice == 'f8588A':
            self.close_f8588A()
        else:
            raise ValueError("Failed to close DMM instrument!"
                             "\nThe DMM selected may not match what is currently in remote.")

        self.connected = False


class DMM_Measurement:
    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, parent):
        self.panel = parent
        self.DUMMY_DATA = False  # can be toggled by the gui
        self.amplitude_good = False  # Flag indicates user input for amplitude value is good (True)
        self.frequency_good = False  # Flag indicates user input for frequency value is good (True)

        self.DUT_choice = ''
        self.DMM_choice = ''
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
            return e

        return True

    def close_instruments(self):
        dut_connected = hasattr(self.M, 'f5560A') or hasattr(self.M, 'f5730A')
        dmm_connected = hasattr(self.M, 'f8588A') or hasattr(self.M, 'f884xA')
        if dut_connected and dmm_connected:
            self.M.close_instruments()

        self.panel.text_DUT_report.Clear()
        self.panel.text_DMM_report.Clear()

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
                    self.panel.error_dialog('\nCheck amplitude and frequency values.')
            elif self.DUMMY_DATA:
                self.DMM_choice = self.panel.DMM_choice
                self.run_selected_function(selection)
            else:
                self.panel.error_dialog('\nConnect to instruments first.')
            self.panel.btn_start.SetLabel('START')
            self.panel.checkbox_autorange.Enable()
            self.panel.checkbox_always_voltage.Enable()

        except ValueError as e:
            message = 'finished with errors.'
            print(f"{message} {'-' * (100 - len(message))}")

            self.panel.flag_complete = True
            self.panel.btn_start.SetLabel('START')
            self.panel.error_dialog(e)
        else:
            message = 'done'
            print(f"{message} {'-' * (100 - len(message))}\n")
            self.panel.flag_complete = True

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
        DUT_choice = self.DUT_choice

        print('Running Single Measurement with Multimeter.')
        self.panel.toggle_controls()
        self.panel.flag_complete = False

        try:
            func(setup=True)
            if not self.DUMMY_DATA:
                if DUT_choice == 'f5560A':
                    self.M.standby_f5560A()
                elif DUT_choice == 'f5730A':
                    self.M.standby_f5730A()
                else:
                    raise ValueError("Invalid DUT selection made!")

        except ValueError:
            self.panel.toggle_controls()
            raise

        self.panel.toggle_controls()
        self.panel.flag_complete = True

    def run_sweep(self, df, func):
        DUT_choice = self.DUT_choice

        print('Running Sweep.')
        self.panel.flag_complete = False
        headers = ['amplitude', 'frequency', 'measured', 'freq_meas', 'std']
        results = np.zeros(shape=(len(df.index), len(headers)))
        t = threading.currentThread()
        for idx, row in df.iterrows():
            if getattr(t, "do_run", True):
                if not self.DUMMY_DATA:
                    self.panel.text_amplitude.SetValue(str(row.amplitude))
                    self.panel.text_frequency.SetValue(str(row.frequency))
                    amplitude, units, ft = self.get_string_value(row.amplitude, str(row.frequency))

                    self.params['amplitude'] = amplitude
                    self.params['frequency'] = ft
                    self.params['units'] = units

                    try:
                        results[idx] = func(setup=True)

                        if DUT_choice == 'f5560A':
                            self.M.standby_f5560A()
                        elif DUT_choice == 'f5730A':
                            self.M.standby_f5730A()
                        else:
                            raise ValueError("Invalid DUT selection made!")

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
        self.panel.flag_complete = True

    # TEST FUNCTIONS ###################################################################################################
    def test_multimeter(self, setup):
        params = self.params

        # SOURCE Parameters --------------------------------------------------------------------------------------------
        amplitude = params['amplitude']
        rms = params['rms']
        if rms != 0:
            amplitude = amplitude / np.sqrt(2)
            print('Provided amplitude converted to RMS.')

        Ft = params['frequency']
        units = params['units']

        # START DATA COLLECTION ----------------------------------------------------------------------------------------
        if not self.DUMMY_DATA:
            always_voltage = params['always_voltage']
            autorange = params['autorange']

            self.setup_dmm(amplitude, setup, always_voltage, units, autorange, Ft)
            self.run_dut(units, amplitude, Ft)
            outval, freqval, std = self.run_dmm()

        else:
            # DUMMY_DATA for random number generation
            freqval, outval, std = Ft, (7 + 1 * np.random.random(1))[0], (0.25 + np.random.random(1))[0]
            if self.DMM_choice == 'f884xA':
                M = dmm1.f884xA_instrument()
            elif self.DMM_choice == 'f8588A':
                M = dmm2.f8588A_instrument()
                # M.setup_f8588A_meter(autorange=True, units=dmm_units, frequency=Ft)
            else:
                raise ValueError("Invalid DMM selection made!")

            print(f"Fluke 5560A operating units: {units}")

        self.panel.update_plot(freqval, outval, std)
        return amplitude, Ft, outval, freqval, std

    def setup_dmm(self, amplitude=0, setup=True, always_voltage=True, units='V', autorange=True, Ft=1000):
        DMM_choice = self.DMM_choice

        # In transimpedance situations where voltage is being measured across a load -----------------------------------
        if always_voltage:
            dmm_units = 'V'
        else:
            dmm_units = units
        print(f"Measured units: {dmm_units}")
        time.sleep(1)

        # START DATA COLLECTION ----------------------------------------------------------------------------------------
        # Usually enters on each new measurement, but only once for each sweep -----------------------------------------
        if DMM_choice == 'f884xA':
            if setup:
                self.M.setup_f884xA_meter(autorange=autorange, units=dmm_units, frequency=Ft)
                self._Ft = Ft

            # During a loop (measurement sweep) we want to catch changes from either AC to DC or vice-versa --------
            elif (Ft * self._Ft) == 0 and Ft != self._Ft:
                self.M.setup_f884xA_meter(autorange=autorange, units=dmm_units, frequency=Ft)
                self._Ft = Ft

        elif DMM_choice == 'f8588A':
            if setup:
                self.M.setup_f8588A_meter(autorange=autorange, units=dmm_units, frequency=Ft)
                self._Ft = Ft

            # During a loop (measurement sweep) we want to catch changes from either AC to DC or vice-versa --------
            elif (Ft * self._Ft) == 0 and Ft != self._Ft:
                self.M.setup_f8588A_meter(autorange=autorange, units=dmm_units, frequency=Ft)
                self._Ft = Ft

        # If manually ranging meter ------------------------------------------------------------------------------------
        if not autorange:
            if DMM_choice == 'f884xA':
                self.M.set_f884xA_range(ideal_range_val=amplitude, units=units, frequency=Ft)
            elif DMM_choice == 'f8588A':
                self.M.set_f8588A_range(ideal_range_val=amplitude, units=units, frequency=Ft)
            else:
                raise ValueError("Invalid DMM selection made!")
            time.sleep(1)

        return True

    def run_dmm(self):
        DUT_choice = self.DUT_choice
        DMM_choice = self.DMM_choice

        try:
            if DMM_choice == 'f884xA':
                outval, freqval, std = self.M.average_f884xA_reading(10)
            elif DMM_choice == 'f8588A':
                outval, freqval, std = self.M.average_f8588A_reading(10)
            else:
                raise ValueError("Invalid DMM selection made!")
        except ValueError:
            print(f'error occurred while connecting to DMM. Placing Fluke {DUT_choice} in Standby.')
            if DUT_choice == 'f5560A':
                self.M.standby_f5560A()
            elif DUT_choice == 'f5730A':
                self.M.standby_f5730A()
            else:
                raise ValueError("Invalid DUT selection made!")
            raise

        return outval, freqval, std

    def run_dut(self, units, amplitude, Ft):
        DUT_choice = self.DUT_choice

        try:
            if DUT_choice == 'f5560A':
                self.M.run_f5560A_source(units, amplitude, Ft)
            elif DUT_choice == 'f5730A':
                self.M.run_f5730A_source(units, amplitude, Ft)
            else:
                raise ValueError("Invalid DUT selection made!")
        except ValueError:
            print('error occurred while connecting to DUT.')
            raise

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
                self.panel.error_dialog('prefix used, but units not specified!')
                self.amplitude_good = False
            elif len(s_split) == 1:
                self.panel.error_dialog('units not specified!')
                self.amplitude_good = False
            else:
                self.panel.error_dialog('improper prefix used!')
                self.amplitude_good = False
        except ValueError:
            self.panel.error_dialog('Invalid amplitude entered!')
            self.amplitude_good = False
            pass

        # CHECK IF FREQUENCY USER INPUT IS VALID
        try:
            frequency = float(freq_string)
        except ValueError:
            self.panel.error_dialog(f"The value {freq_string} is not a valid frequency!")
            self.frequency_good = False
        else:
            self.frequency_good = True

        return amplitude, units, frequency
