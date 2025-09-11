"""
Advanced Content Intelligence System for Context Cleaner

This module provides sophisticated content analysis capabilities including semantic
analysis, conversation flow analysis, and knowledge extraction from JSONL data.

Phase 4 - PR24: Deep Content Intelligence System
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import logging
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from textblob import TextBlob
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.chunk import ne_chunk
from nltk.tag import pos_tag

logger = logging.getLogger(__name__)

# Download required NLTK data (only if not already present)
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

try:
    nltk.data.find('taggers/averaged_perceptron_tagger')
except LookupError:
    nltk.download('averaged_perceptron_tagger', quiet=True)

try:
    nltk.data.find('chunkers/maxent_ne_chunker')
except LookupError:
    nltk.download('maxent_ne_chunker', quiet=True)

try:
    nltk.data.find('corpora/words')
except LookupError:
    nltk.download('words', quiet=True)


@dataclass
class SemanticInsight:
    """Container for semantic analysis results."""
    insight_id: str
    content_type: str
    topics: List[str]
    key_concepts: List[str]
    sentiment_score: float
    sentiment_label: str
    complexity_score: float
    quality_score: float
    named_entities: List[Dict[str, str]]
    key_phrases: List[str]
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert semantic insight to dictionary format."""
        return {
            "insight_id": self.insight_id,
            "content_type": self.content_type,
            "topics": self.topics,
            "key_concepts": self.key_concepts,
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label,
            "complexity_score": self.complexity_score,
            "quality_score": self.quality_score,
            "named_entities": self.named_entities,
            "key_phrases": self.key_phrases,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class ConversationFlow:
    """Container for conversation flow analysis results."""
    flow_id: str
    conversation_id: str
    total_turns: int
    average_turn_length: float
    topic_switches: int
    question_answer_pairs: int
    decision_points: List[Dict[str, Any]]
    efficiency_score: float
    coherence_score: float
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert conversation flow to dictionary format."""
        return {
            "flow_id": self.flow_id,
            "conversation_id": self.conversation_id,
            "total_turns": self.total_turns,
            "average_turn_length": self.average_turn_length,
            "topic_switches": self.topic_switches,
            "question_answer_pairs": self.question_answer_pairs,
            "decision_points": self.decision_points,
            "efficiency_score": self.efficiency_score,
            "coherence_score": self.coherence_score,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class KnowledgeNode:
    """Container for extracted knowledge."""
    node_id: str
    concept: str
    description: str
    confidence: float
    related_concepts: List[str]
    source_conversations: List[str]
    frequency: int
    importance_score: float
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert knowledge node to dictionary format."""
        return {
            "node_id": self.node_id,
            "concept": self.concept,
            "description": self.description,
            "confidence": self.confidence,
            "related_concepts": self.related_concepts,
            "source_conversations": self.source_conversations,
            "frequency": self.frequency,
            "importance_score": self.importance_score,
            "created_at": self.created_at.isoformat()
        }


class SemanticAnalyzer:
    """Advanced semantic analysis of conversation content."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the semantic analyzer."""
        self.config = config or {}
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 3)
        )
        self.topic_model = None
        self.stop_words = set(stopwords.words('english'))
        self.is_trained = False

    async def analyze_content(self, content: str, content_id: str = None) -> SemanticInsight:
        """Perform comprehensive semantic analysis on content."""
        
        if not content or len(content.strip()) == 0:
            return None

        try:
            # Generate unique ID
            insight_id = content_id or f"semantic_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Extract topics and key concepts
            topics = await self._extract_topics(content)
            key_concepts = await self._extract_key_concepts(content)
            
            # Sentiment analysis
            sentiment_score, sentiment_label = await self._analyze_sentiment(content)
            
            # Calculate complexity and quality scores
            complexity_score = await self._calculate_complexity(content)
            quality_score = await self._calculate_quality(content)
            
            # Named entity recognition
            named_entities = await self._extract_named_entities(content)
            
            # Key phrase extraction
            key_phrases = await self._extract_key_phrases(content)

            return SemanticInsight(
                insight_id=insight_id,
                content_type="conversation",
                topics=topics,
                key_concepts=key_concepts,
                sentiment_score=sentiment_score,
                sentiment_label=sentiment_label,
                complexity_score=complexity_score,
                quality_score=quality_score,
                named_entities=named_entities,
                key_phrases=key_phrases,
                metadata={
                    "content_length": len(content),
                    "word_count": len(content.split()),
                    "sentence_count": len(sent_tokenize(content))
                }
            )

        except Exception as e:
            logger.error(f"Error in semantic analysis: {e}")
            return None

    async def _extract_topics(self, content: str) -> List[str]:
        """Extract main topics from content using clustering."""
        try:
            # Simple keyword-based topic extraction
            # In a production system, this would use more sophisticated NLP models
            
            sentences = sent_tokenize(content)
            if len(sentences) < 2:
                return ["general"]
            
            # Create TF-IDF vectors for sentences
            tfidf_matrix = self.vectorizer.fit_transform(sentences)
            
            # Use clustering to identify topics
            n_clusters = min(3, len(sentences))
            if n_clusters > 1:
                kmeans = KMeans(n_clusters=n_clusters, random_state=42)
                clusters = kmeans.fit_predict(tfidf_matrix)
                
                # Get top terms for each cluster as topics
                feature_names = self.vectorizer.get_feature_names_out()
                topics = []
                
                for i in range(n_clusters):
                    # Get centroid
                    cluster_center = kmeans.cluster_centers_[i]
                    # Get top terms
                    top_indices = cluster_center.argsort()[-5:][::-1]
                    cluster_terms = [feature_names[idx] for idx in top_indices]
                    topic = " ".join(cluster_terms[:2])  # Use top 2 terms as topic
                    topics.append(topic)
                
                return topics
            else:
                return ["general"]
                
        except Exception as e:
            logger.error(f"Error extracting topics: {e}")
            return ["general"]

    async def _extract_key_concepts(self, content: str) -> List[str]:
        """Extract key concepts using NLP techniques."""
        try:
            # Tokenize and POS tag
            tokens = word_tokenize(content.lower())
            pos_tags = pos_tag(tokens)
            
            # Extract nouns and adjectives as potential concepts
            concepts = []
            for word, pos in pos_tags:
                if pos.startswith('NN') or pos.startswith('JJ'):  # Nouns and adjectives
                    if len(word) > 3 and word not in self.stop_words:
                        concepts.append(word)
            
            # Count frequency and return top concepts
            concept_counts = Counter(concepts)
            return [concept for concept, count in concept_counts.most_common(10)]
            
        except Exception as e:
            logger.error(f"Error extracting key concepts: {e}")
            return []

    async def _analyze_sentiment(self, content: str) -> Tuple[float, str]:
        """Analyze sentiment of content."""
        try:
            blob = TextBlob(content)
            sentiment_score = blob.sentiment.polarity  # Range: -1 to 1
            
            # Map to labels
            if sentiment_score > 0.1:
                sentiment_label = "positive"
            elif sentiment_score < -0.1:
                sentiment_label = "negative"
            else:
                sentiment_label = "neutral"
            
            return float(sentiment_score), sentiment_label
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return 0.0, "neutral"

    async def _calculate_complexity(self, content: str) -> float:
        """Calculate content complexity score."""
        try:
            sentences = sent_tokenize(content)
            words = word_tokenize(content)
            
            if len(sentences) == 0 or len(words) == 0:
                return 0.0
            
            # Average sentence length
            avg_sentence_length = len(words) / len(sentences)
            
            # Lexical diversity
            unique_words = len(set(word.lower() for word in words if word.isalpha()))
            lexical_diversity = unique_words / len(words) if words else 0
            
            # Complexity based on sentence length and vocabulary
            complexity = (avg_sentence_length / 20.0) * 0.6 + lexical_diversity * 0.4
            
            return min(complexity, 1.0)  # Cap at 1.0
            
        except Exception as e:
            logger.error(f"Error calculating complexity: {e}")
            return 0.0

    async def _calculate_quality(self, content: str) -> float:
        """Calculate content quality score."""
        try:
            # Quality factors
            word_count = len(content.split())
            sentence_count = len(sent_tokenize(content))
            
            # Base quality on content length and structure
            length_score = min(word_count / 100.0, 1.0)  # Favor longer content
            structure_score = min(sentence_count / 10.0, 1.0)  # Favor structured content
            
            # Check for questions (indicates engagement)
            question_count = content.count('?')
            engagement_score = min(question_count / 5.0, 1.0)
            
            # Overall quality score
            quality = (length_score * 0.4 + structure_score * 0.3 + engagement_score * 0.3)
            
            return quality
            
        except Exception as e:
            logger.error(f"Error calculating quality: {e}")
            return 0.0

    async def _extract_named_entities(self, content: str) -> List[Dict[str, str]]:
        """Extract named entities from content."""
        try:
            tokens = word_tokenize(content)
            pos_tags = pos_tag(tokens)
            entities = ne_chunk(pos_tags)
            
            named_entities = []
            for chunk in entities:
                if hasattr(chunk, 'label'):
                    entity_name = ' '.join([token for token, pos in chunk.leaves()])
                    named_entities.append({
                        "text": entity_name,
                        "label": chunk.label()
                    })
            
            return named_entities[:10]  # Limit to top 10
            
        except Exception as e:
            logger.error(f"Error extracting named entities: {e}")
            return []

    async def _extract_key_phrases(self, content: str) -> List[str]:
        """Extract key phrases using n-gram analysis."""
        try:
            # Simple n-gram based key phrase extraction
            sentences = sent_tokenize(content)
            
            if not sentences:
                return []
            
            # Extract 2-3 word phrases
            vectorizer = TfidfVectorizer(
                ngram_range=(2, 3),
                stop_words='english',
                max_features=20
            )
            
            tfidf_matrix = vectorizer.fit_transform(sentences)
            feature_names = vectorizer.get_feature_names_out()
            
            # Get phrases with highest TF-IDF scores
            scores = tfidf_matrix.sum(axis=0).A1
            phrase_scores = list(zip(feature_names, scores))
            phrase_scores.sort(key=lambda x: x[1], reverse=True)
            
            return [phrase for phrase, score in phrase_scores[:10] if score > 0]
            
        except Exception as e:
            logger.error(f"Error extracting key phrases: {e}")
            return []


