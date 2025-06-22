# region ------------- IMPORTS -------------------
import socket
import struct
import pickle
import threading
import cv2
from PIL import Image, ImageTk


# endregion
# region ------------- MAINFUNCTION -------------------

def start_p2p_video_listener(host='0.0.0.0', port=6000, target_label=None, stop_flag=None):
    """
    מאזין לחיבורי וידאו נכנסים ומציג את הווידאו המתקבל על GUI
    """

    def listen():
        listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener_socket.bind((host, port))
        listener_socket.listen(1)
        print(f"[LISTENER] Waiting for peer to connect on {host}:{port}...")
        conn, addr = listener_socket.accept()
        print(f"[CONNECTED] Peer connected from {addr}")

        data_buffer = b""
        payload_size = struct.calcsize("Q")

        while stop_flag["running"]:
            try:
                while len(data_buffer) < payload_size:
                    packet = conn.recv(4096)
                    if not packet:
                        return
                    data_buffer += packet

                packed_msg_size = data_buffer[:payload_size]
                data_buffer = data_buffer[payload_size:]
                msg_size = struct.unpack("Q", packed_msg_size)[0]

                while len(data_buffer) < msg_size:
                    packet = conn.recv(4096)
                    if not packet:
                        return
                    data_buffer += packet

                frame_data = data_buffer[:msg_size]
                data_buffer = data_buffer[msg_size:]

                frame = pickle.loads(frame_data)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                imgtk = ImageTk.PhotoImage(image=img)

                if target_label:
                    def update_gui():
                        target_label.imgtk = imgtk
                        target_label.configure(image=imgtk)
                target_label.after(0, update_gui)

            except Exception as e:
                print("[ERROR - Listener]", e)
                break

        conn.close()
        listener_socket.close()

    thread = threading.Thread(target=listen, daemon=True)
    thread.start()

# endregion
