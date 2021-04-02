import numpy as np
import matplotlib.pyplot as plt
import csv
import os
from pathlib import Path
import datetime

DIGITIZER_SAMPLING_FREQUENCY = 5e6
CONTAINS_HARMONICS = True
CONTAINS_NOISE = True


def getSamplingFrequency(F0, bw=100e3):
    """
    The maximum detectable frequency resolved by an FFT is defined as half the sampling frequency.
    :param bw: the maximum resolved frequency of the fft.
    :return: sampling rate, fs
    """
    # Ideal sampling frequency
    _Fs = max(2 * bw, 100 * F0)

    # An integer number of samples averaged per measurement determines actual sampling frequency
    N = max(round(DIGITIZER_SAMPLING_FREQUENCY / _Fs), 1)
    Fs = DIGITIZER_SAMPLING_FREQUENCY / N
    return Fs


def getWindowLength(f0=10e3, fs=2.5e6, windfunc='blackman', error=0.1):
    """
    Computes the window length of the measurement. An error is expressed since the main lobe width is directly
    proportional to the number of cycles captured. The minimum value of M correlates to the lowest detectable frequency
    by the windowing function. For instance, blackman requires a minimum of 6 period cycles of the frequency of interest
    in order to express content of that lobe in the DFT. Sampling frequency does not play a role in the width of the
    lobe, only the resolution of the lobe.

    :param f0: fundamental frequency of signal
    :param fs: sampling frequency
    :param windfunc: "Rectangular", "Bartlett", "Hanning", "Hamming", "Blackman"
    :param error: 100% error suggests the lowest detectable frequency is the fundamental
    :return: window length of integer value (number of time series samples collected)
    """
    # lowest detectable frequency by window
    ldf = f0 * error

    if windfunc == 'Rectangular':
        M = int(fs / ldf)
    elif windfunc in ('Bartlett', 'Hanning', 'Hamming'):
        M = int(4 * (fs / ldf))
    elif windfunc == 'blackman':
        M = int(6 * (fs / ldf))
    else:
        raise ValueError('Not a valid windowing function.')

    return M


def get_FFT_parameters(Ft, lpf, error):
    Fs = getSamplingFrequency(Ft, lpf)
    N = getWindowLength(f0=Ft, fs=Fs, windfunc='blackman', error=error)

    return Fs, N


def plot(xt, yt, xf, yf, N):
    # TEMPORAL ---------------------------------------------------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(2, 1, constrained_layout=True)
    ax1.plot(xt, yt, linestyle='-')

    ax1.set_title('Time Series Data')
    ax1.set_xlabel('time (t)')
    ax1.set_ylabel('amplitude')

    # SPECTRAL ---------------------------------------------------------------------------------------------------------
    yf_peak = max(abs(yf))
    ax2.plot(xf, 20*np.log10(np.abs(yf/yf_peak)), linestyle='-')

    xf_left = 0
    xf_right = xf[int(N / 2) - 1]

    ax2.set_xlim(left=xf_left, right=xf_right)

    ax2.set_title('FFT Spectral Plot')
    ax2.set_xlabel('frequency (kHz)')
    ax2.set_ylabel('Magnitude (dB)')

    ax1.margins(x=0)
    ax1.autoscale(axis='y')

    # UPDATE PLOT FEATURES ---------------------------------------------------------------------------------------------
    plt.grid()
    plt.show()


def _getFilepath(directory='', fname='filename'):
    Path(directory).mkdir(parents=True, exist_ok=True)
    date = datetime.date.today().strftime("%Y%m%d")
    filename = f'{fname}_{date}'
    index = 0

    while os.path.isfile(f'{directory}/{filename}_{str(index).zfill(2)}.csv'):
        index += 1
    filename = filename + "_" + str(index).zfill(2)
    return f'{directory}/{filename}.csv'


def write_to_csv(path, fname, header, *args):
    table = list(zip(*args))
    pathname = _getFilepath(path, fname)
    with open(pathname, 'w', newline='') as outfile:
        writer = csv.writer(outfile, delimiter=',')
        if header:
            writer.writerow(header)
        for row in table:
            writer.writerow(row)


def main():
    Ft = 1e3
    lpf = 100e3
    error = 0.1

    Fs, N = get_FFT_parameters(Ft, lpf, error)

    # TEMPORAL ---------------------------------------------------------------------------------------------------------
    xt = np.arange(0, N, 1) / Fs
    yt = 2*np.sin(2 * np.pi * Ft * xt)
    if CONTAINS_HARMONICS:
        yt = yt + 0.001 * np.sin(2 * np.pi * 3 * Ft * xt) + 0.0001 * np.sin(2 * np.pi * 5 * Ft * xt)
    if CONTAINS_NOISE:
        yt = yt + np.random.normal(0, 1, N)*0.0001

    yrms = np.sqrt(np.mean(np.absolute(yt) ** 2))

    # SPECTRAL ---------------------------------------------------------------------------------------------------------
    xf = np.linspace(0.0, Fs, N)
    w = np.blackman(N)

    # Calculate amplitude correction factor after windowing ------------------------------------------------------------
    # https://stackoverflow.com/q/47904399/3382269
    amplitude_correction_factor = 1 / np.mean(w)

    # Calculate the length of the FFT ----------------------------------------------------------------------------------
    if (N % 2) == 0:
        # for even values of N: FFT length is (N / 2) + 1
        fft_length = int(N / 2) + 1
    else:
        # for odd values of N: FFT length is (N + 1) / 2
        fft_length = int((N + 2) / 2)

    yf_fft = (np.fft.fft(yt * w) / fft_length) * amplitude_correction_factor

    plot(xt, yt, xf, yf_fft, N)
    header = ['xt', 'yt', 'xf', 'yf']
    write_to_csv('../results/history', 'generated', header, xt, yt, xf, yf_fft)


if __name__ == "__main__":
    main()
