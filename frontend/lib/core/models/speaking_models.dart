class SpeechEvaluateResponseTranscriptWord {
  final String word;
  final int? startMs;
  final int? endMs;
  final double? confidence;

  SpeechEvaluateResponseTranscriptWord({
    required this.word,
    this.startMs,
    this.endMs,
    this.confidence,
  });

  factory SpeechEvaluateResponseTranscriptWord.fromJson(Map<String, dynamic> json) {
    return SpeechEvaluateResponseTranscriptWord(
      word: json['word'] as String,
      startMs: json['startMs'] as int?,
      endMs: json['endMs'] as int?,
      confidence: (json['confidence'] as num?)?.toDouble(),
    );
  }
}

class SpeechEvaluateResponseTranscript {
  final String text;
  final List<SpeechEvaluateResponseTranscriptWord> words;

  SpeechEvaluateResponseTranscript({required this.text, required this.words});

  factory SpeechEvaluateResponseTranscript.fromJson(Map<String, dynamic> json) {
    final items = (json['words'] as List?)?.map((e) => SpeechEvaluateResponseTranscriptWord.fromJson(e as Map<String, dynamic>)).toList() ?? [];
    return SpeechEvaluateResponseTranscript(
      text: json['text'] as String,
      words: items,
    );
  }
}

class SpeechEvaluateResponseAccuracy {
  final double wer;
  final int correct;
  final int insertions;
  final int deletions;
  final int substitutions;

  SpeechEvaluateResponseAccuracy({
    required this.wer,
    required this.correct,
    required this.insertions,
    required this.deletions,
    required this.substitutions,
  });

  factory SpeechEvaluateResponseAccuracy.fromJson(Map<String, dynamic> json) {
    return SpeechEvaluateResponseAccuracy(
      wer: (json['wer'] as num).toDouble(),
      correct: json['correct'] as int,
      insertions: json['insertions'] as int,
      deletions: json['deletions'] as int,
      substitutions: json['substitutions'] as int,
    );
  }
}

class SpeechEvaluateResponsePronunciationIssue {
  final String word;
  final String issue;
  final String? suggestion;

  SpeechEvaluateResponsePronunciationIssue({
    required this.word,
    required this.issue,
    this.suggestion,
  });

  factory SpeechEvaluateResponsePronunciationIssue.fromJson(Map<String, dynamic> json) {
    return SpeechEvaluateResponsePronunciationIssue(
      word: json['word'] as String,
      issue: json['issue'] as String,
      suggestion: json['suggestion'] as String?,
    );
  }
}

class SpeechEvaluateResponsePronunciation {
  final List<SpeechEvaluateResponsePronunciationIssue> issues;
  final double? score;

  SpeechEvaluateResponsePronunciation({required this.issues, this.score});

  factory SpeechEvaluateResponsePronunciation.fromJson(Map<String, dynamic> json) {
    final items = (json['issues'] as List?)?.map((e) => SpeechEvaluateResponsePronunciationIssue.fromJson(e as Map<String, dynamic>)).toList() ?? [];
    return SpeechEvaluateResponsePronunciation(
      issues: items,
      score: (json['score'] as num?)?.toDouble(),
    );
  }
}

class SpeechEvaluateResponseFluencyPause {
  final int start;
  final int end;

  SpeechEvaluateResponseFluencyPause({required this.start, required this.end});

  factory SpeechEvaluateResponseFluencyPause.fromJson(Map<String, dynamic> json) {
    return SpeechEvaluateResponseFluencyPause(
      start: json['start'] as int,
      end: json['end'] as int,
    );
  }
}

class SpeechEvaluateResponseFluency {
  final double wpm;
  final double? avgPauseMs;
  final List<SpeechEvaluateResponseFluencyPause> longPauses;

  SpeechEvaluateResponseFluency({required this.wpm, this.avgPauseMs, required this.longPauses});

  factory SpeechEvaluateResponseFluency.fromJson(Map<String, dynamic> json) {
    final items = (json['longPauses'] as List?)?.map((e) => SpeechEvaluateResponseFluencyPause.fromJson(e as Map<String, dynamic>)).toList() ?? [];
    return SpeechEvaluateResponseFluency(
      wpm: (json['wpm'] as num).toDouble(),
      avgPauseMs: (json['avgPauseMs'] as num?)?.toDouble(),
      longPauses: items,
    );
  }
}

class SpeechEvaluateResponseTiming {
  final int durationMs;
  SpeechEvaluateResponseTiming({required this.durationMs});
  factory SpeechEvaluateResponseTiming.fromJson(Map<String, dynamic> json) {
    return SpeechEvaluateResponseTiming(durationMs: json['durationMs'] as int);
  }
}

/// Detailed phoneme feedback from Speechace
class SpeechPhonemeScore {
  final String phoneme;
  final double score;
  final String? soundMostLike;
  final String? issue;

  SpeechPhonemeScore({
    required this.phoneme,
    required this.score,
    this.soundMostLike,
    this.issue,
  });

  factory SpeechPhonemeScore.fromJson(Map<String, dynamic> json) {
    return SpeechPhonemeScore(
      phoneme: json['phoneme'] as String? ?? '',
      score: (json['score'] as num?)?.toDouble() ?? 0.0,
      soundMostLike: json['sound_most_like'] as String?,
      issue: json['issue'] as String?,
    );
  }
}

