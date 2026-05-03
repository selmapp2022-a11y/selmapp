import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

const Color kBg = Color(0xFF0C1C2C);
const Color kAccent = Color(0xFF2DD4BF);
const Color kMuted = Color(0xFF6B7B8C);
const Color kInk = Color(0xFF0C1C2C);

const List<String> kCefrLevels = ['A1','A2','B1','B2','C1','C2'];

const List<String> kSampleTopics = [
  'Travel', 'Food', 'Work', 'Family', 'Hobbies', 'Technology',
  'Health', 'Education', 'Sports', 'Music', 'Movies', 'Nature',
];

PreferredSizeWidget pageAppBar(BuildContext ctx, String title, {List<Widget>? actions}) => AppBar(
  backgroundColor: kBg,
  elevation: 0,
  leading: IconButton(
    icon: const Icon(Icons.arrow_back, color: Colors.white),
    onPressed: () { if (Navigator.canPop(ctx)) { Navigator.pop(ctx); } else { ctx.go('/dashboard'); } },
  ),
  title: Text(title, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
  actions: actions,
);

Widget whiteCard({required Widget child, EdgeInsetsGeometry padding = const EdgeInsets.all(18)}) =>
    Container(
      padding: padding,
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
      child: child,
    );

Widget primaryButton({required String label, VoidCallback? onPressed, IconData? icon, bool loading = false}) {
  return SizedBox(
    width: double.infinity,
    child: ElevatedButton(
      onPressed: loading ? null : onPressed,
      style: ElevatedButton.styleFrom(
        backgroundColor: kBg, foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(vertical: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      child: loading
          ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
          : Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (icon != null) ...[Icon(icon, size: 18), const SizedBox(width: 8)],
                Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
              ],
            ),
    ),
  );
}

Widget levelChips(String value, ValueChanged<String> onChanged) {
  return Wrap(
    spacing: 8, runSpacing: 8,
    children: kCefrLevels.map((lv) {
      final sel = lv == value;
      return GestureDetector(
        onTap: () => onChanged(lv),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: sel ? kAccent : Colors.white,
            border: Border.all(color: sel ? kAccent : const Color(0xFFE2E8F0)),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Text(lv, style: TextStyle(color: sel ? Colors.white : kInk, fontSize: 13, fontWeight: FontWeight.w700)),
        ),
      );
    }).toList(),
  );
}

Widget topicChips(String? value, ValueChanged<String> onChanged) {
  return Wrap(
    spacing: 8, runSpacing: 8,
    children: kSampleTopics.map((t) {
      final sel = value == t;
      return GestureDetector(
        onTap: () => onChanged(t),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: sel ? kAccent.withValues(alpha: 0.15) : const Color(0xFFF1F5F9),
            border: Border.all(color: sel ? kAccent : const Color(0xFFE2E8F0)),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Text(t, style: TextStyle(color: sel ? kAccent : kInk, fontSize: 13, fontWeight: FontWeight.w600)),
        ),
      );
    }).toList(),
  );
}

dynamic unwrapResp(dynamic raw, [String? preferredKey]) {
  if (raw is! Map) return raw;
  if (preferredKey != null && raw[preferredKey] != null) return raw[preferredKey];
  if (raw.containsKey('success')) {
    final ignore = {'success', 'metadata', 'error', 'message'};
    for (final k in raw.keys) {
      if (!ignore.contains(k.toString())) return raw[k];
    }
  }
  return raw;
}

Map<String, dynamic>? parseAIContent(dynamic raw) {
  String? s;
  if (raw is String) {
    s = raw;
  } else if (raw is Map) {
    final c = raw['content'] ?? raw['message'];
    if (c != null) s = c.toString();
  }
  if (s == null) return null;
  s = s.trim();
  final fence = RegExp(r'^```(?:json)?\s*\n?([\s\S]*?)\n?```\s*$').firstMatch(s);
  if (fence != null) s = fence.group(1)!;
  try {
    final dec = jsonDecode(s);
    if (dec is Map) return Map<String, dynamic>.from(dec);
  } catch (_) {}
  final m = RegExp(r'\{[\s\S]*\}').firstMatch(s);
  if (m != null) {
    try {
      final dec = jsonDecode(m.group(0)!);
      if (dec is Map) return Map<String, dynamic>.from(dec);
    } catch (_) {}
  }
  return null;
}

Color scoreBg(num s) {
  if (s >= 80) return const Color(0xFFD1FAE5);
  if (s >= 60) return const Color(0xFFFEF3C7);
  return const Color(0xFFFEE2E2);
}

Color scoreFg(num s) {
  if (s >= 80) return const Color(0xFF047857);
  if (s >= 60) return const Color(0xFFB45309);
  return const Color(0xFFB91C1C);
}
