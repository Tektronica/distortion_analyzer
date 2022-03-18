import VisaClient
import time

instruments = {'f5730A': {'address': '129.196.136.130', 'port': '3490', 'gpib': '6', 'mode': 'SOCKET'}}


########################################################################################################################
class f5730A_instrument:
    """"""

    def __init__(self):
        super().__init__()
        self.measurement = []
        self.f5730A_IDN = ''
        self.f5730_connected = False

    def connect_to_f5730A(self, instr_id):
        # ESTABLISH COMMUNICATION TO INSTRUMENT -----------------------------------------------------------------------
        self.f5730A = VisaClient.VisaClient(instr_id)  # Fluke 5730A

        if self.f5730A.healthy:
            self.f5730_connected = True
            self.f5730A_IDN = self.f5730A.query('*IDN?')
        else:
            print('[X] Unable to connect to the Fluke 5730A. Check software configuration, ensure instrument is'
                  '\nconnected properly or not being used by another remote session. Consider power cycling the '
                  '\nsuspected instrument\n')

    def setup_f5730A_source(self):
        self.f5730A.write('*RST')
        time.sleep(1)
        self.f5730A.write('REM_MODE SERIAL, COMP')
        self.f5730A.write('REM_MODE ENET, TERM')
        self.f5730A.write('^C')
        time.sleep(0.5)

    def run_f5730A_source(self, mode, rms, Ft):
        try:
            if mode in ("a", "A"):
                self.f5730A.write(f'\nout {rms}A, {Ft}Hz')
                time.sleep(2)
                print(f'[5730A command] out: {rms}A, {Ft}Hz')

            elif mode in ("v", "V"):
                self.f5730A.write(f'\nout {rms}V, {Ft}Hz')
                time.sleep(2)
                print(f'\nout: {rms}V, {Ft}Hz')

            else:
                raise ValueError("Invalid mode selected. Specify units 'V' or 'A'.")
            time.sleep(1)

            self.f5730A.write('oper')
            time.sleep(5)
        except ValueError:
            raise

    def standby_f5730A(self):
        time.sleep(1)
        self.f5730A.write('STBY')
        self.f5730A.write('*WAI')
        time.sleep(1)

    def close_f5730A(self):
        if self.f5730_connected:
            time.sleep(1)
            self.f5730A.write('LOCal')
            self.f5730A.close()
            self.f5730_connected = False


# Run
if __name__ == "__main__":
    mode, rms, Ft = 'A', 120e-3, 1000

    instr = f5730A_instrument()
    instr.connect_to_f5730A(instruments)
    instr.setup_f5730A_source()

    instr.run_f5730A_source(mode, rms, Ft)
    time.sleep(5)
    instr.close_f5730A()
