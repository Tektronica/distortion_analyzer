import VisaClient
import time

instruments = {'f8588A': {'address': '10.205.92.156', 'port': '3490', 'gpib': '6', 'mode': 'SOCKET'}}


########################################################################################################################
def to_float(s):
    f = 0.0
    try:
        f = float(s)
    except ValueError:
        print('[ERROR] Measurement could not be converted to float. Possible issues with configuration.')
        pass
    return f


class f8588A_instrument:
    """"""

    def __init__(self):
        super().__init__()
        self.measurement = []
        self.f8588A_IDN = ''
        self.connected = False

    def connect_to_f8588A(self, instr_id):
        # ESTABLISH COMMUNICATION TO INSTRUMENTS -----------------------------------------------------------------------
        self.f8588A = VisaClient.VisaClient(instr_id)  # Fluke 8588A

        if self.f8588A.okay:
            self.f8588A_IDN = self.f8588A.query('*IDN?')
        else:
            print('\nUnable to connect to the Fluke 8588A. Check software configuration, ensure instrument are in'
                  'appropriate mode, and consider power cycling the suspected instrument\n')

    def hello(self, s):
        print(f'hello, {s}')
        print(self.f8588A)

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
    def close(self):
        time.sleep(1)
        self.f8588A.close()


# Run
if __name__ == "__main__":
    output, mode = 'VOLT', 'AC'
    instr = f8588A_instrument(0)

    instr.connect(instruments)
    instr.setup_meter(output, mode)

    outval, freqval = instr.read_meter(mode)
    print(f"\nOutput: {outval}\nFrequency: {freqval} Hz")

    instr.close()
