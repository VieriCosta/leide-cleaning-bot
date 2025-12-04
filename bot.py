import os
from datetime import datetime

from flask import Flask, request, jsonify
import requests

from google.oauth2 import service_account
from googleapiclient.discovery import build

# ==========================================
# CONFIGURAÇÕES BÁSICAS
# ==========================================

# ➜ COLOQUE AQUI O TOKEN DA SUA PÁGINA DO FACEBOOK
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "YOUR_PAGE_ACCESS_TOKEN_HERE")

# ➜ COLOQUE AQUI UM VERIFY_TOKEN QUE VOCÊ INVENTAR
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MY_LEIDE_VERIFY_TOKEN")

# ➜ ID DA SUA PLANILHA (VOCÊ ME PASSOU ESSE)
SPREADSHEET_ID = "1375TOS-mGJiSBdhYpDOgzcM7PpKpSPmJBty6nurLHE"

# ➜ CAMINHO DO ARQUIVO DE CREDENCIAL DO GOOGLE (service account)
GOOGLE_CREDENTIALS_FILE = "credentials.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ==========================================
# ESTADO EM MEMÓRIA (SIMPLÃO) POR USUÁRIO
# ==========================================

# Ex: user_states["123456"] = {"step": "ask_phone", "data": {...}}
user_states = {}

app = Flask(_name_)


# ==========================================
# FUNÇÕES AUXILIARES – GOOGLE SHEETS
# ==========================================

def get_sheets_service():
    """
    Cria o cliente da API do Google Sheets usando uma Service Account.
    Você precisa ter o arquivo credentials.json na mesma pasta.
    E compartilhar a planilha com o e-mail da service account.
    """
    credentials = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=credentials)
    return service


def append_row_to_sheet(user_data):
    """
    Envia uma linha para a planilha do Google Sheets.
    Colunas: Name | Phone | Address | CleaningType | Bedrooms | Bathrooms | Notes | Timestamp
    """
    service = get_sheets_service()
    sheet = service.spreadsheets()

    timestamp = datetime.utcnow().isoformat()

    values = [[
        user_data.get("name", ""),
        user_data.get("phone", ""),
        user_data.get("address", ""),
        user_data.get("cleaning_type", ""),
        user_data.get("bedrooms", ""),
        user_data.get("bathrooms", ""),
        user_data.get("notes", ""),
        timestamp
    ]]

    body = {
        "values": values
    }

    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="A2",
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()


# ==========================================
# FUNÇÕES AUXILIARES – FACEBOOK MESSENGER
# ==========================================

def send_message(recipient_id, text):
    """
    Envia uma mensagem de texto para o usuário no Messenger.
    """
    url = "https://graph.facebook.com/v17.0/me/messages"
    params = {
        "access_token": PAGE_ACCESS_TOKEN
        }
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }

    response = requests.post(url, params=params, json=payload)
    if response.status_code != 200:
        print("Erro ao enviar mensagem:", response.status_code, response.text)


# ==========================================
# LÓGICA DO FLUXO DO BOT
# ==========================================

def get_user_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = {
            "step": "start",
            "data": {}
        }
    return user_states[user_id]


def handle_user_message(user_id, message_text):
    """
    Lida com o fluxo de perguntas e respostas.
    """
    state = get_user_state(user_id)
    step = state["step"]
    data = state["data"]
    text = (message_text or "").strip()

    # Passo 1: início / boas-vindas
    if step == "start":
        send_message(
            user_id,
            "Hi! 👋 Thanks for contacting Leide Cleaning.\n"
            "I will ask you a few quick questions to request your cleaning."
        )
        send_message(user_id, "First, what is your full name?")
        state["step"] = "ask_name"
        return

    # Passo 2: Nome
    if step == "ask_name":
        data["name"] = text
        send_message(user_id, f"Nice to meet you, {data['name']}! 😊")
        send_message(user_id, "What is the best phone number to contact you?")
        state["step"] = "ask_phone"
        return

    # Passo 3: Telefone
    if step == "ask_phone":
        data["phone"] = text
        send_message(user_id, "Great! What is the full address where you need the cleaning?")
        state["step"] = "ask_address"
        return

    # Passo 4: Endereço
    if step == "ask_address":
        data["address"] = text
        send_message(
            user_id,
            "What type of cleaning do you need?\n"
            "- Standard Cleaning\n"
            "- Deep Cleaning\n"
            "- Move In / Move Out\n"
            "- Post-construction\n"
            "- Commercial\n"
            "- Vacation Home\n"
            "- Carpet Cleaning"
        )
        state["step"] = "ask_cleaning_type"
        return

    # Passo 5: Tipo de limpeza
    if step == "ask_cleaning_type":
        data["cleaning_type"] = text
        send_message(user_id, "How many bedrooms?")
        state["step"] = "ask_bedrooms"
        return

    # Passo 6: Quartos
    if step == "ask_bedrooms":
        data["bedrooms"] = text
        send_message(user_id, "How many bathrooms?")
        state["step"] = "ask_bathrooms"
        return

    # Passo 7: Banheiros
    if step == "ask_bathrooms":
        data["bathrooms"] = text
        send_message(user_id, "Any extra notes? (pets, recent construction, special requests, etc.)")
        state["step"] = "ask_notes"
        return

    # Passo 8: Observações
    if step == "ask_notes":
        data["notes"] = text

        # Aqui salva na planilha
        try:
            append_row_to_sheet(data)
            print(f"Dados salvos na planilha para user {user_id}: {data}")
        except Exception as e:
            print("Erro ao salvar na planilha:", e)

        # Mensagem final para o cliente
        summary = (
            "Thank you! 🙌 We have received your cleaning request.\n\n"
            f"Name: {data.get('name', '')}\n"
            f"Phone: {data.get('phone', '')}\n"
            f"Address: {data.get('address', '')}\n"
            f"Cleaning Type: {data.get('cleaning_type', '')}\n"
            f"Bedrooms: {data.get('bedrooms', '')}\n"
            f"Bathrooms: {data.get('bathrooms', '')}\n"
            f"Notes: {data.get('notes', '')}\n\n"
            "A representative from Leide Cleaning will contact you as soon as possible. 🧽✨"
        )
        send_message(user_id, summary)

        # Reseta o fluxo para poder começar de novo
        user_states[user_id] = {"step": "start", "data": {}}
        return

    # Se por algum motivo cair num estado desconhecido:
    send_message(user_id, "Sorry, something went wrong. Let's start again.")
    user_states[user_id] = {"step": "start", "data": {}}
    send_message(user_id, "What is your full name?")


# ==========================================
# ROTAS DO FLASK – WEBHOOK DO FACEBOOK
# ==========================================

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """
    Verificação do Webhook pelo Facebook (fase de configuração).
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verificado com sucesso!")
        return challenge, 200
    else:
        print("Falha na verificação do webhook.")
        return "Verification token mismatch", 403


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """
    Recebe mensagens reais dos usuários.
    """
    payload = request.get_json()
    # Debug (opcional)
    # print("Payload recebido:", payload)

    if payload.get("object") == "page":
        for entry in payload.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]

                if "message" in messaging_event:
                    message = messaging_event["message"]
                    text = message.get("text")

                    if text:
                        handle_user_message(sender_id, text)

    return "EVENT_RECEIVED", 200


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Leide Cleaning bot is running"}), 200


# ==========================================
# MAIN
# ==========================================

if _name_ == "_main_":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)