# -*- coding: utf-8 -*-

import math
from simpleai.machine_learning import ClassificationProblem, is_attribute

from yalign.datatypes import ScoreFunction, SentencePair
from yalign.svm import SVMClassifier


class SentencePairScore(ScoreFunction):
    def __init__(self):
        super(SentencePairScore, self).__init__(0, 1)
        self.classifier = None
        self.sign = 1

    # FIXME: Consider giving the word_aligner instead of word_score_function
    def train(self, pairs, word_score_function):
        """
        Trains the sentence pair likelihood score using examples.
        `pairs` is an interable of `SentencePair` instances.
        `word_score_function` is an instance of ScoreFunction, perhaps even an
        instance of `WordPairScore`.
        """
        pairs = list(pairs)
        self.problem = SentencePairScoreProblem(word_score_function)
        self.classifier = SVMClassifier(pairs, self.problem)
        class_ = None
        for a, b in pairs:
            sent = a = SentencePair(a, b)
            score = self.classifier.score(sent)
            if score != 0:
                class_ = bool(self.classifier.classify(sent)[0])
                if (score > 0 and class_ is True) or \
                   (score < 0 and class_ is False):
                    self.sign = -1
                break
        if class_ is None:
            raise ValueError("Cannot infer sign with this data")

    def load(self, filepath):
        self.classifier = SVMClassifier.load(filepath)

    def save(self, filepath):
        self.classifier.save(filepath)

    def __call__(self, a, b):
        """
        Returns the score of a sentence.
        """
        if self.classifier is None:
            raise LookupError("Score not trained or loaded yet")
        a = SentencePair(a, b)
        score = self.classifier.score(a) * self.sign
        result = logistic_function(score * 3)
        # FIXME: Consider moving this to a test
        assert self.min_bound <= result <= self.max_bound
        return result

    @property
    def word_pair_score(self):
        return self.classifier.problem.word_pair_score


class SentencePairScoreProblem(ClassificationProblem):
    def __init__(self, word_pair_score):
        super(SentencePairScoreProblem, self).__init__()
        # If gap > 0.5 then the returned value could be > 1.
        self.word_pair_score = word_pair_score

    @is_attribute
    def position_difference(self, alignment):
        d = alignment.a.position - alignment.b.position
        return abs(d)

    @is_attribute
    def word_length_difference(self, alignment):
        a = len(alignment.a)
        b = len(alignment.b)
        return ratio(a, b)

    @is_attribute
    def uppercase_words_difference(self, alignment):
        a = len([x for x in alignment.a if x.isupper()])
        b = len([x for x in alignment.b if x.isupper()])
        return ratio(a, b)

    @is_attribute
    def capitalized_words_difference(self, alignment):
        a = len([x for x in alignment.a if x.istitle()])
        b = len([x for x in alignment.b if x.istitle()])
        return ratio(a, b)

    @is_attribute
    def commas(self, alignment):
        a = len([x for x in alignment.a if x == ","])
        b = len([x for x in alignment.b if x == ","])
        return ratio(a, b)

    @is_attribute
    def question_marks(self, alignment):
        a = len([x for x in alignment.a if x == "?"])
        b = len([x for x in alignment.b if x == "?"])
        return ratio(a, b)

    @is_attribute
    def punctuation(self, alignment):
        punc = ",.-?+<>_\\/"
        a = len([x for x in alignment.a if x in punc])
        b = len([x for x in alignment.b if x in punc])
        return ratio(a, b)

    @is_attribute
    def digits(self, alignment):
        a = len([x for x in alignment.a if x.isdigit()])
        b = len([x for x in alignment.b if x.isdigit()])
        return ratio(a, b)

    @is_attribute
    def word_match(self, alignment):
        a, b = list(alignment.a), list(alignment.b)
        diff = abs(len(a) - len(b))
        if diff > 2 * len(a) or diff > 2 * len(b):
            return 1
        score = 0
        for cost, word_a, word_b in self._word_pairs(alignment):
            if word_a in a and word_b in b:
                score += cost
                a.remove(word_a)
                b.remove(word_b)
        score += len(a) + len(b)
        return float(score) / max(len(alignment.a), len(alignment.b))

    def _word_pairs(self, sentencepair):
        a, b = sentencepair
        for word_a in a:
            item = []
            max_score = 1
            for word_b in b:
                cost = self.word_pair_score(word_a, word_b)
                if cost < max_score:
                    max_score = cost
                    item = (max_score, word_a, word_b)
            if item:
                yield item

    #@is_attribute
    def linear_word_match(self, alignment):
        values = {}
        translations = self.word_pair_score.translations
        for word_a in alignment.a:
            word_a = word_a.lower()
            if word_a in translations:
                values.update(translations[word_a])

        total = 0.0
        for word_b in alignment.b:
            word_b = word_b.lower()
            total += values.get(word_b, 0)

        return total / float(max(len(alignment.a), len(alignment.b)))

    @is_attribute
    def linear_word_count(self, alignment):
        values = []
        translations = self.word_pair_score.translations
        for word_a in alignment.a:
            word_a = word_a.lower()
            if word_a in translations:
                values.extend(translations[word_a].keys())

        total = 0.0
        for word_b in alignment.b:
            word_b = word_b.lower()
            if word_b in values:
                total += 1.0

        return total / float(max(len(alignment.a), len(alignment.b)))

    def target(self, alignment):
        return alignment.aligned


def ratio(a, b):
    if max(a, b) == 0:
        return 0.0
    return min(a, b) / float(max(a, b))


def logistic_function(x):
    """
    See: http://en.wikipedia.org/wiki/Logistic_function
    """
    return 1 / (1 + math.e ** (-x))


class CacheOfSizeOne(object):
    f = None

    def __init__(self, f):
        self.f = f
        self.args = None
        self.kwargs = None

    def __call__(self, *args, **kwargs):
        if args != self.args or kwargs != self.kwargs:
            self.result = self.f(*args, **kwargs)
            self.args = args
            self.kwargs = kwargs
        return self.result

    def __getattr__(self, name):
        return getattr(self.f, name)
