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
            print('Unable to connect to the Fluke 5560A. Check software configuration, ensure instrument is'
                  'connected properly or not being used by another remote session. Consider power cycling the '
                  'suspected instrument\n')

    def setup_source(self):
        self.f5560A.write('*RST')
        time.sleep(1)
        self.f5560A.write('wizard elbereth; ponwiz on')
        self.f5560A.write('COMM_MODE SERIAL, COMP')
        self.f5560A.write('COMM_MODE TELNET, COMP')
        self.f5560A.write('^C')
        time.sleep(0.5)
        self.f5560A.write('MONITOR OFF')
        print(f"\nmonitor: {self.f5560A.query('MONITOR?')}")

    def run_source(self, mode, rms, Ft):
        try:
            if mode in ("a", "A"):
                self.f5560A.write(f'\nout {rms}A, {Ft}Hz')
                time.sleep(2)
                print(f'\nout: {rms}A, {Ft}Hz')
                # self.f5560A.write('write P7P7, #hDC')  # TODO: this turns COMP3 ON - 22uF (distortion amp)
                # self.f5560A.write('write P7P7, #hEC')  # TODO: this turns COMP2 ON - 22nF (distortion amp)
                # self.f5560A.write('Mod P7P1SEL, #h40, 0')  # TODO: this turns idac fly cap inverter off in AC
            # ("v", "V")
            else:
                self.f5560A.write(f'\nout {rms}V, {Ft}Hz')
                time.sleep(2)
                print(f'\nout: {rms}V, {Ft}Hz')
                # self.f5560A.write('Mod P7P1SEL, #h40, 0')  # TODO: this turns idac fly cap inverter off in AC
            time.sleep(1)

            self.f5560A.write('oper')
            time.sleep(5)
        except ValueError:
            raise

    def standby(self):
        time.sleep(1)
        self.f5560A.write('STBY')
        self.f5560A.write('*WAI')
        time.sleep(1)

    def close_f5560A(self):
        if self.f5560_connected:
            time.sleep(1)
            self.f5560A.close()
            self.f5560_connected = False


# Run
if __name__ == "__main__":
    mode, rms, Ft = 'A', 120e-3, 1000

    instr = f5560A_instrument()
    instr.connect_to_f5560A(instruments)
    instr.setup_source()

    instr.run_source(mode, rms, Ft)
    time.sleep(5)
    instr.close_f5560A()
