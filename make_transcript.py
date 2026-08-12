import whisper

# 1. Load the AI model ('base' is small and fast)
print("Downloading and loading AI model... (This takes a minute the first time)")
model = whisper.load_model("base")

# 2. Transcribe your MP3
print("Listening to the audio file...")
result = model.transcribe(r"C:\Users\dasun\Downloads\caveman_story.mp3")

# 3. Save it to a text file with timestamps
with open("timestamped_transcript.txt", "w", encoding="utf-8") as file:
    for segment in result["segments"]:
        # Get times in seconds
        start_time = round(segment["start"], 1)
        end_time = round(segment["end"], 1)
        text = segment["text"].strip()
        
        # Create the layout (e.g., [0.0s to 5.2s] Hello world)
        line = f"[{start_time}s to {end_time}s] {text}\n"
        
        print(line.strip()) # Show it on your screen
        file.write(line)

print("\nSuccess! Your transcript is saved as timestamped_transcript.txt")