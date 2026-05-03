import 'package:flutter_tts/flutter_tts.dart';

class TtsService {
  static final TtsService instance = TtsService._();
  final FlutterTts _tts = FlutterTts();
  bool _initialized = false;
  bool _speaking = false;
  void Function()? _onComplete;

  TtsService._();

  Future<void> _init() async {
    if (_initialized) return;
    _initialized = true;
    await _tts.setLanguage('en-US');
    await _tts.setSpeechRate(0.5);
    await _tts.setVolume(1.0);
    await _tts.setPitch(1.0);
    _tts.setCompletionHandler(() {
      _speaking = false;
      _onComplete?.call();
    });
    _tts.setCancelHandler(() {
      _speaking = false;
    });
    _tts.setErrorHandler((_) {
      _speaking = false;
      _onComplete?.call();
    });
  }

  static const _femaleNames = {
    'sarah','emily','maria','anna','lisa','amy','kate','laura','olivia','sophia','emma','jessica','rachel',
    'julia','rebecca','linda','susan','karen','helen','elena','ana','nina','mia','grace','elise','ella','clara',
    'fiona','natalie','holly','amelia','molly','jane','mary','michelle','amber','samantha','hannah','lauren',
    'victoria','kelly','christina','her','she','ms','mrs','anya','aria',
  };
  static const _maleNames = {
    'tom','john','michael','david','james','peter','mark','paul','andrew','daniel','chris','alex','adam','luke',
    'ben','sam','ryan','ethan','noah','william','henry','george','robert','steven','kevin','brian','jason','tony',
    'carlos','jose','ali','ahmed','jack','jacob','joseph','thomas','charles','christopher','matthew','liam','mason',
    'logan','oliver','elijah','aiden','him','he','mr',
  };
  String _altGender = 'female';
  final Map<String, String> _speakerCache = {};

  String genderForSpeaker(String raw) {
    final s = raw.trim();
    if (s.isEmpty) return 'female';
    if (_speakerCache.containsKey(s)) return _speakerCache[s]!;
    final first = s.toLowerCase().split(RegExp(r'[\s:,\-_/.]+')).first;
    String g;
    if (_femaleNames.contains(first)) {
      g = 'female';
    } else if (_maleNames.contains(first)) {
      g = 'male';
    } else {
      g = _altGender;
      _altGender = _altGender == 'female' ? 'male' : 'female';
    }
    _speakerCache[s] = g;
    return g;
  }

  Future<void> speak(String text, {String? speaker, String? gender, double rate = 0.5, void Function()? onDone}) async {
    await _init();
    await stop();
    final g = gender ?? (speaker != null ? genderForSpeaker(speaker) : 'female');
    await _tts.setPitch(g == 'female' ? 1.18 : 0.82);
    await _tts.setSpeechRate(rate);
    _onComplete = onDone;
    _speaking = true;
    await _tts.speak(text);
  }

  Future<void> speakSequence(
    List<Map<String, String>> parts, {
    double rate = 0.5,
    void Function(int)? onProgress,
    void Function()? onDone,
  }) async {
    await _init();
    await stop();
    var i = 0;
    void next() async {
      if (i >= parts.length) {
        onDone?.call();
        return;
      }
      onProgress?.call(i);
      final p = parts[i];
      i++;
      await speak(p['text'] ?? '', speaker: p['speaker'], rate: rate, onDone: next);
    }
    next();
  }

  Future<void> stop() async {
    if (!_initialized) return;
    _onComplete = null;
    _speaking = false;
    try { await _tts.stop(); } catch (_) {}
  }

  bool get isSpeaking => _speaking;
}
