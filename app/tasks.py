# app/tasks.py
import os
import threading
import re
import json
import base64
import shutil
import time
import subprocess
import contextlib
import wave
from uuid import uuid4

from celery import Celery
from gradio_client import Client, handle_file
import requests
import asyncio
import tempfile

from telethon import TelegramClient
from gradio_client import Client, handle_file
import base64, re, os, sys
from config import (
    REDIS_URL,
    GRADIO_URL,
    API_ID,
    API_HASH,
    BOT_TOKEN,
    TTS_PROVIDER_MAP,
    WORKER_NUMBER,
    OUTPUT_DIR,
    ACCENT_URL,
    API_TOKEN,
    FISH_API_KEY,
)
from ui_components import MAIN_MENU_BUTTONS_COMMANDS
from db import consume_credit, increase_model_count
from fish_audio_sdk import Session, TTSRequest, ReferenceAudio, ASRRequest


def wait_for_gradio(url, timeout=60, interval=3):
    start = time.time()
    while True:
        try:
            # Пробуем сделать обычный GET-запрос, чтобы проверить доступность
            response = requests.get(url)
            if response.status_code == 200:
                print("Gradio сервис доступен")
                return
        except requests.exceptions.RequestException:
            pass
        if time.time() - start > timeout:
            raise TimeoutError(f"Сервис Gradio не открылся за {timeout} секунд")
        print("Ждем пока сервис Gradio запустится...")
        time.sleep(interval)


# путь модели внутри контейнера (как вы указали)
MODEL_IN_CONTAINER = "/app/models/F5TTS_v1_Base_v2/model_last_inference.safetensors"
# vocab (если есть)
VOCAB_IN_CONTAINER = "/app/models/F5TTS_v1_Base_v2/vocab.txt"
# пример конфигурации (одна из опций, показанных в inspect)
CUSTOM_MODEL_CFG = '{"dim": 1024, "depth": 22, "heads": 16, "ff_mult": 2, "text_dim": 512, "conv_layers": 4}'


def try_set_custom_model(client):
    """
    Попробуем несколько форматов и endpoints, чтобы заставить сервер загрузить файл модели:
      1) Попробовать endpoint /set_custom_model (и _1/_2) с аргументом равным пути в контейнере.
      2) Попробовать file:// URI.
      3) Если у вас модель есть на HuggingFace, подставьте hf://... (не реализовано здесь).
    Возвращает True если вызов прошёл без исключений.
    """
    candidates = [
        ("/set_custom_model", MODEL_IN_CONTAINER),
        ("/set_custom_model_1", MODEL_IN_CONTAINER),
        ("/set_custom_model_2", MODEL_IN_CONTAINER),
        ("/set_custom_model", f"file://{MODEL_IN_CONTAINER}"),
        ("/set_custom_model_1", f"file://{MODEL_IN_CONTAINER}"),
        ("/set_custom_model_2", f"file://{MODEL_IN_CONTAINER}"),
    ]
    for api_name, ckpt_path in candidates:
        try:
            print(
                f"Попытка установить модель через {api_name} с custom_ckpt_path={ckpt_path} ..."
            )
            # форма: predict(custom_ckpt_path, custom_vocab_path, custom_model_cfg, api_name=...)
            # передаём позиционно (gradio_client лучше работает с позиционными args)
            res = client.predict(
                ckpt_path, VOCAB_IN_CONTAINER, CUSTOM_MODEL_CFG, api_name=api_name
            )
            # Обычно set_custom_model возвращает None, но если нет исключения — шанс что сработало.
            print(f"Вызов {api_name} завершился (результат: {res})")
            return True
        except Exception as e:
            print(f"{api_name} с {ckpt_path} — ошибка: {e}")
    print(
        "Не удалось явно установить модель через set_custom_model endpoints (см. выше)."
    )
    return False


# Ждем доступности сервиса перед созданием клиента
_gradio_client = None
_gradio_lock = threading.Lock()


