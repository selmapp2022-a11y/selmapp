import 'package:flutter/material.dart';
import '../../data/models/lesson_models.dart';

class AIConversationPage extends StatefulWidget {
  final ConversationTopic topic;
  final AIConversation? existingConversation;

  const AIConversationPage({
    super.key,
    required this.topic,
    this.existingConversation,
  });

  @override
  State<AIConversationPage> createState() => _AIConversationPageState();
}

class _AIConversationPageState extends State<AIConversationPage>
    with TickerProviderStateMixin {
  late AnimationController _recordingController;
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;
  
  AIConversation? conversation;
  bool isRecording = false;
  bool isAnalyzing = false;
  int recordingDuration = 0;
  final TextEditingController _textController = TextEditingController();
  InteractionType currentInteractionType = InteractionType.speaking;
  
  @override
  void initState() {
    super.initState();
    
    _recordingController = AnimationController(
      duration: const Duration(milliseconds: 1000),
      vsync: this,
    );
    
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: this,
    );
    
    _pulseAnimation = Tween<double>(
      begin: 0.8,
      end: 1.2,
    ).animate(CurvedAnimation(
      parent: _pulseController,
      curve: Curves.easeInOut,
    ));

    // Initialize conversation
    if (widget.existingConversation != null) {
      conversation = widget.existingConversation;
    } else {
      _startNewConversation();
    }
  }

  @override
  void dispose() {
    _recordingController.dispose();
    _pulseController.dispose();
    _textController.dispose();
    super.dispose();
  }

  void _startNewConversation() {
    final starters = _getConversationStarters(widget.topic);
    final starter = starters.first;
    
    setState(() {
      conversation = AIConversation(
        id: 'conv_${DateTime.now().millisecondsSinceEpoch}',
        topic: widget.topic,
        title: _getTopicTitle(widget.topic),
        context: _getTopicContext(widget.topic),
        messages: [
          ConversationMessage(
            id: 'msg_ai_start',
            content: starter,
            isFromUser: false,
            timestamp: DateTime.now(),
            interactionType: InteractionType.speaking,
          ),
        ],
        suggestedResponses: _getSuggestedResponses(widget.topic),
        currentInteractionType: InteractionType.speaking,
        startedAt: DateTime.now(),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    if (conversation == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      backgroundColor: Colors.grey[50],
      appBar: AppBar(
        title: Text(
          conversation!.title,
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        backgroundColor: _getTopicColor(widget.topic),
        elevation: 0,
        actions: [
          PopupMenuButton<InteractionType>(
            icon: Icon(
              currentInteractionType == InteractionType.speaking 
                  ? Icons.mic 
                  : Icons.keyboard,
              color: Colors.white,
            ),
            onSelected: (type) {
              setState(() {
                currentInteractionType = type;
              });
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: InteractionType.speaking,
                child: Row(
                  children: [
                    Icon(Icons.mic),
                    SizedBox(width: 8),
                    Text('Speaking'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: InteractionType.writing,
                child: Row(
                  children: [
                    Icon(Icons.keyboard),
                    SizedBox(width: 8),
                    Text('Typing'),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          // Context Banner
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: _getTopicColor(widget.topic).withValues(alpha: 0.1),
              border: Border(
                bottom: BorderSide(
                  color: _getTopicColor(widget.topic).withValues(alpha: 0.2),
                ),
              ),
            ),
            child: Text(
              conversation!.context,
              style: TextStyle(
                color: _getTopicColor(widget.topic),
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
              textAlign: TextAlign.center,
            ),
          ),
          
          // Messages List
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: conversation!.messages.length,
              itemBuilder: (context, index) {
                final message = conversation!.messages[index];
                return _buildMessageBubble(message);
              },
            ),
          ),
          
          // Input Area
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.1),
                  blurRadius: 10,
                  offset: const Offset(0, -2),
                ),
              ],
            ),
            child: SafeArea(
              child: currentInteractionType == InteractionType.speaking
                  ? _buildSpeakingInterface()
                  : _buildTypingInterface(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(ConversationMessage message) {
    final isUser = message.isFromUser;
    final hasAnalysis = message.feedback != null;
    
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          // Message Bubble
          Row(
            mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              if (!isUser) ...[
                CircleAvatar(
                  radius: 16,
                  backgroundColor: _getTopicColor(widget.topic),
                  child: const Icon(
                    Icons.smart_toy,
                    color: Colors.white,
                    size: 16,
                  ),
                ),
                const SizedBox(width: 8),
              ],
              Flexible(
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 12,
                  ),
                  decoration: BoxDecoration(
                    color: isUser
                        ? _getTopicColor(widget.topic)
                        : Colors.white,
                    borderRadius: BorderRadius.circular(20),
                    border: isUser ? null : Border.all(color: Colors.grey[300]!),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.05),
                        blurRadius: 5,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        message.content,
                        style: TextStyle(
                          color: isUser ? Colors.white : Colors.black87,
                          fontSize: 16,
                          height: 1.4,
                        ),
                      ),
                      if (message.interactionType == InteractionType.speaking && isUser) ...[
                        const SizedBox(height: 8),
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              Icons.volume_up,
                              color: Colors.white.withValues(alpha: 0.7),
                              size: 14,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              'Tap to replay',
                              style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.7),
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ],
                  ),
                ),
              ),
              if (isUser) ...[
                const SizedBox(width: 8),
                CircleAvatar(
                  radius: 16,
                  backgroundColor: Colors.grey[300],
                  child: const Icon(
                    Icons.person,
                    color: Colors.grey,
                    size: 16,
                  ),
                ),
              ],
            ],
          ),
          
          // AI Analysis Card
          if (hasAnalysis) ...[
            const SizedBox(height: 8),
            Container(
              margin: EdgeInsets.only(
                left: isUser ? 40 : 0,
                right: isUser ? 0 : 40,
              ),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.blue.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.blue.withValues(alpha: 0.2)),
              ),
              child: _buildAIAnalysis(message.feedback!),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildAIAnalysis(AIFeedback feedback) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.psychology,
              color: Colors.blue,
              size: 20,
            ),
            const SizedBox(width: 8),
            Text(
              'AI Feedback',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: Colors.blue,
                fontSize: 14,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        
        // Scores
        if (feedback.scores.isNotEmpty) ...[
          Wrap(
            spacing: 12,
            runSpacing: 8,
            children: feedback.scores.entries.map((entry) {
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: _getScoreColor(entry.value).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: _getScoreColor(entry.value).withValues(alpha: 0.3),
                  ),
                ),
                child: Text(
                  '${entry.key}: ${entry.value}%',
                  style: TextStyle(
                    color: _getScoreColor(entry.value),
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 12),
        ],
        
        // Feedback Text
        Text(
          feedback.overallFeedback,
          style: const TextStyle(
            fontSize: 14,
            height: 1.4,
          ),
        ),
        
        // Suggestions
        if (feedback.suggestions.isNotEmpty) ...[
          const SizedBox(height: 12),
          ...feedback.suggestions.map((suggestion) => Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 4,
                  height: 4,
                  margin: const EdgeInsets.only(top: 8, right: 8),
                  decoration: BoxDecoration(
                    color: Colors.blue,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                Expanded(
                  child: Text(
                    suggestion,
                    style: const TextStyle(
                      fontSize: 12,
                      height: 1.3,
                    ),
                  ),
                ),
              ],
            ),
          )),
        ],
      ],
    );
  }

  Widget _buildSpeakingInterface() {
    return Column(
      children: [
        // Suggested Responses
        if (conversation!.suggestedResponses.isNotEmpty && !isRecording) ...[
          SizedBox(
            height: 40,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: conversation!.suggestedResponses.length,
              itemBuilder: (context, index) {
                final suggestion = conversation!.suggestedResponses[index];
                return Container(
                  margin: const EdgeInsets.only(right: 8),
                  child: ActionChip(
                    label: Text(
                      suggestion,
                      style: const TextStyle(fontSize: 12),
                    ),
                    onPressed: () => _sendTextMessage(suggestion),
                    backgroundColor: Colors.grey[100],
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 16),
        ],
        
        // Recording Interface
        Row(
          children: [
            // Record Button
            GestureDetector(
              onTap: _toggleRecording,
              child: AnimatedBuilder(
                animation: _pulseAnimation,
                builder: (context, child) {
                  return Transform.scale(
                    scale: isRecording ? _pulseAnimation.value : 1.0,
                    child: Container(
                      width: 60,
                      height: 60,
                      decoration: BoxDecoration(
                        color: isRecording
                            ? Colors.red
                            : _getTopicColor(widget.topic),
                        borderRadius: BorderRadius.circular(30),
                        boxShadow: [
                          BoxShadow(
                            color: (isRecording ? Colors.red : _getTopicColor(widget.topic))
                                .withValues(alpha: 0.3),
                            blurRadius: 10,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: Icon(
                        isRecording ? Icons.stop : Icons.mic,
                        color: Colors.white,
                        size: 28,
                      ),
                    ),
                  );
                },
              ),
            ),
            
            const SizedBox(width: 16),
            
            // Recording Status
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    isRecording
                        ? 'Recording... ${recordingDuration}s'
                        : isAnalyzing
                            ? 'Analyzing speech...'
                            : 'Tap to start speaking',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: isRecording
                          ? Colors.red
                          : _getTopicColor(widget.topic),
                    ),
                  ),
                  if (isRecording) ...[
                    const SizedBox(height: 8),
                    LinearProgressIndicator(
                      backgroundColor: Colors.grey[200],
                      valueColor: const AlwaysStoppedAnimation<Color>(Colors.red),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildTypingInterface() {
    return Row(
      children: [
        Expanded(
          child: TextField(
            controller: _textController,
            decoration: InputDecoration(
              hintText: 'Type your message...',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(25),
                borderSide: BorderSide(color: Colors.grey[300]!),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(25),
                borderSide: BorderSide(color: _getTopicColor(widget.topic)),
              ),
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 20,
                vertical: 12,
              ),
            ),
            maxLines: null,
            textCapitalization: TextCapitalization.sentences,
          ),
        ),
        const SizedBox(width: 12),
        FloatingActionButton(
          onPressed: () {
            if (_textController.text.trim().isNotEmpty) {
              _sendTextMessage(_textController.text.trim());
              _textController.clear();
            }
          },
          backgroundColor: _getTopicColor(widget.topic),
          mini: true,
          child: const Icon(Icons.send, color: Colors.white),
        ),
      ],
    );
  }

  void _toggleRecording() async {
    if (isRecording) {
      // Stop recording
      _pulseController.stop();
      setState(() {
        isRecording = false;
        isAnalyzing = true;
      });
      
      // Simulate processing
      await Future.delayed(const Duration(seconds: 2));
      
      // Generate mock speech analysis
      _processSpeechInput();
    } else {
      // Start recording
      setState(() {
        isRecording = true;
        recordingDuration = 0;
      });
      
      _pulseController.repeat(reverse: true);
      _startRecordingTimer();
    }
  }

  void _startRecordingTimer() async {
    while (isRecording && recordingDuration < 30) {
      await Future.delayed(const Duration(seconds: 1));
      if (mounted && isRecording) {
        setState(() {
          recordingDuration++;
        });
      }
    }
    
    if (mounted && isRecording) {
      _toggleRecording(); // Auto-stop after 30 seconds
    }
  }

  void _processSpeechInput() async {
    // Mock speech recognition and analysis
    final mockTexts = [
      'I think that\'s a great idea for our weekend plans.',
      'Yes, I would like to visit the museum on Saturday.',
      'That sounds interesting. Can you tell me more about it?',
      'I agree with your suggestion about the restaurant.',
    ];
    
    final mockText = mockTexts[DateTime.now().millisecond % mockTexts.length];
    
    // Generate mock AI feedback
    final feedback = _generateMockFeedback(mockText);
    
    final userMessage = ConversationMessage(
      id: 'msg_${DateTime.now().millisecondsSinceEpoch}',
      content: mockText,
      isFromUser: true,
      timestamp: DateTime.now(),
      interactionType: InteractionType.speaking,
      feedback: feedback,
    );
    
    setState(() {
      conversation = AIConversation(
        id: conversation!.id,
        topic: conversation!.topic,
        title: conversation!.title,
        context: conversation!.context,
        messages: [...conversation!.messages, userMessage],
        suggestedResponses: conversation!.suggestedResponses,
        currentInteractionType: conversation!.currentInteractionType,
        startedAt: conversation!.startedAt,
      );
      isAnalyzing = false;
    });
    
    // Generate AI response after a delay
    await Future.delayed(const Duration(seconds: 1));
    _generateAIResponse();
  }

  void _sendTextMessage(String text) {
    final userMessage = ConversationMessage(
      id: 'msg_${DateTime.now().millisecondsSinceEpoch}',
      content: text,
      isFromUser: true,
      timestamp: DateTime.now(),
      interactionType: InteractionType.writing,
      feedback: _generateMockFeedback(text),
    );
    
    setState(() {
      conversation = AIConversation(
        id: conversation!.id,
        topic: conversation!.topic,
        title: conversation!.title,
        context: conversation!.context,
        messages: [...conversation!.messages, userMessage],
        suggestedResponses: conversation!.suggestedResponses,
        currentInteractionType: conversation!.currentInteractionType,
        startedAt: conversation!.startedAt,
      );
    });
    
    // Generate AI response
    Future.delayed(const Duration(milliseconds: 1500), () {
      _generateAIResponse();
    });
  }

  void _generateAIResponse() {
    final responses = [
      'That\'s a wonderful perspective! Can you elaborate on that?',
      'I appreciate your thoughts. What made you think about it that way?',
      'Interesting point! How do you think others might view this?',
      'Great! That shows good understanding. What would you do next?',
      'Excellent! Your English is improving. Let\'s continue our discussion.',
    ];
    
    final response = responses[DateTime.now().millisecond % responses.length];
    
    final aiMessage = ConversationMessage(
      id: 'msg_ai_${DateTime.now().millisecondsSinceEpoch}',
      content: response,
      isFromUser: false,
      timestamp: DateTime.now(),
      interactionType: InteractionType.speaking,
    );
    
    setState(() {
      conversation = AIConversation(
        id: conversation!.id,
        topic: conversation!.topic,
        title: conversation!.title,
        context: conversation!.context,
        messages: [...conversation!.messages, aiMessage],
        suggestedResponses: _getSuggestedResponses(widget.topic),
        currentInteractionType: conversation!.currentInteractionType,
        startedAt: conversation!.startedAt,
      );
    });
  }

  AIFeedback _generateMockFeedback(String text) {
    final scores = {
      'grammar': 75 + (DateTime.now().millisecond % 20),
      'pronunciation': 80 + (DateTime.now().millisecond % 15),
      'fluency': 85 + (DateTime.now().millisecond % 10),
    };
    
    final feedbacks = [
      'Great job! Your grammar is mostly correct and your pronunciation is clear.',
      'Good effort! Consider working on sentence structure for better flow.',
      'Excellent! Your vocabulary usage is appropriate and natural.',
      'Nice work! Try to speak a bit more slowly for better clarity.',
    ];
    
    return AIFeedback(
      id: 'feedback_${DateTime.now().millisecondsSinceEpoch}',
      originalText: text,
      suggestions: [
        'Great response! Keep practicing to improve fluency.',
        'Consider adding more details to make your answer more complete.',
      ],
      corrections: [],
      scores: scores,
      overallFeedback: feedbacks[DateTime.now().millisecond % feedbacks.length],
      analyzedAt: DateTime.now(),
    );
  }

  String _getTopicTitle(ConversationTopic topic) {
    switch (topic) {
      case ConversationTopic.dailyLife:
        return 'Daily Life Chat';
      case ConversationTopic.business:
        return 'Business English';
      case ConversationTopic.travel:
        return 'Travel Talk';
      case ConversationTopic.education:
        return 'Education Discussion';
      case ConversationTopic.health:
        return 'Health & Wellness';
      case ConversationTopic.technology:
        return 'Tech Talk';
      default:
        return 'English Conversation';
    }
  }

  String _getTopicContext(ConversationTopic topic) {
    switch (topic) {
      case ConversationTopic.dailyLife:
        return 'Let\'s talk about everyday activities, hobbies, and personal experiences.';
      case ConversationTopic.business:
        return 'Practice professional communication, meetings, and workplace situations.';
      case ConversationTopic.travel:
        return 'Discuss travel experiences, destinations, and cultural differences.';
      case ConversationTopic.education:
        return 'Talk about learning, schools, skills, and educational goals.';
      default:
        return 'Have a natural conversation and practice your English skills.';
    }
  }

  Color _getTopicColor(ConversationTopic topic) {
    switch (topic) {
      case ConversationTopic.dailyLife:
        return const Color(0xFF4CAF50);
      case ConversationTopic.business:
        return const Color(0xFF2196F3);
      case ConversationTopic.travel:
        return const Color(0xFFFF9800);
      case ConversationTopic.education:
        return const Color(0xFF9C27B0);
      case ConversationTopic.health:
        return const Color(0xFFF44336);
      case ConversationTopic.technology:
        return const Color(0xFF607D8B);
      default:
        return const Color(0xFF4CAF50);
    }
  }

  Color _getScoreColor(dynamic score) {
    final intScore = score is int ? score : int.tryParse(score.toString()) ?? 0;
    if (intScore >= 85) return Colors.green;
    if (intScore >= 70) return Colors.orange;
    return Colors.red;
  }

  List<String> _getSuggestedResponses(ConversationTopic topic) {
    switch (topic) {
      case ConversationTopic.dailyLife:
        return [
          'That sounds interesting!',
          'I agree with you.',
          'Can you tell me more?',
          'What do you think about...?',
        ];
      case ConversationTopic.business:
        return [
          'I think that\'s a good point.',
          'Could you clarify that?',
          'I\'d like to add that...',
          'What are the next steps?',
        ];
      default:
        return [
          'That\'s interesting.',
          'I see what you mean.',
          'Could you explain more?',
          'What\'s your opinion on...?',
        ];
    }
  }

  List<String> _getConversationStarters(ConversationTopic topic) {
    switch (topic) {
      case ConversationTopic.dailyLife:
        return [
          'Tell me about your typical morning routine.',
          'What did you do last weekend?',
          'What are your plans for this evening?',
          'Describe your favorite hobby.',
        ];
      case ConversationTopic.business:
        return [
          'Tell me about your current job.',
          'What are your career goals?',
          'Describe a challenging project you worked on.',
          'How do you handle workplace conflicts?',
        ];
      case ConversationTopic.travel:
        return [
          'What\'s your favorite travel destination?',
          'Tell me about your last vacation.',
          'Where would you like to visit next?',
          'What\'s the most interesting place you\'ve been to?',
        ];
      case ConversationTopic.education:
        return [
          'Tell me about your educational background.',
          'What was your favorite subject in school?',
          'How do you prefer to learn new things?',
          'What skills would you like to develop?',
        ];
      default:
        return [
          'Hello! Let\'s have a conversation about ${topic.name}. How are you today?',
        ];
    }
  }
}

