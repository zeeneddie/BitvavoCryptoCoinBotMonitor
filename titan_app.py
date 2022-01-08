from flask import Flask, render_template
from flask import request
from flask_debugtoolbar import DebugToolbarExtension
from core import titan_main
import logging

app = Flask(__name__)
titan_main.start_database()

app.debug = True
app.config['SECRET_KEY'] = '100'
toolbar = DebugToolbarExtension(app)

logger = logging.getLogger(__name__)


@app.route("/")
def mainpage():
    return render_template('main.html')


@app.route("/strategy", methods=['POST'])
def strategy():
    user_exchange = request.form['exchange']
    user_basecurrency = request.form['basecurrency']
    user_quotecurrency = request.form['quotecurrency']
    user_candleinterval = request.form['candleinterval']
    user_sma = request.form['sma']
    user_fma = request.form['fma']
    user_balance = request.form['balance']

    if 'forward_simulation' in request.form:
        user_input = [
            user_exchange.lower(),
            user_basecurrency.upper(),
            user_quotecurrency.upper(),
            user_candleinterval,
            True,
            int(user_sma),
            int(user_fma),
            int(user_balance)]
        titan_main.start_strategy(user_input)
        return render_template('results.html')

    elif 'forward_live' in request.form:
        return render_template('results_live.html')


@app.route("/contact")
def contactpage():
    return render_template('main.html')


@app.route("/about")
def aboutpage():
    return render_template('main.html')


@app.route("/github")
def githubpage():
    return render_template('main.html')


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5555)
