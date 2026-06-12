"""
Views for Quiz Generator Application
"""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Avg, Q
from django.utils import timezone
import random
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import QuestionProgress
from django.utils import timezone
from .models import Document, Question, Quiz, QuizAttempt, QuizAnswer, UserPerformance
from .question_generator import question_generator
import os
from .sm2 import posterior_to_quality, apply_sm2
from .models import QuestionProgress
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import QuizAttempt
from collections import defaultdict
from .analytics import (
    compute_mastery_by_difficulty,
    bloom_mastery,
    mastery_trend,
    DIFFICULTY_WEIGHTS
)
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
import json

from .models import QuizAttempt, Question, QuizAnswer, QuestionProgress
from .sm2 import posterior_to_quality, apply_sm2
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.db.models import Max
from .models import Quiz, QuizAttempt
from .analytics import (
    compute_mastery_by_difficulty,
    bloom_mastery,
)


# ============================================
# AUTHENTICATION VIEWS
# ============================================

def signup_view(request):
    """User registration"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    
    return render(request, 'quiz_app/signup.html', {'form': form})


def login_view(request):
    """User login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    
    return render(request, 'quiz_app/login.html', {'form': form})


@login_required
def logout_view(request):
    """User logout"""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


# ============================================
# DASHBOARD VIEW
# ============================================

@login_required
def dashboard_view(request):
    """Main dashboard"""
    context = {
        'total_documents': Document.objects.filter(user=request.user).count(),
        'total_questions': Question.objects.filter(document__user=request.user).count(),
        'total_quizzes': Quiz.objects.filter(user=request.user).count(),
        'total_attempts': QuizAttempt.objects.filter(user=request.user).count(),
        'recent_documents': Document.objects.filter(user=request.user)[:5],
        'recent_quizzes': Quiz.objects.filter(user=request.user)[:5],
    }
    
    # Calculate average score
    attempts = QuizAttempt.objects.filter(user=request.user, is_completed=True)
    if attempts.exists():
        context['average_score'] = attempts.aggregate(Avg('score'))['score__avg']
    else:
        context['average_score'] = 0
    
    return render(request, 'quiz_app/dashboard.html', context)


# ============================================
# DOCUMENT UPLOAD & PROCESSING
# ============================================


@login_required
def upload_document_view(request):
    """Upload document and generate questions"""

    if request.method == 'POST':
        title = request.POST.get('title')
        file = request.FILES.get('file')
        num_questions = int(request.POST.get('num_questions', 10))

        # ❌ No file check
        if not file:
            messages.error(request, 'Please select a file to upload.')
            return redirect('upload_document')

        # ✅ File type validation
        allowed_extensions = ['.pdf', '.docx', '.txt']
        ext = os.path.splitext(file.name)[1].lower()

        if ext not in allowed_extensions:
            messages.error(request, 'Unsupported file type. Upload PDF, DOCX, or TXT.')
            return redirect('upload_document')

        # ✅ File size validation (10MB)
        if file.size > 10 * 1024 * 1024:
            messages.error(request, 'File size exceeds 10MB limit.')
            return redirect('upload_document')

        # ✅ Create document record
        document = Document.objects.create(
            user=request.user,
            title=title or file.name,
            file=file
        )

        try:
            # 🔥 Extract text
            text = question_generator.extract_text(document.file.path)

            if not text or len(text.strip()) < 50:
                messages.error(request, 'Could not extract meaningful text from document.')
                document.delete()
                return redirect('upload_document')

            # 🔥 Generate questions
            generated_questions = question_generator.generate_questions_from_text(
                text,
                num_questions
            )

            if not generated_questions:
                messages.error(request, 'Failed to generate questions.')
                document.delete()
                return redirect('upload_document')

            # ✅ Save questions
            for q_data in generated_questions:
                Question.objects.create(
                    document=document,
                    question=q_data.get('question', ''),
                    context=q_data.get('context', ''),
                    correct_answer=q_data.get('correct_answer', ''),
                    distractor_1=q_data.get('distractors', [''])[0] if len(q_data.get('distractors', [])) > 0 else '',
                    distractor_2=q_data.get('distractors', [''])[1] if len(q_data.get('distractors', [])) > 1 else '',
                    distractor_3=q_data.get('distractors', [''])[2] if len(q_data.get('distractors', [])) > 2 else '',
                    bloom_level=q_data.get('bloom_level', 'Remember'),
                    difficulty=q_data.get('difficulty', 'Easy')
                )

            # ✅ Mark processed
            document.processed = True
            document.save()

            messages.success(request, f'Successfully generated {len(generated_questions)} questions!')
            return redirect('view_questions', document_id=document.id)

        except Exception as e:
            print("❌ Processing Error:", e)
            messages.error(request, f'Error processing document: {str(e)}')
            document.delete()
            return redirect('upload_document')

    return render(request, 'quiz_app/upload_document.html')


