import tkinter as tk
from PIL import Image, ImageTk
import cv2


def start_local_video(label, stop_flag):
    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

    def update():
        if stop_flag["running"]:
            ret, frame = cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                imgtk = ImageTk.PhotoImage(image=img)
                label.imgtk = imgtk
                label.configure(image=imgtk)
            else:
                print("[DEBUG] Failed to read frame")
            label.after(10, update)
        else:
            cap.release()
            print("[DEBUG] Stopped")

    update()


root = tk.Tk()
label = tk.Label(root)
label.pack()

stop_flag = {"running": True}
start_local_video(label, stop_flag)

root.protocol("WM_DELETE_WINDOW", lambda: (stop_flag.update({"running": False}), root.destroy()))
root.mainloop()
