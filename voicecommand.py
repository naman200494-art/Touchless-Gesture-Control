
import os
import subprocess
import psutil
import win32com.client
import speech_recognition as sr
import pyttsx3
from fuzzywuzzy import process
import time
import winsound
import webbrowser

# -------------------- User Settings --------------------
LISTEN_TIMEOUT = 5         # Idle seconds to go to sleep
PHRASE_LIMIT = 5           # Max seconds per phrase
BEEP_MS = 100              # Short beep duration in ms
VOICE_RATE = 160           # Calm voice

# -------------------- Voice Setup --------------------
try:
    engine = pyttsx3.init()
except Exception as e:
    print("TTS failed, running without voice:", e)
    engine = None

engine.setProperty("rate", VOICE_RATE)

def speak(text):
    print(f"Assistant: {text}")
    if engine:
         engine.say(text)
         engine.runAndWait()

def beep():
    winsound.Beep(1000, BEEP_MS)

# -------------------- App Scanning --------------------
def get_shortcuts():
    paths = [
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
    ]
    shortcuts = {}
    for path in paths:
        if not os.path.isdir(path):
            continue
        for root, _, files in os.walk(path):
            for f in files:
                if f.lower().endswith(".lnk"):
                    shortcuts[os.path.splitext(f)[0].lower()] = os.path.join(root, f)
    return shortcuts

def get_uwp_apps():
    uwp = {}
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        ns = shell.Namespace("shell:AppsFolder")
        for item in ns.Items():
            uwp[item.Name.lower()] = item.Path
    except Exception:
        pass
    return uwp

def get_all_apps():
    apps = get_shortcuts()
    apps.update(get_uwp_apps())
    return apps

# -------------------- Known EXE Apps --------------------
KNOWN_APPS = {
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "microsoft edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "settings": "start ms-settings:",
    "copilot": "start ms-copilot:"
}

# -------------------- Known UWP Apps --------------------
KNOWN_UWP_APPS = {
    "calculator": "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App",
    "microsoft store": "Microsoft.WindowsStore_8wekyb3d8bbwe!App",
    "whatsapp": "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
    "photos": "Microsoft.WindowsPhotos_8wekyb3d8bbwe!App",
    "camera": "Microsoft.WindowsCamera_8wekyb3d8bbwe!App",
    "voice recorder": "Microsoft.WindowsSoundRecorder_8wekyb3d8bbwe!App"
}

# -------------------- Website Aliases --------------------
WEBSITES = {
    "youtube": ["youtube", "yt"],
    "google": ["google", "search"],
    "gmail": ["gmail", "mail"],
    "stackoverflow": ["stackoverflow", "stack overflow"],
    "github": ["github", "git hub"],
}

WEBSITE_URLS = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "stackoverflow": "https://stackoverflow.com",
    "github": "https://github.com",
}

def match_website(name):
    name = name.lower()
    for site, aliases in WEBSITES.items():
        if name in aliases:
            return WEBSITE_URLS.get(site)
    return None

# -------------------- Fuzzy Match --------------------
def find_best_match(name, app_map, threshold=65):
    choices = list(app_map.keys()) + list(KNOWN_APPS.keys()) + list(KNOWN_UWP_APPS.keys())
    match = process.extractOne(name, choices)
    if not match or match[1] < threshold:
        return None
    return match[0]

# -------------------- Open App --------------------
def open_app(name, app_map):
    name = name.lower().strip()
    # Check websites first
    website = match_website(name)
    if website:
        speak(f"Opening {name} in browser...")
        webbrowser.open(website)
        return

    app_name = find_best_match(name, app_map)
    if not app_name:
        speak(f"I couldn't find an app named {name}.")
        return
    speak(f"Opening {app_name}...")

    try:
        # Known EXE
        if app_name in KNOWN_APPS:
            cmd = KNOWN_APPS[app_name]
            subprocess.Popen(cmd, shell=True)
            return

        # Known UWP
        if app_name in KNOWN_UWP_APPS:
            cmd = f'start shell:AppsFolder\\{KNOWN_UWP_APPS[app_name]}'
            subprocess.Popen(cmd, shell=True)
            return

        # Shortcut or UWP scanned automatically
        path = app_map.get(app_name)
        if not path:
            speak("App path not found.")
            return

        if path.lower().endswith(".lnk"):
            shell = win32com.client.Dispatch("WScript.Shell")
            target = shell.CreateShortcut(path).Targetpath
            subprocess.Popen(target)
        else:
            subprocess.Popen(["explorer.exe", path])

    except Exception as e:
        speak("Sorry, I couldn't open it.")
        print(e)

# -------------------- Close App --------------------
def close_app(name):
    name = name.lower().strip()
    closed = False
    if "copilot" in name:
        for proc in psutil.process_iter(['name']):
            try:
                if "msedge.exe" in proc.info['name'].lower():
                    proc.terminate()
                    closed = True
            except: pass
        speak("Copilot closed." if closed else "Copilot not running.")
        return

    if "file explorer" in name or name == "explorer":
        subprocess.run("taskkill /IM explorer.exe /F", shell=True)
        subprocess.Popen("explorer.exe")
        speak("File Explorer restarted.")
        return

    # Close normal and UWP apps
    for proc in psutil.process_iter(['name']):
        try:
            pname = proc.info['name']
            if pname and name in pname.lower():
                proc.terminate()
                closed = True
        except: pass
    speak(f"{name} closed." if closed else f"No running app named {name} found.")

# -------------------- List Apps --------------------
def list_apps(app_map):
    apps = sorted(app_map.keys())
    for i, a in enumerate(apps[:50], 1):
        print(f"{i:02d}. {a}")
    speak(f"I found {len(apps)} apps. Showing first 50 on screen.")

# -------------------- Listen --------------------
recognizer = sr.Recognizer()
def listen(timeout=LISTEN_TIMEOUT, phrase_time_limit=PHRASE_LIMIT):
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            return recognizer.recognize_google(audio, language="en-US").lower()
        except:
            return ""

# -------------------- Main Loop --------------------
if __name__ == "__main__":
    speak("Assistant ready. Listening continuously...")
    app_map = get_all_apps()
    last_refresh = time.time()

    while True:
        # Refresh app list every 10 minutes
        if time.time() - last_refresh > 600:
            app_map = get_all_apps()
            last_refresh = time.time()
            speak("App list refreshed.")

        beep()
        cmd = listen()
        if not cmd:
            # Sleep mode if nothing heard
            continue
        print("Command heard:", cmd)

        if cmd.startswith("open "):
            open_app(cmd.replace("open ", "", 1).strip(), app_map)
        elif cmd.startswith("close "):
            close_app(cmd.replace("close ", "", 1).strip())
        elif "list app" in cmd or "show app" in cmd or "list apps" in cmd:
            list_apps(app_map)
        elif "refresh" in cmd:
            app_map = get_all_apps()
            last_refresh = time.time()
            speak("App list refreshed.")
        elif cmd in ["exit", "quit", "stop", "goodbye"]:
            speak("Goodbye.")
            break
        else:
            # Try opening app or website directly
            open_app(cmd, app_map)
