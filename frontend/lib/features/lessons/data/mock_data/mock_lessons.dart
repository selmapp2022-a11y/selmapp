import '../models/lesson_models.dart';

class MockLessonsData {
  // Mock Personal Study Plans
  static List<PersonalStudyPlan> get studyPlans => [
    PersonalStudyPlan(
      id: 'plan_1',
      title: 'Business English Mastery',
      description: 'Comprehensive program to master professional English communication',
      type: StudyPlanType.intensive,
      targetLevel: DifficultyLevel.b2,
      focusAreas: ['business communication', 'presentations', 'meetings', 'emails'],
      lessons: businessLessons,
      totalLessons: 15,
      completedLessons: 3,
      startDate: DateTime.now().subtract(const Duration(days: 7)),
      estimatedDays: 30,
      progressPercentage: 20.0,
    ),
    PersonalStudyPlan(
      id: 'plan_2',
      title: 'Daily Conversation Skills',
      description: 'Improve everyday English conversation abilities',
      type: StudyPlanType.daily,
      targetLevel: DifficultyLevel.b1,
      focusAreas: ['daily conversations', 'social interactions', 'pronunciation'],
      lessons: conversationLessons,
      totalLessons: 20,
      completedLessons: 8,
      startDate: DateTime.now().subtract(const Duration(days: 14)),
      estimatedDays: 45,
      progressPercentage: 40.0,
    ),
    PersonalStudyPlan(
      id: 'plan_3',
      title: 'Academic Writing Excellence',
      description: 'Master academic and formal writing skills',
      type: StudyPlanType.weekly,
      targetLevel: DifficultyLevel.c1,
      focusAreas: ['essay writing', 'research papers', 'formal language'],
      lessons: writingLessons,
      totalLessons: 12,
      completedLessons: 1,
      startDate: DateTime.now().subtract(const Duration(days: 3)),
      estimatedDays: 60,
      progressPercentage: 8.3,
    ),
  ];

  // Mock Business Lessons
  static List<Lesson> get businessLessons => [
    const Lesson(
      id: 'bus_1',
      title: 'Professional Introductions',
      description: 'Learn to introduce yourself and others in business settings',
      type: LessonType.conversation,
      level: DifficultyLevel.b1,
      estimatedMinutes: 25,
      objectives: [
        'Master professional greeting phrases',
        'Practice self-introduction in business context',
        'Learn to ask appropriate follow-up questions',
      ],
      keyTopics: ['greetings', 'job titles', 'company information', 'networking'],
      isCompleted: true,
      completedAt: null,
      userScore: 85,
    ),
    const Lesson(
      id: 'bus_2',
      title: 'Email Communication',
      description: 'Write professional emails with proper structure and tone',
      type: LessonType.writing,
      level: DifficultyLevel.b2,
      estimatedMinutes: 30,
      objectives: [
        'Structure professional emails effectively',
        'Use appropriate formal language',
        'Practice different email types',
      ],
      keyTopics: ['email structure', 'formal language', 'business tone', 'requests'],
      isCompleted: true,
      completedAt: null,
      userScore: 78,
    ),
    const Lesson(
      id: 'bus_3',
      title: 'Meeting Participation',
      description: 'Actively participate in business meetings and discussions',
      type: LessonType.conversation,
      level: DifficultyLevel.b2,
      estimatedMinutes: 35,
      objectives: [
        'Express opinions professionally',
        'Ask for clarification effectively',
        'Contribute to team discussions',
      ],
      keyTopics: ['meeting phrases', 'opinions', 'agreements', 'disagreements'],
      isCompleted: true,
      completedAt: null,
      userScore: 92,
    ),
  ];

