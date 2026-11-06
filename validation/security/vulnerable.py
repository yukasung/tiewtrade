from flask import Flask, request, jsonify
app = Flask(__name__)
@app.route("/validation-only")
def probe():
    return jsonify(value=request.args["input"])
