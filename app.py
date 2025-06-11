import os
import json
import sqlite3
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime
import random
from pathlib import Path
from question_generator import QuestionGenerator

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

# Question generation configuration
GENERATION_ENABLED = os.getenv('GENERATION_ENABLED', 'true').lower() == 'true'
question_generator = None
if GENERATION_ENABLED and os.getenv('OPENAI_API_KEY'):
    question_generator = QuestionGenerator(model=os.getenv('LLM_MODEL', 'gpt-4'))

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
        # Existing question_stats table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS question_stats (
                question_id TEXT PRIMARY KEY,
                times_shown INTEGER DEFAULT 0,
                times_correct INTEGER DEFAULT 0,
                times_incorrect INTEGER DEFAULT 0,
                UNIQUE(question_id)
            )
        ''')
        
        # New leaderboard table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS leaderboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                score INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                percentage REAL NOT NULL,
                category TEXT DEFAULT 'all',
                difficulty TEXT DEFAULT 'all',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT
            )
        ''')
        
        # New achievements table for future expansion
        conn.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                achievement_type TEXT NOT NULL,
                achievement_name TEXT NOT NULL,
                description TEXT,
                earned_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(player_name, achievement_type, achievement_name)
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

def check_achievements(player_name, score, total_questions, percentage):
    """Check and award achievements for the player."""
    achievements = []
    
    with get_db() as conn:
        # Perfect Score Achievement
        if percentage == 100.0:
            try:
                conn.execute('''
                    INSERT INTO achievements (player_name, achievement_type, achievement_name, description)
                    VALUES (?, ?, ?, ?)
                ''', (player_name, 'perfect_score', 'Perfect Game', 'Scored 100% on a trivia game'))
                achievements.append({'name': 'Perfect Game', 'description': 'Scored 100% on a trivia game'})
            except sqlite3.IntegrityError:
                pass  # Achievement already exists
        
        # High Score Achievement (90%+)
        if percentage >= 90.0:
            try:
                conn.execute('''
                    INSERT INTO achievements (player_name, achievement_type, achievement_name, description)
                    VALUES (?, ?, ?, ?)
                ''', (player_name, 'high_score', 'Trivia Master', 'Scored 90% or higher on a trivia game'))
                achievements.append({'name': 'Trivia Master', 'description': 'Scored 90% or higher on a trivia game'})
            except sqlite3.IntegrityError:
                pass
        
        # Marathon Achievement (20+ questions)
        if total_questions >= 20:
            try:
                conn.execute('''
                    INSERT INTO achievements (player_name, achievement_type, achievement_name, description)
                    VALUES (?, ?, ?, ?)
                ''', (player_name, 'marathon', 'Marathon Player', 'Completed a game with 20 or more questions'))
                achievements.append({'name': 'Marathon Player', 'description': 'Completed a game with 20 or more questions'})
            except sqlite3.IntegrityError:
                pass
        
        # First Game Achievement
        existing_games = conn.execute(
            'SELECT COUNT(*) as count FROM leaderboard WHERE player_name = ?',
            (player_name,)
        ).fetchone()
        
        if existing_games['count'] == 0:  # This will be their first game after insertion
            try:
                conn.execute('''
                    INSERT INTO achievements (player_name, achievement_type, achievement_name, description)
                    VALUES (?, ?, ?, ?)
                ''', (player_name, 'first_game', 'Welcome Player', 'Completed your first trivia game'))
                achievements.append({'name': 'Welcome Player', 'description': 'Completed your first trivia game'})
            except sqlite3.IntegrityError:
                pass
        
        conn.commit()
    
    return achievements

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
    session['question_generated'] = False  # Reset question generation flag
    session['game_category'] = category
    session['game_difficulty'] = difficulty
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
    percentage = round(session['score'] / total_questions * 100, 1)
    
    return jsonify({
        'score': session['score'],
        'totalQuestions': total_questions,
        'percentage': percentage,
        'answers': session['answers'],
        'questions': session['questions'],
        'category': session.get('game_category', 'all'),
        'difficulty': session.get('game_difficulty', 'all')
    })

