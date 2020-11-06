import numpy as np
import matplotlib.pyplot as plt
from scipy import interpolate
from scipy.signal.windows import hann, blackman, blackmanharris
from scipy.fftpack import fft

# https://www.sjsu.edu/people/burford.furman/docs/me120/FFT_tutorial_NI.pdf

# https://www.datatranslation.eu/frontend/products/pdf/DT9862S-UnderSampling.pdf
# https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.interp1d.html
# https://docs.scipy.org/doc/scipy/reference/tutorial/fft.html

# Calculate THDN
# https://gist.github.com/endolith/246092

# Frequency detectors:
# https://gist.github.com/endolith/255291
# https://ccrma.stanford.edu/~jos/sasp/Quadratic_Interpolation_Spectral_Peaks.html

# https://dartbrains.org/features/notebooks/6_Signal_Processing.html

# https://youtu.be/aQKX3mrDFoY
# https://github.com/markjay4k/Audio-Spectrum-Analyzer-in-Python/blob/master/audio%20spectrum_pt2_spectrum_analyzer.ipynb
# https://www.renesas.com/cn/en/www/doc/application-note/an9675.pdf

# RMS in frequency domain
# https://stackoverflow.com/questions/23341935/find-rms-value-in-frequency-domain


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
    freqs = np.fft.rfftfreq(len(yf))

    # FIND FUNDAMENTAL (peak of frequency spectrum)
    idx = np.argmax(np.abs(yf))
    freq = freqs[idx]  # no units
    f0 = freq * fs / 2  # in hertz

    # APPLY LOW PASS FILTERING
    fc = int(lpf * len(y) / fs)
    yf[fc:] = 1e-10
    fundamental_rms = np.sqrt(np.sum(np.abs(yf/len(y))**2))  # Parseval'amp_string Theorem

    # NOTCH REJECT FUNDAMENTAL AND MEASURE NOISE
    # Find local minimas around fundamental frequency and throw away values within boundaries of minima window.
    # TODO: create boundary w.r.thread_continuous. mainlobe width of the windowing function rather than finding local minimas
    lowermin, uppermin = find_range(abs(yf), idx)
    print(f'Boundary window: {lowermin*fs/len(y)} and {uppermin*fs/len(y)}')
    yf[lowermin:uppermin] = 1e-10
    noise_rms = np.sqrt(np.sum(np.abs(yf / len(y)) ** 2))  # Parseval'amp_string Theorem

    THDN = noise_rms / fundamental_rms

    print(f'Sample Rate: {fs}')
    print(f'Frequency: {round(abs(f0), 2)} Hz')
    print(f"THD+N:     {round(THDN * 100, 4)}% or {round(20 * np.log10(THDN), 1)}dB")

    return THDN, f0, yf


