import requests
import os
from db_config import get_db_connection
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
GRAPH_URL = os.getenv("GRAPH_URL")  # Ex: https://graph.microsoft.com/v1.0


def get_access_token():
    """Obtém token de acesso do Microsoft Entra ID (antigo Azure AD)."""
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials"
    }

    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        raise Exception(f"❌ Falha ao obter token: {response.status_code} - {response.text}")


def send_email(sender, recipient, subject, body):
    """Envia e-mail com assinatura via Microsoft Graph API."""
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # ⚠️ Normalizar o e-mail antes de passar para o SQL
    clean_sender = sender.strip().lower()
    print(f"🔍 Buscando assinatura para: [{repr(sender)}] -> [{clean_sender}]")

    # Buscar assinatura no banco de dados
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("EXEC get_signature ?", (clean_sender,))
    row = cursor.fetchone()
    conn.close()

    if row is None or not row[0]:
        raise Exception(f"⚠️ Nenhuma assinatura encontrada para o usuário: {clean_sender}")

    signature = row[0]
    print(f"🖊️ Assinatura aplicada: {signature[:60]}...")

    # Adicionar a assinatura ao corpo
    new_body = f"{body}<br><br>{signature}"

    email_message = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": new_body
            },
            "toRecipients": [
                {"emailAddress": {"address": recipient}}
            ],
            "internetMessageHeaders": [
                {
                    "name": "X-Signature-Processed",
                    "value": "true"
                }
            ]
        },
        "saveToSentItems": False
    }

    send_url = f"{GRAPH_URL}/users/{clean_sender}/sendMail"
    response = requests.post(send_url, headers=headers, json=email_message)

    if response.status_code == 202:
        print(f"✅ E-mail enviado com sucesso para {recipient}")
        return True
    else:
        raise Exception(f"❌ Erro ao enviar e-mail: {response.status_code} - {response.text}")
