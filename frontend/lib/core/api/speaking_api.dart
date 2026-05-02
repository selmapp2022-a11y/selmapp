import 'package:universal_io/io.dart' as io;

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show Uint8List, kDebugMode, kIsWeb;
import 'package:http/http.dart' as http;

import '../models/speaking_models.dart';
import '../network/api_client.dart';
import '../storage/secure_storage.dart';

class SpeakingApi {
  final ApiClient _client;

  SpeakingApi(SecureStorage storage) : _client = ApiClient(storage);

  /// Evaluate speech from a file (native platforms)
  Future<SpeechEvaluateResponseModel> evaluate({
    required String referenceText,
    required String language,
    required dynamic audioFile, // File on native, null on web
    Uint8List? audioBytes, // For web platform
    String? audioBlobUrl, // Blob URL for web
  }) async {
    FormData formData;
    
    if (kIsWeb) {
      // Web platform - fetch blob data from URL or use provided bytes
      Uint8List bytes;
      
      if (audioBytes != null) {
        bytes = audioBytes;
      } else if (audioBlobUrl != null && audioBlobUrl.isNotEmpty) {
        try {
          // Fetch the blob data from the blob URL
          final response = await http.get(Uri.parse(audioBlobUrl));
          bytes = response.bodyBytes;
          if (kDebugMode) {
            print('🌐 Fetched ${bytes.length} bytes from blob URL');
          }
        } catch (e) {
          if (kDebugMode) {
            print('❌ Failed to fetch blob data: $e');
          }
          throw Exception('Failed to fetch audio blob: $e');
        }
      } else {
        throw Exception('No audio data provided for web platform');
      }
      
      formData = FormData.fromMap({
        'reference_text': referenceText,
        'language': language,
        'audio': MultipartFile.fromBytes(
          bytes,
          filename: 'audio.wav',
          contentType: DioMediaType('audio', 'wav'),
        ),
      });
    } else {
      // Native platform - use file
      final file = audioFile as io.File;
      formData = FormData.fromMap({
        'reference_text': referenceText,
        'language': language,
        'audio': await MultipartFile.fromFile(
          file.path,
          filename: 'audio.wav',
          contentType: DioMediaType('audio', 'wav'),
        ),
      });
    }

    final response = await _client.post(
      '/speech/evaluate',
      data: formData,
      options: Options(contentType: 'multipart/form-data'),
    );
    return SpeechEvaluateResponseModel.fromJson(response.data as Map<String, dynamic>);
  }
}