  // Mock Conversation Lessons
  static List<Lesson> get conversationLessons => [
    const Lesson(
      id: 'conv_1',
      title: 'Small Talk Mastery',
      description: 'Master the art of casual conversation and small talk',
      type: LessonType.conversation,
      level: DifficultyLevel.a2,
      estimatedMinutes: 20,
      objectives: [
        'Start conversations naturally',
        'Keep conversations flowing',
        'End conversations politely',
      ],
      keyTopics: ['weather', 'weekend plans', 'hobbies', 'current events'],
      isCompleted: true,
      completedAt: null,
      userScore: 88,
    ),
    const Lesson(
      id: 'conv_2',
      title: 'Expressing Opinions',
      description: 'Learn to express your thoughts and opinions clearly',
      type: LessonType.conversation,
      level: DifficultyLevel.b1,
      estimatedMinutes: 25,
      objectives: [
        'State opinions confidently',
        'Support opinions with reasons',
        'Respect different viewpoints',
      ],
      keyTopics: ['opinion phrases', 'agreeing', 'disagreeing', 'reasoning'],
      isCompleted: true,
      completedAt: null,
      userScore: 76,
    ),
  ];

  // Mock Writing Lessons
  static List<Lesson> get writingLessons => [
    const Lesson(
      id: 'writ_1',
      title: 'Essay Structure',
      description: 'Master the fundamental structure of academic essays',
      type: LessonType.writing,
      level: DifficultyLevel.b2,
      estimatedMinutes: 40,
      objectives: [
        'Understand essay components',
        'Write strong introductions',
        'Develop coherent body paragraphs',
        'Create effective conclusions',
      ],
      keyTopics: ['introduction', 'thesis statement', 'body paragraphs', 'conclusion'],
      isCompleted: true,
      completedAt: null,
      userScore: 82,
    ),
  ];

  // Mock AI Conversations
  static List<AIConversation> get sampleConversations => [
    AIConversation(
      id: 'conv_ai_1',
      topic: ConversationTopic.dailyLife,
      title: 'Planning Your Weekend',
      context: 'You\'re talking with a friend about your weekend plans. Practice making plans and expressing preferences.',
      messages: [
        ConversationMessage(
          id: 'msg_1',
          content: 'Hi! How are you doing today? Do you have any exciting plans for the weekend?',
          isFromUser: false,
          timestamp: DateTime.now().subtract(const Duration(minutes: 10)),
          interactionType: InteractionType.speaking,
        ),
        ConversationMessage(
          id: 'msg_2',
          content: 'I\'m doing well, thank you! I\'m planning to visit the museum on Saturday.',
          isFromUser: true,
          timestamp: DateTime.now().subtract(const Duration(minutes: 9)),
          interactionType: InteractionType.speaking,
          feedback: AIFeedback(
            id: 'feedback_1',
            originalText: 'I\'m doing well, thank you! I\'m planning to visit the museum on Saturday.',
            suggestions: [
              'Great response! Your grammar is correct.',
              'Try adding more details about which museum you\'re visiting.',
            ],
            corrections: [],
            scores: {
              'grammar': 95,
              'pronunciation': 88,
              'fluency': 90,
            },
            overallFeedback: 'Excellent! Your response was clear and grammatically correct. Consider adding more specific details to make your conversation more engaging.',
            analyzedAt: DateTime.now().subtract(const Duration(minutes: 9)),
          ),
        ),
        ConversationMessage(
          id: 'msg_3',
          content: 'That sounds wonderful! Which museum are you thinking of visiting? I love art museums myself.',
          isFromUser: false,
          timestamp: DateTime.now().subtract(const Duration(minutes: 8)),
          interactionType: InteractionType.speaking,
        ),
      ],
      suggestedResponses: [
        'I\'m planning to visit the Natural History Museum.',
        'I haven\'t decided yet. Do you have any recommendations?',
        'I prefer art museums too. What\'s your favorite one?',
      ],
      currentInteractionType: InteractionType.speaking,
      startedAt: DateTime.now().subtract(const Duration(minutes: 10)),
    ),
    AIConversation(
      id: 'conv_ai_2',
      topic: ConversationTopic.business,
      title: 'Job Interview Practice',
      context: 'Practice a job interview scenario. Focus on professional language and clear communication.',
      messages: [
        ConversationMessage(
          id: 'msg_b1',
          content: 'Good morning! Thank you for coming in today. Could you please tell me a bit about yourself and your background?',
          isFromUser: false,
          timestamp: DateTime.now().subtract(const Duration(minutes: 15)),
          interactionType: InteractionType.speaking,
        ),
        ConversationMessage(
          id: 'msg_b2',
          content: 'Good morning! I have five years experience in marketing and I am very passionate about digital marketing strategies.',
          isFromUser: true,
          timestamp: DateTime.now().subtract(const Duration(minutes: 14)),
          interactionType: InteractionType.speaking,
          feedback: AIFeedback(
            id: 'feedback_b1',
            originalText: 'Good morning! I have five years experience in marketing and I am very passionate about digital marketing strategies.',
            grammarAnalysis: GrammarAnalysis(
              errors: [
                GrammarError(
                  type: 'Article',
                  description: 'Missing article before "five years"',
                  originalText: 'five years experience',
                  correctedText: 'five years of experience',
                  startIndex: 19,
                  endIndex: 38,
                  explanation: 'When talking about duration or amount, use "of" between the number and the noun.',
                ),
              ],
              suggestions: [
                GrammarSuggestion(
                  category: 'Articles',
                  suggestion: 'Use "of" with time expressions',
                  example: 'I have five years of experience',
                  explanation: 'When expressing duration or quantity, use "of" between the number and noun.',
                ),
              ],
              accuracyScore: 85,
              categoryScores: {
                'grammar': 80,
                'vocabulary': 90,
                'structure': 85,
              },
            ),
            suggestions: [
              'Good start! Consider adding more specific details about your achievements.',
              'Try to quantify your experience with specific examples.',
            ],
            corrections: [
              'Change "five years experience" to "five years of experience"',
            ],
            scores: {
              'grammar': 80,
              'content': 85,
              'professionalism': 90,
            },
            overallFeedback: 'Good professional tone! Small grammar correction needed. Consider adding specific achievements to make your response stronger.',
            analyzedAt: DateTime.now().subtract(const Duration(minutes: 14)),
          ),
        ),
      ],
      suggestedResponses: [
        'I have five years of experience in marketing, specializing in digital campaigns.',
        'My background includes marketing strategy and team leadership.',
        'I\'ve worked in marketing for five years, focusing on brand development.',
      ],
      currentInteractionType: InteractionType.speaking,
      startedAt: DateTime.now().subtract(const Duration(minutes: 15)),
    ),
  ];

