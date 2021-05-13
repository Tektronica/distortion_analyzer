import VisaClient
import time
import numpy as np

DIGITIZER_SAMPLING_FREQUENCY = 5e6
instruments = {'f8588A': {'address': '10.205.92.156', 'port': '3490', 'gpib': '6', 'mode': 'SOCKET'}}


########################################################################################################################
def to_float(string_val):
    try:
        float_val = float(string_val)
    except ValueError:
        print('[ERROR] Measurement could not be converted to float. Possible issues with configuration.')
        raise ValueError('Prospective measurement obtained by the Fluke 8588A could not be converted to float. Suspect '
                         'null value or over-range')
    else:
        return float_val


def getSamplingFrequency(f0, bw=100e3):
    """
    The maximum detectable frequency resolved by an FFT is defined as half the sampling frequency.
    :param bw: the maximum resolved frequency of the fft.
    :return: sampling rate, fs
    """
    # Ideal sampling frequency
    _Fs = max(2 * bw, 100 * f0)

    # An integer number of samples averaged per measurement determines actual sampling frequency
    N = max(round(DIGITIZER_SAMPLING_FREQUENCY / _Fs), 1)
    Fs = DIGITIZER_SAMPLING_FREQUENCY / N
    return Fs


def getStuff(f0, LDF=100, BW=100e3, windfunc='rectangular'):
    # Ideal sampling frequency
    _Fs = max(2 * BW, 10 * f0)

    if windfunc == 'rectangular':
        K = 2
    elif windfunc in ('bartlett', 'hanning', 'hamming'):
        K = 4
    elif windfunc == 'blackman':
        K = 6
    else:
        raise ValueError('Not a valid windowing function.')

    res = LDF / K
    Navg = np.ceil(min(DIGITIZER_SAMPLING_FREQUENCY / (res * f0), DIGITIZER_SAMPLING_FREQUENCY / _Fs))
    print(Navg)
    f0 = round(DIGITIZER_SAMPLING_FREQUENCY / (res * Navg), 2)
    Fs = DIGITIZER_SAMPLING_FREQUENCY / Navg

    N = int(np.ceil(Fs / res))
    ldf = round(K * (Fs / N), 3)
    print(ldf)
    return f0, Fs, N


def get_aperture(Fs, N):
    """
    The aperture is the duration after trigger where samples at a rate of 5 MHz are averaged together.

    The aperture can be set from 0 ns to 3 ms in 200 ns increments up to 1 ms, and 100 μs increments from 1 ms to 3 ms.

    Since the minimum duration to trigger one sample is 200ns, an aperture length greater than 0 ns allows more than one
    sample to be captured and averaged by the digitizer. In a sense, increasing the aperture lowers the sampling
    frequency of the digitizer.

    The entire process for one reading is 200 ns, which gives a maximum trigger rate of 5 MHz. The aperture can be
    set from 0 ns to 3 ms in 200 ns increments up to 1 ms, and 100 μs increments from 1 ms to 3 ms. Greater aperture
    length decreases sample rate.
        Fs = 5MHz
        Ts = 200ns
        Aperture = 600ns --> 4 points averaged for each sample since:200ns + 3 * (200ns)
        Apparent sample time: 200ns + 600ns
        Apparent sample rate: 1/(800ns) = 1.25MHz

    Aperture	Time	        Samples (#)	    Fs
    --------------------------------------------------------
    0ns	        200ns	        1	            5 MHz
    200ns	    200ns + 200ns	2	            2.5 MHz
    400ns	    400ns + 200ns	3 	            1.6667 MHz
    600ns	    600ns + 200ns	4	            1.25 MHz
    800ns	    800ns + 200ns	5	            1 MHz
    1us	        1us + 0.2us	    6	            833.33kHz
    --------------------------------------------------------

    """

    """
    Fs = Ft * N / cycles  # The desired sampling frequency
    """
    Navg = max(round(DIGITIZER_SAMPLING_FREQUENCY / Fs), 1)  # The number of samples averaged per trigger

    # The duration of the digitizer averaging per trigger
    aperture = max(200e-9 * (Navg - 1), 0)
    if aperture > 1e-3:
        aperture = max(100e-6 * (Navg - 1), 0)

    runtime = N * (aperture + 200e-9)  # The total runtime

    return aperture, runtime


