import pyvisa as visa
import re
import time


class VisaClient:
    def __init__(self, id):
        self.healthy = True

        try:
            self.rm = visa.ResourceManager()
            self.instr_info = id
            self.mode = self.instr_info['mode']
            self.timeout = 60000  # 1 (60e3) minute timeout
        except ValueError:
            from textwrap import dedent
            msg = ("\n[ValueError] - Could not locate a VISA implementation. Install either the NI binary or pyvisa-py."
                   "\n\n    PyVISA includes a backend that wraps the National Instruments' VISA library by default.\n"
                   "    PyVISA-py is another such library and can be used for Serial/USB/GPIB/Ethernet\n"
                   "    See NI-VISA Installation:\n"
                   "        > https://pyvisa.readthedocs.io/en/1.8/getting_nivisa.html#getting-nivisa\n")
            print(msg)
            self.healthy = False

        if self.healthy:
            self.connect()

    def connect(self):
        for attempt in range(5):
            self.healthy = True
            try:
                # TODO - verify this works as intended... Otherwise leave INSTR lines commented
                # if mode is SOCKET:
                if self.mode == 'SOCKET':
                    # SOCKET is a non-protocol raw TCP connection
                    address = self.instr_info['address']
                    port = self.instr_info['port']
                    self.INSTR = self.rm.open_resource(f'TCPIP0::{address}::{port}::SOCKET', read_termination='\n')

                # if mode is GPIB:
                elif self.mode == 'GPIB':
                    address = self.instr_info['gpib']
                    self.INSTR = self.rm.open_resource(f'GPIB0::{address}::0::INSTR')

                # if mode is INSTR:
                elif self.mode == 'INSTR':
                    # INSTR is a VXI-11 protocol
                    address = self.instr_info['address']
                    self.INSTR = self.rm.open_resource(f'TCPIP0::{address}::inst0::INSTR', read_termination='\n')

                # if mode is SERIAL:
                elif self.mode == 'SERIAL':
                    address = self.instr_info['address']
                    self.INSTR = self.rm.open_resource(f'{address}')
                    self.INSTR.read_termination = '\n'

                # TODO - http://lampx.tugraz.at/~hadley/num/ch9/python/9.2.php
                # if mode is SERIAL:
                elif self.mode == 'USB':
                    address = self.instr_info['address']
                    self.INSTR = self.rm.open_resource(f'{address}', read_termination='\n')

                else:
                    print('No such mode.')

                time.sleep(1)

                # test communication to instrument by identifying instrument
                idn = re.sub(r'[\r\n|\r\n|\n]+', '', self.INSTR.query('*IDN?').lstrip(' '))
                print(f"[FOUND] {idn}")

            except visa.VisaIOError:
                # https://github.com/pyvisa/pyvisa-py/issues/146#issuecomment-453695057
                if self.mode == 'GPIB':
                    print(f"[attempt {attempt + 1}/5] - retrying connection to {self.instr_info['gpib']}")
                else:
                    print(f"[attempt {attempt + 1}/5] - retrying connection to {self.instr_info['address']}")

                self.healthy = False

            except Exception:
                raise ValueError('Could not connect. Session timed out.')
            else:
                break

        if not self.healthy:
            self.InstrumentConnectionFailed(self.instr_info)
        else:
            self.INSTR.timeout = self.timeout

    def InstrumentConnectionFailed(self, info):
        """Raised when attempted connection to instrument has timedout or is unreachable"""
        if info['mode'] in ('SOCKET', 'SERIAL'):
            print(f"\nCannot reach address {info['address']} over {info['mode']}. Connection timed out.")
        else:
            print(f"\nCannot reach address {info['gpib']} over {info['mode']}. Connection timed out.")

    def info(self):
        return self.instr_info

    def IDN(self):
        try:
            if self.mode == 'NIGHTHAWK':
                response = re.sub(r'[\r\n|\r\n|\n]+', '', self.INSTR.query('*IDN?').split("\r")[0].lstrip(' '))
            else:
                response = re.sub(r'[\r\n|\r\n|\n]+', '', self.INSTR.query('*IDN?').lstrip(' '))
                return response
        except visa.VisaIOError:
            self.healthy = False
            print('*IDN? was not returned. Failed to connect to address.')
            raise

    def write(self, cmd):
        try:
            self.INSTR.write(f'{cmd}')
            self.IDN()
        except visa.VisaIOError as e:
            print('Could not write to device.')
            raise ValueError(e)

    def read(self):
        response = None
        if self.mode == 'NIGHTHAWK':
            response = re.sub(r'[\r\n|\r\n|\n]+', '', self.INSTR.read().split("\n")[0].lstrip())
        else:
            response = re.sub(r'[\r\n|\r\n|\n]+', '', self.INSTR.read())
        return response

    def query(self, cmd):
        try:
            if self.mode == 'NIGHTHAWK':
                response = re.sub(r'[\r\n|\r\n|\n]+', '', self.INSTR.query(f'{cmd}').split("\n")[0].lstrip(' '))
            else:
                response = re.sub(r'[\r\n|\r\n|\n]+', '', self.INSTR.query(f'{cmd}').lstrip(' '))
            return response
        except visa.VisaIOError as e:
            raise ValueError(e)

    def close(self):
        try:
            self.INSTR.close()
        except AttributeError:
            # If caught, 'VisaClient' object will have no attribute 'INSTR'. Occurs when instrument not initialized.
            if self.instr_info['mode'] in ('SOCKET', 'SERIAL'):
                print(f"instrument at address {self.instr_info['address']} could not be disconnected.")
                print(f"instrument may not have been found.\n")
            else:
                print(f"instrument at address {self.instr_info['gpib']} could not be disconnected.")


def main():
    """ THIS IS A TEST METHOD FOR THE VISACLIENT CLASS"""

    f5560A_id = {'ip_address': '129.196.136.130', 'port': '3490', 'gpib_address': '', 'mode': 'NIGHTHAWK'}
    f5790A_id = {'ip_address': '', 'port': '', 'gpib_address': '6', 'mode': 'GPIB'}
    k34461A_id = {'ip_address': '10.205.92.63', 'port': '3490', 'gpib_address': '', 'mode': 'INSTR'}
    f8846A_id = {'ip_address': '10.205.92.116', 'port': '3490', 'gpib_address': '', 'mode': 'SOCKET'}

    f5560A = VisaClient(f5560A_id)
    f5790A = VisaClient(f5790A_id)
    k34461A = VisaClient(k34461A_id)
    f8846A = VisaClient(f8846A_id)

    # COMMUNICATE ------------------------------------------------------------------------------------------------------
    f5560A.write('*RST; EXTGUARD ON')

    f5790A.write(f'*RST; INPUT INPUT2; EXTRIG OFF; HIRES ON; EXTGUARD ON')

    k34461A.write('*RST;CONF:VOLT:DC')
    f8846A.write('*RST;CONF:VOLT:AC')

    f5560A.write('MONITOR OFF')
    print(f"monitor? {f5560A.query('MONITOR?')}")
    f5560A.write('MONITOR ON')
    print(f"monitor? {f5560A.query('MONITOR?')}")

    print(f"Read P7P7: {f5560A.query('read P7P7')}")
    f5560A.write('write P7P7, #hDC')
    print(f"Read P7P7: {f5560A.query('read P7P7')}")

    time.sleep(1)
    f5560A.close()
    f5790A.close()
    k34461A.close()
    f8846A.close()


if __name__ == "__main__":
    main()
