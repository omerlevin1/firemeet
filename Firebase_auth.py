# === firebase_auth.py ===
import pyrebase


class FirebaseAuthClient:
    def __init__(self):
        config = {
            "apiKey": "AIzaSyD2fNchOZEIJyC2esxkXu2J5Twikqm7IAs",
            "authDomain": "cyber-project-7879c.firebaseapp.com",
            "databaseURL": "https://cyber-project-7879c-default-rtdb.europe-west1.firebasedatabase.app",
            "projectId": "cyber-project-7879c",
            "storageBucket": "cyber-project-7879c.appspot.com",
            "messagingSenderId": "199516883403",
            "appId": "1:199516883403:web:550830b86521340991ce4e",
            "measurementId": "G-QXR0X194D0"
        }

        self.firebase = pyrebase.initialize_app(config)
        self.auth = self.firebase.auth()

    def login_user(self, email, password):
        try:
            user = self.auth.sign_in_with_email_and_password(email, password)
            id_token = user["idToken"]
            refresh_token = user["refreshToken"]
            return True, {"idToken": id_token, "refreshToken": refresh_token, "email": email}
        except Exception as e:
            return False, str(e)

    def signup_user(self, email, password):
        try:
            user = self.auth.create_user_with_email_and_password(email, password)
            return True, user
        except Exception as e:
            return False, str(e)