/// Detailed syllable feedback from Speechace
class SpeechSyllableScore {
  final String letters;
  final double score;
  final int? stressLevel;
  final double? stressScore;

  SpeechSyllableScore({
    required this.letters,
    required this.score,
    this.stressLevel,
    this.stressScore,
  });

  factory SpeechSyllableScore.fromJson(Map<String, dynamic> json) {
    return SpeechSyllableScore(
      letters: json['letters'] as String? ?? '',
      score: (json['score'] as num?)?.toDouble() ?? 0.0,
      stressLevel: json['stress_level'] as int?,
      stressScore: (json['stress_score'] as num?)?.toDouble(),
    );
  }
}

/// Detailed word feedback from Speechace (includes syllables and phonemes)
class SpeechDetailedWordFeedback {
  final String word;
  final double score;
  final List<SpeechSyllableScore> syllables;
  final List<SpeechPhonemeScore> phonemes;

  SpeechDetailedWordFeedback({
    required this.word,
    required this.score,
    required this.syllables,
    required this.phonemes,
  });

  factory SpeechDetailedWordFeedback.fromJson(Map<String, dynamic> json) {
    return SpeechDetailedWordFeedback(
      word: json['word'] as String? ?? '',
      score: (json['score'] as num?)?.toDouble() ?? 0.0,
      syllables: (json['syllables'] as List?)
              ?.map((e) => SpeechSyllableScore.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      phonemes: (json['phonemes'] as List?)
              ?.map((e) => SpeechPhonemeScore.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
  
  /// Check if this word has pronunciation issues (score < 70)
  bool get hasIssues => score < 70;
  
  /// Get list of problematic phonemes
  List<SpeechPhonemeScore> get problemPhonemes => 
      phonemes.where((p) => p.score < 60 || p.issue != null).toList();
}

class SpeechEvaluateResponseModel {
  final double overallScore;
  final double? pronunciationScore;
  final double? fluencyScore;
  final SpeechEvaluateResponseAccuracy accuracy;
  final SpeechEvaluateResponsePronunciation pronunciation;
  final SpeechEvaluateResponseFluency fluency;
  final SpeechEvaluateResponseTiming timing;
  final SpeechEvaluateResponseTranscript transcript;
  final List<String> tips;
  final Map<String, double>? wordScores;
  final List<SpeechDetailedWordFeedback>? detailedWordFeedback;
  final Map<String, double>? phonemeScores;

  SpeechEvaluateResponseModel({
    required this.overallScore,
    this.pronunciationScore,
    this.fluencyScore,
    required this.accuracy,
    required this.pronunciation,
    required this.fluency,
    required this.timing,
    required this.transcript,
    required this.tips,
    this.wordScores,
    this.detailedWordFeedback,
    this.phonemeScores,
  });

  factory SpeechEvaluateResponseModel.fromJson(Map<String, dynamic> json) {
    Map<String, double>? wordScores;
    if (json['wordScores'] != null && json['wordScores'] is Map) {
      wordScores = (json['wordScores'] as Map).map(
        (k, v) => MapEntry(k.toString(), (v as num).toDouble()),
      );
    }
    
    Map<String, double>? phonemeScores;
    if (json['phonemeScores'] != null && json['phonemeScores'] is Map) {
      phonemeScores = (json['phonemeScores'] as Map).map(
        (k, v) => MapEntry(k.toString(), (v as num).toDouble()),
      );
    }
    
    List<SpeechDetailedWordFeedback>? detailedWordFeedback;
    if (json['detailedWordFeedback'] != null && json['detailedWordFeedback'] is List) {
      detailedWordFeedback = (json['detailedWordFeedback'] as List)
          .map((e) => SpeechDetailedWordFeedback.fromJson(e as Map<String, dynamic>))
          .toList();
    }
    
    return SpeechEvaluateResponseModel(
      overallScore: (json['overallScore'] as num).toDouble(),
      pronunciationScore: (json['pronunciationScore'] as num?)?.toDouble(),
      fluencyScore: (json['fluencyScore'] as num?)?.toDouble(),
      accuracy: SpeechEvaluateResponseAccuracy.fromJson(json['accuracy'] as Map<String, dynamic>),
      pronunciation: SpeechEvaluateResponsePronunciation.fromJson(json['pronunciation'] as Map<String, dynamic>),
      fluency: SpeechEvaluateResponseFluency.fromJson(json['fluency'] as Map<String, dynamic>),
      timing: SpeechEvaluateResponseTiming.fromJson(json['timing'] as Map<String, dynamic>),
      transcript: SpeechEvaluateResponseTranscript.fromJson(json['transcript'] as Map<String, dynamic>),
      tips: (json['tips'] as List?)?.map((e) => e.toString()).toList() ?? const <String>[],
      wordScores: wordScores,
      detailedWordFeedback: detailedWordFeedback,
      phonemeScores: phonemeScores,
    );
  }
  
  /// Get words that need improvement (score < 70)
  List<SpeechDetailedWordFeedback> get wordsNeedingImprovement =>
      detailedWordFeedback?.where((w) => w.hasIssues).toList() ?? [];
}



