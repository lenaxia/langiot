from pathlib import Path
from io import BytesIO
import logging
import subprocess
import os
from pydub import AudioSegment
from pydub.playback import play
from piper import PiperVoice
from piper.download import ensure_voice_exists, get_voices, find_voice
import wave  # Import the wave module

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Configure the paths
PIPER_MODEL_NAME = "en_US-lessac-medium"
PIPER_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), ".piper", "downloads")

# Set synthesis parameters
PIPER_SYNTHESIS_ARGS = {
    "length_scale": 1.0,
    "noise_scale": 0.667,
    "noise_w": 0.8,
    "sentence_silence": 0.0,
}

def load_voice_model():
    # Create the required directories if they don't exist
    piper_download_dir = Path(PIPER_DOWNLOAD_DIR)
    piper_download_dir.mkdir(parents=True, exist_ok=True)

    voices_info = get_voices(PIPER_DOWNLOAD_DIR, update_voices=True)
    ensure_voice_exists(PIPER_MODEL_NAME, [PIPER_DOWNLOAD_DIR], PIPER_DOWNLOAD_DIR, voices_info)
    model_path, config_path = find_voice(PIPER_MODEL_NAME, [PIPER_DOWNLOAD_DIR])
    voice = PiperVoice.load(str(model_path), config_path=str(config_path), use_cuda=False)
    return voice

def generate_tts(text, locale="en"):
    logger.info(f"Generate TTS: [{locale}] {text}")
    if locale != "en":
        text = "Only English is currently supported for offline text to speech."

    try:
        audio_fp = BytesIO()
        with wave.open(audio_fp, "wb") as wav_file:
            voice.synthesize(text, wav_file, **PIPER_SYNTHESIS_ARGS)
        audio_fp.seek(0)
        logger.info(f"Generate TTS finished")
        return audio_fp.read()
    except Exception as e:
        raise Exception(f"Local TTS: Failed to generate speech: {text} {locale} {e}")

def play_audio(audio_data):
    audio_stream = BytesIO(audio_data)

    # Determine the audio format
    try:
        with wave.open(audio_stream, 'r') as wav:
            audio_format = 'wav'
    except wave.Error:
        audio_stream.seek(0)
        audio_format = 'mp3'

    audio_stream.seek(0)
    audio = AudioSegment.from_file(audio_stream, format=audio_format)
    silence = AudioSegment.silent(duration=100)  # 100 milliseconds of silence
    audio = silence + audio

    # Adjust volume
    audio = audio - 5  # Reduce volume by 5 dB

    audio = audio.set_channels(2)
    if audio_format == 'wav':
        audio = audio.set_frame_rate(22050)

    logger.info("Audio data loaded, starting playback.")
    play(audio)
    logger.info("Audio playback finished.")

def main():
    global voice
    voice = load_voice_model()
    text = "This is a test announcement from Piper TTS."
    tts_audio_bytes = generate_tts(text)
    play_audio(tts_audio_bytes)

if __name__ == "__main__":
    main()
