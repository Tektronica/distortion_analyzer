import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.pylab as pylab

FILE = "../results/history/generated_Harmonics_Noise.csv"

pylab_params = {'legend.fontsize': 'medium',
                'font.family': 'Segoe UI',
                'axes.titleweight': 'bold',
                'figure.figsize': (15, 5),
                'axes.labelsize': 'medium',
                'axes.titlesize': 'medium',
                'xtick.labelsize': 'medium',
                'ytick.labelsize': 'medium'}
pylab.rcParams.update(pylab_params)


def open_history(file):
    df = pd.read_csv(file)

    try:
        xt = df['xt'].to_numpy()
        yt = df['yt'].to_numpy()
        xf = df['xf'].to_numpy()

        # https://stackoverflow.com/a/18919965/3382269
        # https://stackoverflow.com/a/51725795/3382269
        df['yf'] = df['yf'].str.replace('i', 'j').apply(lambda x: np.complex(x))
        yf = df['yf'].to_numpy()
    except KeyError:
        raise ValueError('Incorrect file attempted to be opened. '
                         '\nCheck data headers. xt, yt, xf, yf should be present')

    return xt, yt, xf, yf


def plot_temporal(x, y, title='', filename='saved_plot'):
    fig, ax = plt.subplots(1, 1, figsize=(12.8, 4.8), constrained_layout=True)  # default: figsize=(6.4, 4.8)
    ax.plot(x, y, '-')  # scaling is applied.

    # ax.legend(['data'])
    ax.set_title(title.upper())
    ax.set_xlabel('SAMPLES (#)')
    ax.set_ylabel('AMPLITUDE')
    ax.margins(x=0)
    ax.grid()
    plt.savefig(f'../images/static/{filename}.jpg')


def plot_spectrum(xf, yf, title='', filename='saved_plot'):
    fig, ax = plt.subplots(1, 1, figsize=(12.8, 4.8), constrained_layout=True)  # default: figsize=(6.4, 4.8)
    ax.plot(xf, yf, '-')  # scaling is applied.

    ax.set_title(title.upper())
    ax.set_xlabel('FREQUENCY (kHz)')
    ax.set_ylabel('MAGNITUDE (dB)')
    ax.margins(x=0)
    ax.grid()
    plt.savefig(f'../images/static/{filename}.jpg')


def main():
    xt, yt, xf, yf = open_history(FILE)
    N = len(xt)
    Fs = round(1 / (xt[1] - xt[0]), 2)

    plot_temporal(range(N), yt, title=f'Sampled Data (N={N})', filename='00_sampled_data')

    # remove DC offset -------------------------------------------------------------------------------------------------
    yt -= np.mean(yt)

    # Calculate windowing function and its length ----------------------------------------------------------------------
    w = np.blackman(N)
    main_lobe_width = 6 * (Fs / N)
    plot_temporal(range(N), w, title=f'Blackman Window (N={N})', filename='01_blackman_window')

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
    ytw = yt * w
    plot_temporal(range(N), ytw, title=f'Sampled Data with imposed Blackman Window (N={N})', filename='02_windowed_data')

    yf_fft = (np.fft.fft(ytw) / fft_length) * amplitude_correction_factor

    yf_rfft = yf_fft[:fft_length]
    xf_fft = np.linspace(0.0, Fs, N)
    xf_rfft = np.linspace(0.0, Fs / 2, fft_length)

    plot_spectrum(xf_rfft/1000, 20 * np.log10(np.abs(yf_rfft)), title=f'FFT of Windowed Data (N={fft_length})',
                  filename='03_FFT_of_windowed_data')


if __name__ == "__main__":
    main()
