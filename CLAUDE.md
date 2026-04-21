# MockGenerator

## Projektziel
Python-Tool das automatisch CMocka-Mocks für C-Unit-Tests generiert.

**Problem**: Wenn ein neues Testfile angelegt wird, fehlen alle Mocks für externe Funktionen (nicht im zu testenden File definiert). Der GCC-Linker wirft "undefined reference to <Symbol>"-Fehler und der CMake-Build schlägt fehl. Bisher werden Symbole manuell herausgesucht, Prototypen in Headern gefunden und Mocks von Hand geschrieben.

**Lösung**: Das Tool automatisiert diesen Prozess vollständig.

## Workflow
1. User gibt CMake/make Fehler-Log als `.log`/`.txt` ein
2. Tool parst "undefined reference to <Symbol>"-Zeilen → Liste der fehlenden Symbole, gruppiert nach Test-File
3. Tool analysiert CMakeLists.txt-Struktur (nested) → findet alle relevanten Include-Verzeichnisse
4. Tool durchsucht Header-Files nach den Prototypen der fehlenden Symbole
5. Tool generiert CMocka-kompatible Mocks
6. **File-Modus**: Mocks landen in einer `.txt`-Ausgabedatei (Copy-Paste)
7. **Inplace-Modus**: Mocks werden direkt in das Testfile injiziert (bereits implementiert)

## Architektur (Module)
- `log_parser.py` — Parst Linker-Fehler-Output, extrahiert Symbol-Namen (flach + gruppiert nach File)
- `cmake_analyzer.py` — Parst CMakeLists.txt-Struktur, liefert Include-Pfade (mit Exclude-Support, CMake-Variablen-Substitution)
- `header_scanner.py` — Durchsucht Header nach Prototypen/Variablen-Deklarationen
- `mock_generator.py` — Generiert Mock-Code aus Prototypen
- `injector.py` — In-Place-Injection in Testfiles, Duplikat-Erkennung
- `main.py` — CLI-Einstiegspunkt

## Tech Stack
- **Sprache**: Python 3.8+ (Windows, keine externen Abhängigkeiten)
- **Compiler**: GCC
- **Test-Framework**: CMocka
- **Build-System**: CMake (nested CMakeLists.txt)

## Konventionen
- Testfiles folgen dem Muster: `TestUnit_<ModulName>.c` (konfigurierbar)
- Mocks befinden sich im selben Testfile wie die Tests, in einem eigenen Bereich
- Der Mock-Bereich wird durch einen Doxygen-Kommentar eingeleitet: `@defgroup ... Mocks`
- Symbole können Funktionen oder (selten) Variablen sein

## Mock-Format

### Funktionen
Entscheidungsbaum basierend auf Return-Type und Parametern:

| Return  | Parameter | Generierter Body                                        |
|---------|-----------|---------------------------------------------------------|
| `void`  | `void`    | `function_called();`                                    |
| `void`  | non-void  | `check_expected(p)` / `check_expected_ptr(p)` pro Param |
| non-void| `void`    | `return mock();`                                        |
| non-void| non-void  | `check_expected`/`check_expected_ptr` + `return mock();`|

**Pointer-Erkennung**: Enthält der Parameter-Typ ein `*` oder beginnt mit `P2VAR`/`P2CONST`/`CONSTP2VAR`/`CONSTP2CONST` → `check_expected_ptr()`, sonst `check_expected()`

Beispiel void/void:
```c
void Test_TestFunction(void)
{
    function_called();
}
```

Beispiel non-void/non-void:
```c
Std_ReturnType Test_TestFunction2(uint8 Param1, uint32 *Param2)
{
    check_expected(Param1);
    check_expected_ptr(Param2);
    return mock();
}
```

Hinweis: `function_called()` wird bewusst nur bei void/void generiert. Bei void-Rückgabe
mit Parametern reichen die `check_expected`-Calls als Mindest-Überwachung. Reihenfolge-Checks
(`function_called` zusätzlich) sind Spezialfälle — dem Entwickler überlassen.

### Variablen
Alle generierten Variablen-Mocks werden mit `{0}` initialisiert + Hinweis-Kommentar:

```c
uint8 Test_TestVariable = {0}; /* MOCK: verify initial value */
uint8 Test_TestArray[TEST_ARRAY_SIZE] = {0}; /* MOCK: verify initial value */
TestStruct_t Test_TestStruct = {0}; /* MOCK: verify initial value */
```

- Pointer (selten): `= NULL_PTR`
- Alles andere (Scalar, Array, Struct): `= {0}`

Der `/* MOCK: verify initial value */`-Kommentar macht alle generierten Mocks
projektübergreifend per `grep`/`ripgrep` auffindbar.

Bekannte Einschränkung: Scalar vs. Struct wird nicht unterschieden. `{0}` ist für beide
valides C und kompiliert. Eine präzisere Erkennung (z.B. via `<Component>_Types.h`) ist
als spätere Verbesserung vorgesehen.

## Konfiguration
Stabile Einstellungen (Pfade, Excludes) werden in einer **`mockgenerator.ini`** gepflegt —
einmal anlegen, im Repo versionieren, fertig. Keine externen Abhängigkeiten (Python 3.8+ stdlib).

```ini
[project]
cmake_root = C:/Projects/MyProject
test_cmake_lists = tests/CMakeLists.txt
tests_root = tests

[search]
exclude_dirs =
    generated/autosar
    vendor/lowlevel

# CMake-Variablen in Include-Pfaden (z.B. ${Variant})
# [cmake_vars]
# Variant = VariantA

# Regex zum Erkennen fehlender Symbole (ein Capture-Group = Symbolname)
# [log_parser]
# symbol_pattern = undefined reference to `([^']+)'

[output]
mode = file        # "file" = .txt Ausgabe | "inplace" = direkt ins Testfile
output_dir = mocks_out
test_file_prefixes =
    TestUnit_
    TestIntegration_
```

**CLI**:
```
python main.py build_output.log [--inplace] [-v]
```

## Exclude-Mechanismus
Verzeichnisse in `mockgenerator.ini` unter `[search] exclude_dirs` eintragen, z.B.:
- Generierter AUTOSAR-Code
- Low-Level-Libraries / Vendor-Code

## Offene Punkte
- [ ] Regex-Validierung für custom `symbol_pattern` in Config (verhindert Crash bei ungültigem Pattern)
- [ ] Step-4-Zusammenfassung verbessern: "injection failed" vs. "nothing to do" klar trennen
- [ ] README: `@defgroup ... Mocks`-Anforderung und Prefix-Pflicht für Inplace-Modus dokumentieren
- [ ] Magic strings (`@defgroup`, `Mocks`) als Konstanten oder Config-Optionen
- [ ] Scalar vs. Struct Erkennung für präzisere Variablen-Initialisierung (Langfrist)
- [ ] GUI als spätere Ausbaustufe vorgemerkt
