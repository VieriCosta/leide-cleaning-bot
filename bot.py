import os
from datetime import datetime

from flask import Flask, request, jsonify
import requests

# ==========================================
# CONFIGURAÇÕES BÁSICAS
# ==========================================

# Token da página do Facebook
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "YOUR_PAGE_ACCESS_TOKEN_HERE")

# Token de verificação do webhook
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_LEIDE_VERIFY_TOKEN")

# URL do Web App do Google Sheets (Apps Script)
GOOGLE_SHEETS_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzQeTE2Xry0GY4XaQV298w6uLegcdWHy9fY1skqmiA_IGA2xuVHjhwLADJN2XWJfeNP/exec"


# ==========================================
# CONTROLE DE ESTADOS DOS USUÁRIOS
# ==========================================

user_states = {}

app = Flask(__name__)


# ==========================================
# FUNÇÃO PARA SALVAR NO GOOGLE SHEETS
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
            "timestamp": datetime.utcnow().strftime("%m/%d - %H:%M")
        }

        response = requests.post(
            GOOGLE_SHEETS_WEBAPP_URL,
            json=data_to_send,
            timeout=10
        )

        print("Google Sheets response:", response.text)

    except Exception as e:
        print("Error sending data to Google Sheets:", e)


# ==========================================
# FUNÇÃO PARA ENVIAR MENSAGEM NO MESSENGER
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
# GERENCIAMENTO DE ESTADO DO USUÁRIO
# ==========================================

def get_user_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = {
            "step": "start",
            "data": {}
        }
    return user_states[user_id]


# ==========================================
# FLUXO PRINCIPAL DO BOT
# ==========================================

def handle_user_message(user_id, message_text):
    state = get_user_state(user_id)
    step = state["step"]
    data = state["data"]
    text = (message_text or "").strip()

    # 🔒 NÃO RESPONDE SE JÁ FINALIZOU
    if step == "completed":
        return

    # -----------------------------
    # INÍCIO
    # -----------------------------
    if step == "start":
        send_message(
            user_id,
            "Welcome! 👋\n\n"
            "I am the virtual assistant for *Leide Cleaning* and I will help you start your service request.\n\n"
            "What is your full name?"
        )
        state["step"] = "ask_name"
        return

    # -----------------------------
    # NOME COMPLETO
    # -----------------------------
    if step == "ask_name":
        data["name"] = text
        send_message(user_id, "What is your email?")
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
        send_message(user_id, "Please provide your full address.")
        state["step"] = "ask_address"
        return

    # -----------------------------
    # ENDEREÇO
    # -----------------------------
    if step == "ask_address":
        data["address"] = text
        send_message(
            user_id,
            "What type of cleaning do you need?\n\n"
            "- Standard\n"
            "- Deep\n"
            "- Move In / Move Out\n"
            "- Carpet\n"
            "- Commercial"
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
        send_message(
            user_id,
            "Any additional notes?\n"
            "(Pets, construction, special requests, etc.)"
        )
        state["step"] = "ask_notes"
        return

    # -----------------------------
    # OBSERVAÇÕES
    # -----------------------------
    if step == "ask_notes":
        data["notes"] = text

        # Envia os dados para o Google Sheets
        append_row_to_sheet(data)

        send_message(
            user_id,
            "Thank you! ✅\n\n"
            "Your request has been successfully received.\n"
            "A Leide Cleaning representative will contact you shortly."
        )

        # 🔒 FINALIZA DEFINITIVAMENTE (SEM LOOP)
        user_states[user_id] = {
            "step": "completed",
            "data": {}
        }
        return


# ==========================================
# WEBHOOK - VERIFICAÇÃO (GET)
# ==========================================

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verified successfully!")
        return challenge, 200

    return "Invalid verification token", 403


# ==========================================
# WEBHOOK - RECEBIMENTO DE MENSAGENS (POST)
# ==========================================

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


# ==========================================
# ROTA DE STATUS
# ==========================================

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Leide Cleaning bot is running"})


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
