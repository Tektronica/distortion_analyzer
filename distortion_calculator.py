import numpy as np
import math

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
    mean = math.fsum(sqr) / len(sqr)  # computed from partial sums
    return np.sqrt(mean)


def find_range(f, x):
    """
    Find range between nearest local minima from peak at index x
    """
    print('\tfinding range between nearest local minima from peak at index x')
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
    print('\tcomputing window length')

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

    :param yt: time series data
    :param Fs: sampling frequency
    :param N: number of samples, or the length of the time series data
    :param windfunc: the chosen windowing function

    :return:
    xf_fft  : Two sided frequency axis.
    yf_fft  : Two sided power spectrum.
    xf_rfft : One sided frequency axis.
    yf_rfft : One sided power spectrum.
    main_lobe_width : The bandwidth (Hz) of the main lobe of the frequency domain window function.
    """
    print('\tperforming windowed FFT')

    # remove DC offset
    yt -= np.mean(yt)

    # Calculate windowing function and its length ----------------------------------------------------------------------
    if windfunc == 'rectangular':
        w = np.ones(N)
        main_lobe_width = 2 * (Fs / N)
    elif windfunc == 'bartlett':
        w = np.bartlett(N)
        main_lobe_width = 4 * (Fs / N)
    elif windfunc == 'hanning':
        w = np.hanning(N)
        main_lobe_width = 4 * (Fs / N)
    elif windfunc == 'hamming':
        w = np.hamming(N)
        main_lobe_width = 4 * (Fs / N)
    elif windfunc == 'blackman':
        w = np.blackman(N)
        main_lobe_width = 6 * (Fs / N)
    else:
        # TODO - maybe include kaiser as well, but main lobe width varies with alpha
        raise ValueError("Invalid windowing function selected!")

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
    try:
        yf_fft = (np.fft.fft(yt * w) / fft_length) * amplitude_correction_factor
        xf_fft = np.round(np.fft.fftfreq(N, d=1. / Fs), 6)  # two-sided

        yf_rfft = yf_fft[:fft_length]
        xf_rfft = np.round(np.fft.rfftfreq(N, d=1. / Fs), 6)  # one-sided

    except ValueError as e:
        print('\n!!!\nError caught while performing fft of presumably length mismatched arrays.'
              '\nwindowed_fft method in distortion_calculator.py\n!!!\n')
        raise ValueError(e)

    return xf_fft, yf_fft, xf_rfft, yf_rfft, main_lobe_width


########################################################################################################################
def THDN_F(xf, _yf, fs, N, main_lobe_width=None, hpf=0, lpf=100e3):
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
    print('\tcomputing THDN_F figure')

    yf = np.array(_yf, copy=True)  # protects yf from mutation
    # freqs = np.fft.rfftfreq(len(_yf))

    # FIND FUNDAMENTAL (peak of frequency spectrum) --------------------------------------------------------------------
    try:
        f0_idx = np.argmax(np.abs(yf))
        fundamental = xf[f0_idx]
    except IndexError:
        raise ValueError('Failed to find fundamental. Most likely index was outside of bounds.')

    # APPLY HIGH PASS FILTERING ----------------------------------------------------------------------------------------
    if not (hpf == 0) and (hpf < lpf):
        print('>>applying high pass filter<<')
        fc = int(hpf * N / fs)
        yf[:fc] = 1e-10

    # APPLY LOW PASS FILTERING -----------------------------------------------------------------------------------------
    if lpf != 0:
        fc = int(lpf * N / fs) + 1
        yf[fc:] = 1e-10

    # COMPUTE RMS FUNDAMENTAL ------------------------------------------------------------------------------------------
    # https://stackoverflow.com/questions/23341935/find-rms-value-in-frequency-domain
    # Find the local minimas of the main lobe fundamental frequency
    if main_lobe_width:
        left_of_lobe = int((fundamental - main_lobe_width / 2) * (N / fs))
        right_of_lobe = int((fundamental + main_lobe_width / 2) * (N / fs))
    else:
        left_of_lobe, right_of_lobe = find_range(abs(yf), f0_idx)

    rms_fundamental = np.sqrt(math.fsum(np.abs(yf[left_of_lobe:right_of_lobe]) ** 2))

    # REJECT FUNDAMENTAL FOR NOISE RMS ---------------------------------------------------------------------------------
    # Throws out values within the region of the main lobe fundamental frequency
    yf[left_of_lobe:right_of_lobe] = 1e-10

    # COMPUTE RMS NOISE ------------------------------------------------------------------------------------------------
    rms_noise = np.sqrt(math.fsum(np.abs(yf) ** 2))

    # THDN CALCULATION -------------------------------------------------------------------------------------------------
    # https://www.thierry-lequeu.fr/data/PESL-00101-2003-R2.pdf
    THDN = rms_noise / rms_fundamental

    return THDN, fundamental, round(1e6 * rms_noise, 2)


def THDN_R(xf, yf, fs, N, hpf=0, lpf=100e3):
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
    print('\tcomputing THDN_R figure')

    _yf = np.array(yf, copy=True)  # protects yf from mutation
    freqs = np.fft.rfftfreq(len(_yf))

    # FIND FUNDAMENTAL (peak of frequency spectrum) --------------------------------------------------------------------
    try:
        f0_idx = np.argmax(np.abs(_yf))
        fundamental = xf[f0_idx]
    except IndexError:
        raise ValueError('Failed to find fundamental. Most likely index was outside of bounds.')

    # APPLY HIGH PASS FILTERING ----------------------------------------------------------------------------------------
    if not (hpf == 0) and (hpf < lpf):
        print('\t>>applying high pass filter<<')
        fc = int(hpf * N / fs)
        _yf[:fc] = 1e-10

    # APPLY LOW PASS FILTERING -----------------------------------------------------------------------------------------
    if lpf != 0:
        fc = int(lpf * N / fs) + 1
        _yf[fc:] = 1e-10

    # REJECT FUNDAMENTAL FOR NOISE RMS ---------------------------------------------------------------------------------
    # https://stackoverflow.com/questions/ 23341935/find-rms-value-in-frequency-domain
    rms_total = rms_flat(_yf)  # Parseval'sTheorem

    # NOTCH REJECT FUNDAMENTAL AND MEASURE NOISE -----------------------------------------------------------------------
    # Find local minimas around main lobe fundamental frequency and throws out values within this window.
    # TODO: Calculate mainlobe width of the windowing function rather than finding local minimas?
    left_of_lobe, right_of_lobe = find_range(abs(_yf), f0_idx)
    _yf[left_of_lobe:right_of_lobe] = 1e-10

    # COMPUTE RMS NOISE ------------------------------------------------------------------------------------------------
    rms_noise = rms_flat(_yf)  # Parseval's Theorem

    # THDN CALCULATION -------------------------------------------------------------------------------------------------
    # https://www.thierry-lequeu.fr/data/PESL-00101-2003-R2.pdf
    THDN = rms_noise / rms_total

    return THDN, fundamental, round(1e6 * rms_total, 2)


########################################################################################################################
def THD(xf, yf, Fs, N, main_lobe_width):
    print('\tcomputing THD value')
    _yf = np.array(yf, copy=True)  # protects yf from mutation
    _yf_data_peak = max(abs(yf))
    # FIND FUNDAMENTAL (peak of frequency spectrum)
    try:
        f0_idx = np.argmax(np.abs(_yf))
        f0 = xf[f0_idx]
    except IndexError:
        raise ValueError('Failed to find fundamental for computing the THD.\nMost likely related to a zero-size array.')

    # COMPUTE RMS FUNDAMENTAL ------------------------------------------------------------------------------------------
    # https://stackoverflow.com/questions/23341935/find-rms-value-in-frequency-domain
    # Find the local minimas of the main lobe fundamental frequency

    if f0_idx != 0:
        n_harmonics = int(np.floor((Fs / 2) / f0) - 1)  # find maximum number of harmonics
        amplitude = np.zeros(n_harmonics)

        for h in range(n_harmonics):
            local_idx = f0_idx * int(h + 1)
            try:
                local_idx = local_idx + (4-np.argmax(np.abs(yf[local_idx - 4:local_idx + 4])))
                freq = xf[local_idx]

                left_of_lobe = int((freq - main_lobe_width / 2) * (N / Fs))
                right_of_lobe = int((freq + main_lobe_width / 2) * (N / Fs))

                amplitude[h] = np.sqrt(math.fsum(np.abs(np.sqrt(2)*yf[left_of_lobe:right_of_lobe]) ** 2))

            except ValueError:
                raise ValueError('Failed to capture all peaks for calculating THD.\nMost likely zero-size array.')
        thd = np.sqrt(math.fsum(np.abs(amplitude[1:]) ** 2)) / np.abs(amplitude[0])
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
