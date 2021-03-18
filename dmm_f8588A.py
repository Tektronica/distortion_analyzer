import VisaClient
import time

DIGITIZER_SAMPLING_FREQUENCY = 5e6
instruments = {'f8588A': {'address': '10.205.92.156', 'port': '3490', 'gpib': '6', 'mode': 'SOCKET'}}


########################################################################################################################
def to_float(s):
    f = 0.0
    try:
        f = float(s)
    except ValueError:
        print('[ERROR] Measurement could not be converted to float. Possible issues with configuration.')
        raise ValueError('Prospective measurement obtained by the Fluke 8588A could not be converted to float. Suspect '
                         'null value or over-range')
    else:
        return f


def getSamplingFrequency(F0, bw=100e3):
    """
    The maximum detectable frequency resolved by an FFT is defined as half the sampling frequency.
    :param bw: the maximum resolved frequency of the fft.
    :return: sampling rate, fs
    """
    # Ideal sampling frequency
    _Fs = max(2*bw, 100 * F0)

    # An integer number of samples averaged per measurement determines actual sampling frequency
    N = max(round(DIGITIZER_SAMPLING_FREQUENCY / _Fs), 1)
    Fs = DIGITIZER_SAMPLING_FREQUENCY / N
    return Fs


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
            print('\nUnable to connect to the Fluke 8588A. Check software configuration, ensure instrument are in'
                  'appropriate mode, and consider power cycling the suspected instrument\n')

    ####################################################################################################################
    def setup_meter(self, output='CURR', mode='AC'):
        """
        The secondary readings available for AC voltage and current are: “FREQuency”,
        “PERiod”, "PK to Pk", "Crest Factor", "Pos Peak", "Neg peak", “OFF” (turns off
        secondary readings). Additionally, for ACI external shunt and DCI external shunt,
        the secondary reading can be "Shunt Voltage" or "Power coefficient". See
        FETCh?.

        :param output: CURRent or VOLTage
        :param mode: AC or DC
        :return:
        """
        self.f8588A.write(f'CONF:{output}:{mode}')
        self.f8588A.write(f'{output}:{mode}:RANGE:AUTO ON')
        time.sleep(1)

    def read_meter(self, output, mode):
        freqval = 0.0
        time.sleep(1)
        self.f8588A.write('INIT:IMM')

        # Primary result = 1 (page 17 of 8588A's programmers manual)
        # A return of 9.91E+37 indicates there is not a valid value to return (NaN - not a number)
        # time delay prevents NaN result
        time.sleep(0.2)
        outval = to_float(self.f8588A.query('FETCH? 1'))
        dmm_range = to_float(self.f8588A.query(f'{output}:{mode}:RANGE?'))

        if mode == 'AC':
            # FREQuency = 2 (page 17 of 8588A's programmers manual)
            freqval = to_float(self.f8588A.query('FETCH? 2'))

        return outval, dmm_range, freqval

    ####################################################################################################################
    def setup_digitizer(self, mode, oper_range, filter_val, N, aperture):
        # f8588A has a 5MHz sampled rate clock. adjusting aperture time, averages more points, which adjusts sample rate
        self.f8588A.write('*RST')
        if mode in ('A', 'a'):
            self.f8588A.write(':FUNC "DIGitize:CURRent" ')
            self.f8588A.write(f':DIGitize:CURRent:RANGe {oper_range}')
        else:
            self.f8588A.write(':FUNC "DIGitize:VOLTage" ')
            self.f8588A.write(f':DIGitize:VOLTage:RANGe {oper_range}')
        self.f8588A.write(f':DIGitize:FILTer {filter_val}')
        self.f8588A.write(f':DIGitize:APERture {aperture}')
        self.f8588A.write('TRIGger:RESet')
        self.f8588A.write(f'TRIGGER:COUNT {N}')
        self.f8588A.write('TRIGger:DELay:AUTO OFF')
        self.f8588A.write('TRIGGER:DELay 0')

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
    output, mode = 'VOLT', 'AC'
    instr = f8588A_instrument()

    instr.connect_to_f8588A(instruments)
    instr.setup_meter(output, mode)

    outval, dmm_range, freqval = instr.read_meter(mode)
    print(f"\nOutput: {outval}\nFrequency: {freqval} Hz")

    instr.close_f8588A()
