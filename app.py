import json #lets us convert between text and python
import os #later used to read the API key
import re #used to search text, gets used when looking for high fevers for example
import time #lets us create new chats (retry)
# The 4 lines above import resources into the IDE to be used later

# flask is used to turn this python code into a website
from flask import Flask, request, jsonify

# dotenv reads our api key through a hidden file so no one can steal and use our key
from dotenv import load_dotenv

# this line is how we import Gemini into our code
from google import genai
from google.genai import types, errors

#double checks that the correct key, fixes a bug where 
#old keys keep being read
load_dotenv(override=True)

#connects the code to Gemini
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

#these are the models of Gemini we use, if the first isn't available
#we switch to the second
MODELS = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
print("Using models:", MODELS)

#tells Gemini how to act and converse with the user, this ensure that MediBot doesn't
#mislead the user and stays in character. 
SYSTEM_PROMPT = """You are MediBot, a friendly symptom triage assistant, NOT a doctor.
Never diagnose. If unsure, choose the more cautious level.
Fever of 103F or higher, any fever in an infant under 3 months, stiff neck with fever,
confusion, or trouble breathing must be emergency or see_doctor_soon.
Write in warm, plain, short sentences that a non-medical person understands.
Return ONLY JSON:
{"level": "emergency" | "see_doctor_soon" | "self_care" | "need_more_info",
 "follow_up_question": "...",
 "advice": "...",
 "otc_options": ["general type only, no doses"]}
Always advise following package labels and asking a pharmacist."""

#these specific phrases trigger an immediate emergency response from MediBot
#MediBot will send a message telling the user to seek help
EMERGENCY_PHRASES = ["chest pain", "can't breathe", "trouble breathing",
                     "suicidal", "stroke", "severe bleeding", "unconscious"]

#helper functions below that can be resused whenever called

def mentions_high_fever(text):
    has_fever_word = "fever" in text.lower()

    has_high_number = bool(re.search(r"\b(10[3-9]|1[1-9]\d)(\.\d)?\b", text))

    # runs to check for fever higher than 103, if they have a high fever
    #they are advised to seek medical attention
    return has_fever_word and has_high_number


def ask_gemini(conversation):
  # Send Gemini the local conversations and returns its reply
  # this makes us not have to wait for Google servers. It also
  # switches models if the limit is reached
    for model_name in MODELS:
        for attempt in range(3):
            try:
                return gemini_client.models.generate_content(
                    model=model_name,
                    contents=conversation, # the whole conversation thus far, so the bot remembers
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT, #gives MediBot its persona
                        response_mime_type="application/json", #makes the reply a JSON file
                    ),
                )

            except errors.ServerError:
                #if its busy on googles side there will be a wait time
                #and then a retry
                time.sleep(2 * (attempt + 1))

            except errors.ClientError as problem:
                #executes if wrong model name, or chat limit reached, etc.
                print("Model", model_name, "failed:", problem)
                break

    #if all else fails and the bot cant reply, this message is shown to the user
    raise RuntimeError("The assistant is unavailable right now. Please try again in a little while.")

#creates the website
app = Flask(__name__)

#chat histories are stored here for each visior, could be implemented into a database with tigerdata
chat_histories = {}


@app.route("/")
def home():
    #this is where we set MediBots profile picture
    return PAGE.replace("__AVATAR__", AVATAR)


@app.route("/chat", methods=["POST"])
def chat():
    #read what the webpage sent us
    data = request.json
    session_id = data["session_id"]
    user_message = data["message"]

    #look for old chats, if this is the users first message start a new one
    history = chat_histories.setdefault(session_id, [])

    #does the message have any of our emergency symptoms?
    contains_emergency_phrase = any(
        phrase in user_message.lower() for phrase in EMERGENCY_PHRASES
    )
    if contains_emergency_phrase or mentions_high_fever(user_message):
        #run the message below as the situation is dire and the user should seek help
        return jsonify({
            "level": "emergency",
            "advice": ("What you describe can be serious. Call 911 or go to the "
                       "nearest emergency room now. If you are thinking about "
                       "harming yourself, call or text 988."),
        })

    #adds users messages to the history
    history.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    #"do this if something goes wrong"
    try:
        gemini_response = ask_gemini(history)
        reply = json.loads(gemini_response.text)

    #the model failed so remove the users new message 
    except RuntimeError as problem:
        history.pop()
        return jsonify({"level": "need_more_info", "advice": str(problem)})

    #The reply wasn't in json format
    except (json.JSONDecodeError, TypeError):
        history.pop()
        return jsonify({
            "level": "need_more_info",
            "advice": "Sorry, I couldn't process that. Could you describe your symptoms again?",
        })
    #everything worked so save Gemini's answer in the history so it remembers what was just said
    history.append(types.Content(role="model", parts=[types.Part(text=gemini_response.text)]))

    return jsonify(reply)

