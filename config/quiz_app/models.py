"""
Models for Quiz Generator Application
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Document(models.Model):
    """Stores uploaded documents"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return self.title


class Question(models.Model):
    """Stores generated questions"""
    DIFFICULTY_CHOICES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]
    
    BLOOM_LEVEL_CHOICES = [
        ('Knowledge', 'Knowledge'),
        ('Remembering', 'Remembering'),
        ('Understanding', 'Understanding'),
        ('Applying', 'Applying'),
        ('Analyzing', 'Analyzing'),
        ('Evaluating', 'Evaluating'),
        ('Creating', 'Creating'),
    ]
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='questions')
    question = models.TextField()
    context = models.TextField()
    correct_answer = models.CharField(max_length=500)
    distractor_1 = models.CharField(max_length=500)
    distractor_2 = models.CharField(max_length=500)
    distractor_3 = models.CharField(max_length=500)
    bloom_level = models.CharField(max_length=50, choices=BLOOM_LEVEL_CHOICES, default='Understanding')
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='Medium')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['id']
    
    def __str__(self):
        return f"Q{self.id}: {self.question[:50]}..."
    
    def get_all_options(self):
        """Returns all options as a list"""
        return [
            self.correct_answer,
            self.distractor_1,
            self.distractor_2,
            self.distractor_3
        ]


class Quiz(models.Model):
    """Stores quiz metadata"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    duration = models.IntegerField(help_text='Duration in minutes')
    questions = models.ManyToManyField(Question, related_name='quizzes')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Quizzes'
    
    def __str__(self):
        return self.title
    
    def get_total_questions(self):
        return self.questions.count()


class QuizAttempt(models.Model):
    """Stores quiz attempt records"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(default=0.0)
    is_completed = models.BooleanField(default=False)
    prior_knowledge = models.FloatField(default=0.7)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.quiz.title} ({self.started_at})"
    
    def calculate_score(self):
        """Calculate the score based on correct answers"""
        total = self.answers.count()
        if total == 0:
            return 0
        correct = self.answers.filter(is_correct=True).count()
        return (correct / total) * 100
    
    def complete_attempt(self):
        """Mark the attempt as completed"""
        self.is_completed = True
        self.completed_at = timezone.now()
        self.score = self.calculate_score()
        self.save()
# models.py



class QuizAnswer(models.Model):
    """Stores individual question answers"""
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answer = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['answered_at']
        unique_together = ['attempt', 'question']
    
    def __str__(self):
        return f"{self.attempt.user.username} - Q{self.question.id} - {'✓' if self.is_correct else '✗'}"
    
    def save(self, *args, **kwargs):
        """Auto-check if answer is correct"""
        self.is_correct = (self.selected_answer == self.question.correct_answer)
        super().save(*args, **kwargs)


class UserPerformance(models.Model):
    """Tracks user performance metrics for adaptive learning"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='performance')
    difficulty_level = models.CharField(max_length=20, choices=Question.DIFFICULTY_CHOICES)
    bloom_level = models.CharField(max_length=50, choices=Question.BLOOM_LEVEL_CHOICES)
    total_attempted = models.IntegerField(default=0)
    total_correct = models.IntegerField(default=0)
    accuracy_rate = models.FloatField(default=0.0)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'difficulty_level', 'bloom_level']
        ordering = ['user', 'difficulty_level']
    
    def __str__(self):
        return f"{self.user.username} - {self.difficulty_level} - {self.bloom_level}"
    
    def update_performance(self, is_correct):
        """Update performance metrics"""
        self.total_attempted += 1
        if is_correct:
            self.total_correct += 1
        self.accuracy_rate = (self.total_correct / self.total_attempted) * 100 if self.total_attempted > 0 else 0
        self.save()

# models.py

class QuestionProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    repetition = models.IntegerField(default=0)  # n
    interval = models.IntegerField(default=0)    # days
    easiness_factor = models.FloatField(default=2.5)  # EF

    next_review = models.DateTimeField(null=True, blank=True)
    last_reviewed = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'question']

    def __str__(self):
        return f"{self.user.username} - Q{self.question.id}"