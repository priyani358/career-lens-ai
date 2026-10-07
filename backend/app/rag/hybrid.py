"""Pure-Python keyword retrieval and reciprocal-rank fusion helpers."""
import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9+#.]+")


def tokenize(text):
    return _TOKEN.findall(text.lower())


class BM25:
    """Rank documents by query-term relevance using Okapi BM25."""

    def __init__(self, documents, k1=1.5, b=0.75):
        self.documents = [tokenize(document) for document in documents]
        self.k1 = k1
        self.b = b
        self.term_frequencies = [Counter(document) for document in self.documents]
        count = len(self.documents)
        self.average_length = sum(map(len, self.documents)) / max(count, 1)
        document_frequency = Counter(token for document in self.documents for token in set(document))
        self.inverse_document_frequency = {
            token: math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))
            for token, frequency in document_frequency.items()
        }

    def scores(self, query):
        query_tokens = tokenize(query)
        scores = []
        for document, frequencies in zip(self.documents, self.term_frequencies):
            score = 0.0
            for token in query_tokens:
                if token in frequencies:
                    frequency = frequencies[token]
                    denominator = frequency + self.k1 * (
                        1 - self.b + self.b * len(document) / max(self.average_length, 1)
                    )
                    score += self.inverse_document_frequency[token] * frequency * (self.k1 + 1) / denominator
            scores.append(score)
        return scores


def reciprocal_rank_fusion(rankings, k=60):
    """Merge ranked lists by their rank, without requiring comparable scores."""
    scores = {}
    for ranking in rankings:
        for position, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1 / (k + position + 1)
    return sorted(scores, key=scores.get, reverse=True)
