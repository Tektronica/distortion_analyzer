import numpy as np
import matplotlib.pyplot as plt

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


########################################################################################################################
def windowed_fft(yt, Fs, N, windfunc='blackman'):
    # remove DC offset
    yt -= np.mean(yt)

    # Calculate windowing function and its length ----------------------------------------------------------------------
    if windfunc == 'bartlett':
        w = np.bartlett(N)
    elif windfunc == 'hanning':
        w = np.hanning(N)
    elif windfunc == 'hamming':
        w = np.hamming(N)
    elif windfunc == 'blackman':
        w = np.blackman(N)
    else:
        w = np.kaiser(N)

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

    """
    Compute the FFT of the signal Divide by the length of the FFT to recover the original amplitude. Note dividing 
    alternatively by N samples of the time-series data splits the power between the positive and negative sides. 
    However, we are only looking at one side of the FFT.
    """
    yf_fft = (np.fft.fft(yt * w) / fft_length) * amplitude_correction_factor

    yf_rfft = yf_fft[:fft_length]
    xf_fft = np.linspace(0.0, Fs, N)
    xf_rfft = np.linspace(0.0, Fs / 2, fft_length)

    return xf_fft, yf_fft, xf_rfft, yf_rfft


########################################################################################################################
def THDN(yf, fs, N, hpf=0, lpf=100e3):
    """
    Performs a windowed fft of a time-series signal y and calculate THDN.
        + Estimates fundamental frequency by finding peak value in fft
        + Skirts the fundamental by finding local minimas and throws those values away
        + Applies a Low-pass filter at fc (100kHz)
        + Calculates THD+N by calculating the rms ratio of the entire signal to the fundamental removed signal

    :returns: THD and fundamental frequency
    """
    _yf = np.array(yf, copy=True)  # protects yf from mutation
    freqs = np.fft.rfftfreq(len(_yf))

    # FIND FUNDAMENTAL (peak of frequency spectrum) --------------------------------------------------------------------
    try:
        idx = np.argmax(np.abs(_yf))
        freq = freqs[idx]  # no units
        f0 = freq * fs / 2  # in hertz
    except IndexError:
        raise ValueError('Failed to find fundamental. Most likely index was outside of bounds.')

    # APPLY HIGH PASS FILTERING ----------------------------------------------------------------------------------------
    if not (hpf == 0) and (hpf < lpf):
        print('>>applying high pass filter<<')
        fc = int(hpf * N / fs)
        _yf[:fc] = 1e-10

    # APPLY LOW PASS FILTERING -----------------------------------------------------------------------------------------
    if lpf != 0:
        fc = int(lpf * N / fs) + 1
        _yf[fc:] = 1e-10

    # RMS from frequency domain ----------------------------------------------------------------------------------------
    # https://stackoverflow.com/questions/ 23341935/find-rms-value-in-frequency-domain
    total_rms = np.sqrt(np.sum(np.abs(_yf / N) ** 2))  # Parseval'amp_string Theorem

    # NOTCH REJECT FUNDAMENTAL AND MEASURE NOISE -----------------------------------------------------------------------
    # Find local minimas around fundamental frequency and throw away values within boundaries of minima window.
    # TODO: Calculate mainlobe width of the windowing function rather than finding local minimas?
    lowermin, uppermin = find_range(abs(_yf), idx)
    _yf[lowermin:uppermin] = 1e-10
    # __yf = np.array(_yf, copy=True)  # TODO: used for internal plotting only

    # RMS from frequency domain ----------------------------------------------------------------------------------------
    noise_rms = np.sqrt(np.sum(np.abs(_yf / N) ** 2))  # Parseval'amp_string Theorem

    THDN = noise_rms / total_rms

    """    
    # TODO: Uncomment to save plots (can only save one temporal and spectrum plot per run)
    xt = np.arange(0, N, 1)
    xf = np.linspace(0.0, fs/2, int(N/2)+1)/1000
    plot_temporal(xt, y, title='Sampled Data')
    plot_temporal(xt, w, title='Blackman Window')
    plot_temporal(xt, yt * w, title='Sampled Data with imposed Blackman Window')
    plot_spectrum(xf, 20 * np.log10(2 * np.abs(yf_first[0:N] / N)), title='FFT of Windowed Data')
    plot_spectrum(xf, 20 * np.log10(2 * np.abs(yf_second[0:N] / N)),
                  title='FFT of Windowed Data with Rejected Fundamental Frequency')
    """

    return THDN, f0, round(1e6 * total_rms, 2)


