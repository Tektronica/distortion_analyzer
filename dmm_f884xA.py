import VisaClient
import time
import numpy as np

instruments = {'f884xA': {'address': '10.205.92.156', 'port': '3490', 'gpib': '8', 'mode': 'SOCKET'}}


########################################################################################################################
def to_float(s):
    try:
        f = float(s)
    except ValueError:
        print('[ERROR] Measurement could not be converted to float. Possible issues with configuration.')
        raise ValueError('Prospective measurement obtained by the Fluke 884xA could not be converted to float. Suspect '
                         'null value or over-range')
    else:
        return f


class f884xA_instruments:

    def __init__(self):
        self.measurement = []
        self.f884xA_IDN = ''
        self.f884xA_connected = False
        self.setup = True
        self.mode = 'DC'

    def connect_to_f884xA(self, instr_id):
        # ESTABLISH COMMUNICATION TO INSTRUMENTS -----------------------------------------------------------------------
        self.f884xA = VisaClient.VisaClient(instr_id)  # Fluke 8588A

        if self.f884xA.healthy:
            self.f884xA_connected = True
            try:
                self.f884xA_IDN = self.f884xA.query('*IDN?')
            except ValueError:
                raise
        else:
            print('Unable to connect to the Fluke 884xA. Check software configuration, ensure instrument is'
                  'connected properly or not being used by another remote session. Consider power cycling the '
                  'suspected instrument\n')

    ####################################################################################################################
    def setup_meter(self, output='CURR', mode='AC'):
        self.mode = mode
        try:
            self.f884xA.write(f'CONF:{output}:{mode}')
            self.f884xA.write(f'{output}:{mode}:RANGE:AUTO ON')
            time.sleep(1)
        except Exception as e:
            print('setup_meter for 884xA failed. What error was thrown here?')
            print(e)
            raise ValueError('Setting up Fluke 884xA failed. Check connection and configuration to instrument.')
        else:
            self.setup = True

    def get_range(self, output, mode):
        """
        A convenience function for determining the appropriate range for a measurement. Use-case is determining the
        range of an automated measurement without requiring auto-range. This reduces loading non-linearity associated
        with switching ranges. This method allows the meter to range correctly before performing the measurement.
        :param output: The intended amplitude of measurement
        :param mode: The intended function (AC or DC) of measurement
        :return:
        """
        dmm_range = to_float(self.f884xA.query(f'{output}:{mode}:RANGE?'))
        return dmm_range

    ####################################################################################################################
    def read_meter(self):
        if self.setup:
            freqval = 0.0
            time.sleep(1)
            self.f884xA.write('INIT:IMM')
            time.sleep(0.2)

            # FETCh1? Returns measurements from the primary display
            outval = to_float(self.f884xA.query('FETCh1?'))

            if self.mode == 'AC':
                # FETCh2? Returns readings from the secondary display
                freqval = to_float(self.f884xA.query('FETCh2?'))

            return outval, freqval
        else:
            raise ValueError('Fluke 884xA has not been configured for measurement.')

    def average_reading(self, N, dt=0.1):
        readings = np.zeros(N)
        freqval = 0.0

        for idx in range(N):
            readings[idx], freqval = self.read_meter()
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
    output, mode = 'VOLT', 'AC'
    instr = f884xA_instruments()

    instr.connect_to_f884xA(instruments)

    instr.setup_meter(output, mode)
    outval, freqval = instr.read_meter()
    print(f"\nOutput: {outval}\nFrequency: {freqval} Hz")

    instr.close_f884xA()
