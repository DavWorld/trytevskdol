import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
import pyaudio
import wave
import threading
import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload
from pydub import AudioSegment
import time

kivy.require('1.11.1')

class AudioRecorderKivyApp(App):
    def build(self):
        self.record_number = 0
        self.record_duration = 7  # Recording duration in seconds
        self.recording = False
        self.audio_filename = ""
        self.pending_uploads = []  # Store pending uploads

        layout = BoxLayout(orientation='vertical')
        self.status_label = Label(text="Press 'Record' to start recording.")
        self.record_button = Button(text="Record")
        self.record_button.bind(on_release=self.toggle_recording)

        layout.add_widget(self.status_label)
        layout.add_widget(self.record_button)

        return layout

    def toggle_recording(self, instance):
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        self.record_number += 1
        self.recording = True
        self.record_button.text = "Stop Recording"
        self.status_label.text = "Recording..."
        threading.Thread(target=self._record_audio).start()

    def stop_recording(self):
        self.recording = False
        self.record_button.text = "Record"
        self.status_label.text = f"Recording saved as {self.audio_filename}"
        threading.Thread(target=self.upload_to_google_drive).start()

    def _record_audio(self):
        chunk = 1024
        audio_format = pyaudio.paInt16
        channels = 1
        rate = 44100

        p = pyaudio.PyAudio()

        stream = p.open(format=audio_format,
                        channels=channels,
                        rate=rate,
                        input=True,
                        frames_per_buffer=chunk)

        frames = []

        for _ in range(0, int(rate / chunk * self.record_duration)):
            if not self.recording:
                break
            data = stream.read(chunk)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        p.terminate()

        self.audio_filename = f"audio{self.record_number}.wav"

        wf = wave.open(self.audio_filename, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(audio_format))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))
        wf.close()

        # Convert the recorded audio to MP3
        audio = AudioSegment.from_wav(self.audio_filename)
        mp3_filename = self.audio_filename.replace(".wav", ".mp3")
        audio.export(mp3_filename, format="mp3")

        # Delete the original WAV file
        os.remove(self.audio_filename)

        self.audio_filename = mp3_filename

        # Schedule the next recording after 30 second
        threading.Thread(target=self.schedule_next_recording).start()

    def schedule_next_recording(self):
        time.sleep(30)  # Sleep for 30s
        self.start_recording()

    def upload_to_google_drive(self):
        # Your Google Drive API integration code goes here
        # You need to authenticate and use the Google Drive API to upload the audio file

        # Example code to authenticate with Google Drive API:
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        creds = None

        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    r'C:\Users\HP\OneDrive\Desktop\TRU 2\tru.json', SCOPES)  # Replace with your client secret file
                creds = flow.run_local_server(port=0)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        service = build('drive', 'v3', credentials=creds)

        # Define the folder ID where you want to store the audio files
        # Replace 'YOUR_FOLDER_ID_HERE' with the actual folder ID of your Google Drive folder
        folder_id = '1EP-3A03kZzN59pwOUU7oJHmggVrvtgTA'

        # Define the audio file to upload
        file_metadata = {
            'name': self.audio_filename,
            'mimeType': 'audio/mp3',
            'parents': [folder_id]  # Use the folder ID to specify the target folder
        }

        media = MediaFileUpload(self.audio_filename, mimetype='audio/mp3')
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        print(f'File uploaded to your Google Drive folder. File ID: {file.get("id")}')

        # Add the uploaded file to the pending uploads list
        self.pending_uploads.append(self.audio_filename)

        # Check for and upload any pending audio files
        self.upload_pending_audio_files(service, folder_id)

    def upload_pending_audio_files(self, service, folder_id):
        # Get the current time
        current_time = time.time()

        # Iterate through the pending uploads and upload any scheduled files
        for filename in self.pending_uploads:
            # Get the creation time of the file
            created_time = os.path.getctime(filename)
            if (current_time - created_time) < 30:  # Check if the file was created within the 30 second
                media = MediaFileUpload(filename, mimetype='audio/mp3')
                service.files().update(fileId=filename, media_body=media).execute()
                print(f'Pending file uploaded to Google Drive. File ID: {filename}')

                # Remove the uploaded file from the pending uploads list
                self.pending_uploads.remove(filename)

    def on_stop(self):
        # Cancel any remaining recording or uploading threads when the app is closed
        self.recording = False

if __name__ == '__main__':
    AudioRecorderKivyApp().run()