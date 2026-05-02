import 'package:flutter/material.dart';
import '../../data/models/lesson_models.dart';

class AIWritingPage extends StatefulWidget {
  final ConversationTopic topic;
  final String? existingText;
  final AIFeedback? existingFeedback;

  const AIWritingPage({
    super.key,
    required this.topic,
    this.existingText,
    this.existingFeedback,
  });

  @override
  State<AIWritingPage> createState() => _AIWritingPageState();
}

class _AIWritingPageState extends State<AIWritingPage>
    with SingleTickerProviderStateMixin {
  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;
  
  final TextEditingController _writingController = TextEditingController();
  final FocusNode _writingFocusNode = FocusNode();
  
  AIFeedback? currentFeedback;
  bool isAnalyzing = false;
  bool hasSubmitted = false;
  int wordCount = 0;
  String selectedPrompt = '';
  List<String> writingPrompts = [];
  bool showRealTimeHelp = false;
  
  @override
  void initState() {
    super.initState();
    
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    
    _fadeAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeInOut,
    ));
    
    _animationController.forward();
    
    // Initialize with existing data if provided
    if (widget.existingText != null) {
      _writingController.text = widget.existingText!;
      currentFeedback = widget.existingFeedback;
      hasSubmitted = currentFeedback != null;
    }
    
    _writingController.addListener(_onTextChanged);
    _loadWritingPrompts();
  }

  @override
  void dispose() {
    _animationController.dispose();
    _writingController.dispose();
    _writingFocusNode.dispose();
    super.dispose();
  }

  void _loadWritingPrompts() {
    writingPrompts = _getWritingPrompts(widget.topic);
    
    if (selectedPrompt.isEmpty && writingPrompts.isNotEmpty) {
      selectedPrompt = writingPrompts.first;
    }
  }

  List<String> _getWritingPrompts(ConversationTopic topic) {
    switch (topic) {
      case ConversationTopic.business:
        return [
          'Write a professional email requesting a meeting.',
          'Describe your ideal work environment.',
          'Write a brief proposal for a new project.',
          'Compose a thank-you email after an interview.',
        ];
      case ConversationTopic.dailyLife:
        return [
          'Write about your daily routine.',
          'Describe your hometown to a foreign visitor.',
          'Write a letter to a friend about your recent experiences.',
          'Describe your favorite restaurant and why you like it.',
        ];
      case ConversationTopic.education:
        return [
          'Write an essay about the importance of education.',
          'Describe your learning goals and how you plan to achieve them.',
          'Write about a skill you recently learned.',
          'Compose a study plan for improving your English.',
        ];
      default:
        return [
          'Write about your thoughts on ${topic.name}.',
          'Describe your experience with ${topic.name}.',
          'Share your opinion about ${topic.name}.',
        ];
    }
  }

  void _onTextChanged() {
    final text = _writingController.text;
    final words = text.trim().isEmpty ? 0 : text.trim().split(RegExp(r'\s+')).length;
    
    setState(() {
      wordCount = words;
    });

    // Real-time help
    if (showRealTimeHelp && words > 0 && words % 50 == 0) {
      _showRealTimeHint();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[50],
      appBar: AppBar(
        title: Text(
          _getTopicTitle(widget.topic),
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        backgroundColor: _getTopicColor(widget.topic),
        elevation: 0,
        actions: [
          IconButton(
            onPressed: () {
              setState(() {
                showRealTimeHelp = !showRealTimeHelp;
              });
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text(
                    showRealTimeHelp 
                        ? 'Real-time help enabled' 
                        : 'Real-time help disabled',
                  ),
                  duration: const Duration(seconds: 2),
                ),
              );
            },
            icon: Icon(
              showRealTimeHelp ? Icons.help : Icons.help_outline,
              color: Colors.white,
            ),
          ),
        ],
      ),
      body: FadeTransition(
        opacity: _fadeAnimation,
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Writing Prompt Selection
                    _buildPromptSelection(),
                    
                    const SizedBox(height: 20),
                    
                    // Writing Guidelines
                    _buildWritingGuidelines(),
                    
                    const SizedBox(height: 20),
                    
                    // Writing Area
                    _buildWritingArea(),
                    
                    const SizedBox(height: 20),
                    
                    // AI Analysis Results
                    if (currentFeedback != null) _buildAnalysisResults(),
                    
                    const SizedBox(height: 80),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
      
      // Bottom Action Bar
      bottomNavigationBar: Container(
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
          child: hasSubmitted ? _buildCompletionButtons() : _buildSubmitButton(),
        ),
      ),
    );
  }

  Widget _buildPromptSelection() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            _getTopicColor(widget.topic),
            _getTopicColor(widget.topic).withValues(alpha: 0.8),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: _getTopicColor(widget.topic).withValues(alpha: 0.3),
            blurRadius: 12,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                _getTopicIcon(widget.topic),
                color: Colors.white,
                size: 24,
              ),
              const SizedBox(width: 12),
              Text(
                'Writing Prompt',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              selectedPrompt,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
                height: 1.4,
              ),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 40,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: writingPrompts.length,
              itemBuilder: (context, index) {
                final prompt = writingPrompts[index];
                final isSelected = prompt == selectedPrompt;
                
                return Container(
                  margin: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: Text(
                      'Prompt ${index + 1}',
                      style: TextStyle(
                        color: isSelected ? _getTopicColor(widget.topic) : Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    selected: isSelected,
                    onSelected: (selected) {
                      if (selected) {
                        setState(() {
                          selectedPrompt = prompt;
                        });
                      }
                    },
                    backgroundColor: Colors.white.withValues(alpha: 0.2),
                    selectedColor: Colors.white,
                    checkmarkColor: _getTopicColor(widget.topic),
                    side: BorderSide(color: Colors.white.withValues(alpha: 0.5)),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWritingGuidelines() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.checklist,
                color: _getTopicColor(widget.topic),
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                'Writing Guidelines',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: _getTopicColor(widget.topic),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ..._getWritingGuidelines().map((guideline) => Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 6,
                  height: 6,
                  margin: const EdgeInsets.only(top: 8, right: 12),
                  decoration: BoxDecoration(
                    color: _getTopicColor(widget.topic),
                    borderRadius: BorderRadius.circular(3),
                  ),
                ),
                Expanded(
                  child: Text(
                    guideline,
                    style: const TextStyle(
                      fontSize: 14,
                      height: 1.4,
                    ),
                  ),
                ),
              ],
            ),
          )),
        ],
      ),
    );
  }

  Widget _buildWritingArea() {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: _getTopicColor(widget.topic).withValues(alpha: 0.1),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(16),
                topRight: Radius.circular(16),
              ),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.edit,
                  color: _getTopicColor(widget.topic),
                  size: 20,
                ),
                const SizedBox(width: 8),
                Text(
                  'Your Writing',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: _getTopicColor(widget.topic),
                  ),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: _getWordCountColor(),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '$wordCount words',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
          ),
          
          // Writing Text Field
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _writingController,
              focusNode: _writingFocusNode,
              maxLines: 15,
              enabled: !isAnalyzing,
              style: const TextStyle(
                fontSize: 16,
                height: 1.5,
              ),
              decoration: InputDecoration(
                hintText: 'Start writing here...\n\n$selectedPrompt',
                border: InputBorder.none,
                hintStyle: TextStyle(
                  color: Colors.grey[400],
                  fontSize: 16,
                ),
              ),
            ),
          ),
          
          // Writing Stats
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                _buildStatChip('Words', wordCount.toString(), Icons.text_fields),
                const SizedBox(width: 12),
                _buildStatChip('Characters', _writingController.text.length.toString(), Icons.text_format),
                const SizedBox(width: 12),
                _buildStatChip('Paragraphs', _getParagraphCount().toString(), Icons.format_list_bulleted),
              ],
            ),
          ),
          
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildStatChip(String label, String value, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.grey[100],
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: Colors.grey[600]),
          const SizedBox(width: 4),
          Text(
            '$label: $value',
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey[600],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAnalysisResults() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.analytics,
                color: _getTopicColor(widget.topic),
                size: 24,
              ),
              const SizedBox(width: 8),
              Text(
                'AI Writing Analysis',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: _getTopicColor(widget.topic),
                ),
              ),
            ],
          ),
          
          const SizedBox(height: 20),
          
          // Scores Grid
          if (currentFeedback!.writingAnalysis != null) ...[
            _buildScoresGrid(currentFeedback!.writingAnalysis!),
            const SizedBox(height: 20),
          ],
          
          // Overall Feedback
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.blue.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.blue.withValues(alpha: 0.2)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      Icons.smart_toy,
                      color: Colors.blue,
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'AI Feedback:',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: Colors.blue,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  currentFeedback!.overallFeedback,
                  style: const TextStyle(
                    fontSize: 14,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
          
          const SizedBox(height: 16),
          
          // Suggestions
          if (currentFeedback!.suggestions.isNotEmpty) ...[
            Text(
              'Suggestions for Improvement:',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 12),
            ...currentFeedback!.suggestions.map((suggestion) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 6,
                    height: 6,
                    margin: const EdgeInsets.only(top: 8, right: 12),
                    decoration: BoxDecoration(
                      color: Colors.orange,
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ),
                  Expanded(
                    child: Text(
                      suggestion,
                      style: const TextStyle(fontSize: 14, height: 1.4),
                    ),
                  ),
                ],
              ),
            )),
          ],
        ],
      ),
    );
  }

  Widget _buildScoresGrid(WritingAnalysis analysis) {
    final scores = {
      'Overall': analysis.overallScore,
      'Grammar': analysis.grammarScore,
      'Vocabulary': analysis.vocabularyScore,
      'Structure': analysis.structureScore,
      'Clarity': analysis.clarityScore,
      'Coherence': analysis.coherenceScore,
    };
    
    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 3,
      crossAxisSpacing: 12,
      mainAxisSpacing: 12,
      childAspectRatio: 2,
      children: scores.entries.map((entry) {
        return Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: _getScoreColor(entry.value).withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: _getScoreColor(entry.value).withValues(alpha: 0.3),
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                '${entry.value}%',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: _getScoreColor(entry.value),
                ),
              ),
              Text(
                entry.key,
                style: TextStyle(
                  fontSize: 11,
                  color: Colors.grey[600],
                ),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _buildSubmitButton() {
    final canSubmit = wordCount >= 50; // Minimum word requirement
    
    return SizedBox(
      width: double.infinity,
      height: 50,
      child: ElevatedButton(
        onPressed: canSubmit && !isAnalyzing ? _submitWriting : null,
        style: ElevatedButton.styleFrom(
          backgroundColor: _getTopicColor(widget.topic),
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(25),
          ),
          disabledBackgroundColor: Colors.grey[300],
        ),
        child: isAnalyzing
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  color: Colors.white,
                  strokeWidth: 2,
                ),
              )
            : Text(
                isAnalyzing ? 'Analyzing...' : 'Get AI Feedback',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
      ),
    );
  }

  Widget _buildCompletionButtons() {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton(
            onPressed: _reviseWriting,
            child: const Text('Revise'),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: ElevatedButton(
            onPressed: _saveWriting,
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.green,
              foregroundColor: Colors.white,
            ),
            child: const Text('Save Writing'),
          ),
        ),
      ],
    );
  }

  void _submitWriting() async {
    setState(() {
      isAnalyzing = true;
    });

    // Simulate AI analysis
    await Future.delayed(const Duration(seconds: 4));

    // Generate mock analysis
    final mockAnalysis = _generateMockWritingAnalysis(_writingController.text);
    
    setState(() {
      isAnalyzing = false;
      hasSubmitted = true;
      currentFeedback = mockAnalysis;
    });
  }

  void _reviseWriting() {
    setState(() {
      hasSubmitted = false;
      currentFeedback = null;
    });
    
    _writingFocusNode.requestFocus();
  }

  void _saveWriting() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('✅ Writing Saved!'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Your writing has been saved to your portfolio.'),
            const SizedBox(height: 16),
            if (currentFeedback?.writingAnalysis != null)
              Text(
                'Overall Score: ${currentFeedback!.writingAnalysis!.overallScore}%',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: _getScoreColor(currentFeedback!.writingAnalysis!.overallScore),
                ),
              ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.of(context).pop();
              Navigator.of(context).pop();
            },
            child: const Text('Continue'),
          ),
        ],
      ),
    );
  }

  void _showRealTimeHint() {
    final hints = [
      'Great progress! Consider adding more specific examples.',
      'Nice work! Try varying your sentence structure.',
      'Good writing! Remember to check your grammar.',
      'Excellent! Add more descriptive words to enhance your writing.',
    ];
    
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(hints[DateTime.now().millisecond % hints.length]),
        duration: const Duration(seconds: 3),
        backgroundColor: _getTopicColor(widget.topic),
      ),
    );
  }

  AIFeedback _generateMockWritingAnalysis(String text) {
    final analysis = WritingAnalysis(
      overallScore: 75 + (DateTime.now().millisecond % 20),
      grammarScore: 80 + (DateTime.now().millisecond % 15),
      vocabularyScore: 78 + (DateTime.now().millisecond % 18),
      structureScore: 85 + (DateTime.now().millisecond % 12),
      clarityScore: 82 + (DateTime.now().millisecond % 15),
      coherenceScore: 79 + (DateTime.now().millisecond % 16),
      suggestions: [],
      strengths: [
        'Clear communication style',
        'Good vocabulary usage',
        'Well-organized structure',
      ],
      improvements: [
        'Add more specific examples',
        'Vary sentence length for better flow',
        'Use more transition words',
      ],
      wordCount: wordCount,
      readabilityLevel: 'Intermediate',
    );
    
    final feedbacks = [
      'Excellent work! Your writing shows clear thinking and good structure. The vocabulary is appropriate and your ideas flow well.',
      'Great effort! Your writing is clear and engaging. Consider adding more specific examples to strengthen your arguments.',
      'Good job! Your writing demonstrates good command of English. Focus on varying your sentence structures for better rhythm.',
      'Well done! Your ideas are well-expressed. Try using more transition words to improve the flow between paragraphs.',
    ];
    
    return AIFeedback(
      id: 'feedback_${DateTime.now().millisecondsSinceEpoch}',
      originalText: text,
      writingAnalysis: analysis,
      suggestions: [
        'Consider adding more specific examples to support your points',
        'Try varying your sentence lengths for better rhythm',
        'Use more transition words between paragraphs',
      ],
      corrections: [],
      scores: {
        'overall': analysis.overallScore,
        'grammar': analysis.grammarScore,
        'vocabulary': analysis.vocabularyScore,
      },
      overallFeedback: feedbacks[DateTime.now().millisecond % feedbacks.length],
      analyzedAt: DateTime.now(),
    );
  }

  String _getTopicTitle(ConversationTopic topic) {
    switch (topic) {
      case ConversationTopic.dailyLife:
        return 'Daily Life Writing';
      case ConversationTopic.business:
        return 'Business Writing';
      case ConversationTopic.travel:
        return 'Travel Writing';
      case ConversationTopic.education:
        return 'Academic Writing';
      default:
        return 'AI Writing Assistant';
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
      default:
        return const Color(0xFF4CAF50);
    }
  }

  IconData _getTopicIcon(ConversationTopic topic) {
    switch (topic) {
      case ConversationTopic.dailyLife:
        return Icons.home;
      case ConversationTopic.business:
        return Icons.business;
      case ConversationTopic.travel:
        return Icons.flight;
      case ConversationTopic.education:
        return Icons.school;
      default:
        return Icons.edit;
    }
  }

  Color _getWordCountColor() {
    if (wordCount < 50) return Colors.red;
    if (wordCount < 100) return Colors.orange;
    return Colors.green;
  }

  Color _getScoreColor(int score) {
    if (score >= 85) return Colors.green;
    if (score >= 70) return Colors.orange;
    return Colors.red;
  }

  List<String> _getWritingGuidelines() {
    switch (widget.topic) {
      case ConversationTopic.business:
        return [
          'Use professional and formal language',
          'Structure your writing with clear paragraphs',
          'Include specific examples and details',
          'Maintain a respectful and courteous tone',
        ];
      case ConversationTopic.dailyLife:
        return [
          'Write in a natural, conversational style',
          'Include personal experiences and examples',
          'Use descriptive language to paint a picture',
          'Express your thoughts and feelings clearly',
        ];
      case ConversationTopic.education:
        return [
          'Present arguments with supporting evidence',
          'Use academic vocabulary appropriately',
          'Structure with introduction, body, and conclusion',
          'Cite examples and maintain objectivity',
        ];
      default:
        return [
          'Write clearly and concisely',
          'Organize your thoughts logically',
          'Use appropriate vocabulary for your audience',
          'Check grammar and spelling carefully',
        ];
    }
  }

  int _getParagraphCount() {
    final text = _writingController.text.trim();
    if (text.isEmpty) return 0;
    return text.split('\n\n').where((p) => p.trim().isNotEmpty).length;
  }
}

