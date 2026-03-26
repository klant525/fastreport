from flask import Flask, request, render_template
import os
import uuid
from report_models_dayly import process_images, format_report
from report_models_weekly import process_images_weekly
from model_db import MODEL_DB
app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":

        files = request.files.getlist("images")

        paths = []

        for file in files:
            path = os.path.join("uploads", file.filename)
            file.save(path)
            paths.append(path)

        # 👉 xử lý tại đây
        result = process_images(paths)
        report = format_report(result)

        return f"<pre>{report}</pre>"

    return render_template("uploads.html")
@app.route("/weekly", methods=["GET", "POST"])
def weekly():

    if request.method == "POST":

        files = request.files.getlist("images")
        paths = []

        for file in files:
            filename = str(uuid.uuid4()) + ".jpg"
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)
            paths.append(path)

        result = process_images_weekly(paths)

        # xoá file
        for path in paths:
            os.remove(path)

        return f"""
        <h2>BÁO CÁO TUẦN</h2>
        Samsung: {result['samsung']}<br>
        Apple: {result['apple']}<br>
        Oppo: {result['oppo']}<br>
        Xiaomi: {result['xiaomi']}<br>
        Vivo: {result['vivo']}<br>
        Realme: {result['realme']}<br>
        Motorola: {result['motorola']}
        <br><br><a href="/weekly">Quay lại</a>
        """

    return render_template("weekly.html")

if __name__ == "__main__":
    app.run(debug=True)
