import pyaudio
import struct
import threading


def start_audio_listener(client_socket, stop_flag):
    def receive_audio_loop():
        print("[LISTENER] Starting audio listener...")
        audio = pyaudio.PyAudio()

        stream = audio.open(format=pyaudio.paInt16,
                            channels=1,
                            rate=48000,
                            output=True,
                            frames_per_buffer=2048)

        payload_size = struct.calcsize("Q")
        data_buffer = b""

        while stop_flag["running"]:
            try:
                while len(data_buffer) < payload_size:
                    packet = client_socket.recv(4096)
                    if not packet:
                        return
                    data_buffer += packet

                packed_msg_size = data_buffer[:payload_size]
                data_buffer = data_buffer[payload_size:]
                msg_size = struct.unpack("Q", packed_msg_size)[0]

                while len(data_buffer) < msg_size:
                    packet = client_socket.recv(4096)
                    if not packet:
                        return
                    data_buffer += packet

                audio_frame = data_buffer[:msg_size]
                data_buffer = data_buffer[msg_size:]

                stream.write(audio_frame)
                print("[LISTENER] Played", len(audio_frame), "bytes")

            except Exception as e:
                print("[LISTENER ERROR]", e)
                break

        stream.stop_stream()
        stream.close()
        audio.terminate()
        client_socket.close()
        print("[LISTENER] Audio listener stopped")

    threading.Thread(target=receive_audio_loop, daemon=True).start()
