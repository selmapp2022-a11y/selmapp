#!/usr/bin/env python3
"""
Script to create default category learning templates for the onboarding system.
Run this after creating the database tables to populate with initial templates.
"""

import sys
import os
import json
import asyncio
from datetime import datetime

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.models.personalization import CategoryLearningTemplate, LearningCategory
from app.schemas.personalization import CategoryLearningTemplateCreate

def create_template_data(category: str, level: str) -> dict:
    """Create template data structure for a specific category and level"""
    
    # Base template structure
    base_template = {
        "learning_objectives": [],
        "milestones": [],
        "content_sequence": [],
        "assessment_criteria": {},
        "recommended_activities": [],
        "skill_focus": {
            "listening": 25,
            "speaking": 25,
            "reading": 25,
            "writing": 25
        }
    }
    
    # Category-specific templates
    if category == "general_english":
        base_template.update({
            "learning_objectives": [
                f"Master {level} level vocabulary and grammar",
                "Develop balanced language skills",
                "Build confidence in everyday communication",
                "Understand cultural contexts"
            ],
            "milestones": [
                {"week": 1, "focus": "Basic vocabulary and phrases", "target": "50 new words"},
                {"week": 2, "focus": "Simple conversations", "target": "5-minute dialogues"},
                {"week": 4, "focus": "Grammar foundations", "target": "Present/past tenses"},
                {"week": 6, "focus": "Reading comprehension", "target": "Short texts"},
                {"week": 8, "focus": "Writing skills", "target": "Simple paragraphs"},
                {"week": 10, "focus": "Listening practice", "target": "Audio materials"},
                {"week": 12, "focus": "Speaking fluency", "target": "Confident conversations"}
            ],
            "recommended_activities": [
                "Daily vocabulary practice",
                "Conversation simulations",
                "Grammar exercises",
                "Reading short stories",
                "Writing diary entries",
                "Listening to podcasts"
            ]
        })
    
    elif category == "business_english":
        base_template.update({
            "learning_objectives": [
                "Master professional vocabulary",
                "Develop formal communication skills",
                "Learn business etiquette",
                "Practice presentation skills"
            ],
            "milestones": [
                {"week": 1, "focus": "Business vocabulary", "target": "100 business terms"},
                {"week": 2, "focus": "Email writing", "target": "Professional emails"},
                {"week": 4, "focus": "Meeting language", "target": "Meeting participation"},
                {"week": 6, "focus": "Presentations", "target": "5-minute presentations"},
                {"week": 8, "focus": "Negotiations", "target": "Basic negotiation skills"},
                {"week": 10, "focus": "Reports", "target": "Business report writing"},
                {"week": 12, "focus": "Networking", "target": "Professional conversations"}
            ],
            "skill_focus": {
                "listening": 20,
                "speaking": 30,
                "reading": 25,
                "writing": 25
            },
            "recommended_activities": [
                "Business vocabulary drills",
                "Email writing practice",
                "Presentation exercises",
                "Case study discussions",
                "Professional role-plays",
                "Industry reading materials"
            ]
        })
    
    elif category == "conversation_practice":
        base_template.update({
            "learning_objectives": [
                "Improve speaking fluency",
                "Build conversation confidence",
                "Master natural expressions",
                "Develop listening skills"
            ],
            "milestones": [
                {"week": 1, "focus": "Basic conversations", "target": "Daily topics"},
                {"week": 2, "focus": "Question formation", "target": "Natural questions"},
                {"week": 3, "focus": "Expressing opinions", "target": "Personal views"},
                {"week": 4, "focus": "Storytelling", "target": "Personal experiences"},
                {"week": 6, "focus": "Debates", "target": "Structured discussions"},
                {"week": 8, "focus": "Cultural topics", "target": "Cross-cultural communication"},
                {"week": 10, "focus": "Advanced discussions", "target": "Complex topics"}
            ],
            "skill_focus": {
                "listening": 35,
                "speaking": 45,
                "reading": 10,
                "writing": 10
            },
            "recommended_activities": [
                "Daily conversation practice",
                "Pronunciation drills",
                "Listening to native speakers",
                "Role-playing scenarios",
                "Discussion groups",
                "Speaking challenges"
            ]
        })
    
    elif category == "exam_preparation":
        base_template.update({
            "learning_objectives": [
                "Master exam format and strategies",
                "Develop time management skills",
                "Practice all four skills systematically",
                "Build exam confidence"
            ],
            "milestones": [
                {"week": 1, "focus": "Exam format", "target": "Understanding test structure"},
                {"week": 2, "focus": "Reading strategies", "target": "Speed and comprehension"},
                {"week": 4, "focus": "Listening techniques", "target": "Note-taking skills"},
                {"week": 6, "focus": "Writing tasks", "target": "Essay and report writing"},
                {"week": 8, "focus": "Speaking practice", "target": "Interview simulation"},
                {"week": 10, "focus": "Mock tests", "target": "Full practice exams"},
                {"week": 12, "focus": "Final preparation", "target": "Exam readiness"}
            ],
            "skill_focus": {
                "listening": 25,
                "speaking": 25,
                "reading": 25,
                "writing": 25
            },
            "recommended_activities": [
                "Practice tests",
                "Time management exercises",
                "Strategy workshops",
                "Skill-specific drills",
                "Mock examinations",
                "Feedback sessions"
            ]
        })
    
    elif category == "vocabulary_building":
        base_template.update({
            "learning_objectives": [
                "Expand active vocabulary",
                "Learn word families and collocations",
                "Master word usage in context",
                "Develop vocabulary learning strategies"
            ],
            "milestones": [
                {"week": 1, "focus": "Core vocabulary", "target": "100 essential words"},
                {"week": 2, "focus": "Word families", "target": "Related word forms"},
                {"week": 4, "focus": "Collocations", "target": "Natural word combinations"},
                {"week": 6, "focus": "Academic vocabulary", "target": "Formal word usage"},
                {"week": 8, "focus": "Idioms and phrases", "target": "Common expressions"},
                {"week": 10, "focus": "Specialized vocabulary", "target": "Topic-specific words"},
                {"week": 12, "focus": "Vocabulary mastery", "target": "Active usage"}
            ],
            "skill_focus": {
                "listening": 20,
                "speaking": 20,
                "reading": 35,
                "writing": 25
            },
            "recommended_activities": [
                "Spaced repetition practice",
                "Word mapping exercises",
                "Context-based learning",
                "Vocabulary games",
                "Reading for vocabulary",
                "Usage practice"
            ]
        })
    
    # Add level-specific adjustments
    if level in ["A1", "A2"]:
        # Beginner adjustments
        base_template["estimated_weeks"] = 16
        base_template["daily_minutes"] = 20
    elif level in ["B1", "B2"]:
        # Intermediate adjustments
        base_template["estimated_weeks"] = 12
        base_template["daily_minutes"] = 30
    else:  # C1, C2
        # Advanced adjustments
        base_template["estimated_weeks"] = 10
        base_template["daily_minutes"] = 45
    
    return base_template

