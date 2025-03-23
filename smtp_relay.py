import ssl
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from email import policy
from email.parser import BytesParser
from email.message import EmailMessage
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP
from db_config import get_db_connection
from prometheus_client import start_http_server, Counter, Summary
import os
from dotenv import load_dotenv
import requests
from msal import ConfidentialClientApplication

# Carregar variáveis de ambiente
load_dotenv()

# Credenciais do aplicativo Microsoft
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
GRAPH_URL = os.getenv("GRAPH_URL", "https://graph.microsoft.com/v1.0")

# Credenciais do conector
SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
SMTP_USER = os.getenv("DB_USER")
SMTP_PASSWORD = os.getenv("DB_PASSWORD")

# ────────────────────────────────
# 🔐 Certificados TLS
CERT_PATH = r"C:\Certificados\fullchain1.pem"
KEY_PATH = r"C:\Certificados\privkey1.pem"

# 📁 Diretório para salvar .eml
SAVE_DIR = "emails_salvos"
os.makedirs(SAVE_DIR, exist_ok=True)

# ────────────────────────────────
# 📊 Prometheus Métricas
EMAILS_PROCESSED = Counter('emails_processed_total', 'Total de e-mails processados com sucesso')
EMAILS_FAILED = Counter('emails_failed_total', 'Total de e-mails que falharam ao processar')
EMAIL_LATENCY = Summary('email_processing_seconds', 'Tempo de processamento por e-mail')

# ────────────────────────────────
# 📝 Logging
log_formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
log_handler = TimedRotatingFileHandler("smtp_relay.log", when="midnight", backupCount=7, encoding="utf-8")
log_handler.setFormatter(log_formatter)

logger = logging.getLogger("log_smtp_relay")
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

# ────────────────────────────────
# 🔍 Buscar assinatura no banco
def buscar_assinatura(sender_email: str) -> str:
    clean_email = sender_email.strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("EXEC get_signature ?", (clean_email,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else ""

# ────────────────────────────────
# 🔑 Obter token de acesso da Microsoft Graph
def obter_token():
    app = ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" in result:
        return result["access_token"]
    else:
        logger.error(f"Erro ao obter token: {result.get('error_description')}")
        raise Exception("Falha ao obter token de acesso")

# ────────────────────────────────
# 📩 Handler SMTP
class EmailHandler:
    @EMAIL_LATENCY.time()
    async def handle_DATA(self, server, session, envelope):
        try:
            original_msg = BytesParser(policy=policy.default).parsebytes(envelope.content)
            sender = envelope.mail_from
            recipients = envelope.rcpt_tos
            subject = original_msg.get("Subject", "")
            signature = buscar_assinatura(sender)

            # Construir o corpo do e-mail
            body = ""
            body_html = ""
            if original_msg.is_multipart():
                for part in original_msg.iter_parts():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        body = part.get_content() + f"\n\n{signature}"
                    elif content_type == "text/html":
                        body_html = part.get_content() + f"<br><br>{signature}"
            else:
                content_type = original_msg.get_content_type()
                if "html" in content_type:
                    body_html = original_msg.get_content() + f"<br><br>{signature}"
                else:
                    body = original_msg.get_content() + f"\n\n{signature}"

            # Montar o payload para a Graph API
            email_data = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML" if body_html else "Text",
                        "content": body_html if body_html else body,
                    },
                    "from": {"emailAddress": {"address": sender}},
                    "toRecipients": [{"emailAddress": {"address": recipient}} for recipient in recipients],
                },
                "saveToSentItems": "true",
            }

            # Enviar o e-mail via Microsoft Graph API
            token = obter_token()
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            response = requests.post(f"{GRAPH_URL}/users/{sender}/sendMail", json=email_data, headers=headers)

            if response.status_code == 202:
                logger.info(f"E-mail enviado com sucesso: {sender} -> {', '.join(recipients)} | Assunto: {subject}")
                EMAILS_PROCESSED.inc()
                return '250 Message accepted for delivery'
            else:
                logger.error(f"Erro ao enviar e-mail via Graph API: {response.status_code} - {response.text}")
                EMAILS_FAILED.inc()
                return '550 Failed to send message'

        except Exception as e:
            logger.error(f"Erro ao processar e-mail: {e}")
            EMAILS_FAILED.inc()
            return '550 Failed to process message'

# ────────────────────────────────
# 🚀 TLS SMTP Controller
class CustomSMTP(SMTP):
    def __init__(self, handler):
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=CERT_PATH, keyfile=KEY_PATH)
        super().__init__(handler, require_starttls=True, tls_context=context)

class CustomController(Controller):
    def factory(self):
        return CustomSMTP(self.handler)

# ────────────────────────────────
# ▶️ Iniciar
if __name__ == "__main__":
    start_http_server(9100)
    logger.info("Métricas Prometheus disponíveis em http://localhost:9100/metrics")

    handler = EmailHandler()
    controller = CustomController(handler, hostname="170.238.45.85", port=25)
    controller.start()
    logger.info("Servidor SMTP STARTTLS ativo e monitorando com logs, métricas e salvamento de .eml")

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Encerrando servidor SMTP...")
        controller.stop()