def get_gradio_client():
    global _gradio_client
    if _gradio_client is None:
        with _gradio_lock:
            if _gradio_client is None:
                # блокирующая проверка доступности
                wait_for_gradio(GRADIO_URL)
                _gradio_client = Client(GRADIO_URL)
                # опционально: попытаться загрузить модель один раз для процесса
                try:
                    try_set_custom_model(_gradio_client)
                except Exception as e:
                    print("Не удалось установить модель при инициализации:", e)
    return _gradio_client


def call_s1_tts(
    ref_audio_local_path: str, gen_text: str, out_path: str, model="s1", format="wav"
):
    """
    Генерирует речь через Fish Audio (openaudio s1) SDK.
    - ref_audio_local_path: локальный путь к референсу (wav/ogg/mp3)
    - gen_text: текст для синтеза
    - out_path: куда записать результирующий файл (например temp_xxx.wav)
    - model: "s1" по умолчанию
    - format: желаемый формат ("wav" предпочтительно для последующей конкатенации)
    Возвращает out_path при успехе, иначе None.
    """

    if not FISH_API_KEY:
        print("FISH_API_KEY не задан; пропускаем call_s1_tts")
        return None

    try:
        session = Session(FISH_API_KEY)
        # читаем референс
        with open(ref_audio_local_path, "rb") as f:
            audio_data = f.read()
        try:
            # если хотите принудительно английский: language="en"
            asr_resp = session.asr(ASRRequest(audio=audio_data, language="en"))
        except Exception as e:
            print("ASR error:", e)
            raise
        request = TTSRequest(
            text=gen_text,
            references=[
                ReferenceAudio(
                    audio=audio_data,
                    text=asr_resp.text,  # текст, совпадающий с референсом; можно оставить пустым
                )
            ],
            # параметры: подберите по нуждам; используем WAV для удобства
            format=format,
            # можно добавить temperature=0.9, top_p=0.9 и т.д.
            # temperature=0.9, top_p=0.9
        )

        # Стримим в файл
        with open(out_path, "wb") as out_f:
            for chunk in session.tts(request, "s1"):
                out_f.write(chunk)

        # Убедимся, что файл не пустой
        if os.path.exists(out_path) and os.path.getsize(out_path) > 100:
            return out_path
        else:
            print("call_s1_tts: получен пустой файл")
            return None

    except Exception as e:
        print("call_s1_tts error:", e)
        return None


def create_ivc_from_paths(client, name, paths):
    # Вариант: передаём пути
    voice = client.voices.ivc.create(
        name=name,
        files=paths,  # SDK поддерживает список путей
    )
    return voice


from config import ELEVENLABS_API_KEY
from elevenlabs.client import ElevenLabs
from io import BytesIO

elevenlabs = ElevenLabs(api_key=ELEVENLABS_API_KEY)
output_format = "mp3_44100_128"


def call_elevenlabs_tts(
    clone_name,
    ref_audio_local_path: str,
    gen_text: str,
    out_path: str,
    format="wav",
):
    """
    Генерирует речь через ElevenLabs SDK.
    - ref_audio_local_path: локальный путь к референсу (wav/ogg/mp3)
    - gen_text: текст для синтеза
    - out_path: куда записать результирующий файл (например temp_xxx.wav)
    - model: "s1" по умолчанию
    - format: желаемый формат ("wav" предпочтительно для последующей конкатенации)
    Возвращает out_path при успехе, иначе None.
    """

    if not ELEVENLABS_API_KEY:
        print("ELEVENLABS_API_KEY не задан; пропускаем call_elevenlabs_tts")
        return None

    try:
        voice = elevenlabs.voices.ivc.create(
            name=clone_name,
            # Replace with the paths to your audio files.
            # The more files you add, the better the clone will be.
            files=[BytesIO(open(ref_audio_local_path, "rb").read())],
        )

        print("SSSSSSSSSSSSSSS2")
        response = elevenlabs.text_to_speech.convert(
            text=gen_text,
            voice_id=voice.voice_id,
            model_id="eleven_multilingual_v2",  # рекомендуемая мультиязычная модель
            output_format=output_format,
        )
        print("SSSSSSSSSSSSSSS3")
        with open(out_path, "wb") as f:
            for chunk in response:
                if chunk:
                    f.write(chunk)
        return out_path

    except Exception as e:
        print("call_s1_tts error:", e)
        raise


