import pyaudio
import struct
import threading


def start_audio_sender(client_socket, stop_flag):
    def send_audio_loop():
        try:
            print("[AUDIO SENDER] Initializing PyAudio...")
            audio = pyaudio.PyAudio()

            stream = audio.open(format=pyaudio.paInt16,
                                channels=1,
                                rate=48000,
                                input=True,
                                frames_per_buffer=2048)

            print("[AUDIO SENDER] Stream started.")
            while stop_flag["running"]:
                try:
                    if not stop_flag.get("muted", False):
                        data = stream.read(2048, exception_on_overflow=False)
                        message = struct.pack("Q", len(data)) + data
                        client_socket.sendall(message)
                    else:
                        stream.read(2048, exception_on_overflow=False)  # discard mic input

                except Exception as e:
                    print(f"[AUDIO SENDER ERROR] During stream: {e}")
                    break

            stream.stop_stream()
            stream.close()
            audio.terminate()
            print("[AUDIO SENDER] Stopped cleanly.")

        except Exception as e:
            print(f"[AUDIO SENDER ERROR] Failed to start: {e}")

    threading.Thread(target=send_audio_loop, daemon=True).start()
