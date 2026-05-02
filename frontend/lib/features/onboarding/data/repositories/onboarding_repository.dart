import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/storage/secure_storage.dart';
import '../models/onboarding_models.dart';

abstract class OnboardingRepository {
  Future<Map<String, dynamic>> registerUser({
    required String name,
    required String email,
    required String password,
  });

  Future<List<AssessmentQuestion>> getAssessmentQuestions({
    required String userId,
    required List<LearningCategory> categories,
  });

  Future<AssessmentResult> submitAssessmentResults({
    required String userId,
    required List<AssessmentAnswer> answers,
  });

  Future<LearningPath> generateLearningPath(UserProfile userProfile);

  Future<void> updateUserProfile(UserProfile userProfile);

  Future<UserProfile?> getUserProfile(String userId);

  Future<List<LearningCategory>> getRecommendedCategories(String userId);

  // New: Start a concrete lesson session for a module/day
  Future<LessonSession> startLearningSession({
    required String moduleId,
    int dayNumber = 1,
  });

  // Learning path persistence methods
  Future<void> saveLearningPath(LearningPath path);
  Future<LearningPath?> loadLearningPath();
  Future<void> updateModuleProgress(
    String moduleId,
    double progress,
    bool unlockNext,
  );

  // Learning session completion
  Future<Map<String, dynamic>> completeLearningSession({
    required String sessionId,
    required String moduleId,
    int dayNumber = 1,
    required int correct,
    required int total,
    required int timeSpentMinutes,
  });

  // Save progress for individual steps (per-activity save)
  Future<void> saveStepProgress({
    required String sessionId,
    required String moduleId,
    required int dayNumber,
    required int stepIndex,
    required int correct,
    required int total,
    required int timeSpentMinutes,
    String? skillType,
  });

  // Allow cancelling in-flight assessment polling
  void cancelAssessmentPolling();

  // Set callback for assessment progress updates
  void setAssessmentProgressCallback(
    void Function(int progress, String message)? callback,
  );
}

class OnboardingRepositoryImpl implements OnboardingRepository {
  final ApiClient _apiClient;
  final SecureStorage _storage;
  CancelToken? _assessmentCancelToken;
  CancelToken? _journeyCancelToken;
  CancelToken? _sessionCancelToken;

  OnboardingRepositoryImpl(this._apiClient, this._storage);

  // Exposed for tests and offline fallback: construct a local, mixed-skill session
  LessonSession buildLocalFallbackSessionForTest(
    LearningModule module,
    int dayNumber,
  ) {
    final levelDescriptions = {
      'A1': 'beginner',
      'A2': 'elementary',
      'B1': 'intermediate',
      'B2': 'upper-intermediate',
      'C1': 'advanced',
      'C2': 'proficient',
    };
    final levelDesc = levelDescriptions[module.level.code] ?? 'beginner';

    // Generate sample vocabulary based on category with conversational learning
    final vocabContent = _generateConversationalVocabulary(
      module.category.title,
      levelDesc,
    );

    // Generate grammar content with proper teaching flow
    final grammarContent = _generateConversationalGrammar(
      module.category.title,
      levelDesc,
      dayNumber,
    );

    // Generate speaking read-aloud content
    final speakingContent = _generateReadAloudTexts(
      module.category.title.toLowerCase(),
      module.level.code,
    );

    final steps = <LessonStep>[
      // Vocabulary FIRST - Conversational learning with teach-first approach
      LessonStep(
        stepType: 'vocabulary',
        title: 'Learn New Words • ${module.title}',
        content: null,
        estimatedMinutes: 6,
        contentJson: vocabContent,
      ),
      // Grammar SECOND - Learn rules with interactive examples
      LessonStep(
        stepType: 'grammar',
        title: 'Grammar Focus • ${module.title}',
        content: null,
        estimatedMinutes: 6,
        contentJson: grammarContent,
      ),
      // Reading THIRD - With a proper passage
      LessonStep(
        stepType: 'reading',
        title: 'Reading • ${module.title}',
        content: null,
        estimatedMinutes: 6,
        contentJson: {
          'text': _generateReadingPassage(module.category.title, levelDesc),
          'vocabulary_words': [], // Empty since shown in vocab step
          'comprehension_questions': _generateReadingQuestions(
            module.category.title,
          ),
        },
      ),
      // Listening FOURTH
      LessonStep(
        stepType: 'listening',
        title: 'Listening • ${module.title}',
        content: 'Listen to a short conversation and answer the questions.',
        estimatedMinutes: 5,
        contentJson: {
          'transcript': _generateListeningTranscript(module.category.title),
        },
      ),
      // Speaking FIFTH - Read aloud with actual text
      LessonStep(
        stepType: 'speaking',
        title: 'Speaking Practice • Read Aloud',
        content: 'Read the following sentences clearly and at a natural pace.',
        estimatedMinutes: 5,
        contentJson: {
          'mode': 'read_aloud',
          'prompt_text': speakingContent['primary'],
          'sentences': speakingContent['sentences'],
          'tips': [
            'Read each sentence clearly',
            'Maintain a natural, steady pace',
            'Focus on pronunciation of key words',
            'Try to express the meaning naturally',
          ],
          'vocabulary_focus': speakingContent['vocabulary_focus'],
        },
      ),
    ];

    final totalMinutes = steps.fold<int>(
      0,
      (sum, s) => sum + s.estimatedMinutes,
    );
    return LessonSession(
      sessionId: 'local_${module.id}_$dayNumber',
      moduleId: module.id,
      dayNumber: dayNumber,
      steps: steps,
      totalEstimatedMinutes: totalMinutes,
    );
  }

  /// Generate conversational vocabulary content with teach-first approach
  Map<String, dynamic> _generateConversationalVocabulary(
    String category,
    String level,
  ) {
    final sampleVocabulary = _generateSampleVocabulary(category);

    // Create conversational learning flow
    final conversationFlow = <Map<String, dynamic>>[];
    for (int i = 0; i < sampleVocabulary.length && i < 4; i++) {
      final word = sampleVocabulary[i];
      conversationFlow.add({
        'type': 'introduce',
        'content': "Let's learn a new word: **${word['word']}**",
        'word_data': word,
      });
      conversationFlow.add({
        'type': 'explain',
        'content': "${word['word']} means: ${word['definition']}",
      });
      conversationFlow.add({
        'type': 'example',
        'content': "Example: ${word['example']}",
      });
      if (i < sampleVocabulary.length - 1) {
        conversationFlow.add({
          'type': 'transition',
          'content': "Great! Now let's learn another word.",
        });
      }
    }

    // Generate practice questions based on the vocabulary
    final practiceQuestions = <Map<String, dynamic>>[];
    for (int i = 0; i < sampleVocabulary.length && i < 4; i++) {
      final word = sampleVocabulary[i];
      practiceQuestions.add({
        'question': 'What does "${word['word']}" mean?',
        'options': _generateDefinitionOptions(
          word['definition'] as String,
          sampleVocabulary,
          i,
        ),
        'answer': 0,
        'explanation': '${word['word']}: ${word['definition']}',
      });
    }

    return {
      'mode': 'conversational',
      'introduction':
          "Today you'll learn ${sampleVocabulary.length} new words about $category. Let's start!",
      'vocabulary_words': sampleVocabulary,
      'conversation_flow': conversationFlow,
      'practice_questions': practiceQuestions,
      'summary':
          "Excellent! You've learned ${sampleVocabulary.length} new words. Practice using them in sentences!",
    };
  }

  List<String> _generateDefinitionOptions(
    String correctDef,
    List<Map<String, dynamic>> allWords,
    int correctIndex,
  ) {
    final options = <String>[correctDef];
    for (int i = 0; i < allWords.length && options.length < 4; i++) {
      if (i != correctIndex) {
        options.add(allWords[i]['definition'] as String);
      }
    }
    // Add filler options if needed
    while (options.length < 4) {
      options.add('A type of action or behavior');
    }
    return options;
  }

  /// Generate grammar content with conversational teaching flow
  Map<String, dynamic> _generateConversationalGrammar(
    String category,
    String level,
    int dayNumber,
  ) {
    // Rotate through different grammar topics based on day number
    final grammarTopics = [
      {
        'grammar_point': 'Present Simple vs Present Continuous',
        'explanation':
            'We use Present Simple for habits, routines, and general truths. We use Present Continuous for actions happening right now or temporary situations.',
        'structure':
            'Present Simple: Subject + verb (base form)\nPresent Continuous: Subject + am/is/are + verb-ing',
        'when_to_use': [
          'Present Simple: habits, routines, facts, schedules',
          'Present Continuous: actions now, temporary situations, plans',
        ],
        'examples': [
          {
            'sentence': 'I work in an office.',
            'explanation': 'habit/routine - Present Simple',
          },
          {
            'sentence': 'She is working from home today.',
            'explanation': 'temporary situation - Present Continuous',
          },
          {
            'sentence': 'Water boils at 100 degrees.',
            'explanation': 'fact/general truth - Present Simple',
          },
          {
            'sentence': 'Look! The children are playing in the park.',
            'explanation': 'action happening now - Present Continuous',
          },
        ],
        'exercises': [
          {
            'question': 'She ___ to the gym every Monday.',
            'options': ['goes', 'is going', 'go', 'going'],
            'answer': 0,
            'explanation': 'Regular habit requires Present Simple (goes).',
          },
          {
            'question': 'Look! The children ___ in the park.',
            'options': ['play', 'plays', 'are playing', 'is playing'],
            'answer': 2,
            'explanation':
                'Action happening now requires Present Continuous (are playing).',
          },
          {
            'question': 'I usually ___ coffee in the morning.',
            'options': ['drink', 'am drinking', 'drinks', 'drinking'],
            'answer': 0,
            'explanation':
                '"Usually" indicates a habit, so we use Present Simple.',
          },
        ],
      },
      {
        'grammar_point': 'Past Simple Tense',
        'explanation':
            'We use Past Simple to talk about completed actions in the past. The action started and finished at a specific time.',
        'structure':
            'Subject + verb (past form)\nRegular verbs: add -ed (worked, played)\nIrregular verbs: special forms (went, saw, ate)',
        'when_to_use': [
          'Completed actions in the past',
          'Past habits and routines',
          'Sequences of past events',
        ],
        'examples': [
          {
            'sentence': 'I visited Paris last summer.',
            'explanation': 'completed action in the past',
          },
          {
            'sentence': 'She worked here for five years.',
            'explanation': 'past situation that ended',
          },
          {
            'sentence': 'We ate dinner and then watched a movie.',
            'explanation': 'sequence of past events',
          },
        ],
        'exercises': [
          {
            'question': 'Yesterday I ___ to the store.',
            'options': ['went', 'go', 'going', 'goes'],
            'answer': 0,
            'explanation':
                'Past action requires Past Simple (went is irregular).',
          },
          {
            'question': 'She ___ the book last week.',
            'options': ['finished', 'finishes', 'finish', 'finishing'],
            'answer': 0,
            'explanation':
                '"Last week" indicates past time, so we use Past Simple.',
          },
          {
            'question': 'They ___ in London in 2020.',
            'options': ['lived', 'live', 'living', 'lives'],
            'answer': 0,
            'explanation': 'Specific past time (2020) requires Past Simple.',
          },
        ],
      },
      {
        'grammar_point': 'Articles: A, An, The',
        'explanation':
            'Articles are small words that come before nouns. "A" and "an" are indefinite articles (for general things). "The" is the definite article (for specific things).',
        'structure':
            'A + consonant sound (a book, a university)\nAn + vowel sound (an apple, an hour)\nThe + specific noun',
        'when_to_use': [
          'A/An: first mention, one of many, general statements',
          'The: already mentioned, unique things, specific context',
        ],
        'examples': [
          {
            'sentence': 'I saw a dog in the park.',
            'explanation':
                'first mention of the dog (a), specific park we know (the)',
          },
          {
            'sentence': 'She is an engineer.',
            'explanation': 'one of many engineers, starts with vowel sound',
          },
          {
            'sentence': 'The sun rises in the east.',
            'explanation': 'unique things (only one sun)',
          },
        ],
        'exercises': [
          {
            'question': 'I need ___ umbrella because it\'s raining.',
            'options': ['an', 'a', 'the', '-'],
            'answer': 0,
            'explanation':
                '"Umbrella" starts with a vowel sound, so we use "an".',
          },
          {
            'question': '___ Eiffel Tower is in Paris.',
            'options': ['The', 'A', 'An', '-'],
            'answer': 0,
            'explanation': 'Specific, unique landmark requires "the".',
          },
          {
            'question': 'She wants to be ___ doctor.',
            'options': ['a', 'an', 'the', '-'],
            'answer': 0,
            'explanation':
                'One of many doctors, "doctor" starts with consonant sound.',
          },
        ],
      },
    ];

    final topicIndex = (dayNumber - 1) % grammarTopics.length;
    final topic = grammarTopics[topicIndex];

    return {
      'mode': 'conversational',
      'introduction':
          "Today we'll learn about ${topic['grammar_point']}. This is an important grammar concept that will help you speak and write better English!",
      ...topic,
      'usage_tips': topic['when_to_use'],
      'common_mistakes': [
        'Confusing when to use each form',
        'Forgetting the correct verb form',
      ],
      'summary':
          "Great job! You've learned about ${topic['grammar_point']}. Practice using it in your conversations!",
    };
  }