def call_basic_tts_and_save(
    ref_audio,
    ref_text,
    gen_text,
    out_path="out_from_basic_tts.wav",
):
    """
    Вызываем /basic_tts (позиционные аргументы в порядке из view_api):
      (ref_audio_input, ref_text_input, gen_text_input, remove_silence, randomize_seed,
       seed_input, cross_fade_duration_slider, nfe_slider, speed_slider)
    """

    client = get_gradio_client()
    try:
        print("Вызов /basic_tts ... (загрузка файла и генерация)")
        result = client.predict(
            handle_file(ref_audio),  # ref_audio_input (file)
            ref_text,  # ref_text_input
            gen_text,  # gen_text_input
            False,  # remove_silence
            False,  # randomize_seed
            0,  # seed_input
            0.15,  # cross_fade_duration_slider
            32,  # nfe_slider
            1.0,  # speed_slider
            api_name="/basic_tts",
        )
        # result -> (synthesized_audio, spectrogram, reference_text, value_15)
        audio_out = result[0]
        # common cases: data URI, tuple (sr, np.array), or server filepath/URL
        return audio_out
    except Exception as e:
        print("Ошибка при вызове /basic_tts:", e)


def _write_bytes_to_file(bts: bytes, out_path: str):
    with open(out_path, "wb") as f:
        f.write(bts)


def _convert_to_mp3(input_path: str, out_path: str):
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-codec:a",
        "libmp3lame",
        "-qscale:a",
        "2",
        out_path,
    ]
    subprocess.run(cmd, check=True)


def _safe_filename(prefix="tts", ext="mp3"):
    from uuid import uuid4

    return f"{prefix}_{uuid4().hex}.{ext}"


