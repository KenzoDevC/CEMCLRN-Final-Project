from flask import Flask, render_template, request, send_file
from datetime import datetime, timedelta
from disaster_scrape import run_scraper

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    # Automatically set date range to past 7 days
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=7)

    # Optionally, you can call the scraper here if you want the CSV ready
    output_path = run_scraper(start_date=start_date, end_date=end_date)

    # Render the index.html page
    return render_template("index.html", csv_path=output_path)

if __name__ == "__main__":
    app.run(debug=True)
