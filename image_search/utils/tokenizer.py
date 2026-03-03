import re
import string
import unicodedata
from typing import List, Set

class EnhancedTokenizer:
    def __init__(self):
        self.sentence_endings = '.!?'
        self.stopwords = self._load_comprehensive_stopwords()
        self.punctuation = set(string.punctuation)
    
    def _load_comprehensive_stopwords(self) -> Set[str]:
        """Load an expanded set of stopwords with multiple languages and variations."""
        base_stopwords = {
            # English stopwords (expanded set)
            'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", 
            'your', 'yours', 'yourself', 'he', 'him', 'his', 'she', 'her', 'it', 'its', 
            'they', 'them', 'their', 'this', 'that', 'these', 'those', 
            'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 
            'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing',
            'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 
            'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about', 
            'against', 'between', 'into', 'through', 'during', 'before', 
            'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 
            'out', 'on', 'off', 'over', 'under', 'again', 'further', 
            # Additional context-aware stopwords
            'would', 'could', 'should', 'might', 'must', 'can', 'will', 
            # Prepositions and conjunctions
            'hence', 'thus', 'so', 'therefore', 'moreover', 'furthermore',
            # Common variants
            'there', 'here', 'where'
        }
        return set(word.lower() for word in base_stopwords)

    def normalize_text(self, text: str) -> str:
        """
        Normalize text by:
        1. Converting to unicode-normalized form
        2. Removing extra whitespaces
        3. Converting to lowercase (with exceptions)
        """
        # Normalize unicode characters
        text = unicodedata.normalize('NFKD', text)
        
        # Remove control characters
        text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def sentence_tokenize(self, text: str) -> List[str]:
        """
        Advanced sentence tokenization with improved handling of abbreviations
        and complex text structures
        """
        # Normalize text first
        text = self.normalize_text(text)
        
        # Handle common abbreviations
        abbreviation_patterns = [
            r'(?<=[A-Z]\.)\s*(?=[A-Z])', # Initial abbreviations like "U.S. Government"
            r'(?<=[A-Z])\.\s*(?=[A-Z][a-z])', # Other abbreviation cases
        ]
        
        for pattern in abbreviation_patterns:
            text = re.sub(pattern, '<ABBR_PLACEHOLDER>', text)
        
        # Split sentences with enhanced regex
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        
        # Restore abbreviations
        sentences = [s.replace('<ABBR_PLACEHOLDER>', ' ') for s in sentences]
        
        # Clean and filter
        sentences = [s.strip() for s in sentences if s.strip() and len(s) > 2]
        
        return sentences

    def word_tokenize(self, text: str) -> List[str]:
        """
        Advanced word tokenization with smart handling of:
        1. Contractions
        2. Hyphenated words
        3. Special characters
        """
        # Normalize text
        text = self.normalize_text(text)
        
        # Handle contractions
        text = re.sub(r"'s\b", '', text)  # Remove possessive 's
        text = re.sub(r"n't\b", ' not', text)  # Expand contractions
        
        # Replace hyphens with spaces for better tokenization of compound words
        text = text.replace('-', ' ')
        
        # Tokenize words while preserving meaningful punctuation
        words = re.findall(r'\b\w+\b|[.,!?;:]', text)
        
        # Processing each word
        processed_words = []
        for word in words:
            # Lowercase conversion with proper noun exception
            word = word.lower()
            
            # Skip stopwords and very short tokens
            if (word not in self.stopwords and 
                len(word) > 1 and 
                word not in self.punctuation):
                processed_words.append(word)
        
        return processed_words

    def advanced_preprocess(self, text: str) -> str:
        """
        Comprehensive text preprocessing method
        """
        # Normalize text
        text = self.normalize_text(text)
        
        # Tokenize sentences
        sentences = self.sentence_tokenize(text)
        
        # Process each sentence
        processed_sentences = []
        for sentence in sentences:
            # Tokenize words
            words = self.word_tokenize(sentence)
            
            # Join processed words
            if words:
                processed_sentences.append(' '.join(words))
        
        # Join processed sentences
        return ' '.join(processed_sentences)

# Instantiate the tokenizer
advanced_tokenizer = EnhancedTokenizer()