celery_app = Celery("tts_tasks", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.task_routes = {"tasks.synthesize_and_send": {"queue": "tts"}}


# 4) отправка через Telethon
async def _send(chat_id, final_path, caption):
    client = TelegramClient(f"bot_worker_{WORKER_NUMBER}", int(API_ID), API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    if not API_ID or not API_HASH or not BOT_TOKEN:
        raise RuntimeError("API_ID/API_HASH/BOT_TOKEN не заданы в окружении воркера.")
    if final_path:
        await client.send_file(chat_id, final_path, caption=caption or "")
    else:
        await client.send
    await client.disconnect()


def send_file(chat_id, final_path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    with open(final_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat_id, "caption": ""}
        resp = requests.post(url, data=data, files=files)
        resp.raise_for_status()


# Формируем клавиатуру
keyboard = []
for row in MAIN_MENU_BUTTONS_COMMANDS:
    keyboard_row = [{"text": command} for command, _label in row]
    keyboard.append(keyboard_row)

reply_markup = {
    "keyboard": keyboard,
    "resize_keyboard": True,
    "one_time_keyboard": False,
    "persistent_keyboard": True,
}


def send_text(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text,
            "reply_markup": json.dumps(reply_markup),
        },
    )
    resp.raise_for_status()


def send_file_with_persistent_menu(chat_id, file_path, send_as_mp3=False):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {
            "chat_id": chat_id,
            "caption": "",  # пустой текст
            "reply_markup": json.dumps(reply_markup),
        }
        resp = requests.post(url, data=data, files=files)
        resp.raise_for_status()


from pathlib import Path
from config import VC_PROXY_API_KEY, VC_PROXY_BACKEND_URL


def generate_via_tts_backend(
    user_id: int, ref_audio_local_path: str, text: str, temp_base_path: str
) -> str:
    # сформируем имя для сохраняемого файла
    Path(temp_base_path).mkdir(parents=True, exist_ok=True)
    out_filename = f"{user_id}_{int(time.time())}.mp3"
    out_path = str(Path(temp_base_path) / out_filename)

    headers = {"X-API-KEY": VC_PROXY_API_KEY}
    with open(ref_audio_local_path, "rb") as f:
        files = {
            "ref_audio": (
                os.path.basename(ref_audio_local_path),
                f,
                "application/octet-stream",
            )
        }
        data = {"text": text}

        # stream=True чтобы не держать весь ответ в памяти
        resp = requests.post(
            VC_PROXY_BACKEND_URL,
            headers=headers,
            files=files,
            data=data,
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()

        # пишем поток в файл
        with open(out_path, "wb") as outf:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    outf.write(chunk)

    # при желании удалить локальный референс (чтобы он не оставался)
    try:
        os.remove(ref_audio_local_path)
    except Exception:
        pass

    return out_path


@celery_app.task(bind=True, acks_late=True, soft_time_limit=360)
def synthesize_and_send(
    self,
    chat_id,
    user_id,
    balance,
    gen_text,
    ref_audio_local_path,
    auto_accent=True,
    send_as_mp3=True,
    caption=None,
    tts_provider=1,
):
    """
    Упрощённая задача, ориентированная на кейс: F5 возвращает абсолютный путь на хосте (например /tmp/xxx.wav).
    Требования:
      - Host: файл в /tmp (или в TTS_OUTPUT_DIR) и /tmp смонтирован в контейнер воркера как /tmp.
      - ffmpeg в образе, если нужна конвертация в mp3.
      - API_ID/API_HASH/BOT_TOKEN заданы в окружении воркера.
    """
    # accentizer = get_accentizer()
    # подготовим временную рабочую папку внутри /tmp
    if not os.path.exists(ref_audio_local_path):
        print("Референсный аудиофайл не найден:", ref_audio_local_path)
        print("Подготовьте короткий WAV и укажите путь в LOCAL_REF_AUDIO.")
        return

    # final_path = call_basic_tts_and_save(
    #    ref_audio_local_path,
    #    "",
    #    accentizer.process_all(gen_text),
    #    out_path="out_from_basic_tts.wav",
    # )
    pattern = r"(\[пауза\s*:?\s*(?:\d+(?:\.\d+)?)\s*\])"
    parts = re.split(pattern, gen_text)
    # Список для хранения путей к временным файлам, которые нужно будет удалить
    paths_to_cleanup = []
    # Список для ffmpeg: пути к файлам или информация о паузах
    ffmpeg_segments = []

    try:
        for part in parts:
            if not part or not part.strip():
                continue

            # если это маркер паузы — достаём число из него и добавляем паузу
            if part.strip().startswith("[пауза"):
                m = re.search(r"\d+(?:\.\d+)?", part)
                pause_duration = float(m.group()) if m else 0.0
                ffmpeg_segments.append(("pause", pause_duration))
            else:
                # обычный текст — в синтез
                temp_base_path = f"temp_{len(paths_to_cleanup)}.wav"
                if auto_accent and tts_provider == 1:
                    try:
                        url = f"{ACCENT_URL}/accent"
                        headers = {
                            "Content-Type": "application/json",
                            "x-api-token": API_TOKEN,
                        }
                        json_data = {"text": part}

                        response = requests.post(url, headers=headers, json=json_data)

                        if response.status_code == 200:
                            data = response.json()
                            part = data["accented_text"]
                        else:
                            print("Ошибка:", response.status_code, response.text)
                            raise RuntimeError(
                                f"Ошибка запроса к Accentizer: {response.status_code} {response.text}"
                            )
                    except Exception as e:
                        print(e)
                if tts_provider == 1:
                    # стандартный путь — F5 / локальный Gradio
                    unique_final_path = call_basic_tts_and_save(
                        ref_audio_local_path, "", part, out_path=temp_base_path
                    )

                elif tts_provider == 2:
                    unique_final_path = call_s1_tts(
                        ref_audio_local_path,
                        part,
                        out_path=temp_base_path,
                        model="s1",
                        format="wav",
                    )
                elif tts_provider == 3:
                    unique_final_path = call_elevenlabs_tts(
                        str(user_id), ref_audio_local_path, part, temp_base_path
                    )
                # send_file(chat_id, unique_final_path)

                paths_to_cleanup.append(unique_final_path)
                ffmpeg_segments.append(unique_final_path)

        if not ffmpeg_segments:
            return None

        # Определяем расширение файла на основе флага send_as_mp3
        extension = ".mp3" if send_as_mp3 else ".ogg"

        # Формируем имя файла из user_id и расширения
        filename = f"{user_id}{extension}"

        # Соединяем путь к директории и имя файла
        final_audio_path = os.path.join(OUTPUT_DIR, filename)

        ffmpeg_command = ["ffmpeg", "-y"]
        filter_complex_parts = []
        input_counter = 0

        for segment in ffmpeg_segments:
            if isinstance(segment, tuple) and segment[0] == "pause":
                duration = segment[1]
                # Добавляем параметры sample_rate (r) и channel_layout (cl) для тишины
                ffmpeg_command.extend(
                    [
                        "-f",
                        "lavfi",
                        "-t",
                        str(duration),
                        "-i",
                        "anullsrc=r=24000:cl=mono",
                    ]
                )
            else:
                ffmpeg_command.extend(["-i", segment])

            filter_complex_parts.append(f"[{input_counter}:a]")
            input_counter += 1

        filter_complex_str = (
            "".join(filter_complex_parts)
            + f"concat=n={len(ffmpeg_segments)}:v=0:a=1[out]"
        )
        ffmpeg_command.extend(["-filter_complex", filter_complex_str, "-map", "[out]"])

        if send_as_mp3:
            ffmpeg_command.extend(["-c:a", "libmp3lame", "-q:a", "2"])
        else:
            # Для голосового Telegram
            ffmpeg_command.extend(
                ["-c:a", "libopus", "-b:a", "24k", "-ar", "16000", "-ac", "1"]
            )

        ffmpeg_command.append(final_audio_path)

        subprocess.run(ffmpeg_command, check=True, capture_output=True, text=True)
        # concat_with_ffmpeg_python(ffmpeg_segments, final_audio_path, send_as_mp3=False)
        paths_to_cleanup.append(final_audio_path)

        # вычисляем длительность (секунды), сначала через ffprobe, иначе через wave
        duration_seconds = 0.0
        try:
            out = subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    final_audio_path,
                ],
                stderr=subprocess.STDOUT,
            )
            duration_seconds = float(out.strip())
        except Exception:
            # fallback для WAV
            try:
                with contextlib.closing(wave.open(final_audio_path, "rb")) as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    duration_seconds = frames / float(rate) if rate else 0.0
            except Exception:
                duration_seconds = 0.0

        amount_minutes = duration_seconds / 60.0  # float, может быть <1
        if amount_minutes <= balance:
            send_file_with_persistent_menu(chat_id, final_audio_path)

            asyncio.get_event_loop().run_until_complete(
                consume_credit(user_id, amount_minutes)
            )
        else:
            send_text(chat_id, "У вас недостаточно минут для требуемой генерации")
        tts_provider_name = TTS_PROVIDER_MAP.get(tts_provider)
        if tts_provider_name:
            asyncio.get_event_loop().run_until_complete(
                increase_model_count(tts_provider_name)
            )
        return {"status": "ok", "sent_to": chat_id}
    except Exception as e:
        send_text(chat_id, "Произошла ошибка во время генерации")

    finally:
        # Удаляем все файлы, пути к которым мы получили от функции синтеза
        for final_path in paths_to_cleanup:
            try:
                os.remove(final_path)
                print(f"Removed: {final_path}")
            except OSError as e:
                print(f"Error removing file {final_path}: {e}")


def _detect_wav_params(path):
    with contextlib.closing(wave.open(path, "rb")) as wf:
        return wf.getnchannels(), wf.getsampwidth(), wf.getframerate()


def concat_with_ffmpeg_python(ffmpeg_segments, final_audio_path, send_as_mp3=False):
    """
    ffmpeg_segments: list of either ("pause", seconds) or path_to_wav
    final_audio_path: target (mp3/ogg/wav)
    send_as_mp3: if True - produce mp3, else ogg; if ffmpeg not available -> produce wav
    """
    # убедимся, что ffmpeg бинарь доступен
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg binary not found in PATH")

    # определим параметры (channels, rate) по первому реальному wav
    first_wav = None
    for seg in ffmpeg_segments:
        if isinstance(seg, tuple) and seg[0] == "pause":
            continue
        first_wav = seg
        break

    if first_wav is None:
        raise RuntimeError("Нет ни одного аудиосегмента для определения параметров")

    nchannels, sampwidth, sample_rate = _detect_wav_params(first_wav)

    # создаём временный WAV для промежуточной конкатенации
    tmp_wav = tempfile.NamedTemporaryFile(
        suffix=".wav", dir=OUTPUT_DIR, delete=False
    ).name

    # Формируем ffmpeg-python inputs; для пауз используем anullsrc lavfi
    inputs = []
    for seg in ffmpeg_segments:
        if isinstance(seg, tuple) and seg[0] == "pause":
            dur = float(seg[1])
            # anullsrc нужно параметризовать по каналам/частоте
            inp = ffmpeg.input(
                "anullsrc=channel_layout={}:sample_rate={}".format(
                    "mono" if nchannels == 1 else "stereo", sample_rate
                ),
                f="lavfi",
                t=str(dur),
            )
        else:
            # подаём файл как вход; принудительно приведём к нужной частоте/числу каналов фильтрами ниже
            inp = ffmpeg.input(seg)
        inputs.append(inp.audio)

    # Конкатенируем все аудиопотоки через filter concat
    try:
        concat_stream = ffmpeg.concat(*inputs, v=0, a=1, n=len(inputs))
        # Сохраняем промежуточный WAV с PCM 16 (большинство TTS/ботов работают с таким)
        wav_out = ffmpeg.output(
            concat_stream,
            tmp_wav,
            format="wav",
            acodec="pcm_s16le",
            ar=sample_rate,
            ac=nchannels,
        )
        ffmpeg.run(wav_out, capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        # печатаем stderr для дебага
        err = (
            e.stderr.decode()
            if isinstance(e.stderr, (bytes, bytearray))
            else str(e.stderr)
        )
        print("ffmpeg concat error:", err)
        # очистим tmp если он создан
        if os.path.exists(tmp_wav):
            try:
                os.remove(tmp_wav)
            except:
                pass
        raise

    # Если нужен mp3/ogg — перекодируем tmp_wav в финал
    if send_as_mp3:
        try:
            mp3_out = ffmpeg.input(tmp_wav)
            ff = ffmpeg.output(
                mp3_out, final_audio_path, acodec="libmp3lame", audio_bitrate="192k"
            )
            ffmpeg.run(ff, capture_stdout=True, capture_stderr=True)
            os.remove(tmp_wav)
        except ffmpeg.Error as e:
            print(
                "ffmpeg encode error:",
                e.stderr.decode()
                if isinstance(e.stderr, (bytes, bytearray))
                else e.stderr,
            )
            # если кодирование не удалось — оставим tmp_wav как результат (или пробросим ошибку)
            raise
    else:
        # сохраняем ogg (libvorbis)
        try:
            ogg_out = ffmpeg.input(tmp_wav)
            ff = ffmpeg.output(
                ogg_out, final_audio_path, acodec="libvorbis", audio_bitrate="192k"
            )
            ffmpeg.run(ff, capture_stdout=True, capture_stderr=True)
            os.remove(tmp_wav)
        except ffmpeg.Error as e:
            print(
                "ffmpeg encode error:",
                e.stderr.decode()
                if isinstance(e.stderr, (bytes, bytearray))
                else e.stderr,
            )
            raise
