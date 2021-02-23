import numpy as np
from scipy.signal.windows import hann, blackman, blackmanharris
from scipy.fftpack import fft

"""
FFT Fundamentals
https://www.sjsu.edu/people/burford.furman/docs/me120/FFT_tutorial_NI.pdf
https://docs.scipy.org/doc/scipy/reference/tutorial/fft.html
https://youtu.be/aQKX3mrDFoY
https://github.com/markjay4k/Audio-Spectrum-Analyzer-in-Python/blob/master/audio%20spectrum_pt2_spectrum_analyzer.ipynb

DIGITIZING + SAMPLING
https://www.datatranslation.eu/frontend/products/pdf/DT9862S-UnderSampling.pdf
https://www.renesas.com/cn/en/www/doc/application-note/an9675.pdf
https://dartbrains.org/features/notebooks/6_Signal_Processing.html

INTERPOLATION
https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.interp1d.html
https://ccrma.stanford.edu/~jos/sasp/Quadratic_Interpolation_Spectral_Peaks.html

Frequency detectors:
https://gist.github.com/endolith/255291

Calculate THDN
https://gist.github.com/endolith/246092

RMS in frequency domain
https://stackoverflow.com/questions/23341935/find-rms-value-in-frequency-domain
"""


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
def windowed_fft(y, N, windfunc='blackman'):
    w = blackman(N)
    ywf = fft(y * w)
    return ywf


########################################################################################################################
def THDN(y, fs, hpf=0, lpf=100e3):
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
    N = len(y)

    w = blackman(N)  # TODO Kaiser?
    yf = np.fft.rfft(y * w)  # length is N/2 + 1
    freqs = np.fft.rfftfreq(len(yf))

    # FIND FUNDAMENTAL (peak of frequency spectrum)
    idx = np.argmax(np.abs(yf))
    freq = freqs[idx]  # no units
    f0 = freq * fs / 2  # in hertz

    # APPLY HIGH PASS FILTERING
    if not (hpf == 0) and (hpf < lpf):
        fc = int(hpf * N / fs)
        yf[0:fc] = 1e-10

    # APPLY LOW PASS FILTERING
    if lpf != 0:
        fc = int(lpf * N / fs)
        yf[fc:] = 1e-10

    # RMS from frequency domain
    # https: // stackoverflow.com / questions / 23341935 / find - rms - value - in -frequency - domain
    total_rms = np.sqrt(np.sum(np.abs(yf / N) ** 2))  # Parseval'amp_string Theorem

    # NOTCH REJECT FUNDAMENTAL AND MEASURE NOISE
    # Find local minimas around fundamental frequency and throw away values within boundaries of minima window.
    # TODO: Calculate mainlobe width of the windowing function rather than finding local minimas?
    lowermin, uppermin = find_range(abs(yf), idx)
    # print(f'Boundary window: {lowermin * fs / len(y)} and {uppermin * fs / len(y)}')
    yf[lowermin:uppermin] = 1e-10

    # RMS from frequency domain
    noise_rms = np.sqrt(np.sum(np.abs(yf / N) ** 2))  # Parseval'amp_string Theorem

    THDN = noise_rms / total_rms

    return THDN, f0, yf, round(noise_rms, 4)


########################################################################################################################
def THD(y, Fs):
    # PERFORM FFT
    # TODO: Do this in the frequency domain, and take any skirts with it?
    # y -= np.mean(y)
    ypeak = np.max(y)
    w = blackman(len(y))  # TODO Kaiser?
    yf = np.fft.rfft(y * w)

    # FIND FUNDAMENTAL (peak of frequency spectrum)
    idx = np.argmax(np.abs(yf))
    freqs = np.fft.rfftfreq(len(yf))
    freq = freqs[idx]  # no units
    F0 = freq * Fs / 2  # in hertz

    if idx != 0:
        n_harmonics = int((Fs/2) / F0)  # find maximum number of harmonics

        amplitude = np.zeros(n_harmonics)
        for h in range(n_harmonics):
            local = int(idx * (h + 1))
            amplitude[h] = np.max(np.abs(yf[local - 4:local + 4])) / ypeak
        thd = np.sqrt(np.sum(np.abs(amplitude[1:]) ** 2)) / np.abs(amplitude[0])
    else:
        print('Check the damn connection, you husk of an oat!')
        thd = 1  # bad input usually. Check connection.

    return thd
