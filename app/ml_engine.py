import math
import re
from typing import List, Dict, Any, Tuple
from collections import Counter

# Standard english stopwords to filter out common noise words
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", 
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", 
    "by", "can", "did", "do", "does", "doing", "don", "down", "during", "each", "few", "for", 
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", 
    "him", "himself", "his", "how", "if", "in", "into", "is", "it", "its", "itself", "just", 
    "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once", 
    "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she", 
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", 
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", 
    "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", 
    "why", "with", "you", "your", "yours", "yourself", "yourselves"
}

def tokenize(text: str) -> List[str]:
    """Tokenize, lowercase, and remove non-alphanumeric chars & stopwords."""
    if not text:
        return []
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
    return [w for w in words if w not in STOPWORDS]

def compute_tf(tokens: List[str]) -> Dict[str, float]:
    """Compute term frequencies for a list of tokens."""
    counts = Counter(tokens)
    total = len(tokens)
    if total == 0:
        return {}
    return {word: count / total for word, count in counts.items()}

def compute_cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Compute cosine similarity between two sparse term vectors: (A . B) / (||A|| * ||B||)."""
    common_keys = set(vec_a.keys()) & set(vec_b.keys())
    if not common_keys:
        return 0.0

    dot_product = sum(vec_a[k] * vec_b[k] for k in common_keys)
    norm_a = math.sqrt(sum(val * val for val in vec_a.values()))
    norm_b = math.sqrt(sum(val * val for val in vec_b.values()))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)

class RecommendationEngine:
    """
    AI/ML Content-Based Filtering Recommendation Engine for SmartFest.
    Conforms to SRS Feature 2 (FR-2.1 to FR-2.7) and Experiment 7 UML interaction flows.
    """

    @classmethod
    def get_recommendations_for_student(
        cls,
        student_id: int,
        student_interests: List[str],
        student_department: str,
        all_events: List[Dict[str, Any]],
        registered_events: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Calculates affinity match scores for all open published events.
        Excludes full events, registered events, and events with time collisions.
        """
        # 1. Filter out events student is already registered for
        registered_ids = {r["event_id"] for r in registered_events if r.get("status") == "confirmed"}
        candidate_events = [
            e for e in all_events 
            if e["status"] == "published" 
            and e["registered_count"] < e["max_capacity"]
            and e["id"] not in registered_ids
        ]

        if not candidate_events:
            return []

        # 2. Filter out events that collide in date/time with registered events
        valid_candidates = []
        for cand in candidate_events:
            has_conflict = False
            for reg in registered_events:
                if reg.get("status") != "confirmed":
                    continue
                if reg.get("event_date") == cand["date"]:
                    # Check temporal interval overlap: max(start1, start2) < min(end1, end2)
                    r_start = reg.get("event_start_time", "00:00")
                    r_end = reg.get("event_end_time", "23:59")
                    c_start = cand["start_time"]
                    c_end = cand["end_time"]
                    if max(r_start, c_start) < min(r_end, c_end):
                        has_conflict = True
                        break
            if not has_conflict:
                valid_candidates.append(cand)

        if not valid_candidates:
            return []

        # 3. Construct Document Corpus to compute Inverse Document Frequency (IDF)
        corpus_docs = []
        for e in all_events:
            doc_text = f"{e['title']} {e['category']} {e['description']} {e.get('rules', '')} {e.get('eligibility', '')}"
            corpus_docs.append(tokenize(doc_text))

        num_docs = len(corpus_docs)
        doc_freq = Counter()
        for doc in corpus_docs:
            unique_words = set(doc)
            for w in unique_words:
                doc_freq[w] += 1

        idf: Dict[str, float] = {}
        for w, df in doc_freq.items():
            idf[w] = math.log((num_docs + 1) / (df + 1)) + 1.0

        # 4. Construct Student Profile Vector
        # Weighted combination of explicit interests (weight=3.0), department (weight=1.5), and past registrations (weight=1.2)
        student_tokens: List[Tuple[str, float]] = []

        for interest in student_interests:
            for w in tokenize(interest):
                student_tokens.append((w, 3.0))

        if student_department:
            for w in tokenize(student_department):
                student_tokens.append((w, 1.5))

        for reg in registered_events:
            reg_text = f"{reg.get('event_title', '')} {reg.get('event_category', '')}"
            for w in tokenize(reg_text):
                student_tokens.append((w, 1.2))

        # Compute Student TF-IDF Vector
        student_tf: Dict[str, float] = Counter()
        for w, weight in student_tokens:
            student_tf[w] += weight

        total_student_weight = sum(student_tf.values()) or 1.0
        student_vec = {w: (cnt / total_student_weight) * idf.get(w, 1.0) for w, cnt in student_tf.items()}

        # 5. Compute Event Feature Vectors and Cosine Similarity Scores
        scored_events = []
        for cand in valid_candidates:
            # Build event document with category given higher weighting
            event_text = f"{cand['title']} {cand['category']} {cand['category']} {cand['description']} {cand.get('rules', '')}"
            e_tokens = tokenize(event_text)
            e_tf = compute_tf(e_tokens)
            e_vec = {w: tf_val * idf.get(w, 1.0) for w, tf_val in e_tf.items()}

            cos_sim = compute_cosine_similarity(student_vec, e_vec)
            
            # Additional category boost if event category matches student interest directly
            category_lower = cand['category'].lower()
            if any(category_lower in interest.lower() or interest.lower() in category_lower for interest in student_interests):
                cos_sim += 0.20

            # Boost if capacity is > 50% available (promotes filling under-subscribed events)
            fill_ratio = cand['registered_count'] / max(1, cand['max_capacity'])
            if fill_ratio < 0.5:
                cos_sim += 0.05

            match_pct = min(99, max(45, int(cos_sim * 100)))

            scored_events.append({
                **cand,
                "recommendation_score": round(cos_sim, 4),
                "match_percentage": match_pct,
                "recommendation_reason": cls._generate_reason(cand, student_interests, student_department)
            })

        # Rank descending by score
        scored_events.sort(key=lambda x: x["recommendation_score"], reverse=True)
        return scored_events[:top_k]

    @staticmethod
    def _generate_reason(event: Dict[str, Any], interests: List[str], dept: str) -> str:
        """Generate human-readable AI explanation for the recommendation."""
        cat = (event.get('category') or '')
        desc = (event.get('description') or '')
        eligibility = (event.get('eligibility') or '')
        dept_val = (dept or '')

        for interest in interests:
            if interest and cat and (interest.lower() in cat.lower() or cat.lower() in interest.lower()):
                return f"Matches your declared interest in {interest}"
        if dept_val and ((dept_val.lower() in desc.lower()) or (dept_val.lower() in eligibility.lower())):
            return f"Popular among students in {dept_val}"
        return f"Trending {cat} event with open seats"