  List<Map<String, dynamic>> _generateReadingQuestions(String category) {
    return [
      {
        'question': 'What is the main topic of this passage?',
        'options': [category, 'Sports', 'Weather', 'History'],
        'answer': 0,
        'explanation': 'The passage is about $category.',
      },
      {
        'question': 'What is the purpose of this text?',
        'options': [
          'To inform the reader',
          'To tell a joke',
          'To sell a product',
          'To complain',
        ],
        'answer': 0,
        'explanation': 'This is an informative text about $category.',
      },
    ];
  }

  String _generateListeningTranscript(String category) {
    final transcripts = {
      'Daily Life': '''Person A: Good morning! How's your day going?
Person B: Pretty good, thanks! I woke up early today and had a nice breakfast.
Person A: That sounds great. What did you have?
Person B: I had some toast with eggs and a cup of coffee. It's my usual morning routine.
Person A: Nice! I should try waking up earlier too. What time do you usually get up?
Person B: Around 6:30. It gives me time to exercise before work.''',
      'Food & Dining': '''Person A: Have you tried the new restaurant downtown?
Person B: Not yet, but I've heard it's really good. What's the cuisine like?
Person A: It's Italian. The pasta is amazing, and they have delicious appetizers.
Person B: That sounds wonderful. Is it expensive?
Person A: It's reasonable. The portions are generous too.
Person B: Great, let's go there this weekend!''',
      'Travel': '''Person A: I'm planning a trip to Europe next month.
Person B: How exciting! Which countries are you visiting?
Person A: I'm going to France and Italy. I've always wanted to see the Eiffel Tower.
Person B: That sounds amazing. Have you booked your accommodation?
Person A: Yes, I found a nice hotel near the city center. It's got great reviews.
Person B: Perfect! Don't forget to try the local food!''',
    };
    return transcripts[category] ?? transcripts['Daily Life']!;
  }

  List<Map<String, dynamic>> _generateSampleVocabulary(String category) {
    final vocabularyByCategory = {
      'Daily Life': [
        {
          'word': 'routine',
          'definition': 'A regular way of doing things in a particular order',
          'example': 'My morning routine includes exercise and breakfast.',
          'part_of_speech': 'noun',
        },
        {
          'word': 'household',
          'definition': 'All the people living together in a house',
          'example': 'Every household has different rules.',
          'part_of_speech': 'noun',
        },
        {
          'word': 'chores',
          'definition': 'Regular tasks that need to be done at home',
          'example': 'I do my chores every weekend.',
          'part_of_speech': 'noun',
        },
        {
          'word': 'schedule',
          'definition': 'A plan that shows when activities will happen',
          'example': 'I check my schedule every morning.',
          'part_of_speech': 'noun',
        },
      ],
      'Food & Dining': [
        {
          'word': 'appetizer',
          'definition': 'A small dish served before the main meal',
          'example': 'We ordered soup as an appetizer.',
          'part_of_speech': 'noun',
        },
        {
          'word': 'cuisine',
          'definition': 'A style of cooking',
          'example': 'Italian cuisine is popular worldwide.',
          'part_of_speech': 'noun',
        },
        {
          'word': 'ingredients',
          'definition': 'Foods that are combined to make a dish',
          'example': 'This recipe requires fresh ingredients.',
          'part_of_speech': 'noun',
        },
        {
          'word': 'delicious',
          'definition': 'Having a very pleasant taste',
          'example': 'The pasta was absolutely delicious.',
          'part_of_speech': 'adjective',
        },
      ],
      'Travel': [
        {
          'word': 'destination',
          'definition': 'The place where someone is going',
          'example': 'Paris is a popular tourist destination.',
          'part_of_speech': 'noun',
        },
        {
          'word': 'itinerary',
          'definition': 'A plan of a journey',
          'example': 'Our itinerary includes three cities.',
          'part_of_speech': 'noun',
        },
        {
          'word': 'accommodation',
          'definition': 'A place to stay, like a hotel',
          'example': 'We booked accommodation near the beach.',
          'part_of_speech': 'noun',
        },
        {
          'word': 'departure',
          'definition': 'The act of leaving a place',
          'example': 'The departure time is 8 AM.',
          'part_of_speech': 'noun',
        },
      ],
      'Business': [
        {
          'word': 'negotiate',
          'definition': 'To discuss to reach an agreement',
          'example': 'We need to negotiate the contract terms.',
          'part_of_speech': 'verb',
        },
        {
          'word': 'deadline',
          'definition': 'A time by which something must be completed',
          'example': 'The project deadline is next Friday.',
          'part_of_speech': 'noun',
        },
        {
          'word': 'presentation',
          'definition': 'A talk given to an audience',
          'example': 'I have a presentation tomorrow.',
          'part_of_speech': 'noun',
        },
        {
          'word': 'collaboration',
          'definition': 'Working together with others',
          'example': 'This project requires team collaboration.',
          'part_of_speech': 'noun',
        },
      ],
    };

    return vocabularyByCategory[category] ??
        vocabularyByCategory['Daily Life']!;
  }

  String _generateReadingPassage(String category, String level) {
    final passages = {
      'Daily Life':
          '''A typical day for most people starts in the morning. Many people have a morning routine that helps them prepare for the day. This routine might include having breakfast, taking a shower, and getting dressed.

During the day, people often work or study. Some people work from home, while others go to an office. After work, many people like to relax. They might watch television, read a book, or spend time with family and friends.

In the evening, people usually have dinner. This is often a good time for families to talk about their day. Before going to bed, some people like to prepare for the next day by setting out their clothes or making a to-do list.

Good habits and routines can help us be more productive and feel better. What is your daily routine like?''',
      'Food & Dining':
          '''Food is an important part of every culture around the world. Different countries have different types of cuisine. Italian food is known for pasta and pizza. Japanese food includes sushi and ramen. Indian food is famous for its spices and curries.

When eating at a restaurant, you usually start by looking at the menu. You might order an appetizer to start, followed by a main course. Many people also enjoy dessert at the end of their meal.

Cooking at home can be healthier and more affordable than eating out. To cook well, you need fresh ingredients and good recipes. Many people learn to cook from their parents or grandparents.

Whether you eat at home or in a restaurant, sharing food with others is always enjoyable. What is your favorite type of cuisine?''',
      'Travel':
          '''Traveling to new places is one of life's greatest adventures. Before any trip, good planning is essential. You need to choose your destination, book your accommodation, and plan your itinerary.

At the airport, you go through several steps. First, you check in your luggage. Then, you pass through security. Finally, you wait at your departure gate until it's time to board your flight.

When you arrive at your destination, there are many things to explore. You might visit famous landmarks, try local food, or learn about the history and culture. Taking photos helps you remember your experiences.

Every trip teaches us something new. We learn about different cultures and meet interesting people. What places would you like to visit?''',
      'Business':
          '''In the modern business world, communication skills are very important. Whether you are sending an email, giving a presentation, or having a meeting, clear communication helps you succeed.

Working in a team requires good collaboration. Team members need to share ideas, listen to each other, and work together toward common goals. Meeting deadlines is also important in business.

Many business deals involve negotiation. This means discussing terms until both sides reach an agreement. Good negotiators listen carefully and try to find solutions that work for everyone.

Technology has changed how we do business. Many people now work remotely and use video calls for meetings. However, the basic skills of communication and teamwork remain essential for success.''',
    };

    return passages[category] ?? passages['Daily Life']!;
  }

