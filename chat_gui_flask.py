import tkinter as tk
from tkinter import scrolledtext, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import threading
import socket
import cv2
import numpy as np
import gzip
import time
import requests
import pyaudio
from urllib.parse import urlparse


class ChatClientGUI:
    VIDEO_PORT = 6000
    AUDIO_PORT = 6001
    CHAT_POLL_INTERVAL = 1.5
    PARTICIPANT_POLL_INTERVAL = 2.0
    AUDIO_CHUNK = 1024
    AUDIO_FORMAT = pyaudio.paInt16
    AUDIO_CHANNELS = 1
    AUDIO_RATE = 16000

    def __init__(self, server_url="http://172.16.1.33:5000", meeting_id=None,
                 return_to_meeting_home=None, email=None, host_ip=None):
        self.sidebar_window = None
        self.host_ip = host_ip

        self.root = tk.Toplevel()
        self.root.title("Client Chat")
        self.root.geometry("1024x720")

        self.stop_flag = {"running": True, "muted": False}
        self.video_visible = True
        self.peer_video_slots = {}
        self.peer_ips = set()
        self.threads = []

        parsed = urlparse(server_url)
        self.server_url = server_url
        self.my_ip = socket.gethostbyname(socket.gethostname())
        self.sender_id = self.my_ip
        self.current_meeting_id = meeting_id
        self.return_to_meeting_home = return_to_meeting_home
        self.email = email

        self.audio = pyaudio.PyAudio()
        self.audio_input = self.audio.open(format=self.AUDIO_FORMAT,
                                           channels=self.AUDIO_CHANNELS,
                                           rate=self.AUDIO_RATE,
                                           input=True,
                                           frames_per_buffer=self.AUDIO_CHUNK)
        self.audio_output = self.audio.open(format=self.AUDIO_FORMAT,
                                            channels=self.AUDIO_CHANNELS,
                                            rate=self.AUDIO_RATE,
                                            output=True,
                                            frames_per_buffer=self.AUDIO_CHUNK)

        self.video_sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.audio_sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Build UI and start services
        self.setup_ui()
        self.start_local_video()
        self.start_video_listener()
        self.start_audio_sender()
        self.start_audio_listener()
        self.start_chat_polling()
        self.start_participant_poller()

        self.root.protocol("WM_DELETE_WINDOW", self.logout_via_exit)

    def setup_ui(self):
        self.root.grid_rowconfigure(0, weight=6)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        top_frame = tk.Frame(self.root)
        top_frame.grid(row=0, column=0, sticky="nsew")
        top_frame.grid_rowconfigure(1, weight=1)
        top_frame.grid_columnconfigure(0, weight=3)
        top_frame.grid_columnconfigure(1, weight=2)

        # Chat log
        self.chat_log = scrolledtext.ScrolledText(top_frame, state='disabled', bg="lightgreen")
        self.chat_log.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.chat_log.tag_config("me", foreground="blue", font=("Arial", 10, "bold"))
        self.chat_log.tag_config("others", foreground="black", font=("Arial", 10))

        # Add Participants
        btn_frame = tk.Frame(top_frame, bg="#0B1E3D")
        btn_frame.grid(row=0, column=0, sticky="nw", padx=5, pady=5)
        tk.Button(btn_frame, text="Add Participants", bg="lightblue", font=("Arial", 12, "bold"),
                  command=self.open_add_participants_sidebar).pack()

        # Controls
        ctrl = tk.Frame(top_frame)
        ctrl.grid(row=0, column=1, sticky="ew", padx=5, pady=(5, 0))
        tk.Label(ctrl, text="Cameras (1-4):").pack(side=tk.LEFT)
        self.camera_input = tk.Entry(ctrl, width=5)
        self.camera_input.pack(side=tk.LEFT)
        self.camera_input.bind("<Return>", self.update_camera_count)
        self.video_toggle_button = tk.Button(ctrl, text="Hide Video", command=self.toggle_video)
        self.video_toggle_button.pack(side=tk.LEFT, padx=(10, 0))
        tk.Button(ctrl, text="End Meeting", bg="red", fg="white", command=self.end_meeting).pack(side=tk.RIGHT)
        self.mute_button = tk.Button(ctrl, text="Mute", command=self.toggle_mute)
        self.mute_button.pack(side=tk.LEFT, padx=(10, 0))

        # Video canvases
        vid = tk.Frame(top_frame, bg="gray")
        vid.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        vid.grid_rowconfigure((0, 1), weight=1)
        vid.grid_columnconfigure((0, 1), weight=1)
        self.video_canvases = []
        for i in range(4):
            c = tk.Canvas(vid, width=320, height=240, bg="black")
            r, cidx = divmod(i, 2)
            c.grid(row=r, column=cidx, padx=5, pady=5, sticky="nsew")
            self.video_canvases.append(c)

        # Message entry
        bot = tk.Frame(self.root, bg="tomato")
        bot.grid(row=1, column=0, sticky="nsew")
        bot.grid_columnconfigure(0, weight=5)
        bot.grid_columnconfigure(1, weight=1)
        self.entry_field = tk.Entry(bot)
        self.entry_field.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.entry_field.bind("<Return>", self.send_message)
        tk.Button(bot, text="Send", command=self.send_message).grid(row=0, column=1, padx=5, pady=5)

    def create_camera_off_frame(self):
        img = Image.new("RGB", (320, 240), "black")
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        text = "Camera Off"
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (320 - w) / 2
        y = (240 - h) / 2
        draw.text((x, y), text, fill="white", font=font)
        return img

    # rest of methods unchanged...
    def start_local_video(self):
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

        def loop():
            if not self.stop_flag["running"]:
                return
            ret, frame = self.cap.read()
            if self.video_visible and ret:
                bgr = cv2.resize(frame, (320, 240))
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb)
            else:
                img = self.create_camera_off_frame()
            imgtk = ImageTk.PhotoImage(img)
            self.video_canvases[0].delete("all")
            self.video_canvases[0].create_image(0, 0, anchor=tk.NW, image=imgtk)
            self.video_canvases[0].image = imgtk

            if ret:
                buf = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 50])[1].tobytes()
                comp = gzip.compress(buf)
                for ip in list(self.peer_ips):
                    self.video_sender_socket.sendto(comp, (ip, self.VIDEO_PORT))

            self.video_canvases[0].after(30, loop)

        loop()

    def start_video_listener(self):
        def recv():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', self.VIDEO_PORT))
            while self.stop_flag["running"]:
                data, addr = sock.recvfrom(65536)
                frame = cv2.imdecode(np.frombuffer(gzip.decompress(data), np.uint8), cv2.IMREAD_COLOR)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                imgtk = ImageTk.PhotoImage(img)
                if addr[0] not in self.peer_video_slots:
                    for i in range(1, 4):
                        if i not in self.peer_video_slots.values():
                            self.peer_video_slots[addr[0]] = i
                            break
                idx = self.peer_video_slots.get(addr[0], 1)
                self.root.after(0, lambda i=idx, img=imgtk: (
                    self.video_canvases[i].delete('all'),
                    self.video_canvases[i].create_image(0, 0, anchor=tk.NW, image=img),
                    setattr(self.video_canvases[i], 'image', img)
                ))
            sock.close()

        t = threading.Thread(target=recv, daemon=True)
        t.start()
        self.threads.append(t)

    def start_audio_sender(self):
        def send_loop():
            while self.stop_flag["running"]:
                data = self.audio_input.read(self.AUDIO_CHUNK, exception_on_overflow=False)
                comp = gzip.compress(data)
                for ip in list(self.peer_ips):
                    self.audio_sender_socket.sendto(comp, (ip, self.AUDIO_PORT))

        t = threading.Thread(target=send_loop, daemon=True)
        t.start()
        self.threads.append(t)

    def start_audio_listener(self):
        def recv_loop():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', self.AUDIO_PORT))
            while self.stop_flag["running"]:
                data, _ = sock.recvfrom(65536)
                if not self.stop_flag['muted']:
                    pcm = gzip.decompress(data)
                    self.audio_output.write(pcm)
            sock.close()

        t = threading.Thread(target=recv_loop, daemon=True)
        t.start()
        self.threads.append(t)

    def start_chat_polling(self):
        def poll():
            last_id = None
            while self.stop_flag["running"]:
                res = requests.get(f"{self.server_url}/get_messages", params={"meeting_id": self.current_meeting_id, **(
                    {'after_id': last_id} if last_id else {})})
                if res.status_code == 200:
                    for m in res.json():
                        self.root.after(0, lambda msg=m: self._display_chat(msg))
                        last_id = m['id']
                time.sleep(self.CHAT_POLL_INTERVAL)

        t = threading.Thread(target=poll, daemon=True)
        t.start()
        self.threads.append(t)

    def _display_chat(self, msg):
        self.chat_log.config(state='normal')
        self.chat_log.insert(tk.END, f"{msg['sender']}: {msg['message']}\n", 'others')
        self.chat_log.config(state='disabled')
        self.chat_log.yview(tk.END)

    def start_participant_poller(self):
        def poll():
            while self.stop_flag["running"]:
                res = requests.get(f"{self.server_url}/get_accepted_users",
                                   params={"meeting_id": self.current_meeting_id})
                if res.status_code == 200:
                    ips = {u['ip'] for u in res.json().get('accepted_users', [])}
                    ips.discard(self.my_ip)
                    self.peer_ips = ips
                time.sleep(self.PARTICIPANT_POLL_INTERVAL)

        t = threading.Thread(target=poll, daemon=True)
        t.start()
        self.threads.append(t)

    def send_message(self, event=None):
        msg = self.entry_field.get().strip()
        if not msg:
            return
        threading.Thread(target=lambda: requests.post(f"{self.server_url}/send_message",
                                                      json={"sender": self.sender_id, "message": msg,
                                                            "meeting_id": self.current_meeting_id}),
                         daemon=True).start()
        self.chat_log.config(state='normal')
        self.chat_log.insert(tk.END, f"me: {msg}\n", 'me')
        self.chat_log.config(state='disabled')
        self.chat_log.yview(tk.END)
        self.entry_field.delete(0, tk.END)

    def open_add_participants_sidebar(self):
        if self.sidebar_window and self.sidebar_window.winfo_exists():
            self.sidebar_window.lift()
            return
        sidebar = tk.Toplevel(self.root)
        self.sidebar_window = sidebar
        sidebar.title("Add Participants")
        sidebar.geometry("300x400")
        sidebar.configure(bg="#1E1E1E")
        frm = tk.Frame(sidebar, bg="#1E1E1E")
        frm.pack(fill=tk.BOTH, expand=True, padx=10)

        def fetch():
            r = requests.get(f"{self.server_url}/online_users")
            if r.status_code == 200:
                for u in r.json():
                    self.display_user_in_sidebar(frm, u)

        fetch()
        sidebar.protocol("WM_DELETE_WINDOW", lambda: setattr(self, 'sidebar_window', None))

    def display_user_in_sidebar(self, parent, user):
        email = user.get('email', '?')
        status = user.get('status', 'offline')
        txt = 'Add' if status == 'online' else ('In Meeting' if status == 'in_meeting' else 'Offline')
        col = 'green' if status == 'online' else ('gray' if status == 'in_meeting' else 'red')
        st = tk.NORMAL if status == 'online' else tk.DISABLED
        row = tk.Frame(parent, bg="#2C2C2C", padx=5, pady=2)
        row.pack(fill=tk.X, pady=1)
        tk.Label(row, text=email, width=20, anchor='w', bg="#2C2C2C", fg='white').pack(side=tk.LEFT)
        tk.Button(row, text=txt, bg=col, fg='white', state=st,
                  command=lambda u=user: self._invite_and_close(u)).pack(side=tk.RIGHT)

    def _invite_and_close(self, user):
        # Send invite
        requests.post(f"{self.server_url}/request_join", json={
            "meeting_id": self.current_meeting_id,
            "email": user['email'],
            "requester": self.email
        })
        # Close sidebar
        if self.sidebar_window:
            self.sidebar_window.destroy()
            self.sidebar_window = None

    def toggle_mute(self):
        self.stop_flag['muted'] = not self.stop_flag['muted']
        self.mute_button.config(text='Unmute' if self.stop_flag['muted'] else 'Mute')

    def toggle_video(self):
        self.video_visible = not self.video_visible
        self.video_toggle_button.config(text='Hide Video' if self.video_visible else 'Show Video')

    def update_camera_count(self, event=None):
        try:
            cnt = int(self.camera_input.get())
        except:
            return
        for i, c in enumerate(self.video_canvases):
            if i < cnt:
                c.grid()
            else:
                c.grid_remove()

    def end_meeting(self):
        try:
            requests.post(f"{self.server_url}/end_meeting", json={"meeting_id": self.current_meeting_id})
            requests.post(f"{self.server_url}/update_status", json={{"email": self.email, "status": "online"}})
        except:
            pass
        self.cleanup_and_exit()

    def logout_via_exit(self):
        try:
            requests.post(f"{self.server_url}/update_status", json={"email": self.email, "status": "offline"})
        except:
            pass
        self.cleanup_and_exit()

    def cleanup_and_exit(self):
        self.stop_flag['running'] = False
        for t in self.threads:
            t.join(timeout=1)
        if hasattr(self, 'cap'):
            self.cap.release()
        self.audio_input.stop_stream()
        self.audio_input.close()
        self.audio_output.stop_stream()
        self.audio_output.close()
        self.audio.terminate()
        self.video_sender_socket.close()
        self.audio_sender_socket.close()
        self.root.destroy()
        if self.return_to_meeting_home:
            self.return_to_meeting_home(self.email)


if __name__ == '__main__':
    ChatClientGUI(server_url="http://127.0.0.1:5000")
