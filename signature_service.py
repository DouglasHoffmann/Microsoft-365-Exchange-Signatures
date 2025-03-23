
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import pyodbc
from db_config import get_db_connection
from graph_email_service import send_email
import uvicorn

app = FastAPI()

# 🔹 Modelos de entrada
class EmailData(BaseModel):
    sender: str
    recipient: str
    subject: str
    body: str

class SignatureData(BaseModel):
    user_email: str
    full_name: str
    job_title: Optional[str] = ""
    phone_number: Optional[str] = ""
    department: Optional[str] = ""
    signature_html: Optional[str] = ""

# 🔸 Processamento de e-mails (chamada pelo SMTP relay)
@app.post("/api/process-email")
async def process_email(data: EmailData):
    try:
        # Prevenção de loop
        if data.sender.lower() == data.recipient.lower():
            return {"status": "ignorado", "mensagem": "Remetente e destinatário são iguais. Ignorando para evitar loop."}

        novo_corpo = data.body

        sucesso = send_email(
            sender=data.sender,
            recipient=data.recipient,
            subject=data.subject,
            body=novo_corpo
        )

        if sucesso:
            return {"status": "ok", "mensagem": "E-mail enviado com sucesso com assinatura"}
        else:
            raise HTTPException(status_code=500, detail="Falha ao enviar e-mail via Microsoft Graph")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar e-mail: {str(e)}")


# 🔸 Cria ou atualiza assinatura
@app.post("/api/signature")
def create_or_update_signature(data: SignatureData):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "EXEC upsert_signature ?, ?, ?, ?, ?, ?",
            (
                data.user_email,
                data.full_name,
                data.job_title,
                data.phone_number,
                data.department,
                data.signature_html
            )
        )
        conn.commit()
        conn.close()
        return {"status": "ok", "mensagem": "Assinatura salva com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar assinatura: {str(e)}")


# 🔸 Deleta assinatura
@app.delete("/api/signature/{email}")
def delete_signature(email: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("EXEC delete_signature ?", (email,))
        conn.commit()
        conn.close()
        return {"status": "ok", "mensagem": "Assinatura excluída com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao excluir assinatura: {str(e)}")


# 🔸 Relatório de todas as assinaturas
@app.get("/api/signatures/report")
def report_signatures():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("EXEC get_all_signatures")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            raise HTTPException(status_code=404, detail="Nenhuma assinatura encontrada.")

        return [
            {
                "user_email": row.user_email,
                "full_name": row.full_name,
                "job_title": row.job_title,
                "phone_number": row.phone_number,
                "department": row.department
            } for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar relatório: {str(e)}")


# 🔸 Health check
@app.get("/")
@app.get("/api/process-email")
def status():
    return {"status": "ok", "mensagem": "API pronta para uso com Exchange Online"}


if __name__ == "__main__":
    uvicorn.run("signature_service:app", host="0.0.0.0", port=5005, reload=False)