#executes when "new chat" is selected, deletes user history
@app.route("/reset", methods=["POST"])
def reset():
    session_id = request.json["session_id"]
    chat_histories.pop(session_id, None)
    return jsonify({"ok": True})

# The HTML code below was purely cosmetic and was generated using Claude.ai


AVATAR = "data:image/webp;base64,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"

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>MediBot</title>
<link rel="icon" href="__AVATAR__">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #eef3f6;
    --panel: #ffffff;
    --ink: #14272e;
    --muted: #5d7279;
    --line: #dbe5ea;
    --accent: #0e7490;
    --accent-dark: #0b566b;
    --user: #0a2f7a;
    --user-ink: #ffffff;
    --bot: #f1f6f8;
    --urgent-bg: #fdecec;
    --urgent-edge: #c0392b;
    --soon-bg: #fff6df;
    --soon-edge: #d9910a;
    --ok-bg: #e7f5ee;
    --ok-edge: #2e8b57;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    background: var(--bg);
    color: var(--ink);
    font-family: "Figtree", system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    font-size: 16px;
    line-height: 1.5;
  }
  .app {
    width: 100%;
    height: 100vh;
    height: 100dvh;
    display: flex;
    flex-direction: column;
    background: var(--panel);
  }
  header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    padding-top: max(16px, env(safe-area-inset-top));
    padding-left: max(20px, env(safe-area-inset-left));
    padding-right: max(20px, env(safe-area-inset-right));
    background: #031a4f;
    color: #fff;
  }
  .logo { width: 46px; height: 46px; flex: none; }
  .logo img {
    width: 100%; height: 100%; border-radius: 50%; display: block;
    box-shadow: 0 0 0 2px rgba(80,230,255,.55), 0 0 16px rgba(34,211,238,.45);
  }
  header h1 { font-size: 19px; margin: 0; font-weight: 700; }
  header p { margin: 0; font-size: 13px; color: #a9c4e8; }
  header .ghost { background: transparent; color: #fff; border-color: rgba(255,255,255,.35); }
  header .ghost:hover { background: rgba(255,255,255,.14); }
  .spacer { flex: 1; }
  .ghost {
    border: 1px solid var(--line); background: #fff; color: var(--ink);
    padding: 8px 14px; border-radius: 999px; font: inherit; font-size: 14px; font-weight: 500;
    cursor: pointer;
  }
  .ghost:hover { background: var(--bot); }
  .notice {
    background: #f6fafb; border-bottom: 1px solid var(--line);
    padding: 8px 20px; font-size: 13px; color: var(--muted);
  }
  .notice b { color: var(--ink); font-weight: 600; }
  #log {
    flex: 1; overflow-y: auto; padding: 20px;
    display: flex; flex-direction: column; gap: 14px;
    scroll-behavior: smooth;
  }
  .row { display: flex; }
  .row.bot { align-items: flex-end; gap: 10px; }
  .av { width: 34px; height: 34px; border-radius: 50%; flex: none; box-shadow: 0 0 0 1.5px #0a2f7a; }
  .hero { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 8px 0 4px; }
  .hero img {
    width: 112px; height: 112px; border-radius: 50%;
    box-shadow: 0 0 0 3px rgba(80,230,255,.6), 0 0 28px rgba(34,211,238,.55);
    animation: glow 3.2s ease-in-out infinite;
  }
  .hero h2 { margin: 12px 0 0; font-size: 22px; }
  .hero p { margin: 2px 0 0; color: var(--muted); font-size: 14px; }
  @keyframes glow {
    0%, 100% { box-shadow: 0 0 0 3px rgba(80,230,255,.6), 0 0 22px rgba(34,211,238,.4); }
    50% { box-shadow: 0 0 0 3px rgba(80,230,255,.85), 0 0 38px rgba(34,211,238,.75); }
  }
  .row.user { justify-content: flex-end; }
  .bubble {
    max-width: min(85%, 760px); padding: 12px 16px; border-radius: 18px;
    overflow-wrap: anywhere;
  }
  .row.bot .bubble { background: var(--bot); border-bottom-left-radius: 6px; }
  .row.user .bubble { background: var(--user); color: var(--user-ink); border-bottom-right-radius: 6px; }
  .bubble p { margin: 0; }
  .bubble p + p { margin-top: 8px; }
  .bubble .headline { font-weight: 700; margin-bottom: 4px; }
  .bubble .followup { font-weight: 600; }
  .bubble .options { font-size: 14px; color: var(--muted); }
  .row.bot .bubble.urgent { background: var(--urgent-bg); border-left: 5px solid var(--urgent-edge); }
  .row.bot .bubble.soon { background: var(--soon-bg); border-left: 5px solid var(--soon-edge); }
  .row.bot .bubble.ok { background: var(--ok-bg); border-left: 5px solid var(--ok-edge); }
  .typing { display: inline-flex; gap: 5px; padding: 4px 0; }
  .typing span {
    width: 8px; height: 8px; border-radius: 50%; background: #9db0b6;
    animation: bounce 1.1s infinite ease-in-out;
  }
  .typing span:nth-child(2) { animation-delay: .15s; }
  .typing span:nth-child(3) { animation-delay: .3s; }
  @keyframes bounce { 0%, 80%, 100% { transform: translateY(0); opacity: .5; } 40% { transform: translateY(-5px); opacity: 1; } }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  .chip {
    border: 1px solid var(--accent); color: var(--accent-dark); background: #fff;
    padding: 7px 13px; border-radius: 999px; font: inherit; font-size: 14px; font-weight: 500; cursor: pointer;
  }
  .chip:hover { background: var(--accent); color: #fff; }
  form {
    display: flex; gap: 10px; padding: 14px 20px;
    border-top: 1px solid var(--line); background: var(--panel);
    padding-left: max(20px, env(safe-area-inset-left));
    padding-right: max(20px, env(safe-area-inset-right));
  }
  #box {
    flex: 1; border: 1px solid var(--line); border-radius: 999px;
    padding: 13px 18px; font: inherit; background: #f8fbfc; color: var(--ink);
  }
  #box:focus { outline: 3px solid rgba(14,116,144,.3); border-color: var(--accent); background: #fff; }
  #send {
    border: 0; background: var(--accent); color: #fff; font: inherit; font-weight: 600;
    padding: 0 22px; border-radius: 999px; cursor: pointer;
  }
  #send:hover { background: var(--accent-dark); }
  #send:disabled { background: #9db0b6; cursor: not-allowed; }
  button:focus-visible { outline: 3px solid rgba(14,116,144,.5); outline-offset: 2px; }
  footer { padding: 0 20px max(14px, env(safe-area-inset-bottom)); font-size: 12px; color: var(--muted); text-align: center; background: var(--panel); }
  @media (max-width: 520px) {
    header p { display: none; }
    .bubble { max-width: 92%; }
  }
  @media (prefers-reduced-motion: reduce) {
    * { animation: none !important; scroll-behavior: auto !important; }
  }
</style>
</head>
<body>
<div class="app">
  <header>
    <div class="logo"><img src="__AVATAR__" alt="MediBot"></div>
    <div>
      <h1>MediBot</h1>
      <p>Describe how you feel and get guidance on next steps</p>
    </div>
    <div class="spacer"></div>
    <button class="ghost" id="newchat" type="button">New chat</button>
  </header>
  <div class="notice"><b>In an emergency, call 911.</b> This is a prototype and not a substitute for a medical professional.</div>

  <div id="log" aria-live="polite"></div>

  <form id="form" autocomplete="off">
    <input id="box" type="text" placeholder="Type your symptoms here..." aria-label="Describe your symptoms" maxlength="1000">
    <button id="send" type="submit">Send</button>
  </form>
  <footer>Not medical advice. Always follow medication labels and ask a pharmacist or doctor if unsure.</footer>
</div>

<script>
  let sid = Math.random().toString(36).slice(2);
  const log = document.getElementById("log");
  const box = document.getElementById("box");
  const sendBtn = document.getElementById("send");
  const form = document.getElementById("form");

  const AVATAR = document.querySelector(".logo img").src;
  const SUGGESTIONS = ["I have a sore throat", "I've had a headache all day", "My stomach hurts", "I have a cough and runny nose"];

  function scrollDown() { log.scrollTop = log.scrollHeight; }

  function makeRow(kind, cls) {
    const row = document.createElement("div");
    row.className = "row " + kind;
    if (kind === "bot") {
      const av = document.createElement("img");
      av.className = "av"; av.src = AVATAR; av.alt = "";
      row.appendChild(av);
    }
    const bubble = document.createElement("div");
    bubble.className = "bubble" + (cls ? " " + cls : "");
    row.appendChild(bubble);
    log.appendChild(row);
    return bubble;
  }

  function addText(bubble, text, className) {
    const p = document.createElement("p");
    if (className) p.className = className;
    p.textContent = text;
    bubble.appendChild(p);
  }

  function greet() {
    const hero = document.createElement("div");
    hero.className = "hero";
    hero.innerHTML = '<img src="' + AVATAR + '" alt="MediBot"><h2>Meet MediBot</h2><p>Your friendly symptom check assistant</p>';
    log.appendChild(hero);
    const b = makeRow("bot");
    addText(b, "Hi there, I'm MediBot, your symptom check assistant. \uD83D\uDC4B");
    addText(b, "Tell me what's going on and I'll help you decide whether home care is enough or if you should see a doctor. I'm not a doctor, so I can't diagnose anything.");
    addText(b, "What symptoms are you having?");
    const chips = document.createElement("div");
    chips.className = "chips";
    SUGGESTIONS.forEach(s => {
      const c = document.createElement("button");
      c.type = "button"; c.className = "chip"; c.textContent = s;
      c.addEventListener("click", () => { chips.remove(); send(s); });
      chips.appendChild(c);
    });
    b.appendChild(chips);
    scrollDown();
  }

  function showTyping() {
    const b = makeRow("bot");
    b.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
    scrollDown();
    return b.parentElement;
  }

  function showReply(d) {
    // Severity is shown through color and friendly wording, never the raw label.
    const styles = { emergency: "urgent", see_doctor_soon: "soon", self_care: "ok" };
    const headlines = {
      emergency: "Please get medical help right away",
      see_doctor_soon: "It's a good idea to see a doctor soon"
    };
    const b = makeRow("bot", styles[d.level] || "");
    if (headlines[d.level]) addText(b, headlines[d.level], "headline");
    if (d.advice) addText(b, d.advice);
    if (d.otc_options && d.otc_options.length) {
      addText(b, "Things that may help: " + d.otc_options.join(", ") + ".", "options");
    }
    if (d.follow_up_question) addText(b, d.follow_up_question, "followup");
    scrollDown();
  }

  async function send(text) {
    const m = (text || box.value).trim();
    if (!m) return;
    box.value = "";
    document.querySelectorAll(".chips").forEach(c => c.remove());
    addText(makeRow("user"), m);
    sendBtn.disabled = true;
    const typing = showTyping();
    try {
      const r = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sid, message: m })
      });
      if (!r.ok) throw new Error("server");
      const d = await r.json();
      typing.remove();
      showReply(d);
    } catch (e) {
      typing.remove();
      showReply({ level: "need_more_info", advice: "Something went wrong on our end. Please try sending that again." });
    }
    sendBtn.disabled = false;
    box.focus();
  }

  form.addEventListener("submit", e => { e.preventDefault(); send(); });

  document.getElementById("newchat").addEventListener("click", async () => {
    try {
      await fetch("/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sid }) });
    } catch (e) {}
    log.innerHTML = "";
    greet();
    box.focus();
  });

  greet();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
