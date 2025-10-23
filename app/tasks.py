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
    WORKER_NUMBER,
    OUTPUT_DIR,
    ACCENT_URL,
    API_TOKEN,
)
from ui_components import MAIN_MENU_BUTTONS_COMMANDS
from db import consume_credit


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


def get_accentizer():
    global _accentizer
    if _accentizer is None:
        _accentizer = RUAccent()
        _accentizer.load(
            omograph_model_size="turbo3.1", use_dictionary=True, tiny_mode=False
        )
    return _accentizer


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


def send_text(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text})
    resp.raise_for_status()


def send_file_with_persistent_menu(chat_id, file_path, send_as_mp3=False):
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
        print("Референсный аудиофайл не найден:", LOCAL_REF_AUDIO)
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
                if auto_accent:
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
                unique_final_path = call_basic_tts_and_save(
                    ref_audio_local_path,
                    "",
                    part,
                    out_path=temp_base_path,
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
        return {"status": "ok", "sent_to": chat_id}

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
