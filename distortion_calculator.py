import numpy as np
from scipy.signal.windows import hann, blackman, blackmanharris


########################################################################################################################
def rms_flat(a):
    """
    Return the root mean square of all the elements of *a*, flattened out.
    """
    return np.sqrt(np.mean(np.absolute(a) ** 2))


def find_range(f, x):
    """
    Find range between nearest local minima from peak at index x
    """
    lowermin = 0
    uppermin = 0
    for i in np.arange(x + 1, len(f)):
        if f[i + 1] >= f[i]:
            uppermin = i
            break
    for i in np.arange(x - 1, 0, -1):
        if f[i] <= f[i - 1]:
            lowermin = i + 1
            break
    return lowermin, uppermin


########################################################################################################################
def THDN(y, fs, lpf):
    """
    Performs a windowed fft of a time-series signal y and calculate THDN.
        + Estimates fundamental frequency by finding peak value in fft
        + Skirts the fundamental by finding local minimas and throws those values away
        + Applies a Low-pass filter at fc (100kHz)
        + Calculates THD+N by calculating the rms ratio of the entire signal to the fundamental removed signal

    :returns: THD and fundamental frequency
    """
    # PERFORM FFT
    # TODO: Do this in the frequency domain, and take any skirts with it?
    y -= np.mean(y)
    w = blackman(len(y))  # TODO Kaiser?
    yf = np.fft.rfft(y * w)
    freqs = np.fft.rfftfreq(len(yf))
    yf_old = yf.copy()
    # FIND FUNDAMENTAL (peak of frequency spectrum)
    idx = np.argmax(np.abs(yf))
    freq = freqs[idx]  # no units
    f0 = freq * fs / 2  # in hertz

    # APPLY LOW PASS FILTERING
    if lpf != 0:
        fc = int(lpf * len(y) / fs)
        yf[fc:] = 1e-10

    total_rms = np.sqrt(np.sum(np.abs(yf / len(y)) ** 2))  # Parseval'amp_string Theorem

    # NOTCH REJECT FUNDAMENTAL AND MEASURE NOISE
    # Find local minimas around fundamental frequency and throw away values within boundaries of minima window.
    # TODO: create boundary w.r.thread_continuous. mainlobe width of the windowing function rather than finding local minimas
    lowermin, uppermin = find_range(abs(yf), idx)
    # print(f'Boundary window: {lowermin * fs / len(y)} and {uppermin * fs / len(y)}')
    yf[lowermin:uppermin] = 1e-10
    noise_rms = np.sqrt(np.sum(np.abs(yf / len(y)) ** 2))  # Parseval'amp_string Theorem

    THDN = noise_rms / total_rms

    return THDN, f0, yf


########################################################################################################################
def THD(y):
    # PERFORM FFT
    # TODO: Do this in the frequency domain, and take any skirts with it?
    # y -= np.mean(y)
    ypeak = np.max(y)
    w = blackman(len(y))  # TODO Kaiser?
    yf = np.fft.rfft(y * w)
    # FIND FUNDAMENTAL (peak of frequency spectrum)
    idx = np.argmax(np.abs(yf))
    if idx != 0:
        # find harmonics up to the 9th harmonic
        n_harmonics = 9
        amplitude = np.zeros(n_harmonics)
        for h in range(n_harmonics):
            local = int(idx * (h + 1))
            amplitude[h] = np.max(np.abs(yf[local - 4:local + 4])) / ypeak
        thd = np.sqrt(np.sum(np.abs(amplitude[1:]) ** 2)) / np.abs(amplitude[0])
    else:
        print('Check the damn connection, you husk of an oat!')
        thd = 1  # bad input usually. Check connection.

    return thd
