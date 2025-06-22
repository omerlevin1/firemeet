import socket
import threading
import cv2
import gzip
import numpy as np


def start_p2p_video_sender(peer_ip, peer_port, stop_flag):
    """
    Sends video frames over UDP to a peer
    """

    def send_loop():
        try:
            sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            cap = cv2.VideoCapture(1)

            while stop_flag["running"]:
                if not stop_flag.get("video_visible", True):
                    # Send camera off image
                    black_frame = np.zeros((240, 320, 3), dtype=np.uint8)
                    _, encoded = cv2.imencode(".jpg", black_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                else:
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    frame = cv2.resize(frame, (320, 240))
                    _, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 50])

                compressed = gzip.compress(encoded.tobytes())

                try:
                    sender_socket.sendto(compressed, (peer_ip, peer_port))
                except Exception as e:
                    print(f"[SENDER ERROR] Failed to send frame: {e}")
                    break

            cap.release()
            sender_socket.close()
            print("[SENDER] Stopped sending")

        except Exception as e:
            print("[SENDER ERROR]", e)

    threading.Thread(target=send_loop, daemon=True).start()
