import '../network/api_client.dart';

/// API service for Text-to-Speech operations
class TTSApi {
  final ApiClient _apiClient;

  TTSApi(this._apiClient);

  /// Generate TTS audio using Gemini native audio model
  /// Returns audio URL that can be played directly
  Future<TTSResult> generateGeminiTTS({
    required String text,
    String? voice,
    String audioType = 'general',
  }) async {
    try {
      final response = await _apiClient.post(
        '/ai/gemini-tts',
        data: {
          'text': text,
          'voice': voice,
          'audio_type': audioType,
        },
      );

      if (response.statusCode == 200 && response.data != null) {
        final data = response.data as Map<String, dynamic>;
        return TTSResult(
          success: data['success'] == true,
          audioUrl: data['audio_url'] as String?,
          durationSeconds: (data['duration_seconds'] as num?)?.toDouble() ?? 0,
          voice: data['voice'] as String?,
          model: data['model'] as String?,
          error: null,
        );
      } else {
        return TTSResult(
          success: false,
          error: 'Failed to generate TTS: ${response.statusCode}',
        );
      }
    } catch (e) {
      return TTSResult(
        success: false,
        error: 'TTS API error: $e',
      );
    }
  }
}

/// Result of a TTS generation request
class TTSResult {
  final bool success;
  final String? audioUrl;
  final double durationSeconds;
  final String? voice;
  final String? model;
  final String? error;

  TTSResult({
    required this.success,
    this.audioUrl,
    this.durationSeconds = 0,
    this.voice,
    this.model,
    this.error,
  });
}












