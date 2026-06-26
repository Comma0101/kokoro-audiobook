import time
import soundfile as sf
from kokoro import KPipeline

print("Loading Kokoro model (Mandarin Chinese)...")
# 'z' is the language code for Mandarin Chinese in Kokoro/misaki
pipeline = KPipeline(lang_code='z')

text = "你好，我是一个非常快的语音模型，测试一下我的中文发音吧！"
print(f"Text to generate: {text}")

print("Generating audio...")
start_time = time.time()

# 'zf_xiaobei' is one of the default female Chinese voices
generator = pipeline(text, voice='zf_xiaobei', speed=1.0, split_pattern=r'\n+')

for i, (gs, ps, audio) in enumerate(generator):
    end_time = time.time()
    generation_time = end_time - start_time
    print(f"Generated in {generation_time:.4f} seconds!")
    
    output_filename = f'output_kokoro_{i}.wav'
    sf.write(output_filename, audio, 24000)
    print(f"Saved to {output_filename}")
