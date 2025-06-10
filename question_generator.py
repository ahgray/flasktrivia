#!/usr/bin/env python3
"""
Question Generator Module
Generates trivia questions using OpenAI's GPT model.
Can be used as a module or run standalone from command line.
"""

import os
import json
import time
import random
from pathlib import Path
from typing import Dict, Tuple, Optional
from openai import OpenAI


class QuestionGenerator:
    """Handles trivia question generation using OpenAI API."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        """
        Initialize the question generator.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: OpenAI model to use (default: gpt-4)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        self.client = None
        
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
    
    def generate_unique_id(self) -> str:
        """Generate a unique ID for new questions."""
        return f"generated_{int(time.time())}_{random.randint(1000, 9999)}"
    
    def validate_question_data(self, data: Dict) -> Tuple[bool, str]:
        """
        Validate the structure of generated question data.
        
        Args:
            data: Question data dictionary
            
        Returns:
            Tuple of (is_valid, error_message)
        """
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
    
    def create_prompt(self, category: str) -> str:
        """Create the prompt for OpenAI API."""
        return f"""Generate a trivia question for the category: {category}

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
    
    def call_openai_api(self, category: str) -> str:
        """
        Call OpenAI API to generate a trivia question.
        
        Args:
            category: The category for the question
            
        Returns:
            Generated question JSON string
            
        Raises:
            Exception: If API call fails
        """
        if not self.client:
            raise Exception("OpenAI client not initialized. Please provide API key.")
        
        prompt = self.create_prompt(category)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
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
    
    def format_question_for_storage(self, question_data: Dict, category: str) -> Dict:
        """
        Format the generated question for storage in questions.json.
        
        Args:
            question_data: Raw question data from API
            category: Question category
            
        Returns:
            Formatted question dictionary
        """
        return {
            "id": self.generate_unique_id(),
            "category": category.lower(),
            "subcategory": category,
            "difficulty": "medium",
            "question": question_data['question'],
            "options": question_data['options'],
            "correctAnswer": question_data['correctAnswer'],
            "explanation": question_data['explanation'],
            "funFact": question_data.get('funFact', '')
        }
    
    def generate_question(self, category: str) -> Dict:
        """
        Generate a new trivia question for the given category.
        
        Args:
            category: The category for the question
            
        Returns:
            Dictionary containing the generated question
            
        Raises:
            Exception: If generation fails
        """
        if not category or not category.strip():
            raise ValueError("Category is required")
        
        if len(category) > 50:
            raise ValueError("Category name too long (max 50 characters)")
        
        # Call OpenAI API
        response_text = self.call_openai_api(category)
        
        # Parse JSON response
        try:
            question_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response from AI: {str(e)}")
        
        # Validate question data
        is_valid, error_msg = self.validate_question_data(question_data)
        if not is_valid:
            raise Exception(f"Invalid question format: {error_msg}")
        
        # Format for storage
        formatted_question = self.format_question_for_storage(question_data, category)
        
        return formatted_question
    
    def save_question(self, question: Dict, questions_file: Path = Path('questions.json')) -> None:
        """
        Save a generated question to the questions.json file.
        
        Args:
            question: Question dictionary to save
            questions_file: Path to questions.json file
        """
        # Load existing questions
        if questions_file.exists():
            with open(questions_file, 'r', encoding='utf-8') as f:
                questions = json.load(f)
        else:
            questions = []
        
        # Create backup
        if questions_file.exists():
            backup_file = questions_file.with_suffix('.json.backup')
            with open(questions_file, 'r', encoding='utf-8') as f:
                backup_data = f.read()
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(backup_data)
        
        # Add new question
        questions.append(question)
        
        # Save updated questions
        with open(questions_file, 'w', encoding='utf-8') as f:
            json.dump(questions, f, indent=2, ensure_ascii=False)


def main():
    """CLI interface for question generation."""
    print("🎯 Trivia Question Generator")
    print("-" * 40)
    
    # Check for API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ Error: OPENAI_API_KEY environment variable not set.")
        print("Please set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-api-key-here'")
        return
    
    # Initialize generator
    generator = QuestionGenerator(api_key=api_key)
    
    while True:
        print("\nEnter a category for the question (or 'quit' to exit):")
        category = input("> ").strip()
        
        if category.lower() in ['quit', 'exit', 'q']:
            print("\n👋 Goodbye!")
            break
        
        if not category:
            print("❌ Please enter a valid category.")
            continue
        
        print(f"\n🤖 Generating {category} question...")
        
        try:
            # Generate question
            question = generator.generate_question(category)
            
            # Display the generated question
            print("\n✅ Generated Question:")
            print(f"Category: {question['category']}")
            print(f"Question: {question['question']}")
            print("\nOptions:")
            for i, option in enumerate(question['options']):
                marker = "✓" if i == question['correctAnswer'] else " "
                print(f"  {marker} {i+1}. {option}")
            print(f"\nExplanation: {question['explanation']}")
            if question.get('funFact'):
                print(f"Fun Fact: {question['funFact']}")
            
            # Ask if user wants to save
            print("\nSave this question to questions.json? (y/n)")
            save_choice = input("> ").strip().lower()
            
            if save_choice == 'y':
                generator.save_question(question)
                print("✅ Question saved successfully!")
            else:
                print("Question not saved.")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            print("Please try again.")


if __name__ == "__main__":
    main()