def main():
    # GENERATED SIGNAL =================================================================================================
    Ft = 1000  # Signal Frequency
    N1 = 8192  # Number of points (Spectrum Bins)
    M1 = 50  # Number of Cycles

    runtime1 = M1 * (N1 - 1) / (Ft * N1)
    signal_step = M1 / (Ft * N1)
    x1 = np.linspace(0.0, N1*signal_step, N1)
    y1 = np.cos(2 * np.pi * Ft * x1 + np.pi / 2)
    f = interpolate.interp1d(x1, y1)

    yrms1 = rms_flat(y1)

    # DIGITIZED SIGNAL =================================================================================================
    N2 = 8192  # Number of points (Spectrum Bins)
    cycles = 25  # have enough cycles to sufficiently attenuate the non-integer cycle during windowing
    Fs = (N2*Ft)/cycles  # Sampling Frequency (Hz) of Digitizer (Ft * N1 / M1)
    # For anti-aliasing effects, try 900Hz or 950Hz... These are below the 1000Hz y frequency
    lpf = 100e3

    x2 = np.arange(0, N2, 1)
    y2 = np.zeros(N2)
    digital_step = 1 / Fs

    for position, placeholder in enumerate(y2):
        try:
            y2[position] = f(x2[position] * digital_step)
        except ValueError:
            y2[position] = 0

    yrms2 = rms_flat(y2)

    # FFT ==============================================================================================================
    xf1 = np.linspace(0.0, 1.0/signal_step, N1)
    yf1 = fft(y1)
    w1 = blackman(N1)
    ywf1 = fft(y1*w1)

    xf2 = np.linspace(0.0, Fs, N2)
    yf2 = fft(y2)
    w2 = blackman(N2)
    ywf2 = fft(y2*w2)

    # Find %THD+N
    thdn, f0, noise_f = THDN(y2, Fs, lpf)

    # PLOT =============================================================================================================
    # PLOT time series y and included sampled data overlay ========================================================
    fig, (ax1, ax2) = plt.subplots(2, 1, constrained_layout=True)
    ax1.plot(x1 * 1e3, y1, '-')
    ax1.plot(x2 * digital_step * 1e3, y2, '.:')
    ax1.set_title('Generated Signal (with digitized overlay)')
    ax1.set_xlabel('time (ms)')
    ax1.set_ylabel('amplitude')
    t = ax1.text(0.95, 0.01, f'Signal Frequency: {Ft}Hz\nSampling Frequency: {Fs}Hz',
                 verticalalignment='bottom', horizontalalignment='right',
                 transform=ax1.transAxes, fontsize=9)
    t.set_bbox(dict(facecolor='white', alpha=0.5, edgecolor='white'))
    ax1.set_xlim([0, runtime1 * 1e3])

    ax2.plot(x2, y2, '.:')
    ax2.set_title('Digitized Waveform')
    ax2.set_xlabel('samples (N)')
    ax2.set_ylabel('amplitude')
    if runtime1 / digital_step > N2:
        ax2.set_xlim([0, N2-1])
    else:
        ax2.set_xlim([0, runtime1 / digital_step])
    fig.suptitle('Waveform Digitalization')

    # PLOT frequency response ==========================================================================================
    fig, (ax3, ax4) = plt.subplots(2, 1, constrained_layout=True)
    ax3.plot(xf1[0:N1], 20*np.log10(2*np.abs(yf1[0:N1]/(yrms1 * N1))), '-b')  # scaling is applied.
    ax3.plot(xf1[0:N1], 20*np.log10(2*np.abs(ywf1[0:N1]/(yrms1 * N1))), '-r')  # scaling is applied.

    # ax3.set_xlim([20, sample_rate/2])  # units are in kHz
    ax3.set_xlim(20, 30000)
    ax3.legend(['FFT', 'FFT w. window'])
    ax3.set_title('Generated Waveform Spectral Response')
    ax3.set_xlabel('frequency (Hz)')
    ax3.set_ylabel('magnitude (dB)')
    ax3.grid()

    ax4.plot(xf2[0:N2], 20*np.log10(2*np.abs(yf2[0:N2]/(yrms2 * N2))), '-b')  # scaling is applied.
    ax4.plot(xf2[0:N2], 20*np.log10(2*np.abs(ywf2[0:N2]/(yrms2 * N2))), '-r')  # scaling is applied.
    # ax4.set_xlim([100, Fs/2])  # units are in kHz
    ax4.set_xlim(100, 30000)
    ax4.legend(['FFT', 'FFT w. window'])
    ax4.set_title('Digitized Waveform Spectral Response')
    ax4.set_xlabel('frequency (Hz)')
    ax4.set_ylabel('magnitude (dB)')
    ax4.grid()

    # PLOT fundamental removed time series y  =====================================================================
    fig, (ax5, ax6) = plt.subplots(2, 1, constrained_layout=True)
    ax5.plot(x2, np.fft.irfft(noise_f), '-')
    ax5.set_xlim(0, N2)
    ax6.plot(xf2[0:N2 // 2], 20*np.log10((2*np.abs(noise_f[0:N2 // 2]/(yrms2 * N2)))), '-b')
    # ax6.set_xlim(20, sample_rate/2)
    ax6.set_xlim(20, 30000)
    ax6.set_ylim(-300, np.max(noise_f))
    ax5.set_title('Windowing time-series response of Measured Noise')
    ax5.set_xlabel('samples (#N)')
    ax5.set_ylabel('amplitude')
    t = ax5.text(0.95, 0.01, f'Signal Frequency: {round(f0, 2)}Hz\nSampling Frequency: {Fs/1000}kHz',
                 verticalalignment='bottom', horizontalalignment='right',
                 transform=ax5.transAxes, fontsize=9)
    t.set_bbox(dict(facecolor='white', alpha=0.5, edgecolor='white'))

    ax6.set_title('Spectral Response of Measured Noise')
    ax6.set_xlabel('frequency (Hz)')
    ax6.set_ylabel('magnitude (dB)')
    t2 = ax6.text(0.95, 0.01, f'THD+N: {round(thdn * 100, 4)}% or {round(20 * np.log10(thdn), 1)}dB',
                  verticalalignment='bottom', horizontalalignment='right',
                  transform=ax6.transAxes, fontsize=9)
    t2.set_bbox(dict(facecolor='white', alpha=0.5, edgecolor='white'))
    ax6.grid()
    plt.show()


if __name__ == "__main__":
    main()
