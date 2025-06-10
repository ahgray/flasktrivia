import os
import json
import sqlite3
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime
import random
from pathlib import Path
import openai
import time

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

# OpenAI configuration
openai.api_key = os.getenv('OPENAI_API_KEY')
LLM_MODEL = os.getenv('LLM_MODEL', 'gpt-4')
GENERATION_ENABLED = os.getenv('GENERATION_ENABLED', 'true').lower() == 'true'

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
    total_questions = len(QUESTIONS)
    return render_template('index.html', total_questions=total_questions)

@app.route('/api/start', methods=['POST'])
def start_game():
    """Start a new game session."""
    # Clear any existing session data first
    session.clear()
    
    data = request.json
    num_questions = min(data.get('numQuestions', 10), len(QUESTIONS))
    category = data.get('category', 'all')
    difficulty = data.get('difficulty', 'all')
    
    # Filter questions based on category and difficulty if specified
    available_questions = QUESTIONS[:]  # Make a copy to avoid modifying original
    if category != 'all':
        available_questions = [q for q in available_questions if q.get('category', '').lower() == category.lower()]
    if difficulty != 'all':
        available_questions = [q for q in available_questions if q.get('difficulty', '').lower() == difficulty.lower()]
    
    # Make sure we have enough questions
    num_questions = min(num_questions, len(available_questions))
    if num_questions == 0:
        return jsonify({'error': 'No questions match your criteria'}), 400
    
    # Select random questions
    selected_questions = random.sample(available_questions, num_questions)
    
    # Initialize session with explicit modification flag
    session['questions'] = selected_questions
    session['current_index'] = 0
    session['score'] = 0
    session['answers'] = []
    session['start_time'] = datetime.now().isoformat()
    session.modified = True
    
    # Debug log to confirm proper initialization
    print(f"INIT: Selected {len(selected_questions)} questions, session has {len(session.get('questions', []))}")
    
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
    
    if current_index >= len(questions):
        return jsonify({'error': 'No more questions'}), 400
    
    question = questions[current_index].copy()  # Make a copy to avoid modifying original
    
    # Shuffle the options and track the new correct answer index
    original_correct = question['correct']
    options_with_indices = [(i, option) for i, option in enumerate(question['options'])]
    random.shuffle(options_with_indices)
    
    # Update the question with shuffled options and new correct index
    question['options'] = [option for _, option in options_with_indices]
    question['correct'] = next(new_index for new_index, (orig_index, _) in enumerate(options_with_indices) if orig_index == original_correct)
    
    # Store the shuffled question back in session for answer checking
    session['questions'][current_index] = question
    session.modified = True
    
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
    
    # Debug log for answer processing
    print(f"ANSWER: index={current_index}/{total_questions}, isLast={is_last}")
    
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
    session.clear()
    session.modified = True
    return jsonify({'success': True})

def generate_unique_id():
    """Generate a unique ID for new questions."""
    return f"generated_{int(time.time())}_{random.randint(1000, 9999)}"

def validate_question_data(data):
    """Validate the structure of generated question data."""
    required_fields = ['question', 'options', 'correctAnswer', 'explanation']
    
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    if not isinstance(data['options'], list) or len(data['options']) != 4:
        return False, "Options must be a list of exactly 4 items"
    
    if not isinstance(data['correctAnswer'], int) or data['correctAnswer'] < 0 or data['correctAnswer'] > 3:
        return False, "correctAnswer must be an integer between 0 and 3"
    
    if not isinstance(data['question'], str) or not data['question'].strip():
        return False, "Question must be a non-empty string"
    
    if not isinstance(data['explanation'], str) or not data['explanation'].strip():
        return False, "Explanation must be a non-empty string"
    
    return True, "Valid"

def call_openai_api(category):
    """Call OpenAI API to generate a trivia question."""
    prompt = f"""Generate a trivia question for the category: {category}

Return ONLY valid JSON in this exact format:
{{
    "question": "Your question here?",
    "options": ["Correct answer", "Wrong answer 1", "Wrong answer 2", "Wrong answer 3"],
    "correctAnswer": 0,
    "explanation": "Why this answer is correct and interesting context",
    "funFact": "An interesting related fact"
}}

Requirements:
- Question should be factual and verifiable
- Difficulty should be medium level (not too easy, not too obscure)
- Options should be plausible but clearly distinct
- Place the correct answer at index 0
- Explanation should be educational and engaging
- Fun fact should be genuinely interesting
- Ensure proper JSON formatting
- Category: {category}"""

    try:
        client = openai.OpenAI(api_key=openai.api_key)
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a trivia question generator. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")

def add_question_to_database(question_data, category):
    """Add a new question to the questions.json file."""
    global QUESTIONS
    
    # Create the new question object
    new_question = {
        "id": generate_unique_id(),
        "category": category.lower(),
        "subcategory": category,
        "difficulty": "medium",
        "question": question_data['question'],
        "options": question_data['options'],
        "correctAnswer": question_data['correctAnswer'],
        "explanation": question_data['explanation'],
        "funFact": question_data.get('funFact', '')
    }
    
    # Add to questions list
    QUESTIONS.append(new_question)
    
    # Save to file
    questions_file = Path('questions.json')
    
    # Create backup first
    backup_file = Path('questions_backup.json')
    if questions_file.exists():
        with open(questions_file, 'r', encoding='utf-8') as f:
            backup_data = f.read()
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(backup_data)
    
    # Write updated questions
    with open(questions_file, 'w', encoding='utf-8') as f:
        json.dump(QUESTIONS, f, indent=2, ensure_ascii=False)
    
    return new_question

@app.route('/api/generate-question', methods=['POST'])
def generate_question():
    """Generate a new trivia question using OpenAI API."""
    if not GENERATION_ENABLED:
        return jsonify({'error': 'Question generation is currently disabled'}), 503
    
    if not openai.api_key:
        return jsonify({'error': 'OpenAI API key not configured'}), 500
    
    data = request.json
    category = data.get('category', '').strip()
    
    if not category:
        return jsonify({'error': 'Category is required'}), 400
    
    if len(category) > 50:
        return jsonify({'error': 'Category name too long (max 50 characters)'}), 400
    
    try:
        # Call OpenAI API
        response_text = call_openai_api(category)
        
        # Parse JSON response
        try:
            question_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            return jsonify({'error': f'Invalid JSON response from AI: {str(e)}'}), 500
        
        # Validate question data
        is_valid, error_msg = validate_question_data(question_data)
        if not is_valid:
            return jsonify({'error': f'Invalid question format: {error_msg}'}), 500
        
        # Add to database
        new_question = add_question_to_database(question_data, category)
        
        return jsonify({
            'success': True,
            'message': f'Successfully generated question for category: {category}',
            'question_id': new_question['id'],
            'total_questions': len(QUESTIONS)
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to generate question: {str(e)}'}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True)