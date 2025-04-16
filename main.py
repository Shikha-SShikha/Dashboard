
from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, emit
import pandas as pd
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app)

# Read Excel file and structure the data
try:
    df = pd.read_excel('attached_assets/test.xlsx')
    # Assuming first column is team name, rest are members
    member_cols = df.columns[1:]
    teams = []
    team_names = []
    
    for _, row in df.iterrows():
        team_name = row.iloc[0]  # Use iloc to access first column
        members = [str(row[col]) for col in member_cols if pd.notna(row[col])]
        teams.append({
            'team_name': team_name,
            'members': ','.join(members)
        })
        team_names.append(team_name)
except Exception as e:
    print(f"Error reading Excel file: {e}")
    teams = []
    team_names = []

import sqlite3
from replit import db

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('hackathon.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS evaluations
                 (juror TEXT, jury_type TEXT, team TEXT, criteria TEXT, score TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Initialize empty lists in db if they don't exist
if 'help_requests' not in db:
    db['help_requests'] = []
if 'meme_submissions' not in db:
    db['meme_submissions'] = []

@app.route('/')
def index():
    return render_template('index.html', team_names=team_names)

@app.route('/submit_help', methods=['POST'])
def submit_help():
    team = request.form.get('team')
    help_type = request.form.get('help_type')
    help_requests = db['help_requests']
    help_requests.append({'team': team, 'help_type': help_type})
    db['help_requests'] = help_requests
    socketio.emit('new_help_request', {'team': team, 'help_type': help_type})
    return redirect(url_for('index'))

@app.route('/submit_meme', methods=['POST'])
def submit_meme():
    team = request.form.get('team')
    meme_url = request.form.get('meme_url')
    meme_submissions = db['meme_submissions']
    meme_submissions.append({'team': team, 'meme_url': meme_url})
    db['meme_submissions'] = meme_submissions
    return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    if username == 'admin' and password == 'admin':
        session['is_admin'] = True
        return redirect(url_for('admin'))
    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return redirect(url_for('index'))
    
    # Initialize evaluations in db if not exists
    if 'evaluations' not in db:
        db['evaluations'] = {}
        
    return render_template('admin.html', 
                         teams=teams, 
                         help_requests=db['help_requests'], 
                         meme_submissions=db['meme_submissions'],
                         evaluations=db['evaluations'])

@app.route('/submit_evaluation', methods=['POST'])
def submit_evaluation():
    if not session.get('is_admin'):
        return redirect(url_for('index'))
        
    juror = request.form.get('juror')
    jury_type = request.form.get('jury_type', 'secondary')
    team = request.form.get('team')
    
    conn = sqlite3.connect('hackathon.db')
    c = conn.cursor()
    
    if jury_type == 'primary':
        criteria = ['innovation', 'technical', 'ux', 'presentation']
        for criterion in criteria:
            score = request.form.get(f'{criterion}_score')
            c.execute('INSERT INTO evaluations (juror, jury_type, team, criteria, score) VALUES (?, ?, ?, ?, ?)',
                     (juror, jury_type, team, criterion, score))
    else:
        criteria = ['mvp_completeness', 'functionality', 'simplicity_ux']
        for criterion in criteria:
            score = 'true' if request.form.get(criterion) == 'true' else 'false'
            c.execute('INSERT INTO evaluations (juror, jury_type, team, criteria, score) VALUES (?, ?, ?, ?, ?)',
                     (juror, jury_type, team, criterion, score))
    
    conn.commit()
    conn.close()
    
    # Set a session variable to mark this juror's evaluation as complete
    if 'completed_evaluations' not in session:
        session['completed_evaluations'] = []
    session['completed_evaluations'].append(juror)
    
    return redirect(url_for('admin'))

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
