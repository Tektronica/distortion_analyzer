import VisaClient
import time

instruments = {'f5560A': {'address': '129.196.136.130', 'port': '3490', 'gpib': '6', 'mode': 'SOCKET'}}


########################################################################################################################
class f5560A_instrument:
    """"""

    def __init__(self):
        super().__init__()
        self.measurement = []
        self.f5560A_IDN = ''
        self.f5560_connected = False

    def connect_to_f5560A(self, instr_id):
        # ESTABLISH COMMUNICATION TO INSTRUMENT -----------------------------------------------------------------------
        self.f5560A = VisaClient.VisaClient(instr_id)  # Fluke 5560A

        if self.f5560A.healthy:
            self.f5560_connected = True
            self.f5560A_IDN = self.f5560A.query('*IDN?')
        else:
            print('[X] Unable to connect to the Fluke 5560A. Check software configuration, ensure instrument is'
                  '\nconnected properly or not being used by another remote session. Consider power cycling the '
                  '\nsuspected instrument\n')

    def setup_f5560A_source(self):
        self.f5560A.write('*RST')
        time.sleep(1)
        self.f5560A.write('wizard elbereth; ponwiz on')
        self.f5560A.write('COMM_MODE SERIAL, COMP')
        self.f5560A.write('COMM_MODE TELNET, COMP')
        self.f5560A.write('^C')
        time.sleep(0.5)
        self.f5560A.write('MONITOR OFF')
        print(f"\nmonitor: {self.f5560A.query('MONITOR?')}")

    def run_f5560A_source(self, mode, rms, Ft):
        try:
            if mode in ("a", "A"):
                self.f5560A.write(f'\nout {rms}A, {Ft}Hz')
                time.sleep(2)
                print(f'[5560A command] out: {rms}A, {Ft}Hz')

            elif mode in ("v", "V"):
                self.f5560A.write(f'\nout {rms}V, {Ft}Hz')
                time.sleep(2)
                print(f'\nout: {rms}V, {Ft}Hz')

            else:
                raise ValueError("Invalid mode selected. Specify units 'V' or 'A'.")
            time.sleep(1)

            self.f5560A.write('oper')
            time.sleep(5)
        except ValueError:
            raise

    def standby_f5560A(self):
        time.sleep(1)
        self.f5560A.write('STBY')
        self.f5560A.write('*WAI')
        time.sleep(1)

    def close_f5560A(self):
        if self.f5560_connected:
            time.sleep(1)
            self.f5560A.write('LOCal')
            self.f5560A.close()
            self.f5560_connected = False


# Run
if __name__ == "__main__":
    mode, rms, Ft = 'A', 120e-3, 1000

    instr = f5560A_instrument()
    instr.connect_to_f5560A(instruments)
    instr.setup_f5560A_source()

    instr.run_f5560A_source(mode, rms, Ft)
    time.sleep(5)
    instr.close_f5560A()