@app.route('/api/submit-score', methods=['POST'])
def submit_score():
    """Submit score to leaderboard."""
    if 'questions' not in session or 'answers' not in session:
        return jsonify({'error': 'No completed game'}), 400
    
    data = request.json
    player_name = data.get('playerName', '').strip()
    
    if not player_name:
        return jsonify({'error': 'Player name is required'}), 400
    
    if len(player_name) > 50:
        return jsonify({'error': 'Player name too long (max 50 characters)'}), 400
    
    # Calculate score details
    score = session['score']
    total_questions = len(session['questions'])
    percentage = round(score / total_questions * 100, 1)
    category = session.get('game_category', 'all')
    difficulty = session.get('game_difficulty', 'all')
    
    try:
        with get_db() as conn:
            # Insert score into leaderboard
            cursor = conn.execute('''
                INSERT INTO leaderboard (player_name, score, total_questions, percentage, category, difficulty, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (player_name, score, total_questions, percentage, category, difficulty, session.get('session_id', '')))
            
            leaderboard_id = cursor.lastrowid
            conn.commit()
        
        # Check for achievements
        achievements = check_achievements(player_name, score, total_questions, percentage)
        
        return jsonify({
            'success': True,
            'leaderboard_id': leaderboard_id,
            'achievements': achievements,
            'message': f'Score submitted successfully! You scored {score}/{total_questions} ({percentage}%)'
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to submit score: {str(e)}'}), 500

@app.route('/api/leaderboard')
def get_leaderboard():
    """Get leaderboard data with filtering options."""
    category = request.args.get('category', 'all')
    difficulty = request.args.get('difficulty', 'all')
    limit = min(int(request.args.get('limit', 10)), 100)  # Max 100 entries
    
    try:
        with get_db() as conn:
            # Build query with filters
            query = '''
                SELECT player_name, score, total_questions, percentage, category, difficulty, timestamp
                FROM leaderboard
                WHERE 1=1
            '''
            params = []
            
            if category != 'all':
                query += ' AND category = ?'
                params.append(category)
            
            if difficulty != 'all':
                query += ' AND difficulty = ?'
                params.append(difficulty)
            
            # Order by percentage desc, then by score desc, then by total questions desc
            query += ' ORDER BY percentage DESC, score DESC, total_questions DESC, timestamp ASC LIMIT ?'
            params.append(limit)
            
            results = conn.execute(query, params).fetchall()
            
            leaderboard = []
            for i, row in enumerate(results, 1):
                leaderboard.append({
                    'rank': i,
                    'playerName': row['player_name'],
                    'score': row['score'],
                    'totalQuestions': row['total_questions'],
                    'percentage': row['percentage'],
                    'category': row['category'],
                    'difficulty': row['difficulty'],
                    'timestamp': row['timestamp']
                })
            
            return jsonify({
                'leaderboard': leaderboard,
                'filters': {
                    'category': category,
                    'difficulty': difficulty,
                    'limit': limit
                }
            })
            
    except Exception as e:
        return jsonify({'error': f'Failed to load leaderboard: {str(e)}'}), 500

@app.route('/api/player-stats/<player_name>')
def get_player_stats(player_name):
    """Get detailed statistics for a specific player."""
    try:
        with get_db() as conn:
            # Get game history
            games = conn.execute('''
                SELECT score, total_questions, percentage, category, difficulty, timestamp
                FROM leaderboard
                WHERE player_name = ?
                ORDER BY timestamp DESC
                LIMIT 20
            ''', (player_name,)).fetchall()
            
            # Get achievements
            achievements = conn.execute('''
                SELECT achievement_name, description, earned_date
                FROM achievements
                WHERE player_name = ?
                ORDER BY earned_date DESC
            ''', (player_name,)).fetchall()
            
            # Calculate summary stats
            if games:
                total_games = len(games)
                total_questions_answered = sum(game['total_questions'] for game in games)
                total_correct = sum(game['score'] for game in games)
                avg_percentage = sum(game['percentage'] for game in games) / total_games
                best_score = max(games, key=lambda x: x['percentage'])
                
                stats = {
                    'totalGames': total_games,
                    'totalQuestionsAnswered': total_questions_answered,
                    'totalCorrectAnswers': total_correct,
                    'averagePercentage': round(avg_percentage, 1),
                    'bestScore': {
                        'score': best_score['score'],
                        'totalQuestions': best_score['total_questions'],
                        'percentage': best_score['percentage'],
                        'category': best_score['category'],
                        'difficulty': best_score['difficulty']
                    }
                }
            else:
                stats = {
                    'totalGames': 0,
                    'totalQuestionsAnswered': 0,
                    'totalCorrectAnswers': 0,
                    'averagePercentage': 0,
                    'bestScore': None
                }
            
            return jsonify({
                'playerName': player_name,
                'stats': stats,
                'recentGames': [dict(game) for game in games],
                'achievements': [dict(achievement) for achievement in achievements]
            })
            
    except Exception as e:
        return jsonify({'error': f'Failed to load player stats: {str(e)}'}), 500

@app.route('/api/reset', methods=['POST'])
def reset_game():
    """Reset the game session."""
    session.clear()
    session.modified = True
    return jsonify({'success': True})

@app.route('/api/categories')
def get_categories():
    """Get available categories and difficulties."""
    return jsonify({
        'categories': list(set(q.get('category', 'general') for q in QUESTIONS)),
        'difficulties': list(set(q.get('difficulty', 'medium') for q in QUESTIONS))
    })

@app.route('/api/generate-question', methods=['POST'])
def generate_question():
    """Generate a new trivia question using OpenAI API."""
    if not GENERATION_ENABLED:
        return jsonify({'error': 'Question generation is currently disabled'}), 503
    
    if not question_generator:
        return jsonify({'error': 'Question generator not initialized. Please check API key configuration.'}), 500
    
    data = request.json
    category = data.get('category', '').strip()
    
    if not category:
        return jsonify({'error': 'Category is required'}), 400
    
    try:
        # Check if user already generated a question in this session
        if session.get('question_generated', False):
            return jsonify({'error': 'You have already generated a question for this game. Please play again to generate another!'}), 429
        
        # Generate question using the module
        new_question = question_generator.generate_question(category)
        
        # Save to our questions file
        question_generator.save_question(new_question)
        
        # Mark that user has generated a question this session
        session['question_generated'] = True
        session.modified = True
        
        # Reload questions to include the new one
        global QUESTIONS
        QUESTIONS = load_questions()
        
        return jsonify({
            'success': True,
            'message': f'Successfully generated question for category: {category}',
            'question_id': new_question['id'],
            'total_questions': len(QUESTIONS),
            'generated_question': {
                'question': new_question['question'],
                'options': new_question['options'],
                'correctAnswer': new_question['correctAnswer'],
                'explanation': new_question['explanation'],
                'funFact': new_question.get('funFact', ''),
                'category': new_question['category'],
                'subcategory': new_question['subcategory']
            }
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to generate question: {str(e)}'}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True)