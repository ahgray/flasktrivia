# 🎯 Modern Trivia Game

A sleek, responsive web-based trivia game built with Flask, featuring real-time feedback, global statistics tracking, and a modern UI.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0.0-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## ✨ Features

- **Reactive Interface**: Immediate feedback on answer selection with smooth animations
- **Category & Difficulty Filtering**: Choose from different categories (STEM, History) and difficulty levels
- **Global Statistics**: Track how many times each question has been answered and global accuracy rates
- **Session Management**: Maintains game state throughout the session
- **Responsive Design**: Works perfectly on desktop and mobile devices
- **Modern UI**: Gradient backgrounds, hover effects, and clean typography
- **Detailed Explanations**: Each answer includes explanations and fun facts

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git (for deployment)

## 🚀 Local Development

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd trivia-game
```

### 2. Create a Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Project Structure

Ensure your project has the following structure:

```
trivia-game/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── render.yaml        # Render deployment config
├── questions.json     # Your trivia questions
├── README.md          # This file
└── templates/
    └── index.html     # Game interface
```

### 5. Add Your Questions

Make sure your `questions.json` file is in the root directory. The format should be:

```json
[
    {
        "id": "unique_id_001",
        "category": "stem",
        "subcategory": "Computer Science",
        "difficulty": "medium",
        "question": "Your question here?",
        "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
        "correctAnswer": 0,
        "explanation": "Explanation of the answer",
        "funFact": "An interesting fact!"
    }
]
```

### 6. Run the Application

```bash
python app.py
```

The game will be available at `http://localhost:5000`

### 7. Play the Game!

1. Choose the number of questions, category, and difficulty
2. Answer questions by clicking on options
3. Get immediate feedback with explanations
4. View your final score and review answers

## 🌐 Deployment to Render.com

### 1. Prepare Your Repository

1. Create a new GitHub repository
2. Push your code:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

### 2. Ensure Required Files

Make sure these files are in your repository:

**requirements.txt:**
```
Flask==3.0.0
Werkzeug==3.0.1
gunicorn==21.2.0
```

**render.yaml:**
```yaml
services:
  - type: web
    name: trivia-game
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app --bind 0.0.0.0:$PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
```

### 3. Deploy to Render

1. Sign up for a free account at [render.com](https://render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub account
4. Select your trivia game repository
5. Render will auto-detect the configuration from `render.yaml`
6. Click **"Create Web Service"**

### 4. Wait for Deployment

- Render will automatically build and deploy your application
- The process takes 2-5 minutes
- You'll get a URL like `https://your-app-name.onrender.com`

### 5. Important Notes for Render

- **Free Tier Limitations**: 
  - Apps spin down after 15 minutes of inactivity
  - First request after spin-down takes 30-50 seconds
  - 750 hours of free usage per month
  
- **Database Persistence**: 
  - SQLite database resets on each deployment
  - For persistent stats, consider upgrading to PostgreSQL

## 🔧 Configuration

### Environment Variables

You can set these in Render's dashboard:

- `SECRET_KEY`: Flask secret key (Render will auto-generate if not set)
- `PORT`: Port number (Render sets this automatically)

### Customization

1. **Styling**: Edit the CSS in `templates/index.html`
2. **Questions**: Modify `questions.json`
3. **Game Logic**: Update `app.py`

## 📊 Database

The app uses SQLite to track question statistics:
- Times each question has been shown
- Number of correct/incorrect answers
- Global accuracy percentages

**Note**: On Render's free tier, the database resets with each deployment. For persistent data, consider:
- Upgrading to a paid Render plan
- Using Render's PostgreSQL database
- Using an external database service

## 🐛 Troubleshooting

### Local Development Issues

1. **Port Already in Use**:
   ```bash
   # Change port in app.py
   app.run(debug=True, port=5001)
   ```

2. **Module Not Found**:
   ```bash
   # Ensure virtual environment is activated
   # Reinstall requirements
   pip install -r requirements.txt
   ```

3. **Questions Not Loading**:
   - Check `questions.json` is in the root directory
   - Verify JSON format is correct
   - Check file encoding is UTF-8

### Render Deployment Issues

1. **Build Fails**:
   - Check `requirements.txt` is committed
   - Verify Python version in `render.yaml`
   - Check build logs in Render dashboard

2. **App Crashes**:
   - Check if `gunicorn` is in requirements
   - Verify `app:app` is correct in start command
   - Review logs in Render dashboard

3. **Slow Initial Load**:
   - Normal for free tier (cold start)
   - Consider upgrading for always-on service

## 📱 Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+
- Mobile browsers (iOS Safari, Chrome Android)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Flask framework for the backend
- SQLite for lightweight database
- Modern CSS for the beautiful UI
- Your amazing trivia questions!

## 💡 Future Enhancements

- [ ] User accounts and personal statistics
- [ ] Leaderboards
- [ ] Timer mode
- [ ] Multiplayer support
- [ ] More question categories
- [ ] Achievement system
- [ ] API for external question sources

---

**Happy Trivia Playing! 🎉**

For issues or questions, please open an issue on GitHub.