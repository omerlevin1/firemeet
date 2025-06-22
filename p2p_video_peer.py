# region ------------- IMPORTS -------------------
from client.p2p.p2p_video_listener import start_p2p_video_listener
from client.p2p.p2p_video_sender import start_p2p_video_sender
import threading
import time


# endregion

# region ------------- MAINFUNCTION -------------------
def main():
    # ========== הגדרות ידניות ==========
    my_listen_port = 6000
    peer_ip = "10.0.0.63"  # ← כתובת ה-IP של הצד השני
    peer_port = 6000  # ← הפורט שהוא מאזין עליו

    stop_flag = {"running": True}

    # מאזין לפריימים נכנסים
    threading.Thread(
        target=start_p2p_video_listener,
        args=("0.0.0.0", my_listen_port, None, stop_flag),
        daemon=True
    ).start()

    # נותן זמן קצר למאזין לעלות
    time.sleep(1)

    # שולח פריימים לצד השני
    threading.Thread(
        target=start_p2p_video_sender,
        args=(peer_ip, peer_port, stop_flag),
        daemon=True
    ).start()

    # רץ עד שהמשתמש עוצר
    try:
        print(f"[PEER] רץ. מאזין על פורט {my_listen_port}, שולח לכתובת {peer_ip}:{peer_port}")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_flag["running"] = False
        print("[EXIT] עצרנו.")


# endregion

if __name__ == "__main__":
    main()
