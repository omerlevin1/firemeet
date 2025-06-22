import pyaudio

audio = pyaudio.PyAudio()
device_index = 9  # your current mic index

info = audio.get_device_info_by_index(device_index)
print(f"\n=== Mic Device Info ===\n{info}")

# Optional: test common sample rates
common_rates = [8000, 16000, 22050, 32000, 44100, 48000]
for rate in common_rates:
    try:
        if audio.is_format_supported(rate,
                                     input_device=info['index'],
                                     input_channels=1,
                                     input_format=pyaudio.paInt16):
            print(f"[✓] Supported rate: {rate} Hz")
        else:
            print(f"[✗] Not supported: {rate} Hz")
    except Exception as e:
        print(f"[✗] {rate} Hz threw error: {e}")

audio.terminate()