class f8588A_instrument:
    """"""

    def __init__(self):
        super().__init__()
        self.measurement = []
        self.f8588A_IDN = ''
        self.f8588_connected = False

        self.setup_complete = True
        self.output_type = 'VOLT'
        self.mode = 'DC'

    def connect_to_f8588A(self, instr_id):
        # ESTABLISH COMMUNICATION TO INSTRUMENTS -----------------------------------------------------------------------
        self.f8588A = VisaClient.VisaClient(instr_id)  # Fluke 8588A

        if self.f8588A.healthy:
            self.f8588_connected = True
            try:
                self.f8588A_IDN = self.f8588A.query('*IDN?')
            except ValueError:
                raise
        else:
            print('Unable to connect to the Fluke 8588A. Check software configuration, ensure instrument is'
                  'connected properly or not being used by another remote session. Consider power cycling the '
                  'suspected instrument\n')

    # SETUP METER ######################################################################################################
    def setup_f8588A_meter(self, autorange=True, **kwds):
        """
        method accepts several keyword pairs as arguments. Specify at least two of the following:
            + 'output_type' ('VOLT' or 'CURR') and 'mode' ('AC' or 'DC')
            + 'output_type' ('VOLT' or 'CURR') and 'frequency' (a float value >= 0)
            + 'units' ('A' or 'V') and 'frequency' (a float value >= 0)

        :param autorange: True or False
        :param kwds: dictionary containing at least two of the following: 'output_type', 'mode', 'units', 'frequency'
        :return: True if completion successful
        """

        self.output_type, self.mode = self._get_function_params(**kwds)  # Example: ('VOLT', 'AC')

        try:
            self.f8588A.write(f'CONF:{self.output_type}:{self.mode}')
            if autorange:
                self.f8588A.write(f'{self.output_type}:{self.mode}:RANGE:AUTO ON')
            else:
                # Set Fluke 884xA to largest range for internal protection by default.
                self.set_f8588A_range(ideal_range_val=1000, output_type=self.output_type, mode=self.mode)
            time.sleep(1)
            return True

        except Exception as e:
            print('setup_meter for the Fluke 8588A failed. What error was thrown here?')
            print(e)
            raise ValueError('Setting up Fluke 8588A failed.\nCheck connection and configuration to instrument.')

    def get_f8588A_range(self):
        """
        A convenience function for determining the appropriate range for a measurement. Use-case is determining the
        range of an automated measurement without requiring auto-range. This reduces loading non-linearity associated
        with switching ranges. This method allows the meter to range correctly before performing the measurement.
        :return:
        """
        dmm_range = to_float(self.f8588A.query(f'{self.output_type}:{self.mode}:RANGE?'))
        return dmm_range

    def _get_function_params(self, **kwds):
        """
        method accepts several keyword pairs as arguments. Specify at least two of the following:
            + 'output_type' ('VOLT' or 'CURR')  and  'mode' ('AC' or 'DC')
            + 'output_type' ('VOLT' or 'CURR')  and  'frequency' (a float value >= 0)
            + 'units' ('A' or 'V')              and  'frequency' (a float value >= 0)
            + 'units' ('A' or 'V')              and  'mode' ('AC' or 'DC')

        :param kwds: dictionary containing at least two of the following: 'output_type', 'mode', 'units', 'frequency'
        :return: output and mode used for setting up the Fluke 884xA
        """
        # SORT through what keywords were provided =====================================================================
        keys = kwds.keys()

        # provided mode and either 'output type' or 'units' ------------------------------------------------------------
        if 'mode' in keys:
            mode = kwds['mode']

            if 'output_type' in keys and kwds['output_type'] in ('VOLT', 'CURR'):
                output_type = kwds['output_type']

            elif 'units' in keys:
                if kwds['units'] == 'A':
                    output_type = 'CURR'
                else:
                    output_type = 'VOLT'
            else:
                raise ValueError("While the 'mode' parameter was specified, insufficient or missing values for either "
                                 "'output type' or "
                                 "'units'.")

        # provided frequency and either 'output type' or 'units' -------------------------------------------------------
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
                raise ValueError("The 'frequency' parameter was able to identify an operating 'mode' for the Fluke "
                                 "8588A. However, insufficient or missing values for either 'output type' or "
                                 "'units'.")
        else:
            raise ValueError("Provided keywords or keyword values are insufficient for determining appropriate output "
                             "and mode values for the Fluke 8588A configuration!")

        return output_type, mode

    # RANGE ############################################################################################################
    def determine_f8588A_range(self, ideal_range_val: float, output_type: str):
        # overange is 20%. Max value must be less than (1 + 20%) of nominal range --------------------------------------
        if output_type.upper() in ('A', 'CURR', 'CURRENT'):
            if ideal_range_val < 10e-6 * (1 + 0.2):
                range_val = 10e-6
                range_string = '10uA'
            elif ideal_range_val < 100e-6 * (1 + 0.2):
                range_val = 100e-6
                range_string = '100uA'
            elif ideal_range_val < 1e-3 * (1 + 0.2):
                range_val = 1e-3
                range_string = '1mA'
            elif ideal_range_val < 10e-3 * (1 + 0.2):
                range_val = 10e-3
                range_string = '10mA'
            elif ideal_range_val < 100e-3 * (1 + 0.2):
                range_val = 100e-3
                range_string = '100mA'
            elif ideal_range_val < 1 * (1 + 0.2):
                range_val = 1
                range_string = '1A'
            elif ideal_range_val < 10 * (1 + 0.2):
                range_val = 10
                range_string = '10A'
            else:
                range_val = 30
                range_string = '30A'

        elif output_type.upper() in ('V', 'VOLT', 'VOLTAGE'):
            if ideal_range_val < 0.10 * (1 + 0.2):
                range_val = 0.1
                range_string = '100mV'
            elif ideal_range_val < 1.0 * (1 + 0.2):
                range_val = 1
                range_string = '1V'
            elif ideal_range_val < 10 * (1 + 0.2):
                range_val = 10
                range_string = '10V'
            elif ideal_range_val < 100 * (1 + 0.2):
                range_val = 100
                range_string = '100V'
            else:
                range_val = 1000
                range_string = '1000V'
        else:
            range_val = 1000
            range_string = '1000V'
            print("Failed to find appropriate range. Setting to default.")

        return range_val, range_string

    def set_f8588A_range(self, ideal_range_val, **kwds):
        """
        method accepts several keyword pairs as arguments. Specify at least two of the following:
            + 'output_type' ('VOLT' or 'CURR') and 'mode' ('AC' or 'DC')
            + 'output_type' ('VOLT' or 'CURR') and 'frequency' (a float value >= 0)
            + 'units' ('A' or 'V') and 'frequency' (a float value >= 0)

        Note: Meter displays overload and sends 9.9000 E+37 over the remote interface when input signal is greater
        than the selected range can measure.

        :param ideal_range_val: user defined range to set Fluke 884xA to
        :param kwds: dictionary containing at least two of the following: 'output_type', 'mode', 'units', 'frequency'
        :return: True iff range is set successfully
        """
        # Get function parameters for Fluke 8588A ----------------------------------------------------------------------
        self.output_type, self.mode = self._get_function_params(**kwds)  # ('VOLT', 'AC')

        # Causes the meter to exit autoranging on the primary display and enter manual ranging. The present range ------
        # becomes the selected range. ----------------------------------------------------------------------------------
        self.f8588A.write(f"{self.output_type}:{self.mode}:FIXED")

        # Calculate the closest range for measurement ------------------------------------------------------------------
        range_val, range_string = self.determine_f8588A_range(ideal_range_val, self.output_type)

        # Set new range ------------------------------------------------------------------------------------------------
        try:
            self.f8588A.write(f"{self.output_type}:{self.mode}:RANGE {range_val}")
            print(f"Successfully set range of Fluke 884xA to {range_val} ({range_string})")
            return True
        except Exception:
            raise ValueError(f"Failed to set range to {range_val} ({range_string})")

    # RETRIEVE MEASUREMENT #############################################################################################
    def read_f8588A_meter(self):
        """
        The secondary readings available for AC voltage and current are: “FREQuency”,
        “PERiod”, "PK to Pk", "Crest Factor", "Pos Peak", "Neg peak", “OFF” (turns off
        secondary readings). Additionally, for ACI external shunt and DCI external shunt,
        the secondary reading can be "Shunt Voltage" or "Power coefficient". See
        FETCh?.

        :return: primary and secondary displayed values, and RANGE
        """
        if self.setup_complete:
            time.sleep(1)
            self.f8588A.write('INIT:IMM')

            # Primary result = 1 (page 17 of 8588A's programmers manual)
            # A return of 9.91E+37 indicates there is not a valid value to return (NaN - not a number)
            # time delay prevents NaN result
            time.sleep(0.2)
            outval = to_float(self.f8588A.query('FETCH? 1'))
            dmm_range = self.get_f8588A_range()

            if self.mode == 'AC':
                # FREQuency = 2 (page 17 of 8588A's programmers manual)
                freqval = to_float(self.f8588A.query('FETCH? 2'))
            else:
                freqval = 0.0

            return outval, freqval, dmm_range
        else:
            raise ValueError('Fluke 8588A has not been configured for measurement properly or has been disconnected.')

    def average_f8588A_reading(self, samples=10, dt=0.1):
        readings = np.zeros(samples)
        freqval = 0.0

        for idx in range(samples):
            readings[idx], freqval, dmm_range = self.read_f8588A_meter()
            time.sleep(dt)

        mean = readings.mean()
        std = np.sqrt(np.mean(abs(readings - mean) ** 2))

        return mean, freqval, std

    # DIGITIZER ########################################################################################################
    def setup_digitizer(self, units, ideal_range_val, coupling, filter_val, N, aperture):
        # determine the appropriate digitzer mode from output_type. Setting the mode here doesn't matter
        self.output_type, self.mode = self._get_function_params(units=units, mode='AC')

        # Calculate the closest range for measurement ------------------------------------------------------------------
        range_val, range_string = self.determine_f8588A_range(ideal_range_val, self.output_type)  # (0.1, '0.1A')

        self.f8588A.write('*RST')

        try:
            self.f8588A.write(f':FUNC "DIGitize:{self.output_type}" ')
            self.f8588A.write(f':DIGitize:{self.output_type}:RANGe {range_val}')
            print(f"Successfully set range of Fluke 8588A to {range_string}")

            # :FILTer OFF|100Khz|3MHZ
            if filter_val not in ('None', '2MHz', '2.4MHz'):
                self.f8588A.write(f':DIGitize:FILTer {filter_val}')
            else:
                self.f8588A.write(f':DIGitize:FILTer OFF')

            # AC1M = AC Coupling, 1Mohm input impedance
            # AC10M = AC Coupling, 10Mohm input impedance
            # DC1M = DC Coupling, 1Mohm input impedance
            # DC10M - DC Coupling, 10 Mohm input impedance
            # DCAuto = DC Coupling, maximum avialable input impedance
            self.f8588A.write(f':DIGitize:VOLTage:COUPling:SIGNal {coupling}')

            # f8588A has a 5MHz sampled rate clock. adjusting aperture time,
            # averages more points, which adjusts sample rate
            self.f8588A.write(f':DIGitize:APERture {aperture}')
            self.f8588A.write('TRIGger:RESet')
            self.f8588A.write(f'TRIGGER:COUNT {N}')
            self.f8588A.write('TRIGger:DELay:AUTO OFF')
            self.f8588A.write('TRIGGER:DELay 0')
            return True  # returns true if digitizer setup completes succesfully

        except Exception as e:
            print('setup_digitizer for the Fluke 8588A failed. What error was thrown here?')
            print(e)
            raise ValueError('Setting up digitizer for Fluke 8588A failed.'
                             '\nCheck connection and configuration to instrument.')

    def retrieve_digitize(self):
        self.f8588A.write('INIT:IMM')
        time.sleep(5)
        read = self.f8588A.query('FETCH?')
        buffer = [float(i) for i in read.split(',')]
        return buffer

    ####################################################################################################################
    def close_f8588A(self):
        if self.f8588_connected:
            time.sleep(1)
            self.f8588A.close()
            self.f8588_connected = False


# Run
if __name__ == "__main__":
    DUMMY_DATA = True

    if not DUMMY_DATA:
        instr = f8588A_instrument()
        instr.connect_to_f8588A(instruments)

        # 1. Setup the meter for measurement
        instr.setup_f8588A_meter(autorange=True, output_type='VOLT', mode='AC')
        # 2. Get Average Reading
        outval, freqval, std = instr.average_f8588A_reading(samples=10, dt=0.1)

        print(f"\nOutput: {outval}\nFrequency: {freqval} Hz")

        instr.close_f8588A()

    else:
        instr = f8588A_instrument()
        output_type, mode = instr._get_function_params(units='A', mode='AC')
        print(output_type, mode)

        try:
            instr.setup_digitizer(units='A', ideal_range_val=1,
                                  filter_val='100kHz', N=20000, aperture=0)
        except AttributeError:
            print("AttributeError was raised. The instrument isn't currently connected.")