  // Mock Writing Samples with AI Feedback
  static List<ConversationMessage> get writingSamples => [
    ConversationMessage(
      id: 'write_1',
      content: 'Dear Sir/Madam,\n\nI am writing to apply for the marketing manager position advertised on your website. I have extensive experience in digital marketing and I believe I would be a valuable addition to your team.\n\nI have worked in marketing for over 5 years and have successfully managed several campaigns that increased brand awareness by 40%. I am skilled in social media marketing, content creation, and data analysis.\n\nI would welcome the opportunity to discuss how my skills and experience can contribute to your company\'s success.\n\nThank you for your consideration.\n\nSincerely,\nJohn Smith',
      isFromUser: true,
      timestamp: DateTime.now().subtract(const Duration(hours: 2)),
      interactionType: InteractionType.writing,
      feedback: AIFeedback(
        id: 'write_feedback_1',
        originalText: 'Dear Sir/Madam,\n\nI am writing to apply for the marketing manager position...',
        writingAnalysis: WritingAnalysis(
          overallScore: 82,
          grammarScore: 88,
          vocabularyScore: 78,
          structureScore: 85,
          clarityScore: 80,
          coherenceScore: 84,
          suggestions: [
            WritingSuggestion(
              category: 'Structure',
              suggestion: 'Add more specific examples in the second paragraph',
              originalText: 'I have worked in marketing for over 5 years',
              improvedText: 'During my 5+ years in marketing at ABC Company, I led cross-functional teams',
              explanation: 'Specific details make your experience more credible and memorable.',
              priority: 1,
            ),
            WritingSuggestion(
              category: 'Vocabulary',
              suggestion: 'Use more varied vocabulary',
              originalText: 'I have... I am... I would...',
              improvedText: 'My experience includes... Additionally, my expertise encompasses... Furthermore, I would...',
              explanation: 'Varied sentence starters make your writing more engaging.',
              priority: 2,
            ),
          ],
          strengths: [
            'Clear professional structure',
            'Appropriate formal tone',
            'Specific achievement mentioned (40% increase)',
            'Strong closing statement',
          ],
          improvements: [
            'Add more specific examples of achievements',
            'Vary sentence structures for better flow',
            'Include more industry-specific vocabulary',
            'Quantify more of your accomplishments',
          ],
          wordCount: 95,
          readabilityLevel: 'Professional',
        ),
        suggestions: [
          'Excellent professional tone and structure!',
          'Consider adding more specific examples of your achievements.',
          'Try varying your sentence beginnings to improve flow.',
        ],
        corrections: [],
        scores: {
          'grammar': 88,
          'vocabulary': 78,
          'structure': 85,
          'clarity': 80,
          'overall': 82,
        },
        overallFeedback: 'This is a well-structured cover letter with appropriate professional tone. The main strength is your clear communication and specific achievement mention. To improve, add more concrete examples and vary your sentence structures for better engagement.',
        analyzedAt: DateTime.now().subtract(const Duration(hours: 2)),
      ),
    ),
  ];