  @override
  Future<Map<String, dynamic>> registerUser({
    required String name,
    required String email,
    required String password,
  }) async {
    try {
      final response = await _apiClient.post(
        '/auth/register',
        data: {
          'name': name,
          'email': email,
          'password': password,
          'registration_source': 'onboarding',
        },
      );

      if (response.statusCode == 201 || response.statusCode == 200) {
        final data = response.data;

        // Store authentication tokens (now returned by register endpoint)
        if (data['access_token'] != null) {
          await _storage.write('access_token', data['access_token']);
        }
        if (data['refresh_token'] != null) {
          await _storage.write('refresh_token', data['refresh_token']);
        }
        
        // Store user data for immediate access
        if (data['user'] != null) {
          await _storage.write('user_data', jsonEncode(data['user']));
        }

        // Get user ID from the response (now nested under 'user' key)
        final userId = data['user']?['id'] ?? data['id'];

        return {
          'success': true,
          'userId': userId.toString(),
          'message': 'Registration successful',
        };
      } else {
        return {
          'success': false,
          'message': response.data['detail'] ?? 'Registration failed',
          'errorCode': response.statusCode.toString(),
        };
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 400) {
        final errorData = e.response?.data;
        return {
          'success': false,
          'message': errorData['detail'] ?? 'Invalid registration data',
          'errorCode': '400',
        };
      } else if (e.response?.statusCode == 409) {
        return {
          'success': false,
          'message': 'An account with this email already exists',
          'errorCode': '409',
        };
      } else {
        return {
          'success': false,
          'message': 'Network error. Please check your connection.',
          'errorCode': 'network_error',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'message': 'Unexpected error occurred. Please try again.',
        'errorCode': 'unknown_error',
      };
    }
  }

  /// Callback for progress updates during assessment loading
  void Function(int progress, String message)? _assessmentProgressCallback;

  @override
  void setAssessmentProgressCallback(
    void Function(int progress, String message)? callback,
  ) {
    _assessmentProgressCallback = callback;
  }

  @override
  Future<List<AssessmentQuestion>> getAssessmentQuestions({
    required String userId,
    required List<LearningCategory> categories,
  }) async {
    try {
      // Prefer async job-based assessment for scalability
      _assessmentCancelToken?.cancel('new assessment started');
      _assessmentCancelToken = CancelToken();

      _assessmentProgressCallback?.call(5, 'Starting assessment generation...');

      // Start job
      final startResp = await _apiClient.post(
        '/users/level-assessment/start',
        data: {
          'question_count': 20,
          'personalized': true,
          'user_preferences': categories.map((c) => c.id).toList(),
        },
        options: Options(
          receiveTimeout: const Duration(seconds: 20),
          sendTimeout: const Duration(seconds: 20),
        ),
        cancelToken: _assessmentCancelToken,
      );

      if (startResp.statusCode == 200 && startResp.data is Map) {
        final jobId = (startResp.data['job_id'] ?? '').toString();
        final initialStatus = (startResp.data['status'] ?? '').toString();

        if (jobId.isNotEmpty) {
          if (kDebugMode) {
            print('📋 Assessment job: $jobId, initial status: $initialStatus');
          }

          // Check if we got a stale/failed job back - the backend should have
          // already cleaned it up, but we need to handle the response
          if (initialStatus == 'failed' || initialStatus == 'cancelled') {
            final error =
                startResp.data['message']?.toString() ??
                'Previous assessment failed';
            if (kDebugMode) {
              print('⚠️ Got stale/failed job: $error');
            }
            throw AssessmentGenerationException(
              'Previous assessment attempt failed. Please try again.',
            );
          }

          // Poll for up to ~180s (3 minutes) - AI generation can take time
          final pollDeadline = DateTime.now().add(const Duration(seconds: 180));
          String? lastError;

          while (DateTime.now().isBefore(pollDeadline)) {
            if (_assessmentCancelToken?.isCancelled ?? false) {
              throw AssessmentCancelledException('Assessment was cancelled');
            }

            await Future.delayed(const Duration(seconds: 2));

            try {
              final statusResp = await _apiClient.get(
                '/users/level-assessment/job/$jobId',
                options: Options(
                  receiveTimeout: const Duration(seconds: 15),
                  sendTimeout: const Duration(seconds: 15),
                ),
                cancelToken: _assessmentCancelToken,
              );

              if (statusResp.statusCode == 200 && statusResp.data is Map) {
                final status = statusResp.data['status']?.toString() ?? '';
                final progress = statusResp.data['progress'] as int? ?? 0;
                final message =
                    statusResp.data['message']?.toString() ?? 'Processing...';

                // Report progress to UI
                _assessmentProgressCallback?.call(progress, message);

                if (kDebugMode) {
                  print(
                    '📊 Job status: $status, progress: $progress%, message: $message',
                  );
                }

                if (status == 'completed') {
                  final quiz =
                      (statusResp.data['quiz_data'] as Map?)
                          ?.cast<String, dynamic>() ??
                      {};
                  final List<dynamic> questions =
                      (quiz['questions'] as List?) ?? [];
                  if (questions.isNotEmpty) {
                    _assessmentProgressCallback?.call(100, 'Assessment ready!');
                    return questions
                        .map(
                          (q) => _transformBackendQuestion(
                            (q as Map).cast<String, dynamic>(),
                          ),
                        )
                        .toList();
                  }
                  // Completed but empty - this is a real error
                  lastError =
                      'Assessment completed but no questions were generated';
                  break;
                } else if (status == 'failed' || status == 'cancelled') {
                  lastError =
                      statusResp.data['error']?.toString() ??
                      'Assessment generation failed';
                  break;
                }
              }
            } on DioException catch (e) {
              // Network error during polling - continue polling
              if (kDebugMode) {
                print('⚠️ Poll error (continuing): ${e.message}');
              }
            }
          }

          // If we get here, polling timed out or job failed
          if (lastError != null) {
            throw AssessmentGenerationException(lastError);
          }
          throw AssessmentTimeoutException(
            'Assessment generation is taking longer than expected. Please try again.',
          );
        }
      }

      // If job start failed, throw an error instead of silently falling back
      throw AssessmentGenerationException(
        'Failed to start assessment generation. Please try again.',
      );
    } on AssessmentCancelledException {
      rethrow;
    } on AssessmentTimeoutException {
      rethrow;
    } on AssessmentGenerationException {
      rethrow;
    } on DioException catch (e) {
      if (kDebugMode) {
        print('💥 DioException in assessment: ${e.type} - ${e.message}');
      }
      if (e.type == DioExceptionType.cancel) {
        throw AssessmentCancelledException('Assessment was cancelled');
      }
      throw NetworkException(
        'Network error while loading assessment. Please check your connection.',
      );
    } catch (e) {
      if (kDebugMode) {
        print('💥 Unexpected assessment error: $e');
      }
      throw AssessmentGenerationException(
        'An unexpected error occurred. Please try again.',
      );
    }
  }

  @override
  void cancelAssessmentPolling() {
    _assessmentCancelToken?.cancel('assessment exit');
    _assessmentCancelToken = null;
  }

  /// Transform backend question format to Flutter model format
  AssessmentQuestion _transformBackendQuestion(
    Map<String, dynamic> backendQuestion,
  ) {
    if (kDebugMode) {
      print('🔄 Transforming backend question: ${backendQuestion['id']}');
    }

    // Handle options - fix nested array issue
    List<String> options = [];
    if (backendQuestion['options'] is List) {
      var rawOptions = backendQuestion['options'] as List;
      if (kDebugMode) {
        print('🔍 Raw options details:');
        print('  - rawOptions length: ${rawOptions.length}');
        print('  - rawOptions: $rawOptions');
      }

      for (int i = 0; i < rawOptions.length; i++) {
        if (kDebugMode) {
          print('  - rawOptions[$i] type: ${rawOptions[i].runtimeType}');
          print('  - rawOptions[$i] value: ${rawOptions[i]}');
          print('  - rawOptions[$i] is List: ${rawOptions[i] is List}');
        }
      }

      // Handle different option formats
      if (rawOptions.isNotEmpty) {
        if (rawOptions[0] is List) {
          // Handle nested array case: [["option1", "option2"]]
          if (kDebugMode) {
            print('🔄 Using nested array handling');
          }
          options = (rawOptions[0] as List)
              .map((opt) => opt.toString())
              .toList();
        } else if (rawOptions[0] is String &&
            rawOptions[0].toString().startsWith('[')) {
          // Handle string representation of array: "['option1', 'option2']"
          if (kDebugMode) {
            print('🔄 Using string array parsing');
          }
          try {
            String arrayString = rawOptions[0].toString();
            // Remove brackets and split by comma
            String content = arrayString.substring(1, arrayString.length - 1);
            // Split by comma and clean up quotes
            options = content.split(',').map((opt) {
              String cleaned = opt.trim();
              // Remove surrounding quotes if present
              if (cleaned.startsWith("'") && cleaned.endsWith("'")) {
                cleaned = cleaned.substring(1, cleaned.length - 1);
              } else if (cleaned.startsWith('"') && cleaned.endsWith('"')) {
                cleaned = cleaned.substring(1, cleaned.length - 1);
              }
              return cleaned;
            }).toList();
            if (kDebugMode) {
              print('✅ Parsed string array: $options');
            }
          } catch (e) {
            if (kDebugMode) {
              print('❌ Failed to parse string array: $e');
            }
            options = rawOptions.map((opt) => opt.toString()).toList();
          }
        } else {
          // Handle normal array case: ["option1", "option2"]
          if (kDebugMode) {
            print('🔄 Using normal array handling');
          }
          options = rawOptions.map((opt) => opt.toString()).toList();
        }
      }
    }
    if (kDebugMode) {
      print('✅ Final processed options: $options');
    }

    // Convert correct_answer string to correctAnswerIndex
    String correctAnswer = backendQuestion['correct_answer'] ?? '';
    int correctAnswerIndex = options.indexOf(correctAnswer);
    if (correctAnswerIndex == -1) {
      // If exact match not found, try case-insensitive match
      correctAnswerIndex = options.indexWhere(
        (opt) => opt.toLowerCase() == correctAnswer.toLowerCase(),
      );
    }
    if (correctAnswerIndex == -1) {
      correctAnswerIndex = 0; // Default to first option if not found
    }
    if (kDebugMode) {
      print('✅ Correct answer: "$correctAnswer" -> index: $correctAnswerIndex');
    }

    // Convert difficulty_level to CEFRLevel
    String difficultyLevel = backendQuestion['difficulty_level'] ?? 'A1';
    CEFRLevel targetLevel;
    switch (difficultyLevel.toUpperCase()) {
      case 'A1':
        targetLevel = CEFRLevel.a1;
        break;
      case 'A2':
        targetLevel = CEFRLevel.a2;
        break;
      case 'B1':
        targetLevel = CEFRLevel.b1;
        break;
      case 'B2':
        targetLevel = CEFRLevel.b2;
        break;
      case 'C1':
        targetLevel = CEFRLevel.c1;
        break;
      case 'C2':
        targetLevel = CEFRLevel.c2;
        break;
      default:
        targetLevel = CEFRLevel.a1;
    }
    if (kDebugMode) {
      print('✅ Difficulty level: "$difficultyLevel" -> $targetLevel');
    }

    // Map skill field
    String skillType = backendQuestion['skill'] ?? 'vocabulary';
    if (kDebugMode) {
      print('✅ Skill: "$skillType"');
    }

    // Question type and text answer (for fill in blank)
    final String questionType =
        (backendQuestion['question_type'] ?? 'multiple_choice').toString();
    final String? correctAnswerText = backendQuestion['correct_answer']
        ?.toString();

    // Sanitize question text for fill-in-the-blank: remove hints and answers
    String questionText = (backendQuestion['question'] ?? '').toString();
    if (questionType.toLowerCase() == 'fill_in_blank') {
      try {
        // Remove parentheses and bracketed hints like (study), [study], {study}
        questionText = questionText
            .replaceAll(RegExp(r"\([^)]*\)"), "")
            .replaceAll(RegExp(r"\[[^\]]*\]"), "")
            .replaceAll(RegExp(r"\{[^}]*\}"), "");
        // Replace any direct occurrences of the correct answer with blanks
        if (correctAnswerText != null && correctAnswerText.trim().isNotEmpty) {
          questionText = questionText.replaceAll(
            RegExp(RegExp.escape(correctAnswerText), caseSensitive: false),
            '____',
          );
        }
        // Collapse extra spaces
        questionText = questionText.replaceAll(RegExp(r"\s{2,}"), " ").trim();
      } catch (_) {
        // Fallback: ensure we don't leak answer
        questionText = questionText.replaceAll('(', '').replaceAll(')', '');
      }
    }

    // Extract passage/audio for reading/listening questions if provided
    final String? passage = backendQuestion['passage']?.toString();
    final String? audioUrl = backendQuestion['audio_url']?.toString();
    final String? audioText = backendQuestion['audio_text']?.toString();

    return AssessmentQuestion(
      id: backendQuestion['id']?.toString() ?? '1',
      passage: passage,
      question: questionText,
      options: options,
      correctAnswerIndex: correctAnswerIndex,
      targetLevel: targetLevel,
      skillType: skillType,
      explanation: backendQuestion['explanation'] ?? '',
      questionType: questionType,
      correctAnswerText: questionType.toLowerCase() == 'fill_in_blank'
          ? correctAnswerText
          : null,
      audioUrl: audioUrl,
      audioText: audioText,
    );
  }

  @override
  Future<AssessmentResult> submitAssessmentResults({
    required String userId,
    required List<AssessmentAnswer> answers,
  }) async {
    try {
      final response = await _apiClient.post(
        '/users/level-assessment/submit',
        data: {
          'answers': answers
              .map(
                (a) => {
                  'question_id': a.questionId,
                  'selected_answer': a.selectedAnswerIndex,
                  'text_answer': a.textAnswer,
                  'is_correct': a.isCorrect,
                  'time_spent': a.timeSpentSeconds,
                },
              )
              .toList(),
          'completed_at': DateTime.now().toIso8601String(),
        },
        options: Options(
          receiveTimeout: const Duration(minutes: 2),
          sendTimeout: const Duration(minutes: 2),
        ),
      );

      if (response.statusCode == 200) {
        final data = response.data;

        // Sanitize numeric fields to avoid null/NaN crashes on the results screen
        final rawSkillScores =
            (data['skill_breakdown'] ?? data['skill_scores'] ?? {}) as Map?;
        final sanitizedSkillScores = <String, double>{};
        rawSkillScores?.forEach((key, value) {
          final parsed = value is num
              ? value.toDouble()
              : double.tryParse('$value');
          if (parsed != null && parsed.isFinite) {
            sanitizedSkillScores[key.toString()] = parsed
                .clamp(0.0, 100.0)
                .toDouble();
          }
        });

        final rawOverall = data['score'] ?? data['overall_score'];
        double overallScore;
        if (rawOverall is num && rawOverall.isFinite) {
          overallScore = rawOverall.toDouble();
        } else if (sanitizedSkillScores.isNotEmpty) {
          final total = sanitizedSkillScores.values.fold<double>(
            0,
            (a, b) => a + b,
          );
          overallScore = total / sanitizedSkillScores.length;
        } else {
          overallScore = 0.0;
        }

        final feedbackRaw = (data['message'] ?? data['feedback'] ?? '')
            .toString()
            .trim();
        final feedback = feedbackRaw.isEmpty
            ? 'Assessment completed successfully!'
            : feedbackRaw;

        final recommendations =
            (data['recommendations'] as List?)
                ?.map((r) => r.toString().trim())
                .where((r) => r.isNotEmpty)
                .toList() ??
            const <String>[];

        // Parse the AI-analyzed results (backend AI-enhanced)
        return AssessmentResult(
          userId: userId,
          answers: answers,
          determinedLevel: CEFRLevel.values.firstWhere(
            (l) =>
                l.code.toLowerCase() ==
                (data['new_level'] ?? data['determined_level'] ?? 'B1')
                    .toString()
                    .toLowerCase(),
            orElse: () => CEFRLevel.b1,
          ),
          skillScores: sanitizedSkillScores,
          overallScore: overallScore,
          feedback: feedback,
          recommendations: recommendations,
          completedAt: DateTime.now(),
        );
      } else {
        throw Exception('Assessment submission failed');
      }
    } on DioException catch (e) {
      // Fallback analysis if backend fails
      if (kDebugMode) {
        print('Assessment submission error: ${e.message}');
      }
      return _analyzeAssessmentLocally(userId, answers);
    } catch (e) {
      if (kDebugMode) {
        print('Assessment analysis error: $e');
      }
      return _analyzeAssessmentLocally(userId, answers);
    }
  }

  @override
  Future<LearningPath> generateLearningPath(UserProfile userProfile) async {
    try {
      // Check if assessment results are missing and try to fetch them
      if (userProfile.assessmentResults.isEmpty) {
        try {
          final assessmentResponse = await _apiClient.get(
            '/users/assessment-results',
          ); // Hypothetical endpoint; adjust if needed
          if (assessmentResponse.statusCode == 200) {
            final data = assessmentResponse.data as Map<String, dynamic>;
            userProfile = userProfile.copyWith(
              assessmentResults: data['results'] ?? {},
            );
          }
        } catch (_) {
          // Silently continue with empty results
        }
      }
      // Cancel any previous journey generation
      _journeyCancelToken?.cancel('new journey generation');
      _journeyCancelToken = CancelToken();

      // Call the personal trainer API to generate a learning journey
      // Request a shorter initial journey window to avoid long waits; we can extend progressively
      const desiredWindow = 28; // request 4 weeks initially
      const clampedDays = desiredWindow;

      final requestData = {
        'user_level': userProfile.currentLevel.code,
        'preferred_categories': userProfile.preferredCategories
            .map((c) => c.id)
            .toList(),
        'learning_pace': userProfile.learningPace.id,
        'daily_study_time_minutes':
            userProfile.learningPace.averageDailyMinutes,
        'assessment_results': userProfile.assessmentResults,
        'journey_duration_days': clampedDays,
      };

      if (kDebugMode) {
        print('🚀 FRONTEND: Sending learning journey request: $requestData');
      }

      final response = await _apiClient.post(
        '/personal-trainer/learning-journey',
        data: requestData, // Send as JSON request body
        options: Options(
          receiveTimeout: const Duration(minutes: 3),
          sendTimeout: const Duration(minutes: 2),
        ),
        cancelToken: _journeyCancelToken,
      );

      if (response.statusCode == 200) {
        final data = response.data;
        if (kDebugMode) {
          print('📨 FRONTEND: Received learning journey response: $data');
        }

        // The backend returns journey_overview (now includes optional modules), not learning_modules directly
        final journeyOverview = data['journey'];
        final firstWeekContent = data['first_week_content'];

        // Try to parse modules from API, else fallback to simple modules
        final modules = <LearningModule>[];

        // Example expected shapes (best-effort parsing)
        // 1) journeyOverview may contain a 'modules' list (added server-side for easier parsing)
        if (journeyOverview is Map && journeyOverview['modules'] is List) {
          final apiModules = journeyOverview['modules'] as List;
          for (int i = 0; i < apiModules.length; i++) {
            final m = (apiModules[i] as Map).cast<String, dynamic>();
            modules.add(
              LearningModule(
                id: m['id']?.toString() ?? 'module_$i',
                title: m['title']?.toString() ?? 'Module ${i + 1}',
                category: userProfile.preferredCategories.isNotEmpty
                    ? userProfile.preferredCategories.first
                    : LearningCategory.dailyLife,
                level: userProfile.currentLevel,
                skills: List<String>.from(
                  m['skills'] ?? const ['vocabulary', 'reading'],
                ),
                estimatedMinutes: (m['estimated_minutes'] ?? 20) is num
                    ? (m['estimated_minutes'] as num).toInt()
                    : 20,
                isUnlocked: i == 0,
                progressPercentage: 0.0,
                description: m['description']?.toString() ?? '',
              ),
            );
          }
        }

        // 2) If not, attempt from weeks[0].daily_schedule or weeks[0].days
        if (modules.isEmpty &&
            journeyOverview is Map &&
            journeyOverview['weeks'] is List) {
          final weeks = (journeyOverview['weeks'] as List);
          if (weeks.isNotEmpty) {
            final w0 = (weeks[0] as Map).cast<String, dynamic>();
            final ds = (w0['daily_schedule'] ?? w0['days']) as List? ?? [];
            for (int i = 0; i < ds.length; i++) {
              final d = (ds[i] as Map).cast<String, dynamic>();
              final title =
                  d['session_title']?.toString() ??
                  d['title']?.toString() ??
                  'Day ${i + 1}';
              final est = (d['estimated_minutes'] ?? 20);
              modules.add(
                LearningModule(
                  id: 'day_${i + 1}',
                  title: title,
                  category: userProfile.preferredCategories.isNotEmpty
                      ? userProfile.preferredCategories.first
                      : LearningCategory.dailyLife,
                  level: userProfile.currentLevel,
                  skills: const ['mixed'],
                  estimatedMinutes: (est is num) ? est.toInt() : 20,
                  isUnlocked: i == 0,
                  progressPercentage: 0.0,
                  description: 'A set of lessons to practice mixed skills',
                ),
              );
            }
          }
        }

        // 3) If still empty, try fallback from first_week_content days/lessons
        if (modules.isEmpty &&
            firstWeekContent is Map &&
            firstWeekContent['days'] is List) {
          final days = firstWeekContent['days'] as List;
          for (int i = 0; i < days.length; i++) {
            final d = (days[i] as Map).cast<String, dynamic>();
            final lessons = (d['lessons'] ?? d['modules'] ?? []) as List? ?? [];
            final title = d['title']?.toString() ?? 'Day ${i + 1}';
            modules.add(
              LearningModule(
                id: 'day_${i + 1}',
                title: title,
                category: userProfile.preferredCategories.isNotEmpty
                    ? userProfile.preferredCategories.first
                    : LearningCategory.dailyLife,
                level: userProfile.currentLevel,
                skills: const ['mixed'],
                estimatedMinutes:
                    (d['estimated_minutes'] ?? (lessons.length * 10)) is num
                    ? (d['estimated_minutes'] as num).toInt()
                    : (lessons.length * 10),
                isUnlocked: i == 0,
                progressPercentage: 0.0,
                description: 'A set of lessons to practice mixed skills',
              ),
            );
          }
        }

        // Fallback: build simple modules per preference
        if (modules.isEmpty) {
          for (int i = 0; i < userProfile.preferredCategories.length; i++) {
            final category = userProfile.preferredCategories[i];
            modules.add(
              LearningModule(
                id: 'module_${category.id}_intro',
                title: '${category.title} - Introduction',
                category: category,
                level: userProfile.currentLevel,
                skills: ['vocabulary', 'reading'],
                estimatedMinutes: 15,
                isUnlocked: i == 0,
                progressPercentage: 0.0,
                description: 'Introduction to ${category.title} topics',
              ),
            );
          }
        }

        return LearningPath(
          userId: userProfile.userId,
          categories: userProfile.preferredCategories,
          currentLevel: userProfile.currentLevel,
          targetLevel: _getTargetLevel(userProfile.currentLevel),
          pace: userProfile.learningPace,
          modules: modules,
          createdAt: DateTime.now(),
          updatedAt: DateTime.now(),
        );
      } else {
        throw Exception('Learning path generation failed');
      }
    } on DioException catch (e) {
      if (kDebugMode) {
        print('Learning path generation error: ${e.message}');
      }
      return _generateMockLearningPath(userProfile);
    } catch (e) {
      if (kDebugMode) {
        print('Learning path error: $e');
      }
      return _generateMockLearningPath(userProfile);
    }
  }

  @override
  Future<void> updateUserProfile(UserProfile userProfile) async {
    try {
      // Build snake_case payload aligned with backend UserUpdate
      final payload = {
        'full_name': userProfile.name,
        'current_level': userProfile.currentLevel.code,
        'daily_goal_minutes': userProfile.learningPace.averageDailyMinutes,
        'notification_enabled': true,
        'preferred_study_time': null,
        'onboarding_completed': userProfile.onboardingCompleted,
      };

      if (kDebugMode) {
        print('📤 Updating user profile on backend: $payload');
      }

      final response = await _apiClient.put('/users/profile', data: payload);

      if (kDebugMode) {
        print(
          '✅ Profile updated successfully on backend: ${response.statusCode}',
        );
      }

      // Store user_data locally using snake_case, so router can read onboarding_completed.
      // This is best-effort; we should never block UX flows on storage failures.
      try {
        final localUserData = {
          'id': userProfile.userId,
          'email': userProfile.email,
          'full_name': userProfile.name,
          'username': userProfile.email.split('@').first,
          'current_level': userProfile.currentLevel.code,
          'native_language': 'Persian',
          'target_language': 'English',
          'daily_goal_minutes': userProfile.learningPace.averageDailyMinutes,
          'preferred_study_time': null,
          'notification_enabled': true,
          'onboarding_completed': userProfile.onboardingCompleted,
        };
        await _storage.write('user_data', jsonEncode(localUserData));

        // Also store full user profile for recovery
        await _storage.write('user_profile', jsonEncode(userProfile.toJson()));

        // Store a dedicated flag (small key) as a resilient fallback.
        if (userProfile.onboardingCompleted) {
          await _storage.markOnboardingComplete();
        } else {
          await _storage.clearOnboardingStatus();
        }

        if (kDebugMode) {
          print(
            '💾 User data stored locally with onboarding_completed=${userProfile.onboardingCompleted}',
          );
        }
      } catch (storageErr) {
        if (kDebugMode) {
          print('⚠️ Local profile persistence failed (non-fatal): $storageErr');
        }
      }
    } on DioException catch (e) {
      if (kDebugMode) {
        print('❌ Profile update API error: ${e.message}');
        print('💾 Storing locally as fallback...');
      }
      // Store locally even if API fails
      try {
        final fallbackUserData = {
          'id': userProfile.userId,
          'email': userProfile.email,
          'full_name': userProfile.name,
          'username': userProfile.email.split('@').first,
          'current_level': userProfile.currentLevel.code,
          'native_language': 'Persian',
          'target_language': 'English',
          'daily_goal_minutes': userProfile.learningPace.averageDailyMinutes,
          'preferred_study_time': null,
          'notification_enabled': true,
          'onboarding_completed': userProfile.onboardingCompleted,
        };
        await _storage.write('user_data', jsonEncode(fallbackUserData));
        await _storage.write('user_profile', jsonEncode(userProfile.toJson()));
        if (userProfile.onboardingCompleted) {
          await _storage.markOnboardingComplete();
        } else {
          await _storage.clearOnboardingStatus();
        }
      } catch (storageErr) {
        if (kDebugMode) {
          print('⚠️ Local fallback persistence failed (non-fatal): $storageErr');
        }
      }
    } catch (e) {
      // Defensive: never let onboarding flows crash due to profile sync.
      if (kDebugMode) {
        print('⚠️ Unexpected error updating profile (non-fatal): $e');
      }
      try {
        await _storage.write('user_profile', jsonEncode(userProfile.toJson()));
        if (userProfile.onboardingCompleted) {
          await _storage.markOnboardingComplete();
        }
      } catch (_) {}
    }
  }

  @override
  Future<UserProfile?> getUserProfile(String userId) async {
    try {
      // Prefer stored full user_profile if available
      final storedProfileJson = await _storage.read('user_profile');
      if (storedProfileJson != null) {
        final map = jsonDecode(storedProfileJson) as Map<String, dynamic>;
        return UserProfile.fromJson(map);
      }

      // Fallback: read raw user_data (snake_case) and transform
      final userDataJson = await _storage.read('user_data');
      if (userDataJson != null) {
        final map = jsonDecode(userDataJson) as Map<String, dynamic>;
        final transformed = await _buildUserProfileFromUserData(map);
        if (transformed != null) {
          await _storage.write(
            'user_profile',
            jsonEncode(transformed.toJson()),
          );
          return transformed;
        }
      }

      // Last resort: fetch from API and transform
      final response = await _apiClient.get('/users/profile');
      if (response.statusCode == 200 && response.data is Map) {
        final apiMap = (response.data as Map).cast<String, dynamic>();
        final transformed = await _buildUserProfileFromUserData(apiMap);
        if (transformed != null) {
          await _storage.write(
            'user_profile',
            jsonEncode(transformed.toJson()),
          );
          return transformed;
        }
      }
      return null;
    } catch (e) {
      if (kDebugMode) {
        print('Get user profile error: $e');
      }
      return null;
    }
  }

  Future<UserProfile?> _buildUserProfileFromUserData(
    Map<String, dynamic> userData,
  ) async {
    try {
      final id = userData['id']?.toString();
      final email = userData['email']?.toString();
      final name = (userData['full_name'] ?? userData['username'] ?? '')
          .toString();
      if (id == null || email == null || name.isEmpty) return null;

      // Derive preferred categories from any stored learning_path if present
      List<LearningCategory> preferredCategories = [];
      try {
        final pathJson = await _storage.read('learning_path');
        if (pathJson != null) {
          final pathData = jsonDecode(pathJson) as Map<String, dynamic>;
          final cats = (pathData['categories'] as List?)?.cast<String>() ?? [];
          preferredCategories = cats
              .map(
                (id) => LearningCategory.values.firstWhere(
                  (c) => c.id == id,
                  orElse: () => LearningCategory.dailyLife,
                ),
              )
              .toList();
        }
      } catch (_) {}
      if (preferredCategories.isEmpty) {
        preferredCategories = [
          LearningCategory.dailyLife,
          LearningCategory.travel,
          LearningCategory.business,
        ];
      }

      // Map level and defaults
      final levelCode = (userData['current_level'] ?? 'A1')
          .toString()
          .toUpperCase();
      final currentLevel = CEFRLevel.values.firstWhere(
        (l) => l.code.toUpperCase() == levelCode,
        orElse: () => CEFRLevel.a1,
      );
      final learningPace = LearningPace.steady;
      final createdAtStr =
          (userData['created_at'] ?? DateTime.now().toIso8601String())
              .toString();
      final createdAt =
          DateTime.tryParse(createdAtStr)?.toLocal() ?? DateTime.now();
      final onboardingCompleted =
          (userData['onboarding_completed'] ?? false) == true;

      return UserProfile(
        userId: id,
        name: name,
        email: email,
        preferredCategories: preferredCategories,
        currentLevel: currentLevel,
        learningPace: learningPace,
        assessmentResults: const {},
        createdAt: createdAt,
        onboardingCompleted: onboardingCompleted,
      );
    } catch (_) {
      return null;
    }
  }

  @override
  Future<List<LearningCategory>> getRecommendedCategories(String userId) async {
    try {
      final response = await _apiClient.post(
        '/personal-trainer/personalized-content',
        data: {
          'content_types': ['category_recommendations'],
          'user_preferences': {},
        },
      );

      if (response.statusCode == 200) {
        final data = response.data;
        final recommendations = data['recommendations'] as List?;

        if (recommendations != null) {
          return recommendations
              .map((r) => r['category'] as String)
              .map(
                (categoryId) => LearningCategory.values.firstWhere(
                  (c) => c.id == categoryId,
                  orElse: () => LearningCategory.dailyLife,
                ),
              )
              .toList();
        }
      }

      // Return popular categories as fallback
      return [
        LearningCategory.dailyLife,
        LearningCategory.travel,
        LearningCategory.food,
        LearningCategory.business,
      ];
    } catch (e) {
      if (kDebugMode) {
        print('Recommended categories error: $e');
      }
      return [
        LearningCategory.dailyLife,
        LearningCategory.travel,
        LearningCategory.food,
        LearningCategory.business,
      ];
    }
  }

  /// Clear lesson session cache for a specific module/day or all sessions
  Future<void> clearLessonCache({String? moduleId, int? dayNumber}) async {
    try {
      if (moduleId != null && dayNumber != null) {
        // Clear both legacy and versioned cache keys
        await _storage.delete('lesson_session_${moduleId}_day_$dayNumber');
        await _storage.delete('lesson_session_ts_${moduleId}_day_$dayNumber');
        await _storage.delete('lesson_session_v2_${moduleId}_day_$dayNumber');
        await _storage.delete(
          'lesson_session_ts_v2_${moduleId}_day_$dayNumber',
        );
      }
      // Note: Full cache clear would need a list of all keys
    } catch (e) {
      debugPrint('Error clearing lesson cache: $e');
    }
  }

  @override
  Future<LessonSession> startLearningSession({
    required String moduleId,
    int dayNumber = 1,
  }) async {
    // Try cached session first to avoid re-generating the same day content
    // Bump this when backend/session schema changes to avoid using incompatible cached sessions.
    const lessonSessionCacheVersion = 2;
    final cacheKey =
        'lesson_session_v${lessonSessionCacheVersion}_${moduleId}_day_$dayNumber';
    final cacheTimestampKey =
        'lesson_session_ts_v${lessonSessionCacheVersion}_${moduleId}_day_$dayNumber';

    // Cache invalidation: sessions older than 24 hours get refreshed
    try {
      final cached = await _storage.read(cacheKey);
      final cachedTs = await _storage.read(cacheTimestampKey);

      if (cached != null) {
        bool useCache = true;

        // Check if cache is older than 24 hours
        if (cachedTs != null) {
          try {
            final ts = DateTime.parse(cachedTs).toLocal();
            if (DateTime.now().difference(ts).inHours > 24) {
              debugPrint('📦 Lesson cache expired, fetching fresh content');
              useCache = false;
              await _storage.delete(cacheKey);
              await _storage.delete(cacheTimestampKey);
            }
          } catch (_) {}
        }

        if (useCache) {
          final map = jsonDecode(cached) as Map<String, dynamic>;

          // Safety: invalidate cache if it contains known-bad shapes (older app/backend versions)
          try {
            final rawSteps = map['steps'];
            if (rawSteps is List) {
              final vocabCount = rawSteps
                  .where((s) => s is Map && s['step_type'] == 'vocabulary')
                  .length;
              final hasMapContent = rawSteps.any(
                (s) => s is Map && s['content'] is Map,
              );
              if (vocabCount > 1 || hasMapContent) {
                debugPrint(
                  '📦 Cached session invalid (vocabCount=$vocabCount, hasMapContent=$hasMapContent). Fetching fresh.',
                );
                useCache = false;
                await _storage.delete(cacheKey);
                await _storage.delete(cacheTimestampKey);
              }
            }
          } catch (_) {}

          if (useCache) {
            debugPrint('📦 Using cached lesson session');
            return _ensureSpeakingStep(LessonSession.fromJson(map));
          }
        }
      }
    } catch (_) {}

    // Cancel any previous in-flight session request
    _sessionCancelToken?.cancel('new session request');
    _sessionCancelToken = CancelToken();

    // Get user's daily study time from saved learning path
    int durationMinutes = 25; // default
    LearningPath? path;
    try {
      path = await loadLearningPath();
      if (path != null) {
        durationMinutes = path.pace.averageDailyMinutes;
      }
    } catch (_) {}

    LessonSession buildOfflineFallbackSession(String reason) {
      // Best-effort: find module details from the current learning path so the
      // offline session still respects user interests + level.
      LearningModule? module;
      if (path != null) {
        for (final m in path.modules) {
          if (m.id == moduleId) {
            module = m;
            break;
          }
        }
        // If ids don't match, try interpreting moduleId as "day_X".
        if (module == null) {
          final match = RegExp(r'^day_(\d+)$').firstMatch(moduleId);
          final idx = int.tryParse(match?.group(1) ?? '');
          if (idx != null && idx > 0 && idx <= path.modules.length) {
            module = path.modules[idx - 1];
          }
        }
      }
      module ??= LearningModule(
        id: moduleId,
        title: 'Lesson',
        description: 'Offline lesson content (limited)',
        category: (path?.categories.isNotEmpty ?? false)
            ? path!.categories.first
            : LearningCategory.dailyLife,
        level: path?.currentLevel ?? CEFRLevel.a1,
        skills: const ['vocabulary', 'reading', 'grammar', 'speaking'],
        estimatedMinutes: durationMinutes,
        isUnlocked: true,
        progressPercentage: 0.0,
      );

      if (kDebugMode) {
        debugPrint('📴 Falling back to offline session: $reason');
      }

      return buildLocalFallbackSessionForTest(module, dayNumber);
    }

    try {
      final response = await _apiClient.post(
        '/personal-trainer/learning-session',
        data: {
          'module_id': moduleId,
          'day_number': dayNumber,
          'context': {'duration_minutes': durationMinutes},
        },
        options: Options(
          // Session generation can take time; allow up to 3 minutes to receive
          receiveTimeout: const Duration(minutes: 3),
          sendTimeout: const Duration(minutes: 2),
        ),
        cancelToken: _sessionCancelToken,
      );

      if (response.statusCode == 200) {
        final data = response.data as Map<String, dynamic>;
        // Cache the session for fast reopen
        try {
          await _storage.write(cacheKey, jsonEncode(data));
          await _storage.write(
            cacheTimestampKey,
            DateTime.now().toIso8601String(),
          );
          debugPrint('📦 Cached new lesson session');
        } catch (_) {}
        return _ensureSpeakingStep(LessonSession.fromJson(data));
      }

      throw Exception(
        'Failed to load lesson content (status ${response.statusCode}).',
      );
    } on NetworkException catch (e) {
      // Production-friendly fallback: allow the user to start learning even if
      // the network is flaky. The UI can still offer a retry to fetch AI content.
      return buildOfflineFallbackSession(e.message);
    } on ServerException catch (e) {
      return buildOfflineFallbackSession(e.message);
    }
  }

  LessonSession _ensureSpeakingStep(LessonSession session) {
    final hasSpeaking = session.steps.any((s) => s.stepType == 'speaking');
    if (hasSpeaking) {
      // Make sure existing speaking step has proper read-aloud text
      final steps = session.steps.map((step) {
        if (step.stepType == 'speaking') {
          return _enrichSpeakingStep(step, session);
        }
        return step;
      }).toList();
      return LessonSession(
        sessionId: session.sessionId,
        moduleId: session.moduleId,
        dayNumber: session.dayNumber,
        steps: steps,
        totalEstimatedMinutes: session.totalEstimatedMinutes,
      );
    }

    // Generate a proper read-aloud text based on the session topic
    final speakingStep = _createSpeakingStepForSession(session);

    final steps = List<LessonStep>.from(session.steps)..add(speakingStep);
    return LessonSession(
      sessionId: session.sessionId,
      moduleId: session.moduleId,
      dayNumber: session.dayNumber,
      steps: steps,
      totalEstimatedMinutes:
          session.totalEstimatedMinutes + speakingStep.estimatedMinutes,
    );
  }

  /// Creates a speaking step with actual read-aloud text based on session content
  LessonStep _createSpeakingStepForSession(LessonSession session) {
    // Extract topic from module or use default
    String topic = 'daily life';
    String level = 'A2';

    // Try to infer topic from module ID or existing content
    final moduleId = session.moduleId.toLowerCase();
    if (moduleId.contains('travel')) {
      topic = 'travel';
    } else if (moduleId.contains('food') || moduleId.contains('dining')) {
      topic = 'food and dining';
    } else if (moduleId.contains('business') || moduleId.contains('work')) {
      topic = 'work and business';
    } else if (moduleId.contains('health')) {
      topic = 'health and wellness';
    } else if (moduleId.contains('entertainment')) {
      topic = 'entertainment';
    }

    // Generate a proper read-aloud text (sentences user should speak)
    final readAloudTexts = _generateReadAloudTexts(topic, level);

    return LessonStep(
      stepType: 'speaking',
      title: 'Speaking Practice • Read Aloud',
      content: 'Read the following sentences clearly and at a natural pace.',
      estimatedMinutes: 5,
      contentJson: {
        'mode': 'read_aloud',
        'prompt_text': readAloudTexts['primary'],
        'sentences': readAloudTexts['sentences'],
        'tips': [
          'Read each sentence clearly',
          'Maintain a natural, steady pace',
          'Focus on pronunciation of key words',
          'Try to express the meaning naturally',
        ],
        'vocabulary_focus': readAloudTexts['vocabulary_focus'],
      },
    );
  }

  /// Enriches an existing speaking step with proper read-aloud content if missing
  LessonStep _enrichSpeakingStep(LessonStep step, LessonSession session) {
    final contentJson = step.contentJson ?? {};

    // Check if already has proper read-aloud text
    final hasProperPrompt =
        contentJson['prompt_text'] != null &&
        contentJson['prompt_text'].toString().length > 30 &&
        !contentJson['prompt_text'].toString().toLowerCase().contains(
          'share a quick',
        );

    if (hasProperPrompt) return step;

    // Generate proper read-aloud content
    String topic = 'daily life';
    final moduleId = session.moduleId.toLowerCase();
    if (moduleId.contains('travel')) {
      topic = 'travel';
    } else if (moduleId.contains('food') || moduleId.contains('dining')) {
      topic = 'food and dining';
    } else if (moduleId.contains('business') || moduleId.contains('work')) {
      topic = 'work and business';
    }

    final readAloudTexts = _generateReadAloudTexts(topic, 'A2');

    return LessonStep(
      stepType: 'speaking',
      title: step.title.contains('Read Aloud')
          ? step.title
          : 'Speaking Practice • Read Aloud',
      content: 'Read the following sentences clearly and at a natural pace.',
      estimatedMinutes: step.estimatedMinutes,
      contentJson: {
        'mode': 'read_aloud',
        'prompt_text': readAloudTexts['primary'],
        'sentences': readAloudTexts['sentences'],
        'tips': [
          'Read each sentence clearly',
          'Maintain a natural, steady pace',
          'Focus on pronunciation of key words',
        ],
        'vocabulary_focus': readAloudTexts['vocabulary_focus'],
      },
    );
  }

  /// Generates read-aloud texts based on topic and level
  Map<String, dynamic> _generateReadAloudTexts(String topic, String level) {
    final textsByTopic = {
      'daily life': {
        'primary':
            'Every morning I wake up early and start my day with a healthy breakfast. I usually have coffee with toast and some fresh fruit. After breakfast, I check my schedule and plan the important tasks for the day.',
        'sentences': [
          'Every morning I wake up early and start my day with a healthy breakfast.',
          'I usually have coffee with toast and some fresh fruit.',
          'After breakfast, I check my schedule and plan the important tasks for the day.',
          'In the evening, I like to relax and spend time with my family.',
        ],
        'vocabulary_focus': [
          'morning',
          'breakfast',
          'schedule',
          'tasks',
          'relax',
        ],
      },
      'travel': {
        'primary':
            'I love to travel and explore new places. Last summer, I visited a beautiful city in Europe. The architecture was amazing and the local food was delicious. I took many photographs to remember the trip.',
        'sentences': [
          'I love to travel and explore new places.',
          'Last summer, I visited a beautiful city in Europe.',
          'The architecture was amazing and the local food was delicious.',
          'I took many photographs to remember the trip.',
        ],
        'vocabulary_focus': [
          'travel',
          'explore',
          'architecture',
          'delicious',
          'photographs',
        ],
      },
      'food and dining': {
        'primary':
            'Cooking is one of my favorite hobbies. I enjoy preparing meals for my family and friends. Fresh ingredients are important for making tasty dishes. My specialty is pasta with homemade tomato sauce.',
        'sentences': [
          'Cooking is one of my favorite hobbies.',
          'I enjoy preparing meals for my family and friends.',
          'Fresh ingredients are important for making tasty dishes.',
          'My specialty is pasta with homemade tomato sauce.',
        ],
        'vocabulary_focus': [
          'cooking',
          'preparing',
          'ingredients',
          'tasty',
          'specialty',
        ],
      },
      'work and business': {
        'primary':
            'I work in a modern office in the city center. My job involves meeting with clients and managing important projects. Communication skills are essential in my profession. I always try to meet deadlines and deliver quality work.',
        'sentences': [
          'I work in a modern office in the city center.',
          'My job involves meeting with clients and managing important projects.',
          'Communication skills are essential in my profession.',
          'I always try to meet deadlines and deliver quality work.',
        ],
        'vocabulary_focus': [
          'office',
          'clients',
          'projects',
          'communication',
          'deadlines',
        ],
      },
      'health and wellness': {
        'primary':
            'Taking care of your health is very important. I try to exercise regularly and eat balanced meals. Getting enough sleep helps me feel energetic during the day. Mental health is just as important as physical health.',
        'sentences': [
          'Taking care of your health is very important.',
          'I try to exercise regularly and eat balanced meals.',
          'Getting enough sleep helps me feel energetic during the day.',
          'Mental health is just as important as physical health.',
        ],
        'vocabulary_focus': [
          'health',
          'exercise',
          'balanced',
          'energetic',
          'mental',
        ],
      },
      'entertainment': {
        'primary':
            'I enjoy watching movies and listening to music in my free time. My favorite genre is comedy because it makes me laugh. I also like to read books, especially mystery novels. Entertainment helps me relax after a busy week.',
        'sentences': [
          'I enjoy watching movies and listening to music in my free time.',
          'My favorite genre is comedy because it makes me laugh.',
          'I also like to read books, especially mystery novels.',
          'Entertainment helps me relax after a busy week.',
        ],
        'vocabulary_focus': [
          'entertainment',
          'genre',
          'comedy',
          'mystery',
          'relax',
        ],
      },
    };

    return textsByTopic[topic] ?? textsByTopic['daily life']!;
  }

  @override
  Future<Map<String, dynamic>> completeLearningSession({
    required String sessionId,
    required String moduleId,
    int dayNumber = 1,
    required int correct,
    required int total,
    required int timeSpentMinutes,
  }) async {
    final response = await _apiClient.post(
      '/personal-trainer/learning-session/complete',
      data: {
        'session_id': sessionId,
        'module_id': moduleId,
        'day_number': dayNumber,
        'results': {'correct': correct, 'total': total},
        'time_spent_minutes': timeSpentMinutes,
      },
    );

    if (response.statusCode == 200) {
      final result = Map<String, dynamic>.from(response.data);
      try {
        // Update local learning path: mark current module as completed and unlock next
        final path = await loadLearningPath();
        if (path != null) {
          final modules = List<LearningModule>.from(path.modules);
          final moduleIndex = modules.indexWhere((m) => m.id == moduleId);
          // Unlock next module only when backend explicitly confirms it.
          final unlockedFromApi = result['unlocked_next_module'] == true;

          if (moduleIndex >= 0) {
            // Mark current module as completed
            modules[moduleIndex] = modules[moduleIndex].copyWith(
              isCompleted: true,
              progressPercentage: 100.0,
            );

            if (unlockedFromApi && moduleIndex + 1 < modules.length) {
              modules[moduleIndex + 1] = modules[moduleIndex + 1].copyWith(
                isUnlocked: true,
              );
            }

            // Save updated path
            await saveLearningPath(
              path.copyWith(modules: modules, updatedAt: DateTime.now()),
            );
          }

          // Check if we need to extend journey with more modules
          final allCompleted = modules.every((m) => m.isCompleted);
          final remainingAfterThis = (moduleIndex >= 0)
              ? (modules.length - (moduleIndex + 1))
              : modules.length;
          final nearEnd = remainingAfterThis <= 7;

          // Only extend when near the end (or fully completed), not on every unlock.
          if (allCompleted || nearEnd) {
            try {
              // Fire-and-forget extension to avoid delaying "Complete" UX.
              Future<void>(() async {
                try {
                  final extendResp = await _apiClient.post(
                    '/personal-trainer/learning-journey/extend',
                    data: {'chunk_weeks': 4},
                    options: Options(
                      receiveTimeout: const Duration(seconds: 30),
                      sendTimeout: const Duration(seconds: 20),
                    ),
                  );
                  if (extendResp.statusCode == 200 && extendResp.data is Map) {
                    final data = (extendResp.data as Map)
                        .cast<String, dynamic>();
                    final newModules = (data['modules'] as List?) ?? [];
                    if (newModules.isNotEmpty) {
                      final updatedPath = await loadLearningPath();
                      if (updatedPath != null) {
                        final appended = List<LearningModule>.from(
                          updatedPath.modules,
                        );
                        final baseCategory = updatedPath.categories.isNotEmpty
                            ? updatedPath.categories.first
                            : LearningCategory.dailyLife;
                        for (int i = 0; i < newModules.length; i++) {
                          final m = (newModules[i] as Map)
                              .cast<String, dynamic>();
                          appended.add(
                            LearningModule(
                              // Force unique sequential ids regardless of backend payload
                              id: 'day_${appended.length + 1}',
                              title: m['title']?.toString() ?? 'Practice',
                              category: baseCategory,
                              level: updatedPath.currentLevel,
                              skills: List<String>.from(
                                m['skills'] ?? const ['mixed'],
                              ),
                              estimatedMinutes:
                                  (m['estimated_minutes'] ?? 20) is num
                                  ? (m['estimated_minutes'] as num).toInt()
                                  : 20,
                              isUnlocked: false,
                              progressPercentage: 0.0,
                              description:
                                  m['description']?.toString() ??
                                  'Extended module',
                            ),
                          );
                        }
                        await saveLearningPath(
                          updatedPath.copyWith(
                            modules: appended,
                            updatedAt: DateTime.now(),
                          ),
                        );
                      }
                    }
                  }
                } catch (_) {}
              });
            } catch (_) {}
          }
        }
      } catch (e) {
        debugPrint('Error updating learning path after completion: $e');
      }
      return result;
    } else {
      throw Exception('Failed to complete learning session');
    }
  }

  @override
  Future<void> saveStepProgress({
    required String sessionId,
    required String moduleId,
    required int dayNumber,
    required int stepIndex,
    required int correct,
    required int total,
    required int timeSpentMinutes,
    String? skillType,
  }) async {
    try {
      // Save progress locally for immediate persistence
      final key = 'step_progress_${moduleId}_day_${dayNumber}_step_$stepIndex';
      final progressData = {
        'session_id': sessionId,
        'module_id': moduleId,
        'day_number': dayNumber,
        'step_index': stepIndex,
        'correct': correct,
        'total': total,
        'time_spent_minutes': timeSpentMinutes,
        'skill_type': skillType,
        'saved_at': DateTime.now().toIso8601String(),
      };
      await _storage.write(key, jsonEncode(progressData));

      // Also try to sync with backend (fire and forget)
      try {
        await _apiClient.post(
          '/personal-trainer/step-progress',
          data: progressData,
          options: Options(
            sendTimeout: const Duration(seconds: 5),
            receiveTimeout: const Duration(seconds: 5),
          ),
        );
      } catch (_) {
        // Backend sync is optional - local save succeeded
      }

      // Update local learning path progress
      try {
        final path = await loadLearningPath();
        if (path != null) {
          final modules = List<LearningModule>.from(path.modules);
          final moduleIndex = modules.indexWhere((m) => m.id == moduleId);
          if (moduleIndex >= 0) {
            final module = modules[moduleIndex];
            // Calculate incremental progress based on step completion
            final totalSteps = 4; // Approximate steps per day
            final progressIncrement = 100.0 / totalSteps;
            final newProgress = ((stepIndex + 1) * progressIncrement).clamp(
              0.0,
              99.0,
            );

            modules[moduleIndex] = module.copyWith(
              progressPercentage: newProgress > module.progressPercentage
                  ? newProgress
                  : module.progressPercentage,
            );

            await saveLearningPath(
              path.copyWith(modules: modules, updatedAt: DateTime.now()),
            );
          }
        }
      } catch (_) {}
    } catch (e) {
      // Silent fail - progress saving shouldn't crash the app
      debugPrint('Error saving step progress: $e');
    }
  }

  // Private helper methods

  AssessmentResult _analyzeAssessmentLocally(
    String userId,
    List<AssessmentAnswer> answers,
  ) {
    // Calculate scores based on answers
    final correctAnswers = answers.where((a) => a.isCorrect).length;
    final totalQuestions = answers.length;
    final overallScore = totalQuestions > 0
        ? (correctAnswers / totalQuestions) * 100
        : 0.0;

    // Determine CEFR level based on score
    CEFRLevel level;
    if (overallScore >= 85) {
      level = CEFRLevel.c1;
    } else if (overallScore >= 70) {
      level = CEFRLevel.b2;
    } else if (overallScore >= 55) {
      level = CEFRLevel.b1;
    } else if (overallScore >= 40) {
      level = CEFRLevel.a2;
    } else {
      level = CEFRLevel.a1;
    }

    // Generate skill scores (mock)
    final skillScores = {
      'grammar': overallScore + (overallScore > 50 ? -10 : 10),
      'vocabulary': overallScore + (overallScore > 60 ? -5 : 15),
      'reading': overallScore,
      'listening': overallScore - 5,
    };

    String feedback;
    List<String> recommendations;

    if (overallScore >= 70) {
      feedback = 'Excellent work! You have a strong foundation in English.';
      recommendations = [
        'Challenge yourself with advanced content',
        'Focus on fluency and natural expression',
        'Practice complex grammar structures',
      ];
    } else if (overallScore >= 50) {
      feedback = 'Good progress! You\'re developing solid English skills.';
      recommendations = [
        'Continue practicing grammar fundamentals',
        'Expand your vocabulary through reading',
        'Practice speaking and listening regularly',
      ];
    } else {
      feedback = 'Great start! Focus on building your foundation.';
      recommendations = [
        'Start with basic grammar and vocabulary',
        'Practice simple conversations daily',
        'Use visual and audio learning materials',
      ];
    }

    return AssessmentResult(
      userId: userId,
      answers: answers,
      determinedLevel: level,
      skillScores: skillScores,
      overallScore: overallScore,
      feedback: feedback,
      recommendations: recommendations,
      completedAt: DateTime.now(),
    );
  }

  LearningPath _generateMockLearningPath(UserProfile userProfile) {
    final modules = <LearningModule>[];

    // Build a richer set of mixed-skill modules per preferred category
    final skillsSets = [
      ['vocabulary', 'reading'],
      ['speaking', 'listening'],
      ['grammar', 'writing'],
      ['listening', 'reading'],
      ['speaking', 'grammar'],
      ['writing', 'vocabulary'],
    ];

    int moduleCounter = 0;
    for (int i = 0; i < userProfile.preferredCategories.length; i++) {
      final category = userProfile.preferredCategories[i];
      for (int s = 0; s < skillsSets.length; s++) {
        final skills = skillsSets[s];
        final duration = 15 + (s * 5); // 15,20,25,30,35,40
        modules.add(
          LearningModule(
            id: 'module_${category.id}_${s + 1}',
            title:
                '${category.title} - ${skills.map((e) => e[0].toUpperCase() + e.substring(1)).join(' & ')}',
            category: category,
            level: userProfile.currentLevel,
            skills: skills,
            estimatedMinutes: duration,
            isUnlocked: moduleCounter == 0,
            progressPercentage: 0.0,
            description: 'Practice ${skills.join(' & ')} in ${category.title}',
          ),
        );
        moduleCounter++;
      }
    }

    // Ensure we have at least 8 modules even if few categories were selected
    while (modules.length < 8) {
      modules.add(
        LearningModule(
          id: 'module_extra_${modules.length + 1}',
          title: 'Mixed Skills Practice ${modules.length + 1}',
          category: userProfile.preferredCategories.isNotEmpty
              ? userProfile.preferredCategories.first
              : LearningCategory.dailyLife,
          level: userProfile.currentLevel,
          skills: skillsSets[modules.length % skillsSets.length],
          estimatedMinutes: 20 + (modules.length % 3) * 5,
          isUnlocked: modules.isEmpty,
          progressPercentage: 0.0,
          description: 'Balanced skills practice',
        ),
      );
    }

    return LearningPath(
      userId: userProfile.userId,
      categories: userProfile.preferredCategories,
      currentLevel: userProfile.currentLevel,
      targetLevel: _getTargetLevel(userProfile.currentLevel),
      pace: userProfile.learningPace,
      modules: modules,
      createdAt: DateTime.now(),
      updatedAt: DateTime.now(),
    );
  }

  CEFRLevel _getTargetLevel(CEFRLevel currentLevel) {
    switch (currentLevel) {
      case CEFRLevel.a1:
        return CEFRLevel.a2;
      case CEFRLevel.a2:
        return CEFRLevel.b1;
      case CEFRLevel.b1:
        return CEFRLevel.b2;
      case CEFRLevel.b2:
        return CEFRLevel.c1;
      case CEFRLevel.c1:
        return CEFRLevel.c2;
      case CEFRLevel.c2:
        return CEFRLevel.c2; // Already at max
    }
  }

  @override
  Future<void> saveLearningPath(LearningPath path) async {
    try {
      // First, persist locally for offline access
      final pathJson = jsonEncode(path.toJson());
      await _storage.write('learning_path_backup', pathJson);

      // Then, sync with backend for persistent storage across devices/restarts
      // IMPORTANT: Do not block UI flows (e.g. "Complete" button) on backend sync.
      // Backend sync is best-effort; local save already succeeded.
      Future<void>(() async {
        try {
          await _apiClient.post(
            '/personalization/learning-path/save/',
            data: path.toJson(),
            options: Options(
              receiveTimeout: const Duration(seconds: 15),
              sendTimeout: const Duration(seconds: 15),
            ),
          );
          if (kDebugMode) {
            print('📤 Learning path synced to backend successfully');
          }
        } on DioException catch (e) {
          if (kDebugMode) {
            print(
              '⚠️ Backend sync failed (local save succeeded): ${e.message}',
            );
          }
        } catch (e) {
          if (kDebugMode) {
            print('⚠️ Backend sync failed (local save succeeded): $e');
          }
        }
      });
    } catch (e) {
      // If local persistence fails, surface the error
      throw Exception('Failed to save learning path: ${e.toString()}');
    }
  }

  @override
  Future<LearningPath?> loadLearningPath() async {
    LearningPath? localPath;
    LearningPath? apiPath;

    LearningPath normalizePath(LearningPath p) {
      int consecutiveCompletedFromStart = 0;
      for (var i = 0; i < p.modules.length; i++) {
        if (p.modules[i].isCompleted) {
          consecutiveCompletedFromStart += 1;
        } else {
          break;
        }
      }

      final mods = <LearningModule>[];
      for (var i = 0; i < p.modules.length; i++) {
        final desiredId = 'day_${i + 1}';
        final m = p.modules[i];
        // Enforce sequential progression:
        // - only the first consecutive block can be completed
        // - only the "next day" after the streak is unlocked
        final normalizedCompleted = i < consecutiveCompletedFromStart;
        final shouldUnlocked = i <= consecutiveCompletedFromStart;
        final normalizedTitle = m.title.replaceFirst(
          RegExp(r'^Day\s+\d+', caseSensitive: false),
          'Day ${i + 1}',
        );
        final normalizedProgress = normalizedCompleted
            ? (m.progressPercentage >= 100.0 ? m.progressPercentage : 100.0)
            : (i <= consecutiveCompletedFromStart ? m.progressPercentage : 0.0);
        mods.add(
          m.copyWith(
            id: m.id == desiredId ? m.id : desiredId,
            title: normalizedTitle,
            isUnlocked: shouldUnlocked,
            isCompleted: normalizedCompleted,
            progressPercentage: normalizedProgress,
          ),
        );
      }
      if (mods.isNotEmpty && !mods.first.isUnlocked) {
        mods[0] = mods[0].copyWith(isUnlocked: true);
      }
      return p.copyWith(modules: mods, updatedAt: DateTime.now());
    }

    // Try local storage first for quick load
    try {
      final pathJson = await _storage.read('learning_path_backup');
      if (pathJson != null) {
        final pathData = jsonDecode(pathJson) as Map<String, dynamic>;
        localPath = normalizePath(LearningPath.fromJson(pathData));
        if (kDebugMode) {
          print(
            '📖 Loaded learning path from backup storage (${localPath.modules.length} modules)',
          );
        }
      }
    } catch (storageError) {
      if (kDebugMode) {
        print('Local learning path load failed: $storageError');
      }
    }

    // Try backend API to get the authoritative path (this is the source of truth)
    try {
      final response = await _apiClient.get(
        '/personalization/learning-path/active/',
        options: Options(
          receiveTimeout: const Duration(seconds: 15),
          sendTimeout: const Duration(seconds: 10),
        ),
      );

      if (response.statusCode == 200 && response.data != null) {
        final pathData = response.data as Map<String, dynamic>;

        // Handle path_data from backend which may be nested differently
        final modules = <LearningModule>[];

        // Try to extract modules from path_data if present
        if (pathData['path_data'] != null &&
            pathData['path_data']['modules'] != null) {
          final modulesData = pathData['path_data']['modules'] as List;
          for (var i = 0; i < modulesData.length; i++) {
            final m = (modulesData[i] as Map).cast<String, dynamic>();
            modules.add(LearningModule.fromJson(m));
          }
        }

        if (modules.isNotEmpty) {
          // Build API path from backend data
          final categories =
              pathData['path_data']?['categories'] as List? ?? [];
          apiPath = LearningPath(
            userId: pathData['user_profile_id']?.toString() ?? '',
            categories: categories
                .map(
                  (id) => LearningCategory.values.firstWhere(
                    (c) => c.id == id,
                    orElse: () => LearningCategory.dailyLife,
                  ),
                )
                .toList(),
            currentLevel: CEFRLevel.values.firstWhere(
              (l) =>
                  l.code == (pathData['path_data']?['current_level'] ?? 'A1'),
              orElse: () => CEFRLevel.a1,
            ),
            targetLevel: CEFRLevel.values.firstWhere(
              (l) => l.code == (pathData['path_data']?['target_level'] ?? 'B1'),
              orElse: () => CEFRLevel.b1,
            ),
            pace: LearningPace.steady,
            modules: modules,
            createdAt:
                DateTime.tryParse(pathData['created_at']?.toString() ?? '')
                        ?.toLocal() ??
                    DateTime.now(),
            updatedAt: DateTime.now(),
          );
          apiPath = normalizePath(apiPath);

          if (kDebugMode) {
            print(
              '📖 Loaded learning path from API (${apiPath.modules.length} modules)',
            );
          }
        }
      }
    } on DioException catch (e) {
      // 404 means no path exists in backend - this is expected for new users
      if (e.response?.statusCode != 404) {
        if (kDebugMode) {
          print('⚠️ API learning path load failed: ${e.message}');
        }
      }
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ Learning path load error: $e');
      }
    }

    // Merge local and API paths - prefer API but keep higher local progress
    if (apiPath != null && localPath != null) {
      final mergedModules = <LearningModule>[];
      // Merge by index (day order) to avoid issues when ids were duplicated in older paths.
      final minLen = apiPath.modules.length < localPath.modules.length
          ? apiPath.modules.length
          : localPath.modules.length;
      for (var i = 0; i < apiPath.modules.length; i++) {
        final apiModule = apiPath.modules[i];
        final localModule = i < minLen ? localPath.modules[i] : apiModule;
        mergedModules.add(
          apiModule.copyWith(
            progressPercentage:
                localModule.progressPercentage > apiModule.progressPercentage
                ? localModule.progressPercentage
                : apiModule.progressPercentage,
            isCompleted: localModule.isCompleted || apiModule.isCompleted,
            isUnlocked: localModule.isUnlocked || apiModule.isUnlocked,
          ),
        );
      }
      final mergedPath = apiPath.copyWith(modules: mergedModules);

      // Cache merged result locally
      try {
        final normalizedMerged = normalizePath(mergedPath);
        await _storage.write(
          'learning_path_backup',
          jsonEncode(normalizedMerged.toJson()),
        );
      } catch (_) {}

      if (kDebugMode) {
        print('✅ Merged local and API learning paths');
      }
      return normalizePath(mergedPath);
    }

    // Return API path if we have it
    if (apiPath != null) {
      // Cache it locally
      try {
        await _storage.write(
          'learning_path_backup',
          jsonEncode(apiPath.toJson()),
        );
      } catch (_) {}
      return normalizePath(apiPath);
    }

    // Return local path if we have one (offline mode)
    if (localPath != null) {
      if (kDebugMode) {
        print('📖 Using local learning path (offline mode)');
      }
      return normalizePath(localPath);
    }

    // Final fallback: try older storage key
    try {
      final pathJson = await _storage.read('learning_path');
      if (pathJson != null) {
        final pathData = jsonDecode(pathJson) as Map<String, dynamic>;
        return LearningPath.fromJson(pathData);
      }
    } catch (_) {}

    return null;
  }

