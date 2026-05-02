import 'dart:async';
import 'package:universal_io/io.dart' as io;

import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p; // Use an alias to avoid name conflicts
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

class RecordingController {
  AudioRecorder? _recorder;
  Timer? _timer;
  int _elapsedSeconds = 0;
  String? _currentRecordingPath;
  bool _isRecording = false;
  
  // For web platform - stores the blob URL
  String? _webBlobUrl;

  int get elapsedSeconds => _elapsedSeconds;
  
  /// Check if current platform supports recording
  bool get isRecordingSupported => true; // record package supports web

  /// Initialize the recorder if not already initialized
  Future<AudioRecorder> _getRecorder() async {
    _recorder ??= AudioRecorder();
    return _recorder!;
  }

  Future<bool> ensurePermissions() async {
    // On web, permissions are handled differently via browser
    if (kIsWeb) {
      try {
        final recorder = await _getRecorder();
        final hasPermission = await recorder.hasPermission();
        if (kDebugMode) {
          print('🌐 Web microphone permission: $hasPermission');
        }
        return hasPermission;
      } catch (e) {
        if (kDebugMode) {
          print('❌ Web permission check failed: $e');
        }
        return false;
      }
    }
    
    // Request microphone permission for native platforms
    final status = await Permission.microphone.request();
    if (!status.isGranted) {
      if (kDebugMode) {
        print('❌ Microphone permission denied: $status');
      }
      return false;
    }
    
    // On Android, also check storage permission for older versions
    if (!kIsWeb && io.Platform.isAndroid) {
      final storageStatus = await Permission.storage.request();
      if (kDebugMode) {
        print('📂 Storage permission status: $storageStatus');
      }
    }
    
    return true;
  }

  Future<bool> isRecording() async {
    if (_recorder == null) return false;
    try {
      return await _recorder!.isRecording();
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ Error checking recording status: $e');
      }
      return _isRecording;
    }
  }

  Future<void> start() async {
    try {
      if (kDebugMode) {
        print('🎤 Starting recording... (isWeb: $kIsWeb)');
      }
      
      // Ensure permissions first
      if (!await ensurePermissions()) {
        throw Exception('Microphone permission denied');
      }

      final recorder = await _getRecorder();
      
      // Check if already recording and stop first
      try {
        if (await recorder.isRecording()) {
          if (kDebugMode) {
            print('⚠️ Already recording, stopping first...');
          }
          await recorder.stop();
        }
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ Error checking/stopping existing recording: $e');
        }
      }

      _elapsedSeconds = 0;
      _webBlobUrl = null;
      _timer?.cancel();
      _timer = Timer.periodic(const Duration(seconds: 1), (_) {
        _elapsedSeconds += 1;
      });

      final hasPermission = await recorder.hasPermission();
      if (hasPermission != true) {
        throw Exception('Recorder permission not granted');
      }

      if (kIsWeb) {
        // Web platform - record to memory (blob)
        if (kDebugMode) {
          print('🌐 Starting web recording...');
        }
        
        // For web, we record without a path and get a blob URL
        await recorder.start(
          const RecordConfig(
            encoder: AudioEncoder.wav,
            sampleRate: 16000,
            numChannels: 1,
            bitRate: 256000,
          ),
          path: '', // Empty path for web blob recording
        );
        
        _isRecording = true;
        
        if (kDebugMode) {
          print('✅ Web recording started successfully');
        }
      } else {
        // Native platforms - record to file
        final io.Directory appDir = await getApplicationDocumentsDirectory();
        final io.Directory recordingsDir = io.Directory(p.join(appDir.path, 'recordings'));
        
        // Create recordings directory if it doesn't exist
        if (!await recordingsDir.exists()) {
          await recordingsDir.create(recursive: true);
        }

        // Create a unique file path
        final String filePath = p.join(
          recordingsDir.path,
          'recording_${DateTime.now().millisecondsSinceEpoch}.wav',
        );
        
        _currentRecordingPath = filePath;
        
        if (kDebugMode) {
          print('📁 Recording to: $filePath');
        }

        // Start recording with proper configuration
        await recorder.start(
          const RecordConfig(
            encoder: AudioEncoder.wav,
            sampleRate: 16000,
            numChannels: 1,
            bitRate: 256000,
          ),
          path: filePath,
        );
        
        _isRecording = true;
        
        if (kDebugMode) {
          print('✅ Recording started successfully');
        }
      }
    } catch (e) {
      _isRecording = false;
      _timer?.cancel();
      if (kDebugMode) {
        print('❌ Failed to start recording: $e');
      }
      rethrow;
    }
  }

  Future<String?> stop() async {
    try {
      if (kDebugMode) {
        print('🛑 Stopping recording... (isWeb: $kIsWeb)');
      }
      
      _timer?.cancel();
      _isRecording = false;
      
      if (_recorder == null) {
        if (kDebugMode) {
          print('⚠️ No recorder instance');
        }
        return kIsWeb ? _webBlobUrl : _currentRecordingPath;
      }

      String? path;
      try {
        path = await _recorder!.stop();
      } catch (e) {
        if (kDebugMode) {
          print('⚠️ Error stopping recorder: $e');
        }
        // Fall back to stored path
        path = kIsWeb ? _webBlobUrl : _currentRecordingPath;
      }
      
      if (kIsWeb) {
        // On web, the path is a blob URL
        if (path != null && path.isNotEmpty) {
          _webBlobUrl = path;
          if (kDebugMode) {
            print('✅ Web recording stopped. Blob URL: $path');
          }
          return path;
        }
        if (kDebugMode) {
          print('⚠️ No blob URL returned for web recording');
        }
        return _webBlobUrl;
      }
      
      // Native platform handling
      if (path == null) {
        if (kDebugMode) {
          print('⚠️ No path returned from recorder, using stored path: $_currentRecordingPath');
        }
        path = _currentRecordingPath;
      }
      
      if (path == null) {
        if (kDebugMode) {
          print('❌ No recording path available');
        }
        return null;
      }
      
      final file = io.File(path);
      final exists = await file.exists();
      final length = exists ? await file.length() : 0;
      
      if (kDebugMode) {
        print('📊 Recording file: exists=$exists, length=$length bytes, path=$path');
      }
      
      if (!exists || length == 0) {
        if (kDebugMode) {
          print('❌ Recording file is empty or does not exist');
        }
        // Try alternative path if primary fails
        if (_currentRecordingPath != null && _currentRecordingPath != path) {
          final altFile = io.File(_currentRecordingPath!);
          if (await altFile.exists() && await altFile.length() > 0) {
            if (kDebugMode) {
              print('✅ Using alternative path: $_currentRecordingPath');
            }
            return _currentRecordingPath;
          }
        }
        return null;
      }
      
      if (kDebugMode) {
        print('✅ Recording stopped successfully: $path');
      }
      
      return path;
    } catch (e) {
      if (kDebugMode) {
        print('❌ Error in stop: $e');
      }
      return kIsWeb ? _webBlobUrl : _currentRecordingPath;
    }
  }

  Future<void> dispose() async {
    _timer?.cancel();
    _isRecording = false;
    try {
      await _recorder?.dispose();
    } catch (e) {
      if (kDebugMode) {
        print('⚠️ Error disposing recorder: $e');
      }
    }
    _recorder = null;
  }
}
