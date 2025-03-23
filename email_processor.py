from flask import Flask, request, jsonify
from db_config import get_db_connection
from graph_email_service import send_email

app = Flask(__name__)

@app.route("/signature", methods=["POST"])
def create_signature():
    """Cria ou atualiza uma assinatura personalizada."""
    data = request.json
    email = data.get("user_email")
    full_name = data.get("full_name")
    job_title = data.get("job_title", "")
    phone_number = data.get("phone_number", "")
    department = data.get("department", "")
    signature_html = data.get("signature_html", "")

    if not email or not full_name:
        return "E-mail e nome completo são obrigatórios", 400

    conn = get_db_connection()
    if conn is None:
        return "Falha ao conectar ao banco de dados", 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("EXEC upsert_signature ?, ?, ?, ?, ?, ?", 
                       (email, full_name, job_title, phone_number, department, signature_html))
        conn.commit()
        return "Assinatura salva com sucesso!", 201
    except Exception as e:
        return str(e), 500
    finally:
        conn.close()

@app.route("/api/process-email", methods=["POST"])
def process_email():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "JSON inválido"}), 400

        # Simples validação (Exchange não manda "from", então ignore)
        if not data.get("subject") or not data.get("body"):
            return jsonify({"status": "error", "message": "Campos obrigatórios faltando"}), 400

        # Simula processamento bem-sucedido
        return jsonify({"status": "ok", "message": "Processamento concluído"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
# @app.route("/", methods=["POST", "GET"])
# @app.route("/process-email", methods=["POST", "GET"])
# def process_email():
    # return jsonify({
        # "status": "ok",
        # "message": "API pronta para uso com Exchange Online"
    # }), 200


@app.route("/signatures/report", methods=["GET"])
def report_signatures():
    """Gera um relatório com todas as assinaturas armazenadas."""
    conn = get_db_connection()
    if conn is None:
        return "Falha ao conectar ao banco de dados", 500

    cursor = conn.cursor()
    cursor.execute("EXEC get_all_signatures")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "Nenhuma assinatura encontrada", 404

    # Criar um relatório em texto puro
    report = "\n".join(
        [f"E-mail: {row.user_email}, Nome: {row.full_name}, Cargo: {row.job_title}, Telefone: {row.phone_number}, Departamento: {row.department}" for row in rows]
    )

    return report, 200

@app.route("/signature/<email>", methods=["DELETE"])
def delete_signature(email):
    """Exclui uma assinatura do banco de dados."""
    conn = get_db_connection()
    if conn is None:
        return "Falha ao conectar ao banco de dados", 500

    cursor = conn.cursor()
    cursor.execute("EXEC delete_signature ?", (email,))
    conn.commit()
    conn.close()

    return "Assinatura excluída com sucesso!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=True)
