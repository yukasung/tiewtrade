from flask import Flask, request
app = Flask(__name__)
@app.route("/validation-only")
def probe():
    return str(eval(request.args["input"]))
