#!/usr/bin/env python3
"""
Create basic category learning templates for the onboarding system.
"""
import asyncio
import sys
import os

# Add the parent directory to the path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import AsyncSessionLocal
from app.models.personalization import CategoryLearningTemplate

async def create_basic_templates():
    """Create basic category learning templates"""
    
    async with AsyncSessionLocal() as db:
        try:
            # Define basic categories and levels
            categories = [
                ("general_english", "General English"),
                ("business_english", "Business English"),
                ("conversation_practice", "Conversation Practice"),
                ("exam_preparation", "Exam Preparation"),
                ("vocabulary_building", "Vocabulary Building"),
            ]
            
            levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
            
            templates_created = 0
            
            for category_key, category_name in categories:
                for level in levels:
                    print(f"Creating template for {category_name} - {level}...")
                    
                    # Create basic template data
                    template_data = {
                        "learning_objectives": [
                            f"Master {level} level {category_name.lower()}",
                            "Build confidence in communication",
                            "Develop practical skills"
                        ],
                        "skill_focus": {
                            "listening": 25,
                            "speaking": 25,
                            "reading": 25,
                            "writing": 25
                        },
                        "milestones": [
                            {"week": 2, "focus": "Foundation", "target": "Basic skills"},
                            {"week": 4, "focus": "Development", "target": "Intermediate skills"},
                            {"week": 6, "focus": "Practice", "target": "Applied skills"},
                            {"week": 8, "focus": "Mastery", "target": "Advanced skills"}
                        ],
                        "recommended_activities": [
                            "Interactive exercises",
                            "Practice sessions",
                            "Progress assessments"
                        ]
                    }
                    
                    # Determine duration based on level
                    if level in ["A1", "A2"]:
                        duration_weeks = 12
                        difficulty = "easy"
                    elif level in ["B1", "B2"]:
                        duration_weeks = 10
                        difficulty = "moderate"
                    else:  # C1, C2
                        duration_weeks = 8
                        difficulty = "challenging"
                    
                    # Create template
                    template = CategoryLearningTemplate(
                        category=category_key,
                        name=f"{category_name} - {level} Level",
                        description=f"Comprehensive {category_name.lower()} learning path for {level} level students",
                        target_levels=[level],
                        template_data=template_data,
                        estimated_duration_weeks=duration_weeks,
                        total_milestones=4,
                        listening_percentage=25,
                        speaking_percentage=25,
                        reading_percentage=25,
                        writing_percentage=25,
                        required_vocabulary_topics=["basic", "everyday", level.lower()],
                        required_grammar_points=[f"{level}_grammar"],
                        recommended_content_types=["interactive", "audio", "video", "text"],
                        difficulty_level=difficulty,
                        is_active=True,
                        created_by="system"
                    )
                    
                    db.add(template)
                    templates_created += 1
                    print(f"✓ Created template: {category_name} - {level}")
            
            await db.commit()
            print(f"\n🎉 Successfully created {templates_created} category learning templates!")
            
        except Exception as e:
            print(f"❌ Error creating templates: {e}")
            await db.rollback()
            raise

if __name__ == "__main__":
    print("Creating basic category learning templates...")
    asyncio.run(create_basic_templates())
    print("Done!") 