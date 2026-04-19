# MockGenerator

## Projektziel
Python-Tool das automatisch CMocka-Mocks für C-Unit-Tests generiert.

**Problem**: Wenn ein neues Testfile angelegt wird, fehlen alle Mocks für externe Funktionen (nicht im zu testenden File definiert). Der GCC-Linker wirft "undefined reference to <Symbol>"-Fehler und der CMake-Build schlägt fehl. Bisher werden Symbole manuell herausgesucht, Prototypen in Headern gefunden und Mocks von Hand geschrieben.

**Lösung**: Das Tool automatisiert diesen Prozess vollständig.

## Workflow (geplant)
1. User gibt CMake/make Fehler-Log als `.log`/`.txt` ein
2. Tool parst "undefined reference to <Symbol>"-Zeilen → Liste der fehlenden Symbole
3. Tool analysiert CMakeLists.txt-Struktur (nested) → findet alle relevanten Include-Verzeichnisse
4. Tool durchsucht Header-Files nach den Prototypen der fehlenden Symbole
5. Tool generiert CMocka-kompatible Mocks
6. **Kurzfristig**: Mocks landen in einer `.txt`-Ausgabedatei (Copy-Paste)
7. **Langfristig**: Mocks werden direkt in das Testfile injiziert

## Architektur (Module)
- `log_parser.py` — Parst Linker-Fehler-Output, extrahiert Symbol-Namen
- `cmake_analyzer.py` — Parst CMakeLists.txt-Struktur, liefert Include-Pfade (mit Exclude-Support)
- `header_scanner.py` — Durchsucht Header nach Prototypen/Variablen-Deklarationen
- `mock_generator.py` — Generiert Mock-Code aus Prototypen (Regeln: TBD, siehe unten)
- `main.py` — CLI-Einstiegspunkt

## Tech Stack
- **Sprache**: Python (Windows)
- **Compiler**: GCC
- **Test-Framework**: CMocka
- **Build-System**: CMake (nested CMakeLists.txt)

## Konventionen
- Testfiles folgen dem Muster: `TestUnit_<ModulName>.c`
- Mocks befinden sich im selben Testfile wie die Tests, in einem eigenen Bereich
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

**Pointer-Erkennung**: Enthält der Parameter-Typ ein `*` → `check_expected_ptr()`, sonst `check_expected()`

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
Alle generierten Variablen-Mocks werden mit `0` initialisiert + Hinweis-Kommentar:

```c
uint8 Test_TestVariable = 0; /* MOCK: verify initial value */
uint8 Test_TestArray[TEST_ARRAY_SIZE] = {0}; /* MOCK: verify initial value */
TestStruct_t Test_TestStruct = {0}; /* MOCK: verify initial value */
```

- Scalar (kein `[]`): `= 0`
- Array: `= {0}`
- Struct: `= {0}`
- Pointer (selten): `= NULL_PTR`

Der `/* MOCK: verify initial value */`-Kommentar macht alle generierten Mocks
projektübergreifend per `grep`/`ripgrep` auffindbar.

## Konfiguration
Stabile Einstellungen (Pfade, Excludes) werden in einer **`mockgenerator.ini`** gepflegt —
einmal anlegen, im Repo versionieren, fertig. Keine externen Abhängigkeiten (Python 3.8+ stdlib).

```ini
[project]
cmake_root = C:/Projects/MyProject

[search]
exclude_dirs =
    generated/autosar
    vendor/lowlevel

[output]
output_dir = mocks_out
```

**CLI** wird nur noch für das Log-File genutzt (ändert sich pro Lauf):
```
python main.py build_output.log
```

Alternativ: GUI-Dateidialog statt CLI-Argument (TBD).

## Exclude-Mechanismus
Verzeichnisse in `mockgenerator.ini` unter `[search] exclude_dirs` eintragen, z.B.:
- Generierter AUTOSAR-Code
- Low-Level-Libraries / Vendor-Code

## Offene Punkte
- [ ] In-Place-Injection in Testfiles implementieren
- [ ] Exaktes GCC/CMake Fehlermeldungs-Wording noch zu verifizieren (User liefert nach)
- [ ] GUI als spätere Ausbaustufe vorgemerkt
