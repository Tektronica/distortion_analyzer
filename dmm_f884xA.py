import VisaClient
import time
import numpy as np

instruments = {'f884xA': {'address': '10.205.92.156', 'port': '3490', 'gpib': '8', 'mode': 'SOCKET'}}
INFO = "file:///C:/Users/rholle/AppData/Local/Temp/8845A___pmeng0300.pdf"


########################################################################################################################
def to_float(string_val):
    try:
        float_val = float(string_val)
    except ValueError:
        print('[ERROR] Measurement could not be converted to float. Possible issues with configuration.')
        raise ValueError('Prospective measurement obtained by the Fluke 884xA could not be converted to float. Suspect '
                         'null value or over-range')
    else:
        return float_val


class f884xA_instrument:

    def __init__(self):
        self.measurement = []
        self.f884xA_IDN = ''
        self.f884xA_connected = False

        self.setup_complete = True
        self.output_type = 'VOLT'
        self.mode = 'DC'

    def connect_to_f884xA(self, instr_id):
        # ESTABLISH COMMUNICATION TO INSTRUMENTS -----------------------------------------------------------------------
        self.f884xA = VisaClient.VisaClient(instr_id)  # Fluke 8588A

        if self.f884xA.healthy:
            self.f884xA_connected = True
            try:
                self.f884xA_IDN = self.f884xA.query('*IDN?')
                self.f884xA.write("SYSTem:REMote")
            except ValueError:
                raise
        else:
            print('Unable to connect to the Fluke 884xA. Check software configuration, ensure instrument is'
                  'connected properly or not being used by another remote session. Consider power cycling the '
                  'suspected instrument\n')

    # SETUP METER ######################################################################################################
    def setup_f884xA_meter(self, autorange=True, **kwds):
        """
        method accepts several keyword pairs as arguments. Specify at least two of the following:
            + 'output_type' ('VOLT' or 'CURR') and 'mode' ('AC' or 'DC')
            + 'output_type' ('VOLT' or 'CURR') and 'frequency' (a float value >= 0)
            + 'units' ('A' or 'V') and 'frequency' (a float value >= 0)

        :param autorange: True or False
        :param kwds: dictionary containing at least two of the following keys: 'output', 'mode', 'units', 'frequency'
        :return: True if completion successful
        """
        self.output_type, self.mode = self._get_function_params(**kwds)

        try:
            self.f884xA.write(f'CONF:{self.output_type}:{self.mode}')
            if autorange:
                self.f884xA.write(f'{self.output_type}:{self.mode}:RANGE:AUTO ON')
            else:
                # Set Fluke 884xA to largest range for internal protection by default.
                self.set_f884xA_range(ideal_range_val=1000, output=self.output_type, mode=self.mode)
            time.sleep(1)
            self.setup_complete = True
            return True  # returns true if setup completes succesfully

        except Exception as e:
            print('setup_meter for the Fluke 884xA failed. What error was thrown here?')
            print(e)
            raise ValueError('Setting up Fluke 884xA failed.\nCheck connection and configuration to instrument.')

    def get_f884xA_range(self):
        """
        A convenience function for determining the appropriate range for a measurement. Use-case is determining the
        range of an automated measurement without requiring auto-range. This reduces loading non-linearity associated
        with switching ranges. This method allows the meter to range correctly before performing the measurement.
        :return:
        """
        dmm_range = to_float(self.f884xA.query(f'{self.output_type}:{self.mode}:RANGE?'))
        return dmm_range

    def get_rate(self):
        rate = self.f884xA.query(f'{self.output_type}:{self.mode}:RATE?')
        return rate

    def set_rate(self, new_rate):
        """
        Returns <speed> as "S" for slow (2.5 readings/second), "M" for medium (5.0 readings/second), or "F" for
        fast (20 readings/second).
        """
        if new_rate in ("S", "M", "F"):
            self.f884xA.write(f'{self.output_type}:{self.mode}:RATE {new_rate}')
            return True
        else:
            rate = self.get_rate()
            raise ValueError(f"Failed to set new measurement rate to {new_rate}. Please specify one of the following: "
                             f"S, M, F.\nCurrent rate set to {rate}")

    def _get_function_params(self, **kwds):
        """
        method accepts several keyword pairs as arguments. Specify at least two of the following:
            + 'output_type' ('VOLT' or 'CURR') and 'mode' ('AC' or 'DC')
            + 'output_type' ('VOLT' or 'CURR') and 'frequency' (a float value >= 0)
            + 'units' ('A' or 'V') and 'frequency' (a float value >= 0)
        :param kwds: dictionary containing at least two of the following: 'output_type', 'mode', 'units', 'frequency'
        :return: output and mode used for setting up the Fluke 884xA
        """
        # SORT through what keywords were provided =====================================================================
        keys = kwds.keys()

        # provided output and mode -------------------------------------------------------------------------------------
        if keys >= {'output_type', 'mode'}:
            output_type = kwds['output_type']
            mode = kwds['mode']

        # provided frequency and either output or units ----------------------------------------------------------------
        elif 'frequency' in keys:
            if kwds['frequency'] > 0:
                mode = 'AC'
            else:
                mode = 'DC'

            # provided output ------------------------------------------------------------------------------------------
            if 'output_type' in keys and kwds['output_type'] in ('VOLT', 'CURR'):
                output_type = kwds['output_type']

            # provided units -------------------------------------------------------------------------------------------
            elif 'units' in keys and kwds['units'] in ('A', 'V'):
                if kwds['units'] == 'V':
                    output_type = 'VOLT'
                else:
                    output_type = 'CURR'
            else:
                raise ValueError("Could not determine appropriate mode ('VOLT' or 'CURR') for meter from "
                                 "the provided arguments!")
        else:
            raise ValueError("Provided keywords or keyword values are insufficient for determining appropriate output "
                             "and mode values for the Fluke 884xA configuration!")

        return output_type, mode

    # RANGE ############################################################################################################
    def determine_f884xA_range(self, ideal_range_val: float, output_type: str):
        # Set multiplier based on measurement rate ---------------------------------------------------------------------
        rate = self.get_rate()

        if rate == "S":
            # Slow measurement rate
            multiplier = 1
        else:
            # Fast or Medium measurement rate
            multiplier = 3

        # overange is 20%. Max value must be less than (1 + 20%) of nominal range --------------------------------------
        if output_type.capitalize() in ("A", "CURR"):
            if ideal_range_val < 10e-3 * multiplier * (1 + 0.2):
                range_val = 1
                range_string = '30mA'
            elif ideal_range_val < 100e-3 * (1 + 0.2):
                range_val = 2
                range_string = '100mA'
            else:
                range_val = 3
                range_string = '10A'

        elif output_type.capitalize() in ('V', "VOLT"):
            if ideal_range_val < 100e-3 * multiplier * (1 + 0.2):
                range_val = 1
                range_string = '100mV'
            elif ideal_range_val < 1 * multiplier * (1 + 0.2):
                range_val = 2
                range_string = '1V'
            elif ideal_range_val < 10 * multiplier * (1 + 0.2):
                range_val = 3
                range_string = '10V'
            elif ideal_range_val < 100 * multiplier * (1 + 0.2):
                range_val = 4
                range_string = '100V'
            else:
                range_val = 5
                range_string = '1000VDC, 750VAC'
        else:
            range_val = 5
            range_string = '1000VDC, 750VAC'
            print("Failed to find appropriate range. Setting to default.")

        return range_val, range_string

    def set_f884xA_range(self, ideal_range_val, **kwds):
        """
        method accepts several keyword pairs as arguments. Specify at least two of the following:
            + 'output' ('VOLT' or 'CURR') and 'mode' ('AC' or 'DC')
            + 'output' ('VOLT' or 'CURR') and 'frequency' (a float value >= 0)
            + 'units' ('A' or 'V') and 'frequency' (a float value >= 0)

        Note: Meter displays overload and sends 9.9000 E+37 over the remote interface when input signal is greater
        than the selected range can measure.

        :param ideal_range_val: user defined range to set Fluke 884xA to
        :param kwds: dictionary containing at least two of the following: 'output_type', 'mode', 'units', 'frequency'
        :return: True iff range is set successfully
        """
        # Get function parameters for Fluke 884xA ----------------------------------------------------------------------
        self.output_type, self.mode = self._get_function_params(**kwds)  # ('VOLT', 'AC')

        # Causes the meter to exit autoranging on the primary display and enter manual ranging. The present range ------
        # becomes the selected range. ----------------------------------------------------------------------------------
        self.f884xA.write(f"{self.output_type}:{self.mode}:FIXED")

        # Calculate the closest range for measurement ------------------------------------------------------------------
        range_val, range_string = self.determine_f884xA_range(ideal_range_val, self.output_type)

        # Set new range ------------------------------------------------------------------------------------------------
        try:
            self.f884xA.write(f"{self.output_type}:{self.mode}:RANGE {range_val}")
            print(f"Successfully set range of Fluke 884xA to {range_val} ({range_string})")
            return True
        except Exception:
            raise ValueError(f"Failed to set range to {range_val} ({range_string})")

    # RETRIEVE MEASUREMENT #############################################################################################
    def read_f884xA_meter(self):
        if self.setup_complete:
            time.sleep(1)
            # Initiate Triggering - (MEASure? or READ? or INITiate)
            self.f884xA.write('INIT')
            time.sleep(0.2)

            # FETCh1? Returns measurements from the primary display
            outval = to_float(self.f884xA.query('FETCh1?'))
            dmm_range = self.get_f884xA_range()

            if self.mode == 'AC':
                # FETCh2? Returns readings from the secondary display
                freqval = to_float(self.f884xA.query('FETCh2?'))
            else:
                freqval = 0.0

            return outval, freqval, dmm_range
        else:
            raise ValueError('Fluke 884xA has not been configured for measurement.')

    def average_f884xA_reading(self, samples=10, dt=0.1):
        readings = np.zeros(samples)
        freqval = 0.0

        for idx in range(samples):
            readings[idx], freqval, dmm_range = self.read_f884xA_meter()
            time.sleep(dt)

        mean = readings.mean()
        std = np.sqrt(np.mean(abs(readings - mean) ** 2))

        return mean, freqval, std

    ####################################################################################################################
    def close_f884xA(self):
        if self.f884xA_connected:
            time.sleep(1)
            self.f884xA.close()
            self.f884xA_connected = False


# Run
if __name__ == "__main__":
    instr = f884xA_instrument()
    instr.connect_to_f884xA(instruments)

    # 1. Setup the meter for measurement
    instr.setup_f884xA_meter(autorange=True, output_type='VOLT', mode='AC')
    # 2. Get Average Reading
    outval, freqval, std = instr.average_f884xA_reading(samples=10, dt=0.1)

    print(f"\nOutput: {outval}\nFrequency: {freqval} Hz")

    instr.close_f884xA()
