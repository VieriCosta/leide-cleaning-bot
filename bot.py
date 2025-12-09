import os
from datetime import datetime

from flask import Flask, request, jsonify
import requests

# ==========================================
# CONFIGURAÇÕES BÁSICAS
# ==========================================

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "YOUR_PAGE_ACCESS_TOKEN_HERE")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_LEIDE_VERIFY_TOKEN")

# URL do seu Web App do Google Sheets
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzQeTE2Xry0GY4XaQV298w6uLegcdWHy9fY1skqmiA_IGA2xuVHjhwLADJN2XWJfeNP/exec"


# ==========================================
# ESTADOS
# ==========================================

user_states = {}

app = Flask(__name__)


# ==========================================
# GOOGLE SHEETS VIA WEB APP
# ==========================================

def append_row_to_sheet(user_data):
    try:

        data_to_send = {
            "name": user_data.get("name", ""),
            "email": user_data.get("email", ""),
            "phone": user_data.get("phone", ""),
            "address": user_data.get("address", ""),
            "cleaning_type": user_data.get("cleaning_type", ""),
            "bedrooms": user_data.get("bedrooms", ""),
            "bathrooms": user_data.get("bathrooms", ""),
            "notes": user_data.get("notes", ""),
            "timestamp": datetime.utcnow().strftime("%m/%d - %H:%M")  # DATA LIMPA
        }

        response = requests.post(GOOGLE_SHEETS_WEBAPP_URL, json=data_to_send)
        print("Sheets response:", response.text)

    except Exception as e:
        print("Error sending to Google Sheets:", e)



# ==========================================
# FACEBOOK MESSENGER
# ==========================================

def send_message(recipient_id, text):
    url = "https://graph.facebook.com/v17.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}

    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }

    response = requests.post(url, params=params, json=payload)

    if response.status_code != 200:
        print("Erro ao enviar mensagem:", response.status_code, response.text)



# ==========================================
# FLUXO DO BOT
# ==========================================

def get_user_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = {"step": "start", "data": {}}
    return user_states[user_id]


def handle_user_message(user_id, message_text):
    state = get_user_state(user_id)
    step = state["step"]
    data = state["data"]
    text = (message_text or "").strip()

    # -----------------------------
    # INÍCIO
    # -----------------------------
    if step == "start":
        send_message(user_id, "Hi! What is your full name?")
        state["step"] = "ask_name"
        return

    # -----------------------------
    # NOME
    # -----------------------------
    if step == "ask_name":
        data["name"] = text
        send_message(user_id, "Welcome! 👋 I am the virtual assistant for *Leide Cleaning* and I will start your service request.\n\nWhat is your full name?")
        state["step"] = "ask_email"
        return

    # -----------------------------
    # EMAIL
    # -----------------------------
    if step == "ask_email":
        data["email"] = text
        send_message(user_id, "What is your phone number?")
        state["step"] = "ask_phone"
        return

    # -----------------------------
    # TELEFONE
    # -----------------------------
    if step == "ask_phone":
        data["phone"] = text
        send_message(user_id, "Full address?")
        state["step"] = "ask_address"
        return

    # -----------------------------
    # ENDEREÇO
    # -----------------------------
    if step == "ask_address":
        data["address"] = text
        send_message(
            user_id,
            "Type of cleaning?\n"
            "- Standard\n- Deep\n- Move In/Out\n- Carpet\n- Commercial"
        )
        state["step"] = "ask_cleaning_type"
        return

    # -----------------------------
    # TIPO DE LIMPEZA
    # -----------------------------
    if step == "ask_cleaning_type":
        data["cleaning_type"] = text
        send_message(user_id, "How many bedrooms?")
        state["step"] = "ask_bedrooms"
        return

    # -----------------------------
    # QUARTOS
    # -----------------------------
    if step == "ask_bedrooms":
        data["bedrooms"] = text
        send_message(user_id, "How many bathrooms?")
        state["step"] = "ask_bathrooms"
        return

    # -----------------------------
    # BANHEIROS
    # -----------------------------
    if step == "ask_bathrooms":
        data["bathrooms"] = text
        send_message(user_id, "Any notes? (pets, construction, etc.)")
        state["step"] = "ask_notes"
        return

    # -----------------------------
    # NOTAS
    # -----------------------------
    if step == "ask_notes":
        data["notes"] = text

        # Salva na planilha
        append_row_to_sheet(data)

        send_message(user_id, "Thank you! A representative will contact you soon.")

        # Reinicia o fluxo
        user_states[user_id] = {"step": "start", "data": {}}
        return



# ==========================================
# WEBHOOK FACEBOOK
# ==========================================

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verificado!")
        return challenge, 200

    return "Invalid token", 403



@app.route("/webhook", methods=["POST"])
def handle_webhook():
    payload = request.get_json()

    if payload.get("object") == "page":
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event["sender"]["id"]

                if "message" in event:
                    text = event["message"].get("text")
                    if text:
                        handle_user_message(sender_id, text)

    return "EVENT_RECEIVED", 200



@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Leide Cleaning bot is running"})



# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
