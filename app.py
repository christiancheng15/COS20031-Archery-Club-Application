from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = 's3cR3t_k3Y!oN4z4g@fC9*e1$9Q1#r' # SECRET_KEY RANDOM

db_config = {
    'host': 'feenix-mariadb.swin.edu.au', # HOST
    'user': '', # USER
    'password': '', # PASSWORD
    'database': '' # DATABASE NAME
}

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        dob = datetime.strptime(request.form['dob'], '%Y-%m-%d')
        
        conn = mysql.connector.connect(**db_config)
        cur = conn.cursor()

        cur.execute('''
                SELECT * FROM Archers
                WHERE ArcherFirstName = %s
                AND ArcherLastName = %s
                AND ArcherBirthDate = %s
                ''', (first_name, last_name, dob))
        user = cur.fetchone()

        cur.close()
        conn.close()

        if user:
            session['user'] = (user[0], user[1], user[2], user[3].strftime('%Y-%m-%d'), user[4], user[5] )
            return redirect(url_for('profile'))
        else:
            error_message = "User not found. Please check your credentials."
            return render_template('login.html', error_message=error_message)

@app.route('/profile')
def profile():
    user = session.get('user')
    return render_template('profile.html', user=user)

@app.route('/enter-scores')
def enter_scores():
    user = session.get('user')
    
    conn = mysql.connector.connect(**db_config)
    cur = conn.cursor()

    cur.execute('''
        SELECT ClubRounds.ClubRoundID, 
            ClubRounds.ClubRoundName,
            Rounds.RoundDistance,
            Rounds.RoundTargetFace,
            Rounds.RoundEnds,
            Rounds.RoundMaxScore
        FROM ClubRounds
        JOIN Rounds ON ClubRounds.RoundID = Rounds.RoundID
        WHERE NOW() BETWEEN ClubRoundStartDateTime AND ClubRoundEndDateTime
        AND ClubRoundClassification = %s
    ''', (user[5],))
    rounds = cur.fetchall()
    
    cur.execute('''SELECT CompID, CompName
                FROM Competitions''')
    competitions = cur.fetchall()

    cur.close()
    conn.close()

    equipments = ['Recurve', 'Compound', 'Recurve Barebow', 'Compound Barebow', 'Longbow']

    return render_template('enter-scores.html', rounds=rounds, competitions=competitions, equipments=equipments)

@app.route('/enter-end', methods=['POST'])
def submit_scores():
    user = session.get('user')

    round_id = request.form.get('round')
    competition_id = request.form.get('competition')
    if competition_id == "None":
        competition_id = None
    equipment_type = request.form.get('equipment')

    conn = mysql.connector.connect(**db_config)
    cur = conn.cursor()

    try:
        cur.execute('''
            INSERT INTO Scores (ArcherID, ClubRoundID, CompID, ArcherEquipment)
            VALUES (%s, %s, %s, %s);
        ''', (user[0], round_id, competition_id, equipment_type))

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")

    conn.commit()

    cur.execute('''
        SELECT MAX(ScoreID) AS ScoreID
        FROM Scores
        WHERE ArcherID = %s;
    ''', (user[0],))

    session['score_id'] = cur.fetchone()[0]

    cur.execute('''
    SELECT RoundEnds
    FROM Rounds
    WHERE RoundID = (
        SELECT RoundID
        FROM ClubRounds
        WHERE ClubRoundID = %s
    );
    ''', (round_id,))

    session['round_ends'] = cur.fetchone()[0]

    print(session['score_id'] , session['round_ends'])

    cur.close()
    conn.close()
    
    return redirect(url_for('enter_end', end_number=1))

@app.route('/enter-end/<int:end_number>', methods=['GET', 'POST'])
def enter_end(end_number):

    if request.method == 'POST':
        scores = [int(request.form[f'score_{i}']) for i in range(1, 7)]

        insert_end_scores(scores)

        next_end = end_number + 1
        if next_end <= session['round_ends']:
            return redirect(url_for('enter_end', end_number=next_end))
        else:
            return redirect(url_for('all_ends_scored'))

    return render_template('enter-end.html', end_number=end_number)

def insert_end_scores(scores):
    archer_id = session['user'][0]
    score_id = session['score_id']

    conn = mysql.connector.connect(**db_config)
    cur = conn.cursor()

    try:
        cur.execute('''
            INSERT INTO Ends (ArcherID, EndArrow1, EndArrow2, EndArrow3, EndArrow4, EndArrow5, EndArrow6, ScoreID)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (archer_id, *scores, score_id))

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cur.close()
        conn.close()

@app.route('/all-ends-scored')
def all_ends_scored():
    score_id = session['score_id']
    round_ends = session['round_ends']

    conn = mysql.connector.connect(**db_config)
    cur = conn.cursor()

    cur.execute('''
        SELECT EndArrow1,
            EndArrow2,
            EndArrow3,
            EndArrow4,
            EndArrow5,
            EndArrow6,
            (Ends.EndArrow1 + Ends.EndArrow2 + Ends.EndArrow3 + Ends.EndArrow4 + Ends.EndArrow5 + Ends.EndArrow6) AS TotalScore
        FROM Ends
        WHERE ScoreID = %s;
        ''', (score_id,))
    
    scores = cur.fetchall()

    total_score = sum([score[6] for score in scores])

    cur.close()
    conn.close()

    return render_template('all-ends-scored.html', scores=scores, round_ends=round_ends, total_score=total_score)

if __name__ == '__main__':
    app.run(debug=True)