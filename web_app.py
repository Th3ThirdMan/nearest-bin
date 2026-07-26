from flask import Flask, render_template, request

from app import (
    find_nearest_bin,
    get_bins,
    headers,
    search_radius,
    url
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
    nearest_bin = None
    nearest_distance = None
    error_message = None
    data_source = None

    try:
        user_lat = float(request.form["latitude"])
        user_lon = float(request.form["longitude"])

    except (KeyError, TypeError, ValueError):
        error_message = "Your location could not be read."

        return render_template(
            "index.html",
            title="Nearest Bin",
            nearest_bin=None,
            nearest_distance=None,
            error_message=error_message,
            data_source=None
        )

    query = f"""
    [out:json];
    node["amenity"="waste_basket"]
    (around:{search_radius},{user_lat},{user_lon});
    out;
    """

    data = get_bins(url, query, headers)

    if data is not None:
        data_source = data.get("source")
        bins = data.get("elements", [])

        if bins:
            nearest_bin, nearest_distance = find_nearest_bin(
                bins,
                user_lat,
                user_lon
            )
        else:
            error_message = (
                f"No public bins were found within "
                f"{search_radius} metres."
            )
    else:
        error_message = (
            "The bin service is temporarily unavailable. "
            "Please try again."
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