async def create_category_templates():
    """Create default category learning templates"""
    
    async with AsyncSessionLocal() as db:
        try:
            # Define categories and levels
            categories = [
                ("general_english", "General English"),
                ("business_english", "Business English"),
                ("conversation_practice", "Conversation Practice"),
                ("exam_preparation", "Exam Preparation"),
                ("vocabulary_building", "Vocabulary Building"),
                ("travel_english", "Travel English"),
                ("academic_english", "Academic English"),
                ("grammar_focus", "Grammar Focus"),
                ("writing_skills", "Writing Skills"),
                ("reading_comprehension", "Reading Comprehension"),
                ("listening_skills", "Listening Skills"),
                ("pronunciation_improvement", "Pronunciation Improvement")
            ]
            
            levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
            
            templates_created = 0
            
            for category_key, category_name in categories:
                for level in levels:
                    # Skip duplicate check for now - will handle duplicates with database constraints
                    print(f"Creating template for {category_name} - {level}...")
                    
                    # Create template data
                    template_data = create_template_data(category_key, level)
                    
                    # Determine duration and milestones based on level
                    if level in ["A1", "A2"]:
                        duration_weeks = 16
                        total_milestones = len(template_data.get("milestones", [])) or 8
                    elif level in ["B1", "B2"]:
                        duration_weeks = 12
                        total_milestones = len(template_data.get("milestones", [])) or 6
                    else:  # C1, C2
                        duration_weeks = 10
                        total_milestones = len(template_data.get("milestones", [])) or 5
                    
                    # Create template
                    template = CategoryLearningTemplate(
                        category=category_key,
                        name=f"{category_name} - {level} Level",
                        description=f"Comprehensive {category_name.lower()} learning path for {level} level students",
                        target_levels=[level],
                        template_data=template_data,
                        estimated_duration_weeks=duration_weeks,
                        total_milestones=total_milestones,
                        listening_percentage=template_data["skill_focus"]["listening"],
                        speaking_percentage=template_data["skill_focus"]["speaking"],
                        reading_percentage=template_data["skill_focus"]["reading"],
                        writing_percentage=template_data["skill_focus"]["writing"],
                        required_vocabulary_topics=["basic", "everyday", level.lower()],
                        required_grammar_points=[f"{level}_grammar"],
                        recommended_content_types=["interactive", "audio", "video", "text"],
                        difficulty_level="easy" if level in ["A1", "A2"] else "moderate" if level in ["B1", "B2"] else "challenging",
                        is_active=True,
                        created_by="system"
                    )
                    
                    db.add(template)
                    templates_created += 1
                    print(f"Created template: {category_name} - {level}")
            
            await db.commit()
            print(f"\nSuccessfully created {templates_created} category learning templates!")
            
        except Exception as e:
            print(f"Error creating templates: {e}")
            await db.rollback()
            raise

if __name__ == "__main__":
    print("Creating default category learning templates...")
    asyncio.run(create_category_templates())
    print("Done!") 