from flask import Flask

app = Flask(__name__)


@app.get("/projects")
def list_projects():
    return []
