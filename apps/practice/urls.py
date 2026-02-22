from django.urls import path
from . import views

urlpatterns = [
    path('',                              views.index,            name='practice_index'),
    path('sets/<int:subject_id>/',        views.question_set_list, name='practice_set_list'),
    path('quiz/<int:set_id>/',            views.quiz,             name='practice_quiz'),
    path('quiz/<int:set_id>/submit/',     views.submit_quiz,      name='practice_submit'),
    path('result/<int:attempt_id>/',      views.result,           name='practice_result'),
    path('api/generate/',                 views.ai_generate,      name='practice_ai_generate'),
]
