from flask import Flask, render_template, request, redirect, session, url_for
from pymongo import MongoClient
import hashlib
import subprocess
import tempfile
import os
import sys
import json


PROGRESS_FILE = "team_progress.json"

client = MongoClient(
    'mongodb+srv://Aditya:1234$@cluster0.rl4qm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
)

db = client["Code_Chronicles"]
progress_collection = db["Progress"]

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Challenges with expected access codes ---
challenges = [
    {
        "id": 1,
        "title": "Challenge 1",
        "code": '''\
def slice_and_join(data):
    # supposed to take all but first and last, then join with '-'
    return '-'.join(data[1:len(data)])

items = ["zero","one","two","three","four"]
print(slice_and_join(items))
''',
        "access_code_hash": hashlib.sha256("one-two-three".encode()).hexdigest(),
        "story_keyword": "awakening"
    },
    {
        "id": 2,
        "title": "Challenge 2",
        "code": '''\
import math

def lcm(a, b):
    return abs(a*b) // math.gcd(a, b)

res = lcm(lcm(7,11),13)
print("Result =", res//13)
''',
        "access_code_hash": hashlib.sha256("1001".encode()).hexdigest(),
        "story_keyword": "protocol"
    },
    # Add more challenges here
]


def load_progress():
    if not os.path.exists(PROGRESS_FILE):
        return {}
    with open(PROGRESS_FILE, "r") as f:
        return json.load(f)

def save_progress(data):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=4)





@app.route('/')
def home():
    if 'team_name' not in session:
        return redirect(url_for('login'))
    if 'stage' not in session:
        session['stage'] = 1
    return redirect(url_for('challenge', stage=session['stage']))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        team_name = request.form.get('team_name').strip()
        if team_name:
            session['team_name'] = team_name
            # Optional: initialize progress for new team
            if not os.path.exists('team_progress.json'):
                with open('team_progress.json', 'w') as f:
                    json.dump({}, f)

            team_data = progress_collection.find_one({"team_name": team_name})
            if not team_data:
                progress_collection.insert_one({
                    "team_name": team_name,
                    "completed": [],
                    "keywords": []
                })
                session['stage'] = 1
                session['unlocked_keywords'] = []
            else:
                # Load progress from DB
                completed = team_data.get("completed", [])
                max_stage = max(completed, default=0) + 1
                session['stage'] = min(max_stage, len(challenges))  # Don't go beyond last stage
                session['unlocked_keywords'] = team_data.get("keywords", [])


            return redirect(url_for('home'))
    return render_template('login.html')


@app.route('/challenge/<int:stage>', methods=['GET', 'POST'])
def challenge(stage):
    if stage > len(challenges) or stage < 1:
        return redirect(url_for('challenge', stage=1))

    current = challenges[stage - 1]
    message = ""
    challenge_code = current['code']

    # Initialize unlocked keywords
    if 'unlocked_keywords' not in session:
        session['unlocked_keywords'] = []

    if request.method == 'POST':
        action = request.form.get('action', 'run')
        if action == 'reset':
            challenge_code = current['code']
            message = "Code has been reset to the original."
            
        else:
            user_code = request.form.get('code', '')
            challenge_code = user_code

            with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode='w') as tmp:
                tmp.write(user_code)
                tmp_path = tmp.name

            try:
                result = subprocess.run(
                    [sys.executable, tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=2
                )

                output = result.stdout.strip()
                err = result.stderr.strip()

                if result.returncode != 0:
                    message = f"Your code crashed:\n{err}"
                else:
                    token = next((ln.strip() for ln in reversed(output.splitlines()) if ln.strip()), "")
                    if hashlib.sha256(token.encode()).hexdigest() == current['access_code_hash']:
                        if hashlib.sha256(token.encode()).hexdigest() == current['access_code_hash']:
                            if current['story_keyword'] not in session['unlocked_keywords']:
                                session['unlocked_keywords'].append(current['story_keyword'])
                                session.modified = True
                            
                            # ✅ Save team progress
                            team_name = session['team_name']
                            progress_collection.update_one(
                                    {"team_name": team_name},
                                    {"$addToSet": {"completed": stage, "keywords": current['story_keyword']}}
                                )

                            message = f"✅ Correct! Access Code: {token}\nKeyword Unlocked: {current['story_keyword']}"
                    else:
                        message = f"Output did not match expected Access Code. Your output: {token}"

            except subprocess.TimeoutExpired:
                message = "Your code took too long to run (timeout)."
            except Exception as e:
                message = f"Error while running code: {str(e)}"
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)


    return render_template(
        'challenge.html',
        all_challenges=challenges,
        current_challenge=current,
        challenge_number=stage,
        challenge_code=challenge_code,
        unlocked_keywords=session['unlocked_keywords'],
        error=message
    )


@app.route('/admin/progress')
def view_progress():
    data = list(progress_collection.find({}, {'_id': 0}))
    return render_template('admin_progress.html', progress_data=data, total=len(challenges))



@app.route('/reset')
def reset():
    session.pop('stage', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
