import asyncio
import edge_tts

async def gen_speech(text: str):
    voice = "bn-BD-NabanitaNeural"
    communicate = edge_tts.Communicate(text, voice, rate="+0%", pitch="+2Hz")
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

data = asyncio.run(gen_speech("নমস্কার, নিউজবাংলায় আজকের সম্পূর্ণ খবরটি শুনুন। ঢাকায় আজ আবহাওয়া রৌদ্রোজ্জ্বল থাকবে।"))
print(f"Generated {len(data)} bytes of pristine Bengali sweet female voice!")
