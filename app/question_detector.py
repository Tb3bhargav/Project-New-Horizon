"""
Local rule-based question detector for Project New Horizon.
Evaluates transcript text using fast local heuristic rules (0 network calls).
"""

import re

class QuestionDetector:
    """
    Local rule-based question detector.
    
    Evaluates whether a spoken transcript is a question using:
    1. Interrogative words (who, what, where, when, why, how, etc., including contractions like what's, how's)
    2. Auxiliary verb openings (is, are, can, could, do, does, etc., including contractions like can't, isn't)
    3. Direct request/command forms ("tell me", "explain", "describe", "summarize", etc.)
    4. Explicit ending question marks ('?')
    """
    
    INTERROGATIVES = {
        "who", "what", "where", "when", "why", "how", "which", "whose", "whom",
        "whats", "what's", "whos", "who's", "wheres", "where's", "whens", "when's",
        "whys", "why's", "hows", "how's"
    }

    AUXILIARY_OPENINGS = {
        "is", "are", "was", "were", "do", "does", "did", "can", "could",
        "would", "should", "will", "may", "might", "have", "has", "had", "shall",
        "isnt", "isn't", "arent", "aren't", "wasnt", "wasn't", "werent", "weren't",
        "dont", "don't", "doesnt", "doesn't", "didnt", "didn't", "cant", "can't",
        "couldnt", "couldn't", "wouldnt", "wouldn't", "shouldnt", "shouldn't", "wont", "won't"
    }

    DIRECT_PHRASES = (
        "tell me", "explain", "describe", "show me", "define", "list",
        "give me", "can you", "could you", "would you", "help me", "summarize",
        "write", "count", "calculate", "search for", "find"
    )

    FILLER_WORDS = {"hey", "so", "um", "uh", "well", "please", "hi", "hello", "okay", "ok"}

    def is_question(self, text: str) -> bool:
        """
        Evaluate whether the input text is a question.

        Args:
            text: Transcribed text string.

        Returns:
            bool: True if classified as a question, False otherwise.
        """
        if not text:
            return False

        cleaned = text.strip()
        if not cleaned:
            return False

        # Rule 1: Explicit question mark at the end
        if cleaned.endswith("?"):
            return True

        lower_text = cleaned.lower()
        # Remove leading non-alphanumeric chars except apostrophes inside words
        lower_clean = re.sub(r'^[^\w\s]+', '', lower_text).strip()
        words = lower_clean.split()
        if not words:
            return False

        # Strip leading conversational filler words if present
        while words and words[0].strip(".,!?;:\"'") in self.FILLER_WORDS:
            words.pop(0)

        if not words:
            return False

        lower_clean_no_filler = " ".join(words)
        first_word = words[0].strip(".,!?;:\"'")

        # Rule 2: Interrogative starting word (e.g. "What is...", "How far...", "What's...")
        if first_word in self.INTERROGATIVES:
            return True

        # Rule 3: Direct request phrases (e.g. "Tell me about...", "Explain quantum...")
        for phrase in self.DIRECT_PHRASES:
            if lower_clean_no_filler.startswith(phrase):
                return True

        # Rule 4: Auxiliary opening word if sentence has at least 2 words (e.g. "Can I...", "Is this...")
        if len(words) >= 2 and first_word in self.AUXILIARY_OPENINGS:
            return True

        # Fallback: Single imperative verb check (e.g. "Explain", "Summarize")
        if len(words) == 1 and first_word in self.DIRECT_PHRASES:
            return True

        return False
