import numpy as np
import math
from scipy import signal
from matplotlib import pyplot as plt
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
    # https://stackoverflow.com/a/17463210
    # https://code.activestate.com/recipes/393090/
    # https://stackoverflow.com/a/33004170
    sqr = np.absolute(a) ** 2
    mean = math.fsum(sqr)/len(sqr)  # computed from partial sums
    return np.sqrt(mean)


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


def getWindowLength(f0=10e3, fs=2.5e6, windfunc='blackman', error=0.1, mainlobe_type='relative'):
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
    # aka - the main lobe width
    if mainlobe_type == 'relative':
        ldf = f0 * error
    elif mainlobe_type == 'absolute':
        ldf = error
    else:
        raise ValueError('Incorrect main lobe type used!\nSelection should either be relative or absolute.')

    if windfunc == 'rectangular':
        M = int(2 * (fs / ldf))
    elif windfunc in ('bartlett', 'hanning', 'hamming'):
        M = int(4 * (fs / ldf))
    elif windfunc == 'blackman':
        M = int(6 * (fs / ldf))
    else:
        raise ValueError('Not a valid windowing function.')

    return M


########################################################################################################################
def windowed_fft(yt, Fs, N, windfunc='blackman'):
    """    
    Returns
    -------
    xf_fft :
        Two sided frequency axis.
    yf_fft : TYPE
        Two sided power spectrum.
    xf_rfft :
        One sided frequency axis.
    yf_rfft :
        One sided power spectrum.
    main_lobe_width :
        The bandwidth (Hz) of the main lobe of the frequency domain window function.
    """
    # detrend removes the DC component
    # scaling returns units of V**2/Hz or A**2/Hz. To get power, sum and multiply by the bandwidth.
    xf_rfft, yf_rfft = signal.periodogram(yt, Fs, window=windfunc, detrend='constant', return_onesided=True, scaling='density')
    # Calculate windowing function and its length ----------------------------------------------------------------------
    if windfunc == 'rectangular':
        main_lobe_width = 2 * (Fs / N)
    elif windfunc == 'bartlett':
        main_lobe_width = 4 * (Fs / N)
    elif windfunc == 'hanning':
        main_lobe_width = 4 * (Fs / N)
    elif windfunc == 'hamming':
        main_lobe_width = 4 * (Fs / N)
    elif windfunc == 'blackman':
        main_lobe_width = 6 * (Fs / N)
    else:
        # TODO - maybe include kaiser as well, but main lobe width varies with alpha
        raise ValueError("Invalid windowing function selected!")

    return xf_rfft, yf_rfft, main_lobe_width



def THDN_F(xf, yf, fs, N, main_lobe_width=None, hpf=0, lpf=100e3):
    """
    [THDF compares the harmonic content of a waveform to its fundamental] and is a much better measure of harmonics
    content than THDR. Thus, the usage of THDF is advocated .

    Source: https://www.thierry-lequeu.fr/data/PESL-00101-2003-R2.pdf

    Performs a windowed fft of a time-series signal y and calculate THDN.
        + Estimates fundamental frequency by finding peak value in fft
        + Skirts the fundamental by finding local minimas and throws those values away
        + Applies a Low-pass filter at fc (100kHz)
        + Calculates THD+N by calculating the rms ratio of the entire signal to the fundamental removed signal

    :returns: THD and fundamental frequency
    """
    _yf = np.array(yf, copy=True)  # protects yf from mutation
    freqs = xf

    # FIND FUNDAMENTAL (peak of frequency spectrum) --------------------------------------------------------------------
    try:
        f0_idx = np.argmax(_yf)
    except IndexError:
        raise ValueError('Failed to find fundamental. Most likely index was outside of bounds.')
    print(f'first few elements of _yf: {_yf[:4]}')
    # APPLY HIGH PASS FILTERING ----------------------------------------------------------------------------------------
    if not (hpf == 0) and (hpf < lpf):
        print('>>applying high pass filter<<')
        fc = int(hpf * N / fs)
        _yf[:fc] = 1e-10

    # APPLY LOW PASS FILTERING -----------------------------------------------------------------------------------------
    if lpf != 0:
        fc = int(lpf * N / fs) + 1
        _yf[fc:] = 1e-10

    # COMPUTE RMS FUNDAMENTAL ------------------------------------------------------------------------------------------
    # https://stackoverflow.com/questions/23341935/find-rms-value-in-frequency-domain
    # Find the local minimals of the main lobe fundamental frequency
    if main_lobe_width:
        samples_beside_peak = (main_lobe_width / (fs/N)) / 2 # ([samples in main lobe] - [1 peak sample]) / 2
        if not float.is_integer(samples_beside_peak):
            print("Not expecting an even number of samples in the main lobe.")
        samples_beside_peak = int(samples_beside_peak)
    else:
        samples_beside_peak = 0
    # +1 because slicing doesn't include the end
    rms_fundamental = math.fsum(_yf[f0_idx - samples_beside_peak:f0_idx + samples_beside_peak + 1])

    # REJECT FUNDAMENTAL FOR NOISE RMS ---------------------------------------------------------------------------------
    # Throws out values within the region of the main lobe fundamental frequency
    _yf[f0_idx - samples_beside_peak:f0_idx + samples_beside_peak + 1] = 1e-10
    __yf = np.array(_yf, copy=True)  # TODO: used for internal plotting only

    # COMPUTE RMS NOISE ------------------------------------------------------------------------------------------------
    rms_noise = math.fsum(_yf)  # Parseval's Theorem

    # THDN CALCULATION -------------------------------------------------------------------------------------------------
    # https://www.thierry-lequeu.fr/data/PESL-00101-2003-R2.pdf
    THDN = rms_noise / rms_fundamental

    return THDN, freqs[f0_idx], round(1e6 * rms_noise, 2)


