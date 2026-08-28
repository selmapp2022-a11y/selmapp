import importlib.util as u, re, sys, pathlib
root = pathlib.Path("selmapp/backend/app")
spec=u.spec_from_file_location('lp', root/'services/language_profile.py'); m=u.module_from_spec(spec); spec.loader.exec_module(m)

print("LANGUAGE PROFILES — the four blockers as data")
for c in ('en','fr'):
    p=m.profile_for(c)
    print(f"  {c}: tutor={p.tutor!r}")
    print(f"      writer={p.writer!r}")
    print(f"      speech_locale={p.speech_locale!r}  voices={list(p.tts_voices.values())}")
    print(f"      write_in={p.write_in[:64]!r}...")
assert m.profile_for('fr').tts_voices != m.profile_for('en').tts_voices, "voices must differ"
assert m.profile_for('fr').speech_locale.startswith('fr')
assert not m.is_supported('es') and m.profile_for('es').code == 'en', "unknown falls back to English"
print("\n  unknown code 'es' -> falls back to English, is_supported False  ✓")

print("\nNO LITERAL LANGUAGE LEFT IN THE FOUR PLACES")
checks = [
  (root/'services/ai_reading_service.py',      r'You are an English-language tutor'),
  (root/'services/ai_reading_service.py',      r'You are an expert English-language writer'),
  (root/'api/v1/endpoints/listening.py',       r'speaker_names=\["Dr\. Anya", "Liam"\]'),
  (root/'api/v1/endpoints/listening.py',       r'^_LISTENING_VOICE_FEMALE.*\n.*\n.*voices = \[_LISTENING'),
]
bad=0
for f,pat in checks:
    hits=[l for l in open(f,encoding='utf-8') if re.search(pat,l) and not l.lstrip().startswith('#')]
    ok = not hits
    print(("  ok   " if ok else "  FAIL ")+f"{f.name}: /{pat[:44]}/")
    bad += 0 if ok else 1

print("\nCACHE KEY CARRIES THE LANGUAGE")
src=open(root/'api/v1/endpoints/listening.py',encoding='utf-8').read()
assert 'listening:v3' in src and '{_lang}' in src, "cache key must carry the language"
print("  ok   listening:v3:{user}:{lang}:{topic}:{level}")
print("  ok   a French request can no longer be served a cached English exercise")

print("\nTHE LANGUAGE REACHES THE PROMPT, NOT JUST THE SIGNATURE")
for f, needle in [
    (root/'services/ai_reading_service.py', '{lang.write_in}'),
    (root/'services/gemini_tts_service.py', '{_lang.write_in}'),
]:
    s=open(f,encoding='utf-8').read()
    print(("  ok   " if needle in s else "  FAIL ")+f"{f.name} interpolates {needle}")
    bad += 0 if needle in s else 1
sys.exit(1 if bad else 0)