class ConversationFlowAnalyzer:
    """Analyze conversation flow patterns and efficiency."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the conversation flow analyzer."""
        self.config = config or {}
        self.question_patterns = [
            r'\?',
            r'\bhow\b',
            r'\bwhat\b',
            r'\bwhy\b',
            r'\bwhen\b',
            r'\bwhere\b',
            r'\bwhich\b',
            r'\bcan you\b',
            r'\bcould you\b'
        ]
        
        self.decision_patterns = [
            r'\bdecide\b',
            r'\bchoose\b',
            r'\boption\b',
            r'\balternative\b',
            r'\brecommend\b',
            r'\bshould\b'
        ]

    async def analyze_flow(self, conversation_data: List[Dict[str, Any]]) -> ConversationFlow:
        """Analyze conversation flow and efficiency."""
        
        if not conversation_data:
            return None

        try:
            conversation_id = conversation_data[0].get('conversation_id', 'unknown')
            flow_id = f"flow_{conversation_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Basic metrics
            total_turns = len(conversation_data)
            total_length = sum(len(turn.get('content', '')) for turn in conversation_data)
            average_turn_length = total_length / total_turns if total_turns > 0 else 0

            # Analyze topic switches
            topic_switches = await self._count_topic_switches(conversation_data)

            # Count question-answer pairs
            qa_pairs = await self._count_qa_pairs(conversation_data)

            # Extract decision points
            decision_points = await self._extract_decision_points(conversation_data)

            # Calculate efficiency and coherence scores
            efficiency_score = await self._calculate_efficiency(conversation_data)
            coherence_score = await self._calculate_coherence(conversation_data)

            return ConversationFlow(
                flow_id=flow_id,
                conversation_id=conversation_id,
                total_turns=total_turns,
                average_turn_length=average_turn_length,
                topic_switches=topic_switches,
                question_answer_pairs=qa_pairs,
                decision_points=decision_points,
                efficiency_score=efficiency_score,
                coherence_score=coherence_score
            )

        except Exception as e:
            logger.error(f"Error analyzing conversation flow: {e}")
            return None

    async def _count_topic_switches(self, conversation_data: List[Dict[str, Any]]) -> int:
        """Count the number of topic switches in the conversation."""
        if len(conversation_data) < 2:
            return 0

        try:
            # Simple topic switch detection based on content similarity
            topic_switches = 0
            
            for i in range(1, len(conversation_data)):
                prev_content = conversation_data[i-1].get('content', '')
                curr_content = conversation_data[i].get('content', '')
                
                if len(prev_content) > 0 and len(curr_content) > 0:
                    # Calculate content similarity
                    similarity = await self._calculate_content_similarity(prev_content, curr_content)
                    
                    # If similarity is low, consider it a topic switch
                    if similarity < 0.3:
                        topic_switches += 1
            
            return topic_switches
            
        except Exception as e:
            logger.error(f"Error counting topic switches: {e}")
            return 0

    async def _count_qa_pairs(self, conversation_data: List[Dict[str, Any]]) -> int:
        """Count question-answer pairs in the conversation."""
        try:
            qa_pairs = 0
            
            for i, turn in enumerate(conversation_data):
                content = turn.get('content', '')
                
                # Check if this turn contains a question
                has_question = any(re.search(pattern, content, re.IGNORECASE) 
                                 for pattern in self.question_patterns)
                
                if has_question and i + 1 < len(conversation_data):
                    # Check if next turn provides an answer
                    next_content = conversation_data[i + 1].get('content', '')
                    if len(next_content) > 20:  # Assume substantial responses are answers
                        qa_pairs += 1
            
            return qa_pairs
            
        except Exception as e:
            logger.error(f"Error counting Q&A pairs: {e}")
            return 0

    async def _extract_decision_points(self, conversation_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract decision points from the conversation."""
        try:
            decision_points = []
            
            for i, turn in enumerate(conversation_data):
                content = turn.get('content', '')
                
                # Check if this turn contains decision-related language
                has_decision = any(re.search(pattern, content, re.IGNORECASE) 
                                 for pattern in self.decision_patterns)
                
                if has_decision:
                    decision_points.append({
                        'turn_index': i,
                        'timestamp': turn.get('timestamp', ''),
                        'content_preview': content[:100] + '...' if len(content) > 100 else content,
                        'decision_type': 'explicit'
                    })
            
            return decision_points[:10]  # Limit to top 10
            
        except Exception as e:
            logger.error(f"Error extracting decision points: {e}")
            return []

    async def _calculate_efficiency(self, conversation_data: List[Dict[str, Any]]) -> float:
        """Calculate conversation efficiency score."""
        try:
            if not conversation_data:
                return 0.0
            
            total_turns = len(conversation_data)
            total_length = sum(len(turn.get('content', '')) for turn in conversation_data)
            
            # Factors for efficiency
            avg_turn_length = total_length / total_turns if total_turns > 0 else 0
            
            # Efficiency based on conciseness and productivity
            conciseness_score = max(0, 1.0 - (avg_turn_length / 1000))  # Penalize very long turns
            productivity_score = min(total_turns / 20.0, 1.0)  # Reward active conversations
            
            efficiency = (conciseness_score * 0.6 + productivity_score * 0.4)
            
            return min(efficiency, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating efficiency: {e}")
            return 0.0

    async def _calculate_coherence(self, conversation_data: List[Dict[str, Any]]) -> float:
        """Calculate conversation coherence score."""
        try:
            if len(conversation_data) < 2:
                return 1.0
            
            total_similarity = 0
            pair_count = 0
            
            # Calculate average similarity between adjacent turns
            for i in range(1, len(conversation_data)):
                prev_content = conversation_data[i-1].get('content', '')
                curr_content = conversation_data[i].get('content', '')
                
                if len(prev_content) > 0 and len(curr_content) > 0:
                    similarity = await self._calculate_content_similarity(prev_content, curr_content)
                    total_similarity += similarity
                    pair_count += 1
            
            coherence = total_similarity / pair_count if pair_count > 0 else 0.0
            
            return coherence
            
        except Exception as e:
            logger.error(f"Error calculating coherence: {e}")
            return 0.0

    async def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two pieces of content."""
        try:
            if not content1 or not content2:
                return 0.0
            
            # Simple word overlap similarity
            words1 = set(word.lower() for word in content1.split() if len(word) > 3)
            words2 = set(word.lower() for word in content2.split() if len(word) > 3)
            
            if not words1 or not words2:
                return 0.0
            
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            
            return intersection / union if union > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating content similarity: {e}")
            return 0.0


class KnowledgeExtractor:
    """Extract and organize knowledge from conversation data."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the knowledge extractor."""
        self.config = config or {}
        self.knowledge_graph = {}
        self.concept_frequency = Counter()

    async def extract_knowledge(self, conversation_data: List[Dict[str, Any]]) -> List[KnowledgeNode]:
        """Extract knowledge nodes from conversation data."""
        
        if not conversation_data:
            return []

        try:
            knowledge_nodes = []
            
            # Combine all content
            all_content = ' '.join([turn.get('content', '') for turn in conversation_data])
            
            # Extract concepts using semantic analysis
            semantic_analyzer = SemanticAnalyzer()
            semantic_result = await semantic_analyzer.analyze_content(all_content)
            
            if semantic_result:
                # Create knowledge nodes from key concepts
                for i, concept in enumerate(semantic_result.key_concepts[:10]):
                    node_id = f"knowledge_{concept}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}"
                    
                    # Calculate importance based on frequency and context
                    importance_score = await self._calculate_concept_importance(concept, all_content)
                    
                    # Find related concepts
                    related_concepts = await self._find_related_concepts(
                        concept, semantic_result.key_concepts
                    )
                    
                    knowledge_node = KnowledgeNode(
                        node_id=node_id,
                        concept=concept,
                        description=f"Key concept extracted from conversation analysis",
                        confidence=0.8,  # Default confidence
                        related_concepts=related_concepts,
                        source_conversations=[conversation_data[0].get('conversation_id', 'unknown')],
                        frequency=all_content.lower().count(concept.lower()),
                        importance_score=importance_score
                    )
                    
                    knowledge_nodes.append(knowledge_node)
            
            return knowledge_nodes
            
        except Exception as e:
            logger.error(f"Error extracting knowledge: {e}")
            return []

    async def _calculate_concept_importance(self, concept: str, content: str) -> float:
        """Calculate importance score for a concept."""
        try:
            # Factors for importance
            frequency = content.lower().count(concept.lower())
            content_length = len(content.split())
            
            # Normalize frequency by content length
            normalized_frequency = frequency / content_length if content_length > 0 else 0
            
            # Importance based on frequency and concept length (longer concepts often more important)
            concept_length_factor = min(len(concept) / 10.0, 1.0)
            
            importance = normalized_frequency * 0.7 + concept_length_factor * 0.3
            
            return min(importance, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating concept importance: {e}")
            return 0.0

    async def _find_related_concepts(self, concept: str, all_concepts: List[str]) -> List[str]:
        """Find concepts related to the given concept."""
        try:
            related = []
            concept_words = set(concept.lower().split())
            
            for other_concept in all_concepts:
                if other_concept != concept:
                    other_words = set(other_concept.lower().split())
                    
                    # Check for word overlap
                    if concept_words.intersection(other_words):
                        related.append(other_concept)
            
            return related[:5]  # Limit to top 5 related concepts
            
        except Exception as e:
            logger.error(f"Error finding related concepts: {e}")
            return []


class ContentIntelligenceEngine:
    """Main orchestrator for all content intelligence capabilities."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the content intelligence engine."""
        self.config = config or {}
        self.semantic_analyzer = SemanticAnalyzer(config)
        self.flow_analyzer = ConversationFlowAnalyzer(config)
        self.knowledge_extractor = KnowledgeExtractor(config)

    async def analyze_conversation(self, conversation_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform comprehensive analysis on conversation data."""
        
        if not conversation_data:
            return {}

        try:
            results = {}

            # Combine all content for semantic analysis
            all_content = '\n'.join([turn.get('content', '') for turn in conversation_data])
            conversation_id = conversation_data[0].get('conversation_id', 'unknown')

            # Semantic analysis
            semantic_result = await self.semantic_analyzer.analyze_content(all_content, conversation_id)
            if semantic_result:
                results['semantic_analysis'] = semantic_result.to_dict()

            # Conversation flow analysis
            flow_result = await self.flow_analyzer.analyze_flow(conversation_data)
            if flow_result:
                results['flow_analysis'] = flow_result.to_dict()

            # Knowledge extraction
            knowledge_nodes = await self.knowledge_extractor.extract_knowledge(conversation_data)
            results['knowledge_extraction'] = [node.to_dict() for node in knowledge_nodes]

            # Summary statistics
            results['summary'] = {
                'conversation_id': conversation_id,
                'total_turns': len(conversation_data),
                'total_content_length': len(all_content),
                'analysis_timestamp': datetime.now().isoformat(),
                'topics_identified': len(semantic_result.topics) if semantic_result else 0,
                'concepts_extracted': len(knowledge_nodes),
                'flow_efficiency': flow_result.efficiency_score if flow_result else 0.0
            }

            return results

        except Exception as e:
            logger.error(f"Error in conversation analysis: {e}")
            return {}

    async def get_content_insights_summary(self) -> Dict[str, Any]:
        """Get summary of content intelligence capabilities and recent insights."""
        
        return {
            'capabilities': {
                'semantic_analysis': True,
                'topic_extraction': True,
                'sentiment_analysis': True,
                'named_entity_recognition': True,
                'conversation_flow_analysis': True,
                'knowledge_extraction': True,
                'quality_scoring': True
            },
            'recent_analysis': {
                'conversations_analyzed': 0,  # Would be populated from database
                'avg_quality_score': 0.0,
                'avg_complexity_score': 0.0,
                'most_common_topics': [],
                'knowledge_nodes_extracted': 0
            },
            'system_status': {
                'models_loaded': True,
                'processing_ready': True,
                'last_updated': datetime.now().isoformat()
            }
        }


# Global instance for easy access
_content_intelligence_engine = None

def get_content_intelligence_engine(config: Dict[str, Any] = None) -> ContentIntelligenceEngine:
    """Get or create global content intelligence engine instance."""
    global _content_intelligence_engine
    if _content_intelligence_engine is None:
        _content_intelligence_engine = ContentIntelligenceEngine(config)
    return _content_intelligence_engine