@login_required
def view_questions_view(request, document_id):
    """View generated questions from a document"""

    document = get_object_or_404(
        Document,
        id=document_id,
        user=request.user
    )

    questions = Question.objects.filter(document=document)

    # Optimized single query aggregation
    stats = questions.aggregate(
        easy_count=Count('id', filter=Q(difficulty='Easy')),
        medium_count=Count('id', filter=Q(difficulty='Medium')),
        hard_count=Count('id', filter=Q(difficulty='Hard')),
    )

    context = {
        'document': document,
        'questions': questions,
        'total_count': questions.count(),
        **stats
    }

    return render(request, 'quiz_app/view_questions.html', context)


# ============================================
# QUIZ CREATION & MANAGEMENT
# ============================================

@login_required
def create_quiz_view(request):
    """Create a new quiz"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        duration = int(request.POST.get('duration', 30))
        question_ids = request.POST.getlist('questions')
        
        if not title or not question_ids:
            messages.error(request, 'Please provide title and select questions.')
            return redirect('create_quiz')
        
        # Create quiz
        quiz = Quiz.objects.create(
            user=request.user,
            title=title,
            description=description,
            duration=duration
        )
        
        # Add questions
        questions = Question.objects.filter(id__in=question_ids, document__user=request.user)
        quiz.questions.set(questions)
        
        messages.success(request, f'Quiz "{title}" created successfully!')
        return redirect('quiz_list')
    
    # Get all available questions
    documents = Document.objects.filter(user=request.user, processed=True)
    questions = Question.objects.filter(document__user=request.user)
    
    context = {
        'documents': documents,
        'questions': questions,
    }
    
    return render(request, 'quiz_app/create_quiz.html', context)


@login_required
def quiz_list_view(request):
    """List all quizzes"""
    quizzes = Quiz.objects.filter(user=request.user)
    
    context = {
        'quizzes': quizzes,
    }
    
    return render(request, 'quiz_app/quiz_list.html', context)


@login_required
def quiz_detail_view(request, quiz_id):
    """View quiz details"""
    quiz = get_object_or_404(Quiz, id=quiz_id, user=request.user)
    
    context = {
        'quiz': quiz,
        'questions': quiz.questions.all(),
    }
    
    return render(request, 'quiz_app/quiz_detail.html', context)


# ============================================
# QUIZ TAKING
# ============================================



@login_required
def take_quiz_view(request, quiz_id):
    """Start quiz (with prior knowledge) + render shuffled questions"""

    quiz = get_object_or_404(Quiz, id=quiz_id)

    # ----------------------------------
    # 🔥 START QUIZ (POST)
    # ----------------------------------
    if request.method == "POST":
        prior = float(request.POST.get("prior_knowledge", 0.7))

        # Prevent duplicate unfinished attempts
        existing_attempt = QuizAttempt.objects.filter(
            user=request.user,
            quiz=quiz,
            is_completed=False
        ).first()

        if existing_attempt:
            return redirect("take_quiz", quiz_id=quiz.id)

        # Create new attempt
        QuizAttempt.objects.create(
            user=request.user,
            quiz=quiz,
            prior_knowledge=prior
        )

        return redirect("take_quiz", quiz_id=quiz.id)

    # ----------------------------------
    # 🔥 LOAD QUIZ (GET)
    # ----------------------------------
    attempt = QuizAttempt.objects.filter(
        user=request.user,
        quiz=quiz,
        is_completed=False
    ).first()

    # If no attempt → redirect to detail page
    if not attempt:
        messages.warning(request, "Please start the quiz first.")
        return redirect("quiz_detail", quiz_id=quiz.id)

    # ----------------------------------
    # 🔥 PREPARE QUESTIONS (SHUFFLED)
    # ----------------------------------
    questions_data = []

    for q in quiz.questions.all():

        options = q.get_all_options().copy()  # copy to avoid modifying original
        random.shuffle(options)

        questions_data.append({
            "question": q,
            "options": options,
        })

    context = {
        "quiz": quiz,
        "attempt": attempt,
        "questions_data": questions_data,  # 🔥 USE THIS IN TEMPLATE
    }

    return render(request, "quiz_app/take_quiz.html", context)





@login_required
@require_http_methods(["POST"])
def complete_quiz_view(request, attempt_id):
    """Process quiz submission + Bayesian + SM-2 update"""

    attempt = get_object_or_404(
        QuizAttempt,
        id=attempt_id,
        user=request.user
    )

    data = json.loads(request.body)
    submitted_answers = data.get("answers", {})

    correct_count = 0
    total_questions = len(submitted_answers)

    with transaction.atomic():

        for question_id, selected_option in submitted_answers.items():

            # ✅ Get question
            question = Question.objects.get(id=question_id)

            selected_option = int(selected_option)
            options = question.get_all_options()

            # ⚠️ Safety check (avoid index errors)
            if selected_option < 1 or selected_option > len(options):
                continue

            selected_answer_text = options[selected_option - 1]

            # ✅ Check correctness
            is_correct = selected_answer_text == question.correct_answer

            if is_correct:
                correct_count += 1

            # ✅ Save answer
            QuizAnswer.objects.update_or_create(
                attempt=attempt,
                question=question,
                defaults={
                    "selected_answer": selected_answer_text,
                    "is_correct": is_correct
                }
            )

            # ----------------------------------------
            # 🔥 Bayesian Posterior Calculation
            # ----------------------------------------
            num_options = len(options)
            p0 = attempt.prior_knowledge

            if not is_correct:
                posterior = 0.0
            else:
                p_guess = 1.0 / num_options
                posterior = p0 / (p0 + (1 - p0) * p_guess)

            # ----------------------------------------
            # 🔥 Convert Posterior → Quality (SM-2)
            # ----------------------------------------
            quality = posterior_to_quality(posterior)

            # ----------------------------------------
            # 🔥 Get/Create Question Progress
            # ----------------------------------------
            progress, _ = QuestionProgress.objects.get_or_create(
                user=request.user,
                question=question
            )

            # ----------------------------------------
            # 🔥 Apply SM-2 Scheduling
            # ----------------------------------------
            apply_sm2(progress, quality)

        # ----------------------------------------
        # ✅ Final Score Calculation
        # ----------------------------------------
        score = (correct_count / total_questions) * 100 if total_questions > 0 else 0

        attempt.score = score
        attempt.is_completed = True
        attempt.completed_at = timezone.now()
        attempt.save()

    return redirect("quiz_result", attempt_id=attempt.id)



@login_required
def quiz_result_view(request, attempt_id):
    """View quiz results"""
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, user=request.user)
    answers = QuizAnswer.objects.filter(attempt=attempt).select_related('question')
    
    context = {
        'attempt': attempt,
        'answers': answers,
        'total_questions': answers.count(),
        'correct_answers': answers.filter(is_correct=True).count(),
    }
    
    return render(request, 'quiz_app/quiz_result.html', context)


# ============================================
# ANALYTICS & PERFORMANCE
# ============================================

@login_required
def analytics_view(request):
    user = request.user

    # ----------------------------------
    # Due Questions (SM-2 🔥)
    # ----------------------------------
    due_questions = QuestionProgress.objects.filter(
        user=user,
        next_review__lte=timezone.now()
    ).select_related("question")

    # ----------------------------------
    # Get quizzes attempted
    # ----------------------------------
    attempted_quiz_ids = QuizAttempt.objects.filter(
        user=user,
        is_completed=True
    ).values_list("quiz_id", flat=True).distinct()

    quizzes = Quiz.objects.filter(id__in=attempted_quiz_ids)

    selected_quiz_id = request.GET.get("quiz")

    if not selected_quiz_id and quizzes.exists():
        selected_quiz_id = quizzes.first().id

    selected_quiz = None
    attempts = []

    if selected_quiz_id:
        selected_quiz = get_object_or_404(Quiz, id=selected_quiz_id)

        attempts = QuizAttempt.objects.filter(
            user=user,
            quiz=selected_quiz,
            is_completed=True
        ).order_by("-completed_at").prefetch_related("answers__question")

    # ----------------------------------
    # Latest 2 attempts
    # ----------------------------------
    latest_two = attempts[:2]

    attempt_analytics = []
    trend_labels = []
    trend_mastery = []
    trend_score = []

    for attempt in reversed(latest_two):

        answers = attempt.answers.all()

        mastery_by_diff, overall_mastery, per_q_post, feedback = \
            compute_mastery_by_difficulty(
                answers,
                prior_knowledge=attempt.prior_knowledge
            )

        bloom_scores = bloom_mastery(per_q_post)

        attempt_analytics.append({
            "attempt": attempt,
            "prior": round(attempt.prior_knowledge, 2),
            "overall_mastery": round(overall_mastery * 100, 1),
            "raw_score": attempt.score,
            "difficulty": mastery_by_diff,
            "bloom": bloom_scores,
            "feedback": feedback,
        })

        trend_labels.append(attempt.completed_at.strftime("%d %b"))
        trend_mastery.append(round(overall_mastery * 100, 1))
        trend_score.append(attempt.score)

    context = {
        "quizzes": quizzes,
        "selected_quiz": selected_quiz,
        "attempt_analytics": attempt_analytics,
        "trend_labels": trend_labels,
        "trend_mastery": trend_mastery,
        "trend_score": trend_score,

        # 🔥 NEW SM-2 DATA
        "due_questions": due_questions[:10],  # limit
    }

    return render(request, "quiz_app/analytics.html", context)