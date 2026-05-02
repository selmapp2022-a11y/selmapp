from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum, JSON, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base

class WritingType(str, enum.Enum):
    ESSAY = "essay"
    LETTER = "letter"
    EMAIL = "email"
    STORY = "story"
    REPORT = "report"
    REVIEW = "review"
    DESCRIPTION = "description"
    DIALOGUE = "dialogue"
    SUMMARY = "summary"

class WritingSkillLevel(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

# Import DifficultyLevel from content models to reuse existing enum
from app.models.content import DifficultyLevel

class WritingPrompt(Base):
    """Writing exercise prompts and instructions"""
    __tablename__ = "writing_prompts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    prompt_text = Column(Text, nullable=False)
    instructions = Column(Text)
    writing_type = Column(Enum(WritingType), nullable=False)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    skill_level = Column(Enum(WritingSkillLevel), nullable=False)
    
    # Requirements
    min_words = Column(Integer, default=50)
    max_words = Column(Integer, default=500)
    time_limit_minutes = Column(Integer)
    
    # Content guidelines
    required_vocabulary = Column(JSON)  # List of words that should be used
    grammar_focus = Column(JSON)  # Grammar points to focus on
    topic_keywords = Column(JSON)  # Topic-related keywords
    
    # Scoring criteria
    scoring_rubric = Column(JSON)  # Detailed scoring criteria
    max_points = Column(Integer, default=100)
    
    # Metadata
    topic = Column(String(100))
    tags = Column(JSON)  # List of tags for categorization
    
    # Settings
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    writing_submissions = relationship("WritingSubmission", back_populates="writing_prompt")

class WritingSubmission(Base):
    """User's writing submissions"""
    __tablename__ = "writing_submissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    writing_prompt_id = Column(Integer, ForeignKey("writing_prompts.id"), nullable=False)
    
    # Content
    content = Column(Text, nullable=False)
    word_count = Column(Integer, nullable=False)
    
    # Timing
    time_spent_minutes = Column(Integer)
    started_at = Column(DateTime(timezone=True))
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Auto-correction results
    original_content = Column(Text)  # Before corrections
    corrected_content = Column(Text)  # After auto-corrections
    spelling_errors = Column(JSON)  # List of spelling errors found
    grammar_errors = Column(JSON)  # List of grammar errors found
    
    # Assessment results
    overall_score = Column(Float, default=0.0)
    grammar_score = Column(Float, default=0.0)
    vocabulary_score = Column(Float, default=0.0)
    coherence_score = Column(Float, default=0.0)
    task_achievement_score = Column(Float, default=0.0)
    
    # AI feedback
    ai_feedback = Column(Text)
    suggestions = Column(JSON)  # List of improvement suggestions
    strengths = Column(JSON)    # List of identified strengths
    weaknesses = Column(JSON)   # List of areas for improvement
    
    # Status
    is_draft = Column(Boolean, default=False)
    is_evaluated = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User")
    writing_prompt = relationship("WritingPrompt", back_populates="writing_submissions")
    writing_feedback = relationship("WritingFeedback", back_populates="writing_submission")

class WritingFeedback(Base):
    """Detailed feedback for writing submissions"""
    __tablename__ = "writing_feedback"

    id = Column(Integer, primary_key=True, index=True)
    writing_submission_id = Column(Integer, ForeignKey("writing_submissions.id"), nullable=False)
    
    # Detailed scores breakdown
    content_organization = Column(Float, default=0.0)
    language_accuracy = Column(Float, default=0.0)
    vocabulary_range = Column(Float, default=0.0)
    sentence_structure = Column(Float, default=0.0)
    punctuation_mechanics = Column(Float, default=0.0)
    
    # Specific feedback
    positive_aspects = Column(JSON)  # What the user did well
    areas_for_improvement = Column(JSON)  # What needs work
    specific_errors = Column(JSON)  # Detailed error analysis
    vocabulary_suggestions = Column(JSON)  # Better word choices
    
    # Recommendations
    next_steps = Column(JSON)  # What to practice next
    recommended_exercises = Column(JSON)  # Suggested follow-up exercises
    
    # Feedback metadata
    feedback_type = Column(String(50), default="automated")  # automated, human, hybrid
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    writing_submission = relationship("WritingSubmission", back_populates="writing_feedback")

class WritingTemplate(Base):
    """Templates and structures for different writing types"""
    __tablename__ = "writing_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    writing_type = Column(Enum(WritingType), nullable=False)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    
    # Template structure
    structure = Column(JSON)  # Outline/structure of the writing
    sample_phrases = Column(JSON)  # Useful phrases for this type
    transition_words = Column(JSON)  # Connecting words and phrases
    
    # Content
    description = Column(Text)
    example_text = Column(Text)  # Sample writing following this template
    
    # Settings
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class WritingProgress(Base):
    """User's writing progress tracking"""
    __tablename__ = "writing_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Overall writing metrics
    total_submissions = Column(Integer, default=0)
    total_words_written = Column(Integer, default=0)
    total_writing_time_minutes = Column(Integer, default=0)
    
    # Performance metrics
    average_score = Column(Float, default=0.0)
    best_score = Column(Float, default=0.0)
    average_grammar_score = Column(Float, default=0.0)
    average_vocabulary_score = Column(Float, default=0.0)
    
    # Improvement tracking
    grammar_improvement_rate = Column(Float, default=0.0)
    vocabulary_improvement_rate = Column(Float, default=0.0)
    writing_speed_wpm = Column(Float, default=0.0)  # Words per minute
    
    # Level progress
    current_level = Column(Enum(DifficultyLevel), default=DifficultyLevel.A1)
    submissions_by_level = Column(JSON, default={})  # {"A1": 5, "A2": 3, ...}
    submissions_by_type = Column(JSON, default={})  # {"essay": 3, "letter": 2, ...}
    
    # Error analysis
    common_grammar_errors = Column(JSON, default=[])
    common_spelling_errors = Column(JSON, default=[])
    error_reduction_rate = Column(Float, default=0.0)
    
    # Streaks and consistency
    current_writing_streak = Column(Integer, default=0)
    longest_writing_streak = Column(Integer, default=0)
    last_writing_date = Column(DateTime(timezone=True))
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")

class GrammarRule(Base):
    """Grammar rules for checking and feedback"""
    __tablename__ = "grammar_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)  # tense, article, preposition, etc.
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    
    # Rule definition
    rule_description = Column(Text, nullable=False)
    pattern = Column(String(500))  # Regex pattern for detection
    correct_examples = Column(JSON)  # List of correct examples
    incorrect_examples = Column(JSON)  # List of incorrect examples
    
    # Feedback
    explanation = Column(Text)
    correction_suggestion = Column(Text)
    
    # Settings
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)  # Higher priority rules checked first
    
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 