########################################################################################################################
def THD(y, Fs):
    # PERFORM FFT
    # TODO: Do this in the frequency domain, and take any skirts with it?
    # y -= np.mean(y)
    ypeak = np.max(y)
    w = np.blackman(len(y))  # TODO Kaiser?
    yf = np.fft.rfft(y * w)

    # FIND FUNDAMENTAL (peak of frequency spectrum)
    try:
        idx = np.argmax(np.abs(yf))
        freqs = np.fft.rfftfreq(len(yf))
        freq = freqs[idx]  # no units
        F0 = freq * Fs / 2  # in hertz
    except IndexError:
        raise ValueError('Failed to find fundamental for computing the THD.\nMost likely related to a zero-size array.')

    if idx != 0:
        n_harmonics = int((Fs / 2) / F0)  # find maximum number of harmonics
        amplitude = np.zeros(n_harmonics)
        for h in range(n_harmonics):
            local = int(idx * (h + 1))
            try:
                amplitude[h] = np.max(np.abs(yf[local - 4:local + 4])) / ypeak
            except ValueError:
                raise ValueError('Failed to capture all peaks for calculating THD.\nMost likely zero-size array.')
        thd = np.sqrt(np.sum(np.abs(amplitude[1:]) ** 2)) / np.abs(amplitude[0])
    else:
        print('Check the damn connection, you husk of an oat!')
        thd = 1  # bad input usually. Check connection.

    return thd


def rms_noise(yf, fs, N, hpf=0, lpf=100e3):
    # APPLY HIGH PASS FILTERING
    if not (hpf == 0) and (hpf < lpf):
        fc = int(hpf * N / fs)
        yf[:fc] = 1e-10

    # APPLY LOW PASS FILTERING
    if lpf != 0:
        fc = int(lpf * N / fs)
        yf[fc:] = 1e-10

    return yf


def flicker_noise(yf, fs, N, hpf=0.1, lpf=10):
    # APPLY HIGH PASS FILTERING
    if not (hpf == 0) and (hpf < lpf):
        fc = int(hpf * N / fs)
        yf[:fc] = 1e-10

    # APPLY LOW PASS FILTERING
    if lpf != 0:
        fc = int(lpf * N / fs)
        yf[fc:] = 1e-10

    return yf


# TODO: These methods are used only for internal plotting! -------------------------------------------------------------
def plot_temporal(x, y, title=''):
    fig, ax = plt.subplots(1, 1, constrained_layout=True)
    ax.plot(x, y, '-')  # scaling is applied.

    # ax.legend(['data'])
    ax.set_title(title)
    ax.set_xlabel('Samples (#)')
    ax.set_ylabel('Amplitude')
    ax.grid()
    plt.savefig('images/static/a.jpg')


def plot_spectrum(xf, yf, title=''):
    fig, ax = plt.subplots(1, 1, constrained_layout=True)
    ax.plot(xf, yf, '-')  # scaling is applied.

    # ax.set_xlim(20, 100000)
    # ax.legend(['FFT'])
    ax.set_title(title)
    ax.set_xlabel('frequency (kHz)')
    ax.set_ylabel('magnitude (dB)')
    ax.grid()
    plt.savefig('images/static/b.jpg')
