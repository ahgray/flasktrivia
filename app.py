import os
import json
import sqlite3
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime
import random
from pathlib import Path

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

# Database setup
DATABASE = 'trivia.db'

def get_db():
    """Create a database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with required tables."""
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS question_stats (
                question_id TEXT PRIMARY KEY,
                times_shown INTEGER DEFAULT 0,
                times_correct INTEGER DEFAULT 0,
                times_incorrect INTEGER DEFAULT 0,
                UNIQUE(question_id)
            )
        ''')
        conn.commit()

def load_questions():
    """Load questions from JSON file."""
    questions_file = Path('questions.json')
    if questions_file.exists():
        with open(questions_file, 'r', encoding='utf-8') as f:
            questions = json.load(f)
            # Convert format to match our expected structure
            for q in questions:
                # Rename 'correctAnswer' to 'correct' for consistency
                if 'correctAnswer' in q:
                    q['correct'] = q['correctAnswer']
                # Add funFact to explanation if it exists
                if 'funFact' in q and q['funFact']:
                    q['explanation'] = q.get('explanation', '') + '\n\n' + q['funFact']
            return questions
    else:
        # Default questions if file doesn't exist
        return [
            {
                "id": "default_001",
                "category": "general",
                "subcategory": "Geography",
                "difficulty": "easy",
                "question": "What is the capital of France?",
                "options": ["London", "Berlin", "Paris", "Madrid"],
                "correct": 2,
                "explanation": "Paris has been the capital of France since 987 AD."
            }
        ]

# Load questions on startup
QUESTIONS = load_questions()

@app.route('/')
def index():
    """Main page with game setup."""
    return render_template('index.html')

@app.route('/api/start', methods=['POST'])
def start_game():
    """Start a new game session."""
    # Clear any existing session data first
    session.clear()
    
    data = request.json
    print(f"DEBUG: Received start request with data: {data}")
    
    num_questions = min(data.get('numQuestions', 10), len(QUESTIONS))
    category = data.get('category', 'all')
    difficulty = data.get('difficulty', 'all')
    
    print(f"DEBUG: Processing - num_questions={num_questions}, category={category}, difficulty={difficulty}")
    
    # Filter questions based on category and difficulty if specified
    available_questions = QUESTIONS[:]  # Make a copy to avoid modifying original
    if category != 'all':
        available_questions = [q for q in available_questions if q.get('category', '').lower() == category.lower()]
    if difficulty != 'all':
        available_questions = [q for q in available_questions if q.get('difficulty', '').lower() == difficulty.lower()]
    
    print(f"DEBUG: After filtering - available_questions={len(available_questions)}")
    
    # Make sure we have enough questions
    num_questions = min(num_questions, len(available_questions))
    if num_questions == 0:
        return jsonify({'error': 'No questions match your criteria'}), 400
    
    # Select random questions
    selected_questions = random.sample(available_questions, num_questions)
    
    print(f"DEBUG: Selected {len(selected_questions)} questions")
    
    # Initialize session with explicit modification flag
    session['questions'] = selected_questions
    session['current_index'] = 0
    session['score'] = 0
    session['answers'] = []
    session['start_time'] = datetime.now().isoformat()
    session.modified = True
    
    print(f"DEBUG: Session initialized - questions={len(session['questions'])}, current_index={session['current_index']}")
    
    return jsonify({
        'success': True, 
        'totalQuestions': len(selected_questions),
        'categories': list(set(q.get('category', 'general') for q in QUESTIONS)),
        'difficulties': list(set(q.get('difficulty', 'medium') for q in QUESTIONS))
    })

@app.route('/api/question')
def get_question():
    """Get the current question."""
    if 'questions' not in session:
        return jsonify({'error': 'No active game'}), 400
    
    current_index = session['current_index']
    questions = session['questions']
    
    print(f"DEBUG QUESTION: current_index={current_index}, total_questions={len(questions)}")
    
    if current_index >= len(questions):
        print(f"DEBUG QUESTION: No more questions - returning error")
        return jsonify({'error': 'No more questions'}), 400
    
    question = questions[current_index]
    
    # Get question statistics
    with get_db() as conn:
        stats = conn.execute(
            'SELECT * FROM question_stats WHERE question_id = ?',
            (question['id'],)
        ).fetchone()
    
    if stats:
        total_attempts = stats['times_correct'] + stats['times_incorrect']
        accuracy = (stats['times_correct'] / total_attempts * 100) if total_attempts > 0 else 0
    else:
        accuracy = 0
        total_attempts = 0
    
    return jsonify({
        'question': question['question'],
        'options': question['options'],
        'questionNumber': session['current_index'] + 1,
        'totalQuestions': len(questions),
        'category': question.get('category', 'General'),
        'subcategory': question.get('subcategory', ''),
        'difficulty': question.get('difficulty', 'medium'),
        'globalStats': {
            'timesAnswered': total_attempts,
            'accuracy': round(accuracy, 1)
        }
    })

@app.route('/api/answer', methods=['POST'])
def submit_answer():
    """Submit an answer and get feedback."""
    if 'questions' not in session:
        return jsonify({'error': 'No active game'}), 400
    
    data = request.json
    answer_index = data.get('answer')
    
    current_question = session['questions'][session['current_index']]
    is_correct = answer_index == current_question['correct']
    
    # Update session
    session['answers'].append({
        'question': current_question['question'],
        'userAnswer': answer_index,
        'correct': is_correct,
        'correctAnswer': current_question['correct']
    })
    
    if is_correct:
        session['score'] += 1
    
    # Update global statistics
    with get_db() as conn:
        # Insert or update stats
        conn.execute('''
            INSERT INTO question_stats (question_id, times_shown, times_correct, times_incorrect)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(question_id) DO UPDATE SET
                times_shown = times_shown + 1,
                times_correct = times_correct + ?,
                times_incorrect = times_incorrect + ?
        ''', (
            current_question['id'],
            1 if is_correct else 0,
            0 if is_correct else 1,
            1 if is_correct else 0,
            0 if is_correct else 1
        ))
        conn.commit()
    
    # Move to next question
    session['current_index'] += 1
    session.modified = True
    
    # Check if this was the last question
    current_index = session['current_index']
    total_questions = len(session['questions'])
    is_last = current_index >= total_questions
    
    print(f"DEBUG ANSWER: after increment - current_index={current_index}, total_questions={total_questions}, is_last={is_last}")
    
    return jsonify({
        'correct': is_correct,
        'correctAnswer': current_question['options'][current_question['correct']],
        'explanation': current_question.get('explanation', 'No additional information available.'),
        'isLastQuestion': is_last
    })

@app.route('/api/results')
def get_results():
    """Get game results."""
    if 'questions' not in session or 'answers' not in session:
        return jsonify({'error': 'No completed game'}), 400
    
    total_questions = len(session['questions'])
    return jsonify({
        'score': session['score'],
        'totalQuestions': total_questions,
        'percentage': round(session['score'] / total_questions * 100, 1),
        'answers': session['answers'],
        'questions': session['questions']
    })

@app.route('/api/reset', methods=['POST'])
def reset_game():
    """Reset the game session."""
    print(f"DEBUG RESET: Session cleared")
    session.clear()
    session.modified = True
    return jsonify({'success': True})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)