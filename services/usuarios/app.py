from flask import Flask, jsonify

app = Flask(__name__)

USUARIOS = [
    {"id": 1, "nombre": "Ana Torres", "email": "ana.torres@micropay.cl"},
    {"id": 2, "nombre": "Carlos Reyes", "email": "carlos.reyes@micropay.cl"},
]

@app.route("/usuarios/health")
def health():
    return jsonify(status="ok", service="usuarios"), 200

@app.route("/usuarios")
def list_usuarios():
    return jsonify(usuarios=USUARIOS), 200

@app.route("/usuarios/<int:usuario_id>")
def get_usuario(usuario_id):
    usuario = next((u for u in USUARIOS if u["id"] == usuario_id), None)
    if usuario is None:
        return jsonify(error="usuario no encontrado"), 404
    return jsonify(usuario), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)