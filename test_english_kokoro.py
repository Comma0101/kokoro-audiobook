import time
import soundfile as sf
import numpy as np
from kokoro import KPipeline

print("Loading Kokoro model (American English)...")
# 'a' is the language code for American English
pipeline = KPipeline(lang_code='a')

# Read the long text
with open("trading_psychology.txt", "r", encoding="utf-8") as f:
    text = f.read()

# Clean up some of the massive tabs/newlines from the raw paste
text = " ".join(text.split())

print("Generating audio for long text...")
start_time = time.time()

# 'af_heart' is a highly rated American female voice
# split_pattern ensures we split by sentence to avoid hitting token limits
generator = pipeline(text, voice='af_heart', speed=1.0, split_pattern=r'(?<=[.!?])\s+')

all_audio = []
for i, (gs, ps, audio) in enumerate(generator):
    if audio is not None:
        all_audio.append(audio)

end_time = time.time()
generation_time = end_time - start_time

if all_audio:
    # Concatenate all generated audio chunks
    final_audio = np.concatenate(all_audio)
    
    output_filename = 'output_english_long.wav'
    sf.write(output_filename, final_audio, 24000)
    
    print(f"Generated {len(final_audio) / 24000:.2f} seconds of audio in {generation_time:.4f} seconds!")
    print(f"Real-Time Factor (RTF): {generation_time / (len(final_audio) / 24000):.4f}")
    print(f"Saved to {output_filename}")
else:
    print("Failed to generate audio.")
