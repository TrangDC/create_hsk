# services/eng_audio_service.py
"""
English Audio Service — sinh file MP3 tiếng Anh cho flashcard.
Hỗ trợ 3 model:
    - Chirp3-HD: voice name = "en-US-Chirp3-HD-{Voice}"
    - gemini-3.1-flash-tts-preview: voice name = "{Voice}", cần thêm model_name vào VoiceSelectionParams
    - Narakeet: voice id trực tiếp, mặc định Lisa cho nữ và Jeff cho nam
"""

import os
import requests
from google.cloud import texttospeech
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()

LANGUAGE_CODE = "en-US"

# Các model được hỗ trợ
MODEL_CHIRP3   = "Chirp3-HD"
MODEL_GEMINI   = "gemini-3.1-flash-tts-preview"
MODEL_NARAKEET = "Narakeet"
SUPPORTED_MODELS = [MODEL_CHIRP3, MODEL_GEMINI, MODEL_NARAKEET]

NARAKEET_API_URL = "https://api.narakeet.com/text-to-speech/mp3"
NARAKEET_API_KEY = os.getenv("NARAKEET_API_KEY", "QXGh0KOTHI7CaR9Vdh61M77FPRV98ZBMdNALHcsd")

# Voice mặc định cho các model Google TTS
DEFAULT_WORD_VOICE    = "Aoede"   # Nữ — đọc từ đơn
DEFAULT_EXAMPLE_VOICE = "Charon"  # Nam — đọc câu ví dụ
NARAKEET_WORD_VOICE = "Lisa"      # Nữ — đọc từ đơn
NARAKEET_EXAMPLE_VOICE = "Jeff"   # Nam — đọc câu ví dụ


