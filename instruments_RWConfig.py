import yaml
import os
import platform


########################################################################################################################
def FindConfig():
    if not os.path.exists("instrument_config.yaml"):
        if platform.release() in ('Linux', 'Darwin'):
            os.mknod("instrument_config.yaml")
        else:
            with open(os.path.join('', "instrument_config.yaml"), 'w') as fp:
                pass

        config = {'DUT': {'mode': "SOCKET", 'address': "", 'port': "", 'gpib': ""},
                  'DMM': {'mode': "SOCKET", 'address': "", 'port': "", 'gpib': ""}}
        SaveConfig(config)


def ReadConfig():
    FindConfig()
    if os.path.exists("instrument_config.yaml"):
        with open("instrument_config.yaml", 'r') as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
    else:
        pass


def SaveConfig(config):
    FindConfig()
    if os.path.exists("instrument_config.yaml"):
        with open('instrument_config.yaml', 'w') as f:
            yaml.dump(config, f, sort_keys=False)
    else:
        print()
