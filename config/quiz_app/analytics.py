"""
analytics.py

Bayesian Per-Item Posterior Mastery Estimation
"""

from collections import defaultdict
from .models import QuizAttempt

# ==========================================================
# Difficulty Weights
# ==========================================================

DIFFICULTY_WEIGHTS = {
    "Easy": 0.35,
    "Medium": 0.35,
    "Hard": 0.30,
}


# ==========================================================
# Core Bayesian Mastery
# ==========================================================

def compute_mastery_by_difficulty(
    answers,
    prior_knowledge=0.7,
    difficulty_weights=DIFFICULTY_WEIGHTS
):
    if not answers:
        return {}, 0.0, [], {}

    per_question_posteriors = []
    difficulty_map = defaultdict(list)

    for ans in answers:
        question = ans.question

        if not question:
            continue

        is_correct = 1 if ans.is_correct else 0
        num_options = max(len(question.get_all_options()), 1)

        # Bayesian posterior
        if is_correct == 0:
            posterior = 0.0
        else:
            p_guess = 1.0 / num_options
            p0 = prior_knowledge
            posterior = p0 / (p0 + (1 - p0) * p_guess)

        per_question_posteriors.append({
            "question_id": question.id,
            "difficulty": question.difficulty,
            "bloom_level": question.bloom_level,
            "knowledge_posterior": posterior
        })

        difficulty_map[question.difficulty].append(posterior)

    # Mastery per difficulty
    mastery_by_difficulty = {}
    for level, values in difficulty_map.items():
        mastery_by_difficulty[level] = (
            sum(values) / len(values) if values else 0.0
        )

    # Weighted overall mastery
    weighted_sum = 0.0
    weight_total = 0.0

    for level, mastery in mastery_by_difficulty.items():
        if level in difficulty_weights:
            w = difficulty_weights[level]
            weighted_sum += w * mastery
            weight_total += w

    overall_mastery = (
        weighted_sum / weight_total if weight_total > 0 else 0.0
    )

    # Feedback
    feedback = {}
    for level, mastery in mastery_by_difficulty.items():
        if mastery >= 0.75:
            feedback[level] = "Strong mastery"
        elif mastery >= 0.40:
            feedback[level] = "Partial mastery – needs practice"
        else:
            feedback[level] = "Weak mastery – likely guessing"

    return mastery_by_difficulty, overall_mastery, per_question_posteriors, feedback


# ==========================================================
# Bloom Mastery  ✅ (THIS FIXES YOUR ERROR)
# ==========================================================

def bloom_mastery(per_question_posteriors):
    bloom_map = defaultdict(list)

    for item in per_question_posteriors:
        bloom_map[item["bloom_level"]].append(item["knowledge_posterior"])

    bloom_scores = {}

    for level, values in bloom_map.items():
        bloom_scores[level] = (
            sum(values) / len(values) if values else 0.0
        )

    return bloom_scores


# ==========================================================
# Mastery Trend
# ==========================================================

def mastery_trend(user):
    attempts = QuizAttempt.objects.filter(
        user=user,
        is_completed=True
    ).order_by("completed_at").prefetch_related("answers__question")

    trend = []

    for attempt in attempts:
        answers = attempt.answers.all()

        mastery_by_diff, overall, _, _ = compute_mastery_by_difficulty(
            answers,
            prior_knowledge=attempt.prior_knowledge
        )

        trend.append({
            "date": attempt.completed_at.strftime("%d %b"),
            "mastery": round(overall * 100, 1),
            "score": attempt.score
        })

    return trend