class EngAudioService:
    """
    Sinh audio tiếng Anh cho flashcard.

    Cách dùng:
        svc = EngAudioService(model_name="Chirp3-HD")
        svc.generate_word("apple",            "output/audio/apple.mp3")
        svc.generate_example("I eat an apple.", "output/audio/apple_example.mp3")
    """

    WORD_VOICE    = DEFAULT_WORD_VOICE
    EXAMPLE_VOICE = DEFAULT_EXAMPLE_VOICE

    def __init__(
        self,
        model_name: str    = MODEL_CHIRP3,
        word_voice: str    = DEFAULT_WORD_VOICE,
        example_voice: str = DEFAULT_EXAMPLE_VOICE,
        language_code: str = LANGUAGE_CODE,
    ):
        self.model_name    = model_name if model_name in SUPPORTED_MODELS else MODEL_CHIRP3
        if self.model_name == MODEL_NARAKEET:
            self.word_voice = NARAKEET_WORD_VOICE if word_voice == DEFAULT_WORD_VOICE else word_voice
            self.example_voice = NARAKEET_EXAMPLE_VOICE if example_voice == DEFAULT_EXAMPLE_VOICE else example_voice
        else:
            self.word_voice = word_voice
            self.example_voice = example_voice
        self.language_code = language_code
        self.client        = self._init_client()

    # ------------------------------------------------------------------
    # Khởi tạo TTS client
    # ------------------------------------------------------------------
    def _init_client(self):
        if self.model_name == MODEL_NARAKEET:
            return bool(NARAKEET_API_KEY)

        try:
            creds = service_account.Credentials.from_service_account_info({
                "type":                        os.getenv("TYPE"),
                "project_id":                  os.getenv("PROJECT_ID"),
                "private_key_id":              os.getenv("PRIVATE_KEY_ID"),
                "private_key":                 os.getenv("PRIVATE_KEY", "").replace("\\n", "\n"),
                "client_email":                os.getenv("CLIENT_EMAIL"),
                "client_id":                   os.getenv("CLIENT_ID", ""),
                "auth_uri":                    os.getenv("AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
                "token_uri":                   os.getenv("TOKEN_URI", "https://oauth2.googleapis.com/token"),
                "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_X509_CERT_URL", "https://www.googleapis.com/oauth2/v1/certs"),
                "client_x509_cert_url":        os.getenv("CLIENT_X509_CERT_URL", ""),
                "universe_domain":             os.getenv("UNIVERSE_DOMAIN", "googleapis.com"),
            })
            return texttospeech.TextToSpeechClient(credentials=creds)
        except Exception as e:
            print(f"❌ [EngAudioService] Lỗi khởi tạo TTS client: {e}")
            return None

    # ------------------------------------------------------------------
    # Xây dựng voice params — khác nhau giữa Chirp3-HD và Gemini TTS
    # ------------------------------------------------------------------
    def _get_voice_name(self, voice_key: str) -> str:
        """
        Chirp3-HD  → "en-US-Chirp3-HD-Aoede"
        Gemini TTS → "Aoede"  (chỉ tên voice, không prefix)
        Narakeet   → "Lisa" / "Jeff" (voice id trực tiếp)
        """
        if self.model_name == MODEL_CHIRP3:
            return f"{self.language_code}-{self.model_name}-{voice_key}"
        else:
            return voice_key

    def _build_voice_params(self, voice_key: str) -> texttospeech.VoiceSelectionParams:
        """
        Chirp3-HD  → VoiceSelectionParams(language_code, name)
        Gemini TTS → VoiceSelectionParams(language_code, name, model_name)
                     (Gemini yêu cầu model_name trong params)
        """
        voice_name = self._get_voice_name(voice_key)

        if self.model_name == MODEL_GEMINI:
            return texttospeech.VoiceSelectionParams(
                language_code=self.language_code,
                name=voice_name,
                model_name=self.model_name,
            )
        else:
            # Chirp3-HD — không có model_name trong params
            return texttospeech.VoiceSelectionParams(
                language_code=self.language_code,
                name=voice_name,
            )

    # ------------------------------------------------------------------
    # Sinh audio
    # ------------------------------------------------------------------
    def _generate_with_narakeet(self, text: str, out_path: str, voice: str) -> bool:
        if not NARAKEET_API_KEY:
            print("❌ [EngAudioService] Thiếu NARAKEET_API_KEY.")
            return False

        response = requests.post(
            f"{NARAKEET_API_URL}?voice={voice}",
            headers={
                "Accept": "application/octet-stream",
                "Content-Type": "text/plain",
                "x-api-key": NARAKEET_API_KEY,
            },
            data=text.encode("utf8"),
            timeout=60,
        )

        if response.status_code != 200:
            print(f"❌ [EngAudioService] Lỗi Narakeet ({response.status_code}): {response.text}")
            return False

        with open(out_path, "wb") as f:
            f.write(response.content)

        return True

    def generate(self, text: str, out_path: str, voice: str | None = None, overwrite: bool = False) -> bool:
        """
        Sinh file MP3 từ text tiếng Anh.

        Args:
            text:     Nội dung cần đọc.
            out_path: Đường dẫn lưu file MP3.
            voice:    Tên voice (mặc định dùng word_voice).
        Returns:
            True nếu thành công, False nếu lỗi.
        """
        if not text or not text.strip():
            return False

        if not self.client:
            print("❌ [EngAudioService] Client chưa được khởi tạo.")
            return False

        # Bỏ qua nếu file đã tồn tại và không yêu cầu ghi đè
        if os.path.exists(out_path) and not overwrite:
            return True

        parent_dir = os.path.dirname(out_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        actual_voice = voice or self.word_voice

        try:
            if self.model_name == MODEL_NARAKEET:
                return self._generate_with_narakeet(text=text, out_path=out_path, voice=actual_voice)

            response = self.client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=text),
                voice=self._build_voice_params(actual_voice),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3,
                    speaking_rate=0.9,  # Hơi chậm để học viên nghe rõ
                ),
            )

            with open(out_path, "wb") as f:
                f.write(response.audio_content)

            return True

        except Exception as e:
            print(f"❌ [EngAudioService] Lỗi sinh audio '{text[:30]}': {e}")
            return False

    def generate_word(self, word: str, out_path: str, overwrite: bool = False) -> bool:
        """Sinh audio cho từ đơn (dùng word_voice)."""
        return self.generate(text=word, out_path=out_path, voice=self.word_voice, overwrite=overwrite)

    def generate_example(self, sentence: str, out_path: str, overwrite: bool = False) -> bool:
        """Sinh audio cho câu ví dụ (dùng example_voice)."""
        return self.generate(text=sentence, out_path=out_path, voice=self.example_voice, overwrite=overwrite)
