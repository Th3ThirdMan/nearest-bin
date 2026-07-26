from flask import Flask, render_template
from app import (
    get_bins,
    find_nearest_bin,
    url,
    query,
    headers,
    user_lat,
    user_lon
)

app = Flask(__name__)


@app.route("/")
def home():
    return render_template(
        "index.html",
        title="Nearest Bin",
        nearest_bin=None,
        nearest_distance=None,
        error_message=None,
        data_source=None
    )


@app.route("/find-bin", methods=["POST"])
def find_bin():
    data = get_bins(url, query, headers)

    nearest_bin = None
    nearest_distance = None
    error_message = None
    data_source = None

    if data is not None:
        data_source = data.get("source")

        nearest_bin, nearest_distance = find_nearest_bin(
            data["elements"],
            user_lat,
            user_lon
        )
    else:
        error_message = (
            "The bin service is temporarily unavailable. Please try again."
        )

    return render_template(
        "index.html",
        title="Nearest Bin",
        nearest_bin=nearest_bin,
        nearest_distance=nearest_distance,
        error_message=error_message,
        data_source=data_source
    )


if __name__ == "__main__":
    app.run(debug=True)