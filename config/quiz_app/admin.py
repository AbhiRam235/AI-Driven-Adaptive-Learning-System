"""
Admin configuration for Quiz App
"""
from django.contrib import admin
from .models import Document, Question, Quiz, QuizAttempt, QuizAnswer, UserPerformance


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'uploaded_at', 'processed']
    list_filter = ['processed', 'uploaded_at']
    search_fields = ['title', 'user__username']
    readonly_fields = ['uploaded_at']


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'question_preview', 'difficulty', 'bloom_level', 'document']
    list_filter = ['difficulty', 'bloom_level', 'created_at']
    search_fields = ['question', 'correct_answer']
    readonly_fields = ['created_at']
    
    def question_preview(self, obj):
        return obj.question[:50] + '...' if len(obj.question) > 50 else obj.question
    question_preview.short_description = 'Question'


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'duration', 'question_count', 'created_at', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'description', 'user__username']
    filter_horizontal = ['questions']
    readonly_fields = ['created_at']
    
    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Questions'


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'quiz', 'score', 'is_completed', 'started_at', 'completed_at']
    list_filter = ['is_completed', 'started_at']
    search_fields = ['user__username', 'quiz__title']
    readonly_fields = ['started_at', 'completed_at', 'score']


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ['attempt', 'question_preview', 'is_correct', 'answered_at']
    list_filter = ['is_correct', 'answered_at']
    search_fields = ['attempt__user__username', 'question__question']
    readonly_fields = ['answered_at', 'is_correct']
    
    def question_preview(self, obj):
        return obj.question.question[:50] + '...' if len(obj.question.question) > 50 else obj.question.question
    question_preview.short_description = 'Question'


@admin.register(UserPerformance)
class UserPerformanceAdmin(admin.ModelAdmin):
    list_display = ['user', 'difficulty_level', 'bloom_level', 'total_attempted', 'total_correct', 'accuracy_rate']
    list_filter = ['difficulty_level', 'bloom_level']
    search_fields = ['user__username']
    readonly_fields = ['last_updated']