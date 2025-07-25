from flask import Flask, render_template, request, redirect, session, url_for
import hashlib
import subprocess
import tempfile
import os
import sys

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

@app.route('/')
def home():
    if 'stage' not in session:
        session['stage'] = 1
    return redirect(url_for('challenge', stage=session['stage']))

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
                    if current['story_keyword'] not in session['unlocked_keywords']:
                        session['unlocked_keywords'].append(current['story_keyword'])
                        session.modified = True
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


@app.route('/reset')
def reset():
    session.pop('stage', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