  // Mock Learning Progress
  static LearningProgress get mockProgress => LearningProgress(
    userId: 'user_123',
    currentLevel: DifficultyLevel.b1,
    skillScores: {
      'speaking': 75,
      'writing': 82,
      'grammar': 78,
      'vocabulary': 85,
      'pronunciation': 70,
      'comprehension': 88,
    },
    completedLessons: ['bus_1', 'bus_2', 'bus_3', 'conv_1', 'conv_2', 'writ_1'],
    strengths: [
      'Excellent vocabulary usage',
      'Strong writing structure',
      'Good comprehension skills',
    ],
    weaknesses: [
      'Pronunciation needs improvement',
      'Grammar accuracy in complex sentences',
      'Speaking fluency under pressure',
    ],
    totalStudyMinutes: 450,
    conversationCount: 12,
    writingCount: 8,
    lastActivity: DateTime.now().subtract(const Duration(hours: 3)),
    recentTopics: [
      'business communication',
      'daily conversations',
      'email writing',
      'job interviews',
    ],
  );

  // Helper methods
  static List<Lesson> getAllLessons() {
    return [
      ...businessLessons,
      ...conversationLessons,
      ...writingLessons,
    ];
  }

  static List<Lesson> getLessonsByType(LessonType type) {
    return getAllLessons().where((lesson) => lesson.type == type).toList();
  }

  static List<Lesson> getLessonsByLevel(DifficultyLevel level) {
    return getAllLessons().where((lesson) => lesson.level == level).toList();
  }

  static PersonalStudyPlan? getActivePlan() {
    try {
      return studyPlans.firstWhere((plan) => plan.isActive);
    } catch (e) {
      return null;
    }
  }

  // Mock conversation starters by topic
  static Map<ConversationTopic, List<String>> get conversationStarters => {
    ConversationTopic.dailyLife: [
      'Tell me about your typical morning routine.',
      'What did you do last weekend?',
      'What are your plans for this evening?',
      'Describe your favorite hobby.',
    ],
    ConversationTopic.business: [
      'Tell me about your current job.',
      'What are your career goals?',
      'Describe a challenging project you worked on.',
      'How do you handle workplace conflicts?',
    ],
    ConversationTopic.travel: [
      'What\'s your favorite travel destination?',
      'Tell me about your last vacation.',
      'Where would you like to visit next?',
      'What\'s the most interesting place you\'ve been to?',
    ],
    ConversationTopic.education: [
      'Tell me about your educational background.',
      'What was your favorite subject in school?',
      'How do you prefer to learn new things?',
      'What skills would you like to develop?',
    ],
  };

  // Mock writing prompts by topic
  static Map<ConversationTopic, List<String>> get writingPrompts => {
    ConversationTopic.business: [
      'Write a professional email requesting a meeting.',
      'Describe your ideal work environment.',
      'Write a brief proposal for a new project.',
      'Compose a thank-you email after an interview.',
    ],
    ConversationTopic.dailyLife: [
      'Write about your daily routine.',
      'Describe your hometown to a foreign visitor.',
      'Write a letter to a friend about your recent experiences.',
      'Describe your favorite restaurant and why you like it.',
    ],
    ConversationTopic.education: [
      'Write an essay about the importance of education.',
      'Describe your learning goals and how you plan to achieve them.',
      'Write about a skill you recently learned.',
      'Compose a study plan for improving your English.',
    ],
  };
}

