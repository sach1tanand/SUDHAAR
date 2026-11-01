"""Optional helper chatbot (spec §4.11). Rule-based and offline: English, Hindi and Hinglish keywords.
It explains the reporting process; it is NOT the complaint-submission path. Swap `reply()` for an LLM later."""
import re

RULES = [
    (r"track|status|kahan|kahaan|ट्रैक|स्थिति|complaint id|कहाँ", {
        "en": "Open 'My complaints' and tap your complaint ID to see its timeline: Registered → Forwarded → Acknowledged → Under Review → Field Officer Assigned → In Progress → Resolved/Rejected.",
        "hi": "'मेरी शिकायतें' खोलें और अपनी शिकायत आईडी पर टैप करें। वहाँ पूरी टाइमलाइन दिखेगी।"}),
    (r"gallery|upload|purani|old photo|download|गैलरी", {
        "en": "Sudhaar accepts only photos/videos captured live inside the app, so every complaint shows real, current evidence. Gallery and downloaded media are not accepted.",
        "hi": "Sudhaar सिर्फ ऐप के अंदर लाइव खींची गई फोटो/वीडियो स्वीकार करता है। गैलरी या डाउनलोड की गई फाइलें मान्य नहीं हैं।"}),
    (r"location|gps|map|pin|jagah|लोकेशन", {
        "en": "Allow location access and Sudhaar adds GPS automatically. If GPS is off, tap the map and drop a pin on the problem spot.",
        "hi": "लोकेशन की अनुमति दें तो GPS अपने आप जुड़ जाएगा। GPS बंद हो तो नक्शे पर पिन लगाएँ।"}),
    (r"reopen|resolved|solve|hal nahi|not fixed|दोबारा|फिर से", {
        "en": "After a complaint is marked Resolved you can view the proof photos, then confirm it is fixed or tap 'Reopen' if the problem remains.",
        "hi": "शिकायत 'Resolved' होने पर प्रमाण देखें, फिर 'ठीक हो गया' चुनें या समस्या बनी रहे तो 'फिर से खोलें' दबाएँ।"}),
    (r"privacy|number|naam|identity|anonymous|गोपनीय|नंबर", {
        "en": "Departments never see your mobile number or identity. They see only the complaint ID, location, media and description.",
        "hi": "विभाग को आपका मोबाइल नंबर या पहचान नहीं दिखती। उन्हें सिर्फ शिकायत आईडी, लोकेशन, मीडिया और विवरण मिलता है।"}),
    (r"categor|kaise|how|report|shikayat|शिकायत|kya karu|start", {
        "en": "To report: 1) log in with your mobile number, 2) choose a category, 3) capture a live photo or video, 4) confirm the location, 5) add an optional note and submit. You will get a complaint ID.",
        "hi": "शिकायत करने के लिए: 1) मोबाइल नंबर से लॉगिन करें, 2) श्रेणी चुनें, 3) लाइव फोटो/वीडियो लें, 4) लोकेशन पक्की करें, 5) चाहें तो विवरण जोड़कर सबमिट करें।"}),
]
DEFAULT = {"en": "I can help with: how to report, tracking a complaint, location/GPS, privacy, and reopening. What would you like to know?",
           "hi": "मैं मदद कर सकता हूँ: शिकायत कैसे करें, ट्रैकिंग, लोकेशन, गोपनीयता और दोबारा खोलना। आप क्या जानना चाहते हैं?"}

def reply(msg: str) -> dict:
    lang = "hi" if re.search(r"[\u0900-\u097F]", msg) else "en"
    low = msg.lower()
    hinglish = lang == "en" and bool(re.search(r"\b(kaise|kya|nahi|karu|kahan|shikayat|hai|mera|meri)\b", low))
    for pat, ans in RULES:
        if re.search(pat, low):
            return {"reply": ans["hi"] if lang == "hi" else ans["en"], "lang": "hi" if lang == "hi" else ("hinglish" if hinglish else "en"),
                    "intent": pat.split("|")[0]}
    return {"reply": DEFAULT["hi"] if lang == "hi" else DEFAULT["en"], "lang": lang, "intent": "fallback"}
