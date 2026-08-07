import pyttsx3

def speak_paragraph(text: str) -> None:
    engine = pyttsx3.init()
    # speak the text out loud
    engine.say(text)
    engine.runAndWait()