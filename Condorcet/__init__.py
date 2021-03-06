from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    flash,
    url_for
)
from functools import wraps
import os
import sys
import random
import string
import time
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)),'..'))


app = Flask(__name__)
app.config.from_object('Condorcet.config')

# convert times in times-tuple
for time_label in 'START_ELECTION', 'CLOSE_ELECTION', 'VIEW_RESULTS':
    app.config[time_label] = time.strptime(app.config[time_label],app.config['DATE_FORMAT'])

import manageDB
from verifyAuthors import isAuthor
import elections

alphabet = string.lowercase
name2letter = dict([(key, val) for key, val in zip(app.config['OPTIONS'], alphabet)])
letter2name = dict([(key, val) for key, val in zip(alphabet, app.config['OPTIONS'])])


def getStrOrder(choice_made):
    return ''.join([name2letter[choice] for choice in choice_made])


def getListChoice(vote):
    return [letter2name[letter] for letter in vote]


def get_environ(var):
    return request.environ[var]


@app.before_request
def set_user():
    # Set user as GD when debugging, else use CERN SSO credentials
    if app.config['DEBUG']:
        session['user'] = {
            'username': 'gdujany',
            'fullname': 'Giulio Dujany'
        }
    else:
        session['user'] = {
            'username': get_environ('ADFS_LOGIN'),
            'fullname': ' '.join([
            get_environ('ADFS_FIRSTNAME'), get_environ('ADFS_LASTNAME')
            ])
        }
    session['user']['author'] = isAuthor(session['user']['fullname'])
    

def author_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session['user']['author']:
            return redirect(url_for('notAuthor'))
        return f(*args, **kwargs)
    return decorated_function

def during_elections(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if time.localtime() < app.config['START_ELECTION']:
            return render_template('notCorrectDate.html',
                                   title = 'Too early to vote',
                                   message='You are a bit too early to vote, we appreciate your enthusiasm but the election will be opening only on '+time.strftime('%d %B %Y at %H.%M',app.config['START_ELECTION'])) 
        if time.localtime() > app.config['CLOSE_ELECTION']:
            return render_template('notCorrectDate.html',
                                   title = 'Too late to vote',
                                   message='I am sorry but the closing date of the election was the '+time.strftime('%d %B %Y at %H.%M',app.config['START_ELECTION'])) 
        return f(*args, **kwargs)
    return decorated_function

def publish_results(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if time.localtime() < app.config['VIEW_RESULTS']:
            return render_template('notCorrectDate.html',
                                   title = 'Too early to see the results',
                                   message='I am sorry but the results are not available yet, visit again this page after the '+time.strftime('%d %B %Y at %H.%M',app.config['START_ELECTION'])) 
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
@during_elections
@author_required
def root():
    fullname = session['user']['fullname']
    if manageDB.isInDB(fullname):
        return render_template('alreadyVoted.html')
    try: session['candidates']
    except KeyError:
        choices_copy = app.config['OPTIONS'][:]
        random.shuffle(choices_copy)
        session['candidates'] = choices_copy
    return render_template('poll.html',
                           title=app.config['TITLE'],
                           fields=session['candidates'])


@app.route('/poll', methods=['POST'])
@during_elections
@author_required
def confirmVote():
    order = []
    choices = app.config['OPTIONS']
    if len(request.form) == len(choices):
        for num in [str(i) for i in range(1, len(choices) + 1)]:
            order.append(request.form.get(num))
        vote = getStrOrder(order)
    else:
        # So that fails next if
        vote = ''
    if len(set(vote)) == len(choices):
        fullname = session['user']['fullname']
        if manageDB.isInDB(fullname):
            return render_template('alreadyVoted.html')
        session['vote'] = vote
        return render_template('confirmVote.html', choices=getListChoice(vote))
    else:
        flash((
            'You must rank all candidates and two candidates cannot share the '
            'same position. Please try again.'
        ), 'error')
    return redirect(url_for('root'))


@app.route('/saveVote')
@during_elections
@author_required
def savePoll():
    fullname = session['user']['fullname']
    if manageDB.isInDB(fullname):
        return render_template('alreadyVoted.html')
    secret_key = manageDB.addVote(fullname, session['vote'])
    return render_template('congrats.html', secret_key=secret_key)


@app.route('/results')
@publish_results
def result():
    # Prepare page with results
    preferences = manageDB.getPreferences()
    choices = app.config['OPTIONS']
    winners = getListChoice(
        elections.getWinner(
            preferences,
            [i for cont, i in enumerate(alphabet) if cont < len(choices)]
        )
    )
    results = [
        [i[0]] + getListChoice(i[1])
        for i in manageDB.getVotes()
    ]
    return render_template('results.html',
                           winners=winners,
                           numCandidates=len(choices),
                           results=results)


@app.route('/unauthorised')
def notAuthor():
    # Authors shouldn't see this page
    if session['user']['author']:
        return redirect(url_for('root'))
    return render_template('notAuthor.html'), 403


if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])
