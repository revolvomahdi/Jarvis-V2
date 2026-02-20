@echo off
echo [NASA AI] Installing Voice Requirements...
echo This will install torch, openai-whisper, and speech_recognition.
echo It might take a while (approx 1-2 GB).

pip install openai-whisper
pip install SpeechRecognition
pip install pyaudio
pip install pyttsx3

echo.
echo [INFO] For Premium TTS (Coqui), it is recommended to install it manually due to size:
echo pip install TTS
echo.
pause
