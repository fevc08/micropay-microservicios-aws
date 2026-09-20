from flask import Flask, jsonify

app = Flask(__name__)

PAGOS = [
    {"id": 1, "usuario_id": 1, "monto": 15000, "moneda": "CLP", "estado": "aprobado", "fecha": "2026-09-01"},
    {"id": 2, "usuario_id": 2, "monto": 32000, "moneda": "CLP", "estado": "pendiente", "fecha": "2026-09-15"},
]

@app.route("/pagos/health")
def health():
    return jsonify(status="ok", service="pagos"), 200

@app.route("/pagos")
def list_pagos():
    return jsonify(pagos=PAGOS), 200

@app.route("/pagos/<int:pago_id>")
def get_pago(pago_id):
    pago = next((p for p in PAGOS if p["id"] == pago_id), None)
    if pago is None:
        return jsonify(error="pago no encontrado"), 404
    return jsonify(pago), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)