  @override
  Future<void> updateModuleProgress(
    String moduleId,
    double progress,
    bool unlockNext,
  ) async {
    try {
      // First get the active learning path to find its ID
      final activePathResponse = await _apiClient.get(
        '/personalization/learning-path/active/',
      );

      if (activePathResponse.statusCode == 200 &&
          activePathResponse.data != null) {
        final pathData = activePathResponse.data as Map<String, dynamic>;
        final pathId = pathData['id'];

        // Update progress via API
        final updateResponse = await _apiClient.put(
          '/personalization/learning-path/$pathId/progress/',
          data: {
            'performance_score': progress / 100.0, // Convert to 0-1 scale
          },
        );

        if (updateResponse.statusCode == 200) {
          // Successfully updated via API
          return;
        }
      }
    } catch (apiError) {
      // API failed, fall back to local storage approach
      debugPrint('API progress update failed, using local storage: $apiError');
    }

    // Fallback to local storage approach (original logic)
    try {
      final path = await loadLearningPath();
      if (path == null) return;

      final updatedModules = path.modules.map((module) {
        if (module.id == moduleId) {
          return module.copyWith(
            progressPercentage: progress,
            isCompleted: progress >= 100.0,
          );
        } else if (unlockNext) {
          // Find the current module index
          final currentIndex = path.modules.indexWhere((m) => m.id == moduleId);
          if (currentIndex != -1 &&
              path.modules.indexOf(module) == currentIndex + 1) {
            // This is the next module, unlock it
            return module.copyWith(isUnlocked: true);
          }
        }
        return module;
      }).toList();

      final updatedPath = path.copyWith(
        modules: updatedModules,
        updatedAt: DateTime.now(),
      );

      await saveLearningPath(updatedPath);
    } catch (e) {
      debugPrint('Failed to update module progress: $e');
    }
  }
}