def THDN_R(yf, fs, N, hpf=0, lpf=100e3):
    """
    [THDR compares the harmonic content of a waveform to the waveform's entire RMS signal.] This method was inherited
    from the area of audio amplifiers, where the THD serves as a measure of the systems linearity where its numerical
    value is always much less than 1 (practically it ranges from 0.1% - 0.3% in Hi-Fi systems up to a few percent in
    conventional audio systems). Thus, for this range of THD values, the error caused by mixing up the two
    definitions of THD was acceptable. However, THDF  is a much better measure of harmonics content. Employment of
    THDR in measurements may yield high errors in significant quantities such as power-factor and distortion-factor,
    derived from THD measurement.

    Source: https://www.thierry-lequeu.fr/data/PESL-00101-2003-R2.pdf

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
        fundamental = freq * fs / 2  # in hertz
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

    # REJECT FUNDAMENTAL FOR NOISE RMS ---------------------------------------------------------------------------------
    # https://stackoverflow.com/questions/ 23341935/find-rms-value-in-frequency-domain
    rms_total = np.sqrt(np.sum(np.abs(_yf) ** 2))  # Parseval'amp_string Theorem

    # NOTCH REJECT FUNDAMENTAL AND MEASURE NOISE -----------------------------------------------------------------------
    # Find local minimas around main lobe fundamental frequency and throws out values within this window.
    # TODO: Calculate mainlobe width of the windowing function rather than finding local minimas?
    left_of_lobe, right_of_lobe = find_range(abs(_yf), idx)
    _yf[left_of_lobe:right_of_lobe] = 1e-10

    # COMPUTE RMS NOISE ------------------------------------------------------------------------------------------------
    rms_noise = np.sqrt(np.sum(np.abs(_yf) ** 2))  # Parseval'amp_string Theorem

    # THDN CALCULATION -------------------------------------------------------------------------------------------------
    # https://www.thierry-lequeu.fr/data/PESL-00101-2003-R2.pdf
    THDN = rms_noise / rms_total

    return THDN, fundamental, round(1e6 * rms_total, 2)


########################################################################################################################
def THD(xf, yf, Fs, N, main_lobe_width):
    _yf = np.array(yf, copy=True)  # protects yf from mutation
    _yf_data_peak = max(abs(yf))
    # Find the fundamental frqeuency (approximately). Should correspond to the
    # largest spectral component.
    try:
        idx = np.argmax(np.abs(yf))
        freqs = xf
        F0 = freqs[idx]
    except IndexError:
        raise ValueError('Failed to find fundamental for computing the THD.\nMost likely related to a zero-size array.')

    if idx != 0:
        n_harmonics = int((Fs / 2) / F0)  # find maximum number of harmonics
        component_power = np.zeros(n_harmonics)
        for h in range(n_harmonics):
            # It may be better to replace this with peak finding, since the
            # fundamental is likely off from the real fundamental.
            local = int(idx * (h + 1))
            try:
                # The  power of each harmonic is calculated by summing the number
                # of samples in the main lobe of the window function. Every window
                # function has a symmetrical spectrum and therefore the main lobe
                # consists of an odd number of samples, or 1 plus the bandwidth
                # of the main lobe.
                samples_beside_peak = (main_lobe_width / (Fs/N)) / 2 # ([samples in main lobe] - [1 peak sample]) / 2
                if not float.is_integer(samples_beside_peak):
                    print("Not expecting an even number of samples in the main lobe.")
                samples_beside_peak = int(samples_beside_peak)
                # +1 because slicing doesn't include the end
                component_power[h] = math.fsum(yf[local - samples_beside_peak:local + samples_beside_peak + 1])
            except ValueError:
                raise ValueError('Failed to capture all peaks for calculating THD.\nMost likely zero-size array.')
        print(f'component power: {component_power}')
        thd = np.sum(component_power[1:]) / component_power[0]
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
