# sm2.py

from datetime import timedelta
from django.utils import timezone


# ----------------------------------------
# Convert Bayesian Posterior → Quality
# ----------------------------------------
def posterior_to_quality(p):
    if p >= 0.85:
        return 5
    elif p >= 0.70:
        return 4
    elif p >= 0.55:
        return 3
    elif p >= 0.40:
        return 2
    else:
        return 1


# ----------------------------------------
# SM-2 Algorithm
# ----------------------------------------
def apply_sm2(progress, quality):
    EF = progress.easiness_factor
    n = progress.repetition
    I = progress.interval

    if quality < 3:
        n = 0
        I = 1
    else:
        n += 1
        if n == 1:
            I = 1
        elif n == 2:
            I = 6
        else:
            I = round(I * EF)

    # Update EF
    EF = EF + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    EF = max(1.3, EF)

    # Next review date
    next_review = timezone.now() + timedelta(days=I)

    # Save back
    progress.repetition = n
    progress.interval = I
    progress.easiness_factor = EF
    progress.next_review = next_review
    progress.last_reviewed = timezone.now()

    progress.save()

    return progress