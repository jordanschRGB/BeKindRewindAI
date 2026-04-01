# BeKindRewindAI — Setup Guide

This guide walks you through installing and running BeKindRewindAI from scratch. By the end, you'll have the app capturing VHS tapes on your computer.

---

## Table of Contents

1. [What You Need First (Prerequisites)](#1-what-you-need-first-prerequisites)
2. [Step 1: Install Python](#2-step-1-install-python)
3. [Step 2: Install the App](#3-step-2-install-the-app)
4. [Step 3: Run the App for the First Time](#4-step-3-run-the-app-for-the-first-time)
5. [Step 4: Set Up Your Capture Card](#5-step-4-set-up-your-capture-card)
6. [Step 5: AI Setup (Optional — Makes Everything Better)](#6-step-5-ai-setup-optional--makes-everything-better)
7. [Recording Your First Tape](#7-recording-your-first-tape)
8. [Where Your Files Go](#8-where-your-files-go)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. What You Need First (Prerequisites)

### Hardware

**A VHS capture card** — This is a small box that connects your VCR to your computer's USB port. We recommend:

- **EasyCAP USB 2.0** (~$15-20 on Amazon) — We tested this and it works reliably on Linux, macOS, and Windows. Look for one with the chip labeled "STK1160" or "UTV007" — avoid ones with "FJ" chips if possible as they can be harder to set up.
- **Any capture card that shows up as a webcam on Mac** — If your Mac recognizes it as a camera input, it will probably work.
- **Any capture card that appears in OBS on Windows** — If OBS can see it, BeKindRewindAI can too.
- **Linux users** — Look for anything that creates a `/dev/video0` device when plugged in.

**An audio cable** — Most capture cards have a 3.5mm (headphone jack) input. You'll need a cable that goes from your VCR's audio output (usually red and white RCA plugs) to your capture card's 3.5mm input. These are sometimes called "RCA to 3.5mm cables" and are available at any electronics store for a few dollars.

**A VCR** — Obviously. Any working VCR will do. If your tapes have been sitting untouched for years, it's worth cleaning the video heads with a head-cleaning cassette before you start — dirty heads are the #1 cause of recording problems.

### Software

**Python 3.10 or 3.11** — Python is the programming language the app is written in. Check if you already have it:

- **macOS/Linux**: Open Terminal and type: `python3 --version`
- **Windows**: Open Command Prompt and type: `python --version`

If it says Python 3.10 or 3.11 (like `Python 3.11.5`), you're good. If it says Python 2.x or nothing, or if it gives an error, you need to install it — go to [python.org/downloads](https://python.org/downloads) and download Python 3.11.

**Important for Windows users**: When you run the Python installer from python.org, make sure you check the box that says "Add Python to PATH" — this makes everything work more smoothly.

---

## 2. Step 1: Install Python

### macOS

1. Go to [python.org/downloads](https://python.org/downloads)
2. Download Python 3.11 (the button that says "Download Python 3.11.x")
3. Open the downloaded file and follow the prompts
4. After it installs, open Terminal and verify: `python3 --version`

You should see something like `Python 3.11.9`.

### Windows

1. Go to [python.org/downloads](https://python.org/downloads)
2. Download Python 3.11
3. Run the installer
4. **Important**: Check the box that says "Add Python to PATH" at the bottom of the installer window
5. Click "Install Now"
6. After it finishes, open Command Prompt and verify: `python --version`

You should see something like `Python 3.11.9`.

To open Command Prompt: Press `Windows Key + R`, type `cmd`, and press Enter.

### Linux (Ubuntu/Debian)

Open Terminal and run:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

Then verify: `python3 --version`

---

## 3. Step 2: Install the App

### Get the App Files

First, you need to download the app to your computer. You do this with a command called `git clone`.

1. **Find the app's download address** — If you're reading this on GitHub or received a link from someone, look for a green button that says "Code" — click it and copy the URL shown there.

2. **Open your terminal**:
   - macOS: Press `Command + Space`, type `Terminal`, press Enter
   - Windows: Press `Windows Key + R`, type `cmd`, press Enter
   - Linux: Press `Ctrl + Alt + T`

3. **Navigate to where you want the app** — We recommend your home folder. In Terminal/Command Prompt, type:
   ```bash
   cd ~
   ```

4. **Download the app** — Replace `<paste-your-url-here>` with the URL you copied (it will look like `https://github.com/username/BeKindRewindAI.git`):
   ```bash
   git clone <paste-your-url-here>
   ```

5. **Go into the app folder** — After the download finishes, type:
   ```bash
   cd BeKindRewindAI
   ```

### Set Up the Python Environment

Python apps work best when kept in an isolated environment so they don't conflict with other Python programs on your computer. We use something called a "virtual environment" (venv for short).

**macOS / Linux:**

```bash
python3 -m venv venv
```

**Windows:**

```bash
python -m venv venv
```

This creates a new folder called `venv` inside the BeKindRewindAI folder. Think of it as a separate Python world just for this app.

### Activate the Virtual Environment

This tells your computer to use the special isolated Python for this app. You need to do this every time you open the app.

**macOS / Linux:**

```bash
source venv/bin/activate
```

**Windows:**

```bash
venv\Scripts\activate
```

When it's activated, you'll see `(venv)` at the start of your command line, like this:

- macOS/Linux: `(venv) your-computer-name:~ your-username$`
- Windows: `(venv) C:\Users\YourName>`

### Install the Required Python Packages

Now install the libraries the app needs:

```bash
pip install -r requirements.txt
```

This reads the `requirements.txt` file and installs everything listed there automatically. It may take a few minutes.

---

## 4. Step 3: Run the App for the First Time

Make sure your capture card is **plugged in** before starting the app (the app detects devices when it starts).

With your virtual environment activated, run:

```bash
python main.py
```

What happens next:

1. A terminal window will show some startup messages
2. Your web browser will open automatically to `http://localhost:5000`
3. A small icon may appear in your system tray (top of screen on Mac, bottom-right on Windows)

If the browser doesn't open automatically, open it yourself and go to: [http://localhost:5000](http://localhost:5000)

**First-time setup**: The first time you run it, the app will automatically download `ffmpeg` — the tool it uses to record video. This is about 80MB and happens in the background. You'll see a message in the app when it's ready. Make sure your computer is connected to the internet for this step.

---

## 5. Step 4: Set Up Your Capture Card

### Connect the Hardware

1. Plug the capture card into a USB port on your computer
2. Connect your VCR to the capture card using the audio cable:
   - The red and white plugs go into the VCR's audio output (red = right, white = left)
   - The 3.5mm plug goes into the capture card's audio input
   - The yellow plug (if your cable has one) connects to the VCR's video output — some capture cards only handle audio and use the USB connection for video, so you may only need red/white

### Configure Devices in the App

1. In the app, click **"Device Setup"** in the top navigation
2. Click the **"Detect Devices"** button
3. Wait a moment — the app scans your computer for capture devices
4. You should see your capture card listed under "Video Devices" and your audio input listed under "Audio Devices"
5. Click on your capture card to select it as the video device
6. Click on your audio input to select it as the audio device

**On Windows**, if your capture card doesn't appear, it may need drivers. EasyCAP cards on Windows sometimes need you to look up the correct driver based on the USB ID (VID/PID) printed on a label on the card. Search online for "EasyCAP [your chip name] driver Windows" to find the right one.

### Test Your Setup

Click **"Test Capture (3 sec)"** — this records 3 seconds of video and audio and checks if everything is working.

- **Success**: You'll see "Test passed! Your devices are working."
- **Failure**: You'll see an error message explaining what went wrong. Common problems:
  - "No such device" — the capture card isn't plugged in or your computer doesn't see it
  - "Device is busy" — another program (like Skype, Zoom, or OBS) is using the capture card. Close those programs and try again.
  - "Input/output error" — usually a driver problem on Windows, or the VCR isn't outputting video

If the test passes but you get "no signal" during real recording, check that your VCR is playing a tape and that all cables are firmly connected.

Click **"Save Config"** when your devices are working.

---

## 6. Step 5: AI Setup (Optional — Makes Everything Better)

The app works fine without AI — you can record and save tapes manually. But turning on AI features gives you automatic transcription (so you can search your tapes by what was said) and smart titles and tags.

### How It Works

The app uses two local AI models:

1. **Whisper** (speech-to-text) — Automatically converts the audio from your tape into text. No internet needed, runs entirely on your computer.
2. **Qwen** (labeling) — Reads the transcript and generates a title and tags for your tape. Also runs on your computer.

Both models run entirely offline. No data is sent anywhere.

### Installing AI Features

1. In the app, click **"Settings"** in the top navigation
2. Scroll to "Smart Features"

You'll see your computer's hardware detected automatically:

- **GPU detected** — If you have an NVIDIA graphics card, AI will run much faster on the GPU
- **CPU only** — If no GPU is found, AI will run on your processor (slower but works fine)

#### Install llama-cpp-python

This is the engine that runs the AI models. Click **"Install llama-cpp-python"** if you see that button. This takes a few minutes — it's a larger package.

#### Download the AI Models

In the models table, you'll see two models:

- **Whisper Small** (speech-to-text) — Click "Download" to get it. It's about 460 MB.
- **Qwen 3.5 4B** (labeling) — Click "Download" to get it. It's about 2.5 GB.

These download directly to your computer (no internet needed after download). The models are stored in `~/.memoryvault/models/` (more on this path below).

Once both models show "Ready", AI features are fully enabled.

### About Ollama and OpenRouter (Advanced)

The app is designed to work with local AI models (above). However, if you have an Ollama server running locally or an OpenRouter account for cloud AI, you can configure those in the **Settings → Smart Features** panel. The app communicates with these services using the OpenAI-compatible API format.

**Ollama** (recommended if you want to experiment with different AI models):
- Download from [ollama.com](https://ollama.com)
- Start Ollama and pull a model: `ollama pull llama3.2` or `ollama pull mistral`
- The app will detect it if it's running at `http://localhost:11434`

**OpenRouter** (cloud-based, requires paid account):
- Sign up at [openrouter.ai](https://openrouter.ai)
- Get an API key from your account settings
- Paste the key into the app's Settings panel

---

## 7. Recording Your First Tape

### The Basic Workflow

1. **Connect your capture card to your VCR** and make sure a tape is in the VCR
2. **Click "Session"** in the app navigation
3. **Click "Start Recording"** — the app starts capturing immediately
4. **Play the tape** on your VCR
5. When the tape ends (or whenever you want to stop), click **"Stop"** in the app
6. The app automatically processes the recording: encoding it, checking quality, and (if AI is set up) transcribing and labeling it
7. Go to **"Library"** to see your saved tape

### Auto-Stop Feature

The app has a useful feature: it automatically stops recording when it detects that the tape has stopped playing. It watches for:
- **10+ seconds of silence** (the tape reached a quiet part or ended)
- **5+ seconds of black screen** (no video signal)

This means you can start recording and walk away — the app will stop itself when the tape is done.

### Reviewing AI Results

After a recording is processed:

1. Go to **Library** in the navigation
2. Click on your new tape
3. You'll see:
   - **Transcript** — the full text of what was said (if Whisper was available)
   - **Title** — a short name for the tape (if Qwen was available)
   - **Tags** — topic labels like "birthday", "outdoor", "music" (if Qwen was available)
4. You can edit the title and tags if they're wrong — click on them to change them
5. Click **Save** to store your changes

---

## 8. Where Your Files Go

### Recordings (Video Files)

**`~/Videos/MemoryVault/`** (that's `C:\Users\YourName\Videos\MemoryVault` on Windows, `/Users/YourName/Videos/MemoryVault` on Mac, `/home/yourname/Videos/MemoryVault` on Linux)

Each tape is saved as an `.mp4` file. Files are named with the tape's title or "Tape_001" format, plus a timestamp.

### Tape Metadata

Every tape also has a `.json` file with the same name. This contains:
- Transcript (if AI was on)
- Title and tags (if AI was on)
- Recording date, duration, file size
- Validation results (did the recording have video? audio? was it blank?)

You can open `.json` files in any text editor (Notepad, TextEdit, etc.) if you're curious.

### Memory Vault (AI Vocabulary)

**`~/.memoryvault/archivist_memory.md`**

This is a plain text file that stores the AI's "memory" across tapes. Each tape teaches the AI new words (names, places, topics) that improve transcription on future tapes. This file grows more useful the more tapes you record.

You can open and edit this file in Notepad or any text editor. If you see a name that was transcribed incorrectly, you can add it here and the AI will remember it for next time.

### Logs

The app keeps logs of its activity. These are mostly useful for debugging problems:

- On Linux/Mac: `~/.memoryvault/logs/`
- On Windows: `C:\Users\YourName\.memoryvault\logs\`

### Temporary Files

During recording, temporary files are created in your system's temp folder. These are cleaned up automatically.

---

## 9. Troubleshooting

### "ffmpeg not found" or the app won't start

The app should download ffmpeg automatically the first time it runs. If this fails:

1. Make sure your computer is connected to the internet
2. Try running the app again
3. If it still fails, the app may not have permission to create folders. Try running your terminal as Administrator (Windows) or with `sudo` (Mac/Linux)

### "No devices found" in the Device Setup

- Is the capture card plugged in? Try unplugging and replugging it
- On Windows: The capture card may need drivers. Look on the card for a label with letters/numbers (like "VID_1D5C PID_2005") and search online for that + "Windows driver"
- On Linux: Check if the device appears in `/dev/video0` by running `ls /dev/video*` in Terminal
- Is another program using the capture card? Close OBS, Zoom, Skype, FaceTime, etc.

### "No signal" during recording

- The VCR isn't outputting video — make sure the VCR is in "play" mode with a tape playing
- The video cable isn't connected — some capture cards need a separate yellow RCA cable for video
- The VCR's video heads are dirty — try cleaning them with a head-cleaning cassette
- The cable between VCR and capture card is bad — try a different cable

### Audio is out of sync with video

This usually happens when your computer's audio sample rate doesn't match what the capture card expects. Try:

1. On Windows: Right-click the speaker icon → Sound Settings → scroll down to "Advanced sound options" → app volume and device preferences → make sure the capture card's sample rate is set to 48000 Hz
2. On Mac: Go to System Settings → Sound → Input — select your capture card and check the sample rate
3. In the app, try a different audio device or the "Default audio input" option

### "Transcription is gibberish" or lots of wrong words

- Enable the "Vocabulary Pre-Game" feature in Settings — this lets you describe what's on the tape before transcription runs, which dramatically improves accuracy
- Add names and terms to `~/.memoryvault/archivist_memory.md` — the more specific words (people's names, place names, technical terms) you add, the better Whisper gets
- Try a different Whisper model in Settings (larger models like "medium" are more accurate but slower)

### Recording auto-stopped too early (tape was still playing)

- If there's a quiet gap in the tape longer than 10 seconds, the app thinks the tape ended. This is most common with tapes that have long silent sections.
- Try playing the loudest part of the tape first (not from the very beginning) so the app has audio to lock onto

### The app is running but the browser shows nothing

- Make sure you're going to `http://localhost:5000` (not `https://`)
- Try a different browser (Chrome, Firefox, Edge — avoid Safari if you're on Mac as it can have issues)
- Check the terminal window for error messages

### AI features are slow or use a lot of CPU

- This is normal on computers without a GPU. Transcription of a 2-hour tape can take 15-30 minutes on a CPU. This is normal and the app will keep working in the background.
- If you have an NVIDIA GPU, make sure CUDA drivers are installed — the app will automatically use the GPU and be much faster

### I closed the app while recording — what happened to my tape?

The app saves the recording continuously as it captures. If you close the app while recording, the last few seconds may not be saved, but everything before that should be intact in `~/Videos/MemoryVault/`. Look for a file with "_raw.mkv" in the name — this is the raw recording before processing.

---

## What BeKindRewindAI Can't Do Yet

**Be honest about the following limitations:**

- **One tape at a time** — The app records and processes one tape at a time. There's no batch processing yet.
- **No internet metadata enrichment** — The app doesn't look up information about what's on your tape from the internet. It only uses what's on the tape itself.
- **No face recognition** — The app doesn't identify people in videos.
- **AI features require setup** — Transcription and labeling don't work out of the box. You need to install the AI models from the Settings page first.
- **No batch export** — You can export one tape or all tapes to JSON or CSV, but there's no automatic backup feature yet.
- **Linux audio can be tricky** — Getting audio input working on Linux sometimes requires extra configuration with PulseAudio or ALSA. The app tries its best but you may need to adjust system audio settings.

---

## Quick Reference: Common Commands

| Action | Command |
|--------|---------|
| Start the app | `python main.py` (with venv activated) |
| Activate virtual environment (macOS/Linux) | `source venv/bin/activate` |
| Activate virtual environment (Windows) | `venv\Scripts\activate` |
| Check Python version | `python3 --version` (Mac/Linux) or `python --version` (Windows) |
| See where files are stored | Your videos: `~/Videos/MemoryVault/`, Memory: `~/.memoryvault/` |
| Update the app to the latest version | `git pull` inside the BeKindRewindAI folder |

---

*Last updated for BeKindRewindAI v0.1.0*
