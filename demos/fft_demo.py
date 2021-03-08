import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pprint
from scipy import interpolate
from scipy.signal.windows import hann, blackman, blackmanharris
from scipy.fftpack import fft
from numpy.fft import rfft, irfft


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
    ywf = yf.copy()

    freqs = np.fft.rfftfreq(len(yf))

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
    print(f'Boundary window: {lowermin * fs / len(y)} and {uppermin * fs / len(y)}')
    yf[lowermin:uppermin] = 1e-10
    yf_notch_removed = yf.copy()

    noise_rms = np.sqrt(np.sum(np.abs(yf / len(y)) ** 2))  # Parseval'amp_string Theorem
    THDN = noise_rms / total_rms

    Nf = len(yf)
    N = len(y)
    x = np.arange(0.0, len(y), 1)
    xf = np.linspace(0.0, Fs / 2, int(N / 2 + 1))

    # TODO Here's a plot!
    plot_temporal(x, y, title='Sampled Data')
    plot_temporal(x, w, title='Blackman Window')
    plot_temporal(x, y*w, title='Convolution of Sampled Data and Blackman Window')
    plot_spectrum(xf, 20 * np.log10(2 * np.abs(ywf[0:N] / N)), title='FFT of Windowed Data')
    plot_spectrum(xf, 20 * np.log10(2 * np.abs(yf_notch_removed[0:N] / N)), title='FFT of Windowed Data with Rejected Fundamental Frequency')

    return THDN, f0, ywf, yf_notch_removed, freqs


def THDN_scipy(y, fs, lpf):
    # TODO: Do this in the frequency domain, and take any skirts with it?
    y -= np.mean(y)
    windowed = y * blackmanharris(len(y))  # TODO Kaiser?

    # Measure the total signal before filtering but after windowing
    total_rms = rms_flat(windowed)

    # Find the peak of the frequency spectrum (fundamental frequency), and
    # filter the signal by throwing away values between the nearest local
    # minima
    f = rfft(windowed)
    i = np.argmax(abs(f))

    # Not exact
    print('Frequency: %f Hz' % (fs * (i / len(windowed))))
    lowermin, uppermin = find_range(abs(f), i)
    f[lowermin: uppermin] = 0

    # Transform noise back into the signal domain and measure it
    # TODO: Could probably calculate the RMS directly in the frequency domain
    # instead
    noise = irfft(f)
    THDN = rms_flat(noise) / total_rms
    print("GITHUB: THD+N:     %.4f%% or %.1f dB" % (THDN * 100, 20 * np.log10(THDN)))


def plot_temporal(x, y, title=''):
    fig, ax = plt.subplots(1, 1, constrained_layout=True)
    ax.plot(x, y, '-b')  # scaling is applied.

    # ax.legend(['data'])
    ax.set_title(title)
    ax.set_xlabel('Samples (#)')
    ax.set_ylabel('Amplitude')
    ax.grid()
    plt.show()


def plot_spectrum(xf, yf, title=''):
    fig, ax = plt.subplots(1, 1, constrained_layout=True)
    ax.plot(xf, yf, '-b')  # scaling is applied.

    # ax.set_xlim(20, 100000)
    # ax.legend(['FFT'])
    ax.set_title(title)
    ax.set_xlabel('frequency (Hz)')
    ax.set_ylabel('magnitude (dB)')
    ax.grid()
    plt.show()


data = pd.read_csv('./demos/y_data.csv')
# TODO: For some reason, df.to_numpy(np.complex) doesn't work
# yf = np.array((data['yf_old'].dropna()).tolist()).astype(np.complex)
# yf_filtered = np.array((data['yf_filter'].dropna()).tolist()).astype(np.complex)
y = data['ydata'].dropna().to_numpy(np.float)
Fs = 714285.714285714286

thdn, f0, ywf, yf_notch_removed, freqs = THDN(y, Fs, 100e3)

N = len(y)  # 10000
# xf = np.linspace(0.0, Fs, int(N/2 + 1))
xf = np.linspace(0.0, Fs/2, int(N/2 + 1))
yrms = rms_flat(y)
print(f"{round(thdn * 100, 4)}% or {round(20 * np.log10(thdn), 1)}dB")
THDN_scipy(y, Fs, 100e3)

# PLOT frequency response ==========================================================================================
fig, (ax1, ax2) = plt.subplots(2, 1, constrained_layout=True)
ax1.plot(xf, 20 * np.log10(2 * np.abs(ywf[0:N] / (yrms * N))), '-b')  # scaling is applied.
ax2.plot(xf, 20 * np.log10(2 * np.abs(yf_notch_removed[0:N] / (yrms * N))),
         '-b')  # scaling is applied.

ax1.set_xlim(20, 30000)
ax1.legend(['FFT', 'FFT w. window'])
ax1.set_title('Generated Waveform Spectral Response')
ax1.set_xlabel('frequency (Hz)')
ax1.set_ylabel('magnitude (dB)')
ax1.grid()
plt.show()
