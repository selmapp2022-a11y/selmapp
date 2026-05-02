"""
Content Service for SelmApp
Handles content retrieval, filtering, and management
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app.models.content import Content, Vocabulary, Grammar, ContentType, DifficultyLevel
from app.models.progress import UserProgress
import random

class ContentService:
    def __init__(self, db: Session):
        self.db = db

    def get_content_by_level(
        self, 
        level: DifficultyLevel, 
        content_type: Optional[ContentType] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Content]:
        """Get content filtered by CEFR level and optionally by content type."""
        query = self.db.query(Content).filter(
            and_(
                Content.difficulty_level == level,
                Content.is_active == True
            )
        )
        
        if content_type:
            query = query.filter(Content.content_type == content_type)
        
        return query.order_by(Content.order_index, Content.created_at).offset(offset).limit(limit).all()

    def get_sentences_for_level(self, level: DifficultyLevel, limit: int = 10) -> List[Content]:
        """Get sentences specifically for a CEFR level."""
        return self.db.query(Content).filter(
            and_(
                Content.difficulty_level == level,
                Content.content_type == ContentType.READING,
                Content.is_active == True,
                Content.content_data.op('->>')('type') == 'sentence'
            )
        ).order_by(func.random()).limit(limit).all()

    def get_random_sentence(self, level: DifficultyLevel) -> Optional[Content]:
        """Get a random sentence for a specific CEFR level."""
        sentences = self.get_sentences_for_level(level, limit=1)
        return sentences[0] if sentences else None

    def get_vocabulary_for_level(self, level: DifficultyLevel, limit: int = 20) -> List[Vocabulary]:
        """Get vocabulary words for a specific CEFR level."""
        return self.db.query(Vocabulary).filter(
            and_(
                Vocabulary.difficulty_level == level,
                Vocabulary.is_active == True
            )
        ).order_by(Vocabulary.frequency_rank.nullslast(), Vocabulary.word).limit(limit).all()

    def get_grammar_for_level(self, level: DifficultyLevel) -> List[Grammar]:
        """Get grammar rules for a specific CEFR level."""
        return self.db.query(Grammar).filter(
            and_(
                Grammar.difficulty_level == level,
                Grammar.is_active == True
            )
        ).order_by(Grammar.order_index, Grammar.title).all()

    def get_personalized_content(
        self, 
        user_id: int, 
        current_level: DifficultyLevel,
        content_type: Optional[ContentType] = None,
        limit: int = 10
    ) -> List[Content]:
        """Get personalized content based on user's progress and level."""
        
        # Get user's completed content IDs
        completed_content_ids = self.db.query(UserProgress.content_id).filter(
            and_(
                UserProgress.user_id == user_id,
                UserProgress.is_completed == True
            )
        ).subquery()
        
        # Get content that user hasn't completed yet
        query = self.db.query(Content).filter(
            and_(
                Content.difficulty_level == current_level,
                Content.is_active == True,
                ~Content.id.in_(completed_content_ids)
            )
        )
        
        if content_type:
            query = query.filter(Content.content_type == content_type)
        
        return query.order_by(Content.order_index, func.random()).limit(limit).all()

    def get_daily_content(self, level: DifficultyLevel) -> Dict[str, Any]:
        """Get daily content mix for a user's level."""
        daily_content = {
            'sentences': self.get_sentences_for_level(level, limit=5),
            'vocabulary': self.get_vocabulary_for_level(level, limit=10),
            'grammar': self.get_grammar_for_level(level)[:2] if self.get_grammar_for_level(level) else []
        }
        
        return daily_content

    def search_content(
        self, 
        query: str, 
        level: Optional[DifficultyLevel] = None,
        content_type: Optional[ContentType] = None,
        limit: int = 20
    ) -> List[Content]:
        """Search content by text query."""
        search_filter = or_(
            Content.title.ilike(f'%{query}%'),
            Content.description.ilike(f'%{query}%'),
            Content.content_data.op('->>')('sentence').ilike(f'%{query}%')
        )
        
        filters = [Content.is_active == True, search_filter]
        
        if level:
            filters.append(Content.difficulty_level == level)
        
        if content_type:
            filters.append(Content.content_type == content_type)
        
        return self.db.query(Content).filter(and_(*filters)).limit(limit).all()

    def get_content_statistics(self) -> Dict[str, Any]:
        """Get content statistics for admin dashboard."""
        stats = {}
        
        # Content count by level
        for level in DifficultyLevel:
            stats[f'{level.value}_count'] = self.db.query(Content).filter(
                and_(
                    Content.difficulty_level == level,
                    Content.is_active == True
                )
            ).count()
        
        # Content count by type
        for content_type in ContentType:
            stats[f'{content_type.value}_count'] = self.db.query(Content).filter(
                and_(
                    Content.content_type == content_type,
                    Content.is_active == True
                )
            ).count()
        
        # Total counts
        stats['total_content'] = self.db.query(Content).filter(Content.is_active == True).count()
        stats['total_vocabulary'] = self.db.query(Vocabulary).filter(Vocabulary.is_active == True).count()
        stats['total_grammar'] = self.db.query(Grammar).filter(Grammar.is_active == True).count()
        
        return stats

    def get_content_by_tags(self, tags: List[str], limit: int = 20) -> List[Content]:
        """Get content filtered by tags."""
        return self.db.query(Content).filter(
            and_(
                Content.is_active == True,
                Content.tags.op('@>')([tags])  # PostgreSQL array contains operator
            )
        ).limit(limit).all()

    def get_next_level_preview(self, current_level: DifficultyLevel, limit: int = 5) -> List[Content]:
        """Get preview content from the next CEFR level."""
        level_order = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        current_index = level_order.index(current_level.value)
        
        if current_index < len(level_order) - 1:
            next_level = DifficultyLevel(level_order[current_index + 1])
            return self.get_content_by_level(next_level, limit=limit)
        
        return []

    def get_review_content(self, user_id: int, limit: int = 10) -> List[Content]:
        """Get content for review based on user's past performance."""
        # Get content that user completed but might need review
        # (completed more than a week ago or had low scores)
        
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        review_content_ids = self.db.query(UserProgress.content_id).filter(
            and_(
                UserProgress.user_id == user_id,
                UserProgress.is_completed == True,
                or_(
                    UserProgress.completed_at < week_ago,
                    UserProgress.score < 70  # Low score threshold
                )
            )
        ).subquery()
        
        return self.db.query(Content).filter(
            and_(
                Content.id.in_(review_content_ids),
                Content.is_active == True
            )
        ).order_by(func.random()).limit(limit).all()

    def create_content(self, content_data: Dict[str, Any]) -> Content:
        """Create new content entry."""
        content = Content(**content_data)
        self.db.add(content)
        self.db.commit()
        self.db.refresh(content)
        return content

    def update_content(self, content_id: int, update_data: Dict[str, Any]) -> Optional[Content]:
        """Update existing content."""
        content = self.db.query(Content).filter(Content.id == content_id).first()
        if content:
            for key, value in update_data.items():
                setattr(content, key, value)
            self.db.commit()
            self.db.refresh(content)
        return content

    def delete_content(self, content_id: int) -> bool:
        """Soft delete content by setting is_active to False."""
        content = self.db.query(Content).filter(Content.id == content_id).first()
        if content:
            content.is_active = False
            self.db.commit()
            return True
        return False

    def get_learning_path(self, user_level: DifficultyLevel) -> Dict[str, Any]:
        """Get structured learning path for a user's level."""
        
        # Get content organized by type and difficulty
        path = {
            'current_level': user_level.value,
            'vocabulary': self.get_vocabulary_for_level(user_level, limit=50),
            'grammar': self.get_grammar_for_level(user_level),
            'reading': self.get_content_by_level(user_level, ContentType.READING, limit=30),
            'listening': self.get_content_by_level(user_level, ContentType.LISTENING, limit=20),
            'next_level_preview': self.get_next_level_preview(user_level)
        }
        
        return path 