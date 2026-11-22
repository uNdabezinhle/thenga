import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

/// Persists tokens and the guest cart session.
abstract class TokenStore {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);
}

class MemoryTokenStore implements TokenStore {
  final Map<String, String> _values = {};

  @override
  Future<String?> read(String key) async => _values[key];

  @override
  Future<void> write(String key, String value) async {
    _values[key] = value;
  }

  @override
  Future<void> delete(String key) async {
    _values.remove(key);
  }
}

class SecureTokenStore implements TokenStore {
  SecureTokenStore([FlutterSecureStorage? storage])
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) =>
      _storage.write(key: key, value: value);

  @override
  Future<void> delete(String key) => _storage.delete(key: key);
}

/// Dio client with JWT + X-Cart-Session (ADR-0004 / ADR-0005).
class RekaApi {
  RekaApi({String? baseUrl, Dio? dio, TokenStore? store})
      : baseUrl = baseUrl ??
            const String.fromEnvironment(
              'REKA_API_BASE',
              defaultValue: 'http://127.0.0.1:8000',
            ),
        _storage = store ?? SecureTokenStore() {
    _dio = dio ??
        Dio(
          BaseOptions(
            baseUrl: this.baseUrl,
            connectTimeout: const Duration(seconds: 15),
            receiveTimeout: const Duration(seconds: 20),
            headers: {
              'Accept': 'application/json',
              'X-App-Version': '1.0.0 (flutter)',
            },
          ),
        );
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          try {
            final access = await _storage.read(_kAccess);
            if (access != null && access.isNotEmpty) {
              options.headers['Authorization'] = 'Bearer $access';
            }
          } catch (_) {}
          try {
            options.headers['X-Cart-Session'] = await cartSessionId();
          } catch (_) {
            options.headers['X-Cart-Session'] = _fallbackSession;
          }
          handler.next(options);
        },
        onError: (err, handler) async {
          if (err.response?.statusCode == 401 &&
              err.requestOptions.extra['retried'] != true) {
            final ok = await _tryRefresh();
            if (ok) {
              final req = err.requestOptions;
              req.extra['retried'] = true;
              try {
                final access = await _storage.read(_kAccess);
                if (access != null && access.isNotEmpty) {
                  req.headers['Authorization'] = 'Bearer $access';
                }
                final res = await _dio.fetch(req);
                return handler.resolve(res);
              } catch (_) {
                return handler.next(err);
              }
            }
          }
          handler.next(err);
        },
      ),
    );
  }

  static const _kAccess = 'access_token';
  static const _kRefresh = 'refresh_token';
  static const _kCart = 'cart_session';
  static const _kMfa = 'mfa_enrolled';

  final String baseUrl;
  late final Dio _dio;
  final TokenStore _storage;
  final _uuid = const Uuid();
  late final String _fallbackSession = _uuid.v4();

  Dio get dio => _dio;

  Future<String> cartSessionId() async {
    try {
      var session = await _storage.read(_kCart);
      if (session == null || session.isEmpty) {
        session = _uuid.v4();
        await _storage.write(_kCart, session);
      }
      return session;
    } catch (_) {
      return _fallbackSession;
    }
  }

  Future<void> rotateCartSession() async {
    try {
      await _storage.delete(_kCart);
    } catch (_) {}
  }

  Future<void> saveTokens({
    required String access,
    required String refresh,
  }) async {
    await _storage.write(_kAccess, access);
    await _storage.write(_kRefresh, refresh);
  }

  Future<String?> readRefresh() async {
    try {
      return await _storage.read(_kRefresh);
    } catch (_) {
      return null;
    }
  }

  Future<void> clearTokens() async {
    try {
      await _storage.delete(_kAccess);
      await _storage.delete(_kRefresh);
    } catch (_) {}
  }

  Future<bool> hasAccessToken() async {
    try {
      final token = await _storage.read(_kAccess);
      return token != null && token.isNotEmpty;
    } catch (_) {
      return false;
    }
  }

  Future<String?> readAccess() async {
    try {
      return await _storage.read(_kAccess);
    } catch (_) {
      return null;
    }
  }

  Future<bool> mfaEnrolled() async {
    try {
      return await _storage.read(_kMfa) == '1';
    } catch (_) {
      return false;
    }
  }

  Future<void> setMfaEnrolled(bool enrolled) async {
    try {
      if (enrolled) {
        await _storage.write(_kMfa, '1');
      } else {
        await _storage.delete(_kMfa);
      }
    } catch (_) {}
  }

  Future<bool> _tryRefresh() async {
    final refresh = await readRefresh();
    if (refresh == null || refresh.isEmpty) return false;
    try {
      final res = await Dio(BaseOptions(baseUrl: baseUrl)).post(
        '/api/v1/auth/token/refresh/',
        data: {'refresh': refresh},
      );
      final access = res.data['access'] as String?;
      final newRefresh = res.data['refresh'] as String?;
      if (access == null) return false;
      await _storage.write(_kAccess, access);
      if (newRefresh != null) {
        await _storage.write(_kRefresh, newRefresh);
      }
      return true;
    } catch (_) {
      await clearTokens();
      return false;
    }
  }

  String errorMessage(Object error) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map && data['error'] is Map) {
        final message = (data['error'] as Map)['message'];
        if (message is String && message.isNotEmpty) return message;
      }
      if (data is String && data.isNotEmpty) {
        return data.length > 180 ? data.substring(0, 180) : data;
      }
      return error.message ?? 'Network error';
    }
    return error.toString();
  }
}

bool? jwtBoolClaim(String token, String claim) {
  final parts = token.split('.');
  if (parts.length < 2) return null;
  var payload = parts[1];
  final remainder = payload.length % 4;
  if (remainder > 0) payload += '=' * (4 - remainder);
  payload = payload.replaceAll('-', '+').replaceAll('_', '/');
  try {
    final decoded = jsonDecode(utf8.decode(base64.decode(payload)));
    if (decoded is Map && decoded[claim] is bool) return decoded[claim] as bool;
  } catch (_) {}
  return null;
}
