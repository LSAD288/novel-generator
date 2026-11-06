# -*- coding: utf-8 -*-
"""离线听写：sherpa-onnx + SenseVoice（中/英/日/韩/粤），首次使用自动下载模型。

不依赖任何云端接口，模型放在数据目录 dictation_models/sense-voice 下。
"""
import os
import io
import json
import time
import wave
import array
import threading
import urllib.request

MODEL_FILES = [
    ("model.int8.onnx", 239233841),
    ("tokens.txt", 315894),
]

# 国内优先走 hf-mirror，失败再试 HuggingFace 原站
MIRRORS = [
    "https://hf-mirror.com/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main/",
    "https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main/",
]

_lock = threading.Lock()
_state = {"downloading": False, "received": 0, "total": 0, "error": "", "done": False}
_recognizer = None


def _base_dir(data_dir):
    return os.path.join(data_dir, "dictation_models", "sense-voice")


def _file_ok(path, min_size):
    try:
        return os.path.getsize(path) >= min_size
    except OSError:
        return False


def status(data_dir):
    base = _base_dir(data_dir)
    installed = all(_file_ok(os.path.join(base, n), s) for n, s in MODEL_FILES)
    total = sum(s for _, s in MODEL_FILES)
    with _lock:
        st = dict(_state)
    st.update({
        "installed": installed,
        "dir": base,
        "total": total,
        "has_sherpa": _has_sherpa(),
    })
    return st


def _has_sherpa():
    try:
        import sherpa_onnx  # noqa: F401
        return True
    except Exception:
        return False


def _download_one(url_base, name, dest, on_bytes):
    url = url_base + name
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "FenghuoWriter/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as fh:
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            fh.write(chunk)
            on_bytes(len(chunk))
    os.replace(tmp, dest)


def start_download(data_dir):
    """后台下载模型；重复调用只会返回当前状态。"""
    st = status(data_dir)
    with _lock:
        if _state["downloading"] or st.get("installed"):
            return st
        _state.update({"downloading": True, "received": 0, "total": 0, "error": "", "done": False})

    def worker():
        base = _base_dir(data_dir)
        last = "下载失败"
        try:
            os.makedirs(base, exist_ok=True)
            for url_base in MIRRORS:
                try:
                    received = [0]

                    def on_bytes(n):
                        received[0] += n
                        with _lock:
                            _state["received"] = received[0]

                    for name, _min in MODEL_FILES:
                        dest = os.path.join(base, name)
                        if _file_ok(dest, 1000):
                            try:
                                received[0] += os.path.getsize(dest)
                            except OSError:
                                pass
                            with _lock:
                                _state["received"] = received[0]
                            continue
                        _download_one(url_base, name, dest, on_bytes)
                    with _lock:
                        _state.update({"downloading": False, "done": True, "error": ""})
                    return
                except Exception as e:  # 换下一个镜像
                    last = str(e)
                    continue
            with _lock:
                _state.update({"downloading": False, "error": last})
        except Exception as e:
            with _lock:
                _state.update({"downloading": False, "error": str(e)})

    threading.Thread(target=worker, daemon=True).start()
    return status(data_dir)


def _get_recognizer(data_dir):
    global _recognizer
    if _recognizer is not None:
        return _recognizer
    with _lock:
        if _recognizer is not None:
            return _recognizer
        import sherpa_onnx
        base = _base_dir(data_dir)
        model = os.path.join(base, "model.int8.onnx")
        tokens = os.path.join(base, "tokens.txt")
        _recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=model,
            tokens=tokens,
            num_threads=2,
            use_itn=True,
            debug=False,
        )
        return _recognizer


def read_wav(data):
    """WAV 字节 → (16k 采样率单声道 float 列表, 采样率)。"""
    with wave.open(io.BytesIO(data), "rb") as wf:
        rate = wf.getframerate()
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())
    if width != 2:
        raise ValueError("只支持 16bit PCM 音频")
    samples = array.array("h")
    samples.frombytes(frames)
    if channels > 1:
        mono = array.array("h", [0]) * (len(samples) // channels)
        for i in range(len(mono)):
            acc = 0
            for c in range(channels):
                acc += samples[i * channels + c]
            mono[i] = int(acc / channels)
        samples = mono
    floats = [s / 32768.0 for s in samples]
    if rate != 16000:
        floats = _resample(floats, rate, 16000)
    return floats, 16000


def _resample(samples, src, dst):
    if src == dst or not samples:
        return samples
    ratio = dst / src
    n = int(len(samples) * ratio)
    out = [0.0] * n
    for i in range(n):
        pos = i / ratio
        i0 = int(pos)
        i1 = min(i0 + 1, len(samples) - 1)
        frac = pos - i0
        out[i] = samples[i0] * (1 - frac) + samples[i1] * frac
    return out


def transcribe_wav(data, data_dir):
    """离线转写。返回 (文本, 错误)。"""
    try:
        samples, rate = read_wav(data)
    except Exception as e:
        return "", "音频解析失败：%s" % e
    if not samples:
        return "", "音频为空"
    try:
        rec = _get_recognizer(data_dir)
    except Exception as e:
        return "", "离线模型加载失败：%s" % e
    try:
        stream = rec.create_stream()
        stream.accept_waveform(rate, samples)
        started = time.time()
        rec.decode_stream(stream)
        text = (stream.result.text or "").strip()
        if time.time() - started > 60:
            return text, ""
        return text, ""
    except Exception as e:
        return "", "离线转写失败：%s" % e
