# === firemeet_home.py ===
import tkinter as tk
from tkinter import messagebox
import sys
import socket
import requests
import threading
import time
from client.gui.chat_gui_flask import ChatClientGUI


class FireMeetHome:
    def __init__(self, email=None):
        self.email = email
        self.root = tk.Tk()
        self.root.title("FireMEET")
        self.root.geometry("800x600")
        self.root.configure(bg="#0B1E3D")  # Dark blue background
        self.server_url = "http://172.16.1.33:5000"  # Adjust as needed
        self.root.protocol("WM_DELETE_WINDOW", lambda: self.logout_via_exit(self.root))
        self.seen_requests = set()  # inside __init__

        self.build_ui()
        self.root.mainloop()

    def build_ui(self):
        title = tk.Label(self.root, text="FireMEET", font=("Arial", 48, "bold"), fg="white", bg="#0B1E3D")
        title.pack(pady=40)

        button_frame = tk.Frame(self.root, bg="#0B1E3D")
        button_frame.pack(pady=20)

        btn_font = ("Arial", 16)
        login_btn = tk.Button(button_frame, text="Login", width=18, height=2, font=btn_font,
                              command=self.open_login_gui)
        signup_btn = tk.Button(button_frame, text="Sign Up", width=18, height=2, font=btn_font,
                               command=self.open_signup_gui)
        about_btn = tk.Button(button_frame, text="About Us", width=18, height=2, font=btn_font, command=self.about)
        exit_btn = tk.Button(button_frame, text="Exit", width=18, height=2, font=btn_font, command=self.root.quit)

        for btn in [login_btn, signup_btn, about_btn, exit_btn]:
            btn.pack(pady=8)

    def open_login_gui(self):
        self.root.withdraw()
        login_win = tk.Toplevel()
        login_win.title("Login")
        login_win.geometry("400x350")
        login_win.configure(bg="#0B1E3D")
        login_win.protocol("WM_DELETE_WINDOW", lambda: self.logout_via_exit(login_win))

        tk.Label(login_win, text="Email:", fg="white", bg="#0B1E3D").pack(pady=5)
        email_entry = tk.Entry(login_win, width=30)
        email_entry.pack(pady=5)

        tk.Label(login_win, text="Password:", fg="white", bg="#0B1E3D").pack(pady=5)
        password_entry = tk.Entry(login_win, show='*', width=30)
        password_entry.pack(pady=5)

        def toggle_password():
            if password_entry.cget('show') == '':
                password_entry.config(show='*')
                toggle_btn.config(text="Show")
            else:
                password_entry.config(show='')
                toggle_btn.config(text="Hide")

        toggle_btn = tk.Button(login_win, text="Show", font=("Arial", 6), width=2, command=toggle_password)
        toggle_btn.pack(pady=5)

        def submit_login(event=None):
            email = email_entry.get()
            password = password_entry.get()
            if not email or not password:
                messagebox.showwarning("Login Error", "Both email and password must be filled.")
                return
            self.handle_login(email, password)

        tk.Button(login_win, text="Login", command=submit_login).pack(pady=10)
        back_btn = tk.Button(login_win, text="Go Back", command=lambda: self.back_to_main(login_win))
        back_btn.pack(pady=10)

        login_win.bind('<Return>', submit_login)

    def open_meeting_homepage(self, email):
        self.email = email
        self.root.withdraw()
        meet_win = tk.Toplevel()
        meet_win.protocol("WM_DELETE_WINDOW", lambda: self.logout_via_exit(meet_win))
        meet_win.title("FireMEET - Meeting Home")
        meet_win.geometry("500x400")
        meet_win.configure(bg="#0B1E3D")
        meet_win.protocol("WM_DELETE_WINDOW", lambda: self.logout_via_exit(meet_win))

        tk.Label(meet_win, text=f"Welcome, {email}!", font=("Arial", 20, "bold"), fg="white", bg="#0B1E3D").pack(
            pady=30)

        btn_font = ("Arial", 16)
        tk.Button(meet_win, text="Start New Meeting", font=btn_font, width=20,
                  command=lambda: self.start_meeting_logic(email, meet_win)).pack(pady=10)

        tk.Button(meet_win, text="Join a Meeting", font=btn_font, width=20,
                  command=lambda: self.prompt_join_meeting(meet_win)).pack(pady=10)

        tk.Button(meet_win, text="Logout", font=btn_font, width=20,
                  command=lambda: self.logout_and_return(meet_win)).pack(pady=30)

        self.poll_for_join_requests(email, meet_win)

    def prompt_join_meeting(self, parent_win):
        join_win = tk.Toplevel(self.root)
        join_win.title("Join Meeting")
        join_win.geometry("350x200")
        join_win.configure(bg="#0B1E3D")

        tk.Label(join_win, text="Enter Meeting ID:", fg="white", bg="#0B1E3D").pack(pady=10)
        meeting_entry = tk.Entry(join_win, width=25)
        meeting_entry.pack(pady=5)

        def send_join_request():
            meeting_id = meeting_entry.get().strip()
            if not meeting_id:
                messagebox.showwarning("Missing ID", "Please enter a meeting ID.")
                return

            try:
                res = requests.post(f"{self.server_url}/request_join_by_id", json={
                    "meeting_id": meeting_id,
                    "email": self.email
                })

                if res.status_code == 200 and res.json().get("success"):
                    messagebox.showinfo("Requested", "Join request sent! Waiting for approval.")
                    join_win.destroy()

                    def poll_for_response():
                        while True:
                            r = requests.get(f"{self.server_url}/get_meeting_info", params={"meeting_id": meeting_id})
                            if r.status_code == 200:
                                accepted = r.json().get("accepted_users", [])
                                if self.email in accepted:
                                    host_email = r.json().get("host", "")
                                    ip = "127.0.0.1"
                                    try:
                                        online_users = requests.get(f"{self.server_url}/online_users").json()
                                        for u in online_users:
                                            if u["email"] == host_email:
                                                ip = u.get("ip", ip)
                                    except:
                                        pass

                                    self.root.withdraw()
                                    parent_win.destroy()
                                    ChatClientGUI(
                                        server_url=self.server_url,
                                        meeting_id=meeting_id,
                                        return_to_meeting_home=self.open_meeting_homepage,
                                        email=self.email,
                                        host_ip=ip
                                    )
                                    break
                            time.sleep(2)

                    threading.Thread(target=poll_for_response, daemon=True).start()

                else:
                    messagebox.showerror("Error", res.json().get("message", "Unknown error"))
            except Exception as e:
                messagebox.showerror("Error", str(e))

        tk.Button(join_win, text="Send Join Request", bg="green", fg="white", command=send_join_request).pack(pady=15)
        tk.Button(join_win, text="Cancel", command=join_win.destroy).pack()

    def start_meeting_logic(self, email, current_window):
        token = self.last_token if hasattr(self, "last_token") else None
        if not token:
            messagebox.showerror("Error", "Token not found. Please log in again.")
            return

        try:
            response = requests.post(
                f"{self.server_url}/start_meeting",
                json={"token": token}
            )
            result = response.json()
            if result.get("success"):
                meeting_id = result["meeting_id"]
                current_window.destroy()
                messagebox.showinfo("Meeting Started", f"Meeting ID: {meeting_id}")
                self.root.withdraw()
                ChatClientGUI(
                    server_url=self.server_url,
                    meeting_id=meeting_id,
                    return_to_meeting_home=self.open_meeting_homepage,
                    email=self.email
                )
            else:
                messagebox.showwarning("Start Failed", result.get("message", "Unknown error"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    import sys

    import sys

    def logout_via_exit(self, win=None):
        import sys
        try:
            if self.email:
                requests.post(f"{self.server_url}/update_status", json={
                    "email": self.email,
                    "status": "offline"
                })
        except Exception as e:
            print(f"[ERROR] Failed to update status on exit: {e}")

        try:
            target = win if win else self.root
            if target.winfo_exists():
                target.destroy()
        except Exception as e:
            print(f"[ERROR] Failed to destroy window: {e}")

        try:
            for widget in self.root.winfo_children():
                try:
                    widget.destroy()
                except:
                    pass
        except:
            pass

        try:
            self.root.quit()
        except:
            pass

        sys.exit(0)

    def logout_and_return(self, current_win):
        try:
            requests.post(f"{self.server_url}/update_status", json={
                "email": self.email,
                "status": "offline"
            })
        except Exception as e:
            print(f"[ERROR] Failed to update status on logout: {e}")

        current_win.destroy()
        self.root.deiconify()

    def open_signup_gui(self):
        self.root.withdraw()
        signup_win = tk.Toplevel()
        signup_win.title("Sign Up")
        signup_win.geometry("400x500")
        signup_win.configure(bg="#0B1E3D")
        signup_win.protocol("WM_DELETE_WINDOW", lambda: self.logout_via_exit(signup_win))

        ip_address = socket.gethostbyname(socket.gethostname())

        tk.Label(signup_win, text="Name:", fg="white", bg="#0B1E3D").pack(pady=5)
        name_entry = tk.Entry(signup_win, width=30)
        name_entry.pack(pady=5)

        tk.Label(signup_win, text="Email:", fg="white", bg="#0B1E3D").pack(pady=5)
        email_entry = tk.Entry(signup_win, width=30)
        email_entry.pack(pady=5)

        tk.Label(signup_win, text="Password:", fg="white", bg="#0B1E3D").pack(pady=5)
        password_entry = tk.Entry(signup_win, show='*', width=30)
        password_entry.pack(pady=5)

        def toggle_signup_pw():
            if password_entry.cget('show') == '':
                password_entry.config(show='*')
                toggle_pw_btn.config(text="Show")
            else:
                password_entry.config(show='')
                toggle_pw_btn.config(text="Hide")

        toggle_pw_btn = tk.Button(signup_win, text="Show", font=("Arial", 6), width=2, command=toggle_signup_pw)
        toggle_pw_btn.pack(pady=5)

        strength_label = tk.Label(signup_win, text="", bg="#0B1E3D")
        strength_label.pack(pady=5)

        submit_button = tk.Button(signup_win, text="Sign Up")
        submit_button.pack(pady=10)

        def is_strong(password):
            return len(password) >= 6 and any(c.isupper() for c in password) and any(c.isdigit() for c in password)

        def update_strength(*args):
            password = password_entry.get()
            if is_strong(password):
                strength_label.config(text="Strong Password", fg="lightgreen")
                submit_button.config(state=tk.NORMAL)
            else:
                strength_label.config(text="Weak Password", fg="red")
                submit_button.config(state=tk.NORMAL)

        password_entry.bind('<KeyRelease>', update_strength)

        tk.Label(signup_win, text="IP Address (auto-filled):", fg="white", bg="#0B1E3D").pack(pady=5)
        ip_label = tk.Label(signup_win, text=ip_address, fg="white", bg="#0B1E3D")
        ip_label.pack(pady=5)

        def submit_signup(event=None):
            name = name_entry.get()
            email = email_entry.get()
            password = password_entry.get()
            if not name or not email or not password:
                messagebox.showwarning("Signup Error", "All fields must be filled.")
                return
            if "@" not in email or not email.endswith(".com"):
                messagebox.showwarning("Signup Error", "Please enter a valid .com email address.")
                return
            if not is_strong(password):
                messagebox.showwarning("Signup Error",
                                       "Your password must have at least 6 characters, include one capital letter, and one number.")
                return
            self.handle_signup(name, email, password, ip_address)

        submit_button.config(command=submit_signup)
        signup_win.bind('<Return>', submit_signup)

        back_btn = tk.Button(signup_win, text="Go Back", command=lambda: self.back_to_main(signup_win))
        back_btn.pack(pady=10)

    def back_to_main(self, window):
        window.destroy()
        self.root.deiconify()

    def handle_login(self, email, password):
        try:
            response = requests.post(
                f"{self.server_url}/login",
                json={
                    "email": email,
                    "password": password
                }
            )
            result = response.json()
            if result.get("success"):
                self.last_token = result['data']['idToken']
                login_win = self.root.winfo_children()[-1]
                login_win.destroy()
                self.open_meeting_homepage(result['data']['email'])
            else:
                messagebox.showwarning("Login Failed", result.get("message", "Unknown error"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def handle_signup(self, name, email, password, ip):
        try:
            response = requests.post(
                f"{self.server_url}/signup",
                json={
                    "name": name,
                    "email": email,
                    "password": password,
                    "ip": ip
                }
            )
            result = response.json()
            if result.get("success"):
                self.last_token = result['data']['idToken']
                messagebox.showinfo("Sign Up", f"Account created for {email}")
                signup_win = self.root.winfo_children()[-1]
                signup_win.destroy()
                self.open_meeting_homepage(email)
            else:
                messagebox.showwarning("Signup Failed", result.get("message", "Unknown error"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def about(self):
        messagebox.showinfo("About Us", "FireMEET is a secure peer-to-peer video chat platform.")

    def poll_for_join_requests(self, email, win):
        def loop():
            while win.winfo_exists():
                try:
                    print("in here")
                    res = requests.get(f"{self.server_url}/get_pending_requests", params={"email": email})
                    if res.status_code == 200:
                        data = res.json()
                        if data.get("pending"):
                            requester = data.get("requester")
                            meeting_id = data.get("meeting_id")
                            unique_key = f"{meeting_id}:{requester}:{email}"

                            if unique_key in self.seen_requests:
                                continue  # skip duplicate request we've already handled

                            self.seen_requests.add(unique_key)
                            print("[DEBUG] Showing popup for:", unique_key)
                            self.root.after(0, lambda: self.show_join_popup(email, requester, meeting_id, win))
                except Exception as e:
                    print(f"[ERROR] Polling join request: {e}")
                time.sleep(4)

        threading.Thread(target=loop, daemon=True).start()

    def show_join_popup(self, email, requester, meeting_id, win):
        popup = tk.Toplevel(self.root)
        popup.title("Join Request")
        popup.geometry("300x150")
        popup.configure(bg="#1E1E1E")

        popup.resizable(False, False)  # 🧱 Prevent resizing
        popup.protocol("WM_DELETE_WINDOW", lambda: None)  # 🔒 Disable the X button

        tk.Label(popup, text=f"{requester} invited you to join a meeting!",
                 bg="#1E1E1E", fg="white", font=("Arial", 10, "bold")).pack(pady=20)

        def respond(answer):
            try:
                print(
                    f"[CLIENT] You {'ACCEPTED' if answer == 'accept' else 'DECLINED'} the invitation from {requester} to join meeting {meeting_id}")

                res = requests.post(f"{self.server_url}/respond_join_request", json={
                    "meeting_id": meeting_id,
                    "email": email,
                    "response": answer
                })

                if answer == "accept" and res.status_code == 200:
                    host_ip = res.json().get("host_ip", "127.0.0.1")
                    print(f"[P2P] Received host IP: {host_ip}")

                    popup.destroy()
                    self.root.withdraw()
                    ChatClientGUI(
                        server_url=self.server_url,
                        meeting_id=meeting_id,
                        return_to_meeting_home=self.open_meeting_homepage,
                        email=email,
                        host_ip=host_ip
                    )
                    return

                elif answer == "decline":
                    unique_key = f"{meeting_id}:{requester}:{email}"
                    if unique_key in self.seen_requests:
                        self.seen_requests.remove(unique_key)

            except Exception as e:
                print(f"[ERROR] Join response failed: {e}")

            popup.destroy()

        tk.Button(popup, text="Accept", bg="green", fg="white", command=lambda: respond("accept")).pack(pady=5)
        tk.Button(popup, text="Decline", bg="red", fg="white", command=lambda: respond("decline")).pack(pady=5)


if __name__ == '__main__':
    FireMeetHome()
