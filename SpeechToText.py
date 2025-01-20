import time
import keyboard
import os
import dotenv

dotenv.load_dotenv()

class SpeechToTextManager:
    azure_speech = None
    azure_audio = None
    azure_speechrecogniser = None

    def __init__(self):
        try:
            pass
            #self.azure_speech = speechsdk.SpeechConfig(subscription=os.getenv('AZURE_TTS_KEY'),
            #                                           region=os.getenv('AZURE_TTS_REGION'))
        except TypeError:
            exit("Environment variables not set")

    def speechtotext_from_mic(self):

        #self.azure_audio = speechsdk.audio.AudioConfig(use_default_microphone=True)
        #self.azure_speechrecogniser = speechsdk.SpeechRecognizer(speech_config=self.azure_speech,
        #                                                         audio_config=self.azure_audio)

        print("Speak into your microphone.")
        speech_recognition_result = self.azure_speechrecogniser.recognize_once_async().get()
        text_result = speech_recognition_result.text

        #if speech_recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:
        #    print("Recognized: {}".format(speech_recognition_result.text))
        #elif speech_recognition_result.reason == speechsdk.ResultReason.NoMatch:
        #    print("No speech could be recognized: {}".format(speech_recognition_result.no_match_details))
        #elif speech_recognition_result.reason == speechsdk.ResultReason.Canceled:
        #    cancellation_details = speech_recognition_result.cancellation_details
        #    print("Speech Recognition canceled: {}".format(cancellation_details.reason))
        #    if cancellation_details.reason == speechsdk.CancellationReason.Error:
        #        print("Error details: {}".format(cancellation_details.error_details))
        #        print("Did you set the speech resource key and region values?")

        print(f"We got the following text: {text_result}")
        return text_result

    def speechtotext_from_mic_continuous(self, stop_key='p'):
        #self.azure_speechrecogniser = speechsdk.SpeechRecognizer(speech_config=self.azure_speech,
        #                                                         audio_config=self.azure_audio)

        done = False

        # Optional callback to print out whenever a chunk of speech is being recognized.
        # This gets called basically every word.
        # def recognizing_cb(evt: speechsdk.SpeechRecognitionEventArgs):
        #    print('RECOGNIZING: {}'.format(evt))
        # self.azure_speechrecogniser.recognizing.connect(recognizing_cb)

        # Optional callback to print out whenever a chunk of speech is finished being recognized.
        # Make sure to let this finish before ending the speech recognition.
        #def recognized_cb(evt: speechsdk.SpeechRecognitionEventArgs):
        #    print('RECOGNIZED: {}'.format(evt))

        #self.azure_speechrecogniser.recognized.connect(recognized_cb)

        # We register this to fire if we get a session_stopped or cancelled event.
        #def stop_cb(evt: speechsdk.SessionEventArgs):
        #    print('CLOSING speech recognition on {}'.format(evt))
        #    nonlocal done
        #    done = True

        # Connect callbacks to the events fired by the speech recognizer
        #self.azure_speechrecogniser.session_stopped.connect(stop_cb)
        #self.azure_speechrecogniser.canceled.connect(stop_cb)

        # This is where we compile the results we receive from the ongoing "Recognized" events
        all_results = []

        def handle_final_result(evt):
            all_results.append(evt.result.text)

        #self.azure_speechrecogniser.recognized.connect(handle_final_result)

        # Perform recognition. `start_continuous_recognition_async asynchronously initiates continuous recognition operation,
        # Other tasks can be performed on this thread while recognition starts...
        # wait on result_future.get() to know when initialization is done.
        # Call stop_continuous_recognition_async() to stop recognition.
        result_future = self.azure_speechrecogniser.start_continuous_recognition_async()
        result_future.get()  # wait for voidfuture, so we know engine initialization is done.
        print('Continuous Speech Recognition is now running, say something.')

        while not done:
            # METHOD 1 - Press the stop key. This is 'p' by default but user can provide different key
            if keyboard.read_key() == stop_key:
                print("\nEnding azure speech recognition\n")
                #self.azure_speechrecogniser.stop_continuous_recognition_async()
                break
            # Other methods: https://stackoverflow.com/a/57644349

            # No real sample parallel work to do on this thread, so just wait for user to give the signal to stop.
            # Can't exit function or speech_recognizer will go out of scope and be destroyed while running.

        final_result = " ".join(all_results).strip()
        print(f"\n\nHere's the result we got!\n\n{final_result}\n\n")
        return final_result