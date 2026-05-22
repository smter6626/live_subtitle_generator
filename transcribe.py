from faster_whisper import WhisperModel

model = WhisperModel("turbo", device="cpu", compute_type="int8")

segments, info = model.transcribe(
    "test.wav",
    language="en"
)

print("Detected language:", info.language)

for seg in segments:
    print(f"[{seg.start:.2f}s -> {seg.end:.2f}s] {